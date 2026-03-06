"""
Celery tasks for PatientLink.
Handles background WhatsApp message sending.
"""
from datetime import datetime, timedelta
import logging
import os
import json
from pathlib import Path

from celery.schedules import crontab
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import models
from celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task
def health_ping():
    """Minimal task to validate worker/queue execution path."""
    return {"ok": True, "ts": datetime.utcnow().isoformat()}


def _get_db_session():
    database_url = os.environ.get("DATABASE_URL", "sqlite:///./patientlink.db")
    connect_args = {"check_same_thread": False} if "sqlite" in database_url else {}
    engine = create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return session_local()


def _write_message_log(owner_user_id, patient_id, phone_number, message_type, status_value, provider_message_id="", error_reason="", payload=None):
    db = _get_db_session()
    try:
        db.add(models.MessageLog(
            owner_user_id=owner_user_id or "",
            patient_id=patient_id or "",
            phone_number=phone_number or "",
            message_type=message_type,
            status=status_value,
            provider_message_id=provider_message_id or "",
            error_reason=error_reason or "",
            payload_json=json.dumps(payload or {}),
        ))
        db.commit()
    finally:
        db.close()


@celery_app.task
def create_scheduled_backup():
    """
    Daily JSON backup snapshot of patients+medicines.
    """
    db = _get_db_session()
    try:
        out_dir = Path(os.environ.get("BACKUP_DIR", "./backups"))
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        file_path = out_dir / f"backup_{ts}.json"

        patients = db.query(models.Patient).all()
        records = []
        for p in patients:
            meds = db.query(models.Medicine).filter(models.Medicine.patient_id == p.id).all()
            records.append({
                "patient": {
                    "id": p.id,
                    "owner_user_id": p.owner_user_id,
                    "name": p.name,
                    "whatsapp_number": p.whatsapp_number,
                    "dob": p.dob,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    "deleted_at": p.deleted_at.isoformat() if p.deleted_at else None,
                },
                "medicines": [
                    {
                        "id": m.id,
                        "medicine_name": m.medicine_name,
                        "morning": m.morning,
                        "evening": m.evening,
                        "night": m.night,
                        "duration_days": m.duration_days,
                        "meal_time": m.meal_time,
                    }
                    for m in meds
                ],
            })

        payload = {"exported_at": datetime.utcnow().isoformat(), "records": records}
        file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return {"success": True, "file": str(file_path)}
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3)
def send_medicine_reminder(self, patient_id, patient_name, phone_number, medicine_name, timing, meal_time=""):
    """
    Send single medicine reminder to a patient via WhatsApp.
    timing: "morning", "evening", or "night"
    meal_time: "before_meal", "after_meal", or ""
    """
    from whatsapp_service import whatsapp_service

    timing_messages = {
        "morning": "Good morning. Time to take your medicine.",
        "evening": "Evening reminder. Please take your medicine.",
        "night": "Night reminder. Please take your medicine before sleeping.",
    }

    meal_instructions = {
        "before_meal": "Take before meal.",
        "after_meal": "Take after meal.",
    }

    message = f"{timing_messages.get(timing, 'Medicine reminder.')}\n\n"
    message += f"Medicine: {medicine_name}"
    if meal_time in meal_instructions:
        message += f"\n{meal_instructions[meal_time]}"
    message += "\n\nStay healthy."

    try:
        logger.info("Sending %s reminder to %s (%s)", timing, patient_name, phone_number)
        result = whatsapp_service.send_message(phone_number, message)
        if result["success"]:
            logger.info("Reminder sent successfully to %s", patient_name)
            return {"success": True, "message_id": result.get("message_id")}
        raise self.retry(exc=Exception(result.get("error", "Unknown WhatsApp error")), countdown=60)
    except Exception as exc:
        logger.exception("Error sending reminder: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def send_patient_medicine_reminder(self, patient_id, patient_name, phone_number, medicines, owner_user_id=""):
    """Send a consolidated medicine reminder for a patient."""
    from whatsapp_service import whatsapp_service

    try:
        logger.info("Sending consolidated reminder to %s (%s)", patient_name, phone_number)
        result = whatsapp_service.send_medicine_reminder(patient_name, phone_number, medicines)
        if result["success"]:
            _write_message_log(
                owner_user_id=owner_user_id,
                patient_id=patient_id,
                phone_number=phone_number,
                message_type="reminder_single",
                status_value="sent",
                provider_message_id=result.get("message_id", ""),
                payload={"patient_name": patient_name, "medicines": medicines},
            )
            logger.info("Consolidated reminder sent to %s", patient_name)
            return {"success": True, "message_id": result.get("message_id"), "patient_id": patient_id}
        _write_message_log(
            owner_user_id=owner_user_id,
            patient_id=patient_id,
            phone_number=phone_number,
            message_type="reminder_single",
            status_value="failed",
            error_reason=result.get("error", "Unknown WhatsApp error"),
            payload={"patient_name": patient_name, "medicines": medicines},
        )
        raise self.retry(exc=Exception(result.get("error", "Unknown WhatsApp error")), countdown=60)
    except Exception as exc:
        _write_message_log(
            owner_user_id=owner_user_id,
            patient_id=patient_id,
            phone_number=phone_number,
            message_type="reminder_single",
            status_value="failed",
            error_reason=str(exc),
            payload={"patient_name": patient_name, "medicines": medicines},
        )
        logger.exception("Error sending consolidated reminder: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=2)
def send_bulk_reminders(self, reminders_data):
    """Queue reminders for all provided patients."""
    queued = 0
    for item in reminders_data:
        send_patient_medicine_reminder.delay(
            patient_id=item["patient_id"],
            patient_name=item["patient_name"],
            phone_number=item["phone_number"],
            medicines=item["medicines"],
            owner_user_id=item.get("owner_user_id", ""),
        )
        queued += 1
    logger.info("Queued %s patient reminders", queued)
    return {"queued": queued}


@celery_app.task(bind=True, max_retries=3)
def send_thank_you_message(self, patient_name, phone_number):
    """Send thank-you message after patient registration."""
    from whatsapp_service import whatsapp_service

    message = (
        "Thank you for visiting.\n\n"
        f"Dear {patient_name},\n\n"
        "Thank you for registering with PatientLink. "
        "We will send your medicine reminders as prescribed.\n\n"
        "Stay healthy."
    )

    try:
        logger.info("Sending thank-you message to %s (%s)", patient_name, phone_number)
        result = whatsapp_service.send_message(phone_number, message)
        if result["success"]:
            logger.info("Thank-you message sent to %s", patient_name)
            return {"success": True, "message_id": result.get("message_id")}
        raise self.retry(exc=Exception(result.get("error", "Unknown WhatsApp error")), countdown=60)
    except Exception as exc:
        logger.exception("Error sending thank-you message: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task
def send_scheduled_reminders():
    """
    Send scheduled medicine reminders based on time of day.
    Sends reminders only for active medicine courses.
    """
    db = _get_db_session()
    try:
        current_hour = datetime.now().hour
        timing_map = {
            range(8, 12): "morning",
            range(16, 19): "evening",
            range(21, 23): "night",
        }

        current_timing = None
        for hour_range, timing in timing_map.items():
            if current_hour in hour_range:
                current_timing = timing
                break

        if not current_timing:
            logger.info("No reminder scheduled for hour %s", current_hour)
            return {"message": "No reminders for this hour"}

        logger.info("Sending %s reminders", current_timing)
        patients = db.query(models.Patient).all()
        sent_count = 0

        for patient in patients:
            medicines = db.query(models.Medicine).filter(
                models.Medicine.patient_id == patient.id,
                getattr(models.Medicine, current_timing).is_(True),
            ).all()

            for med in medicines:
                if med.start_date and med.duration_days:
                    end_date = med.start_date + timedelta(days=med.duration_days)
                    if datetime.now() > end_date:
                        logger.info(
                            "Skipping %s for %s, course completed",
                            med.medicine_name,
                            patient.name,
                        )
                        continue

                send_medicine_reminder.delay(
                    patient_id=patient.id,
                    patient_name=patient.name,
                    phone_number=patient.whatsapp_number,
                    medicine_name=med.medicine_name,
                    timing=current_timing,
                    meal_time=med.meal_time or "",
                )
                sent_count += 1

        return {"timing": current_timing, "queued": sent_count}
    finally:
        db.close()


celery_app.conf.beat_schedule = {
    "send-morning-reminders": {
        "task": "tasks.send_scheduled_reminders",
        "schedule": crontab(hour="8", minute="0"),
    },
    "send-evening-reminders": {
        "task": "tasks.send_scheduled_reminders",
        "schedule": crontab(hour="16", minute="0"),
    },
    "send-night-reminders": {
        "task": "tasks.send_scheduled_reminders",
        "schedule": crontab(hour="21", minute="0"),
    },
    "daily-backup": {
        "task": "tasks.create_scheduled_backup",
        "schedule": crontab(hour="2", minute="0"),
    },
}
