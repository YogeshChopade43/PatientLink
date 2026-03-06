from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class Patient(Base):
    __tablename__ = "patients"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    owner_user_id = Column(String, index=True)
    name = Column(String, index=True)
    whatsapp_number = Column(String, index=True)
    dob = Column(String)  # Store as string in YYYY-MM-DD format
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True, index=True)
    deleted_by_user_id = Column(String, nullable=True)

    # Relationship to medicines
    medicines = relationship("Medicine", back_populates="patient")


class Medicine(Base):
    __tablename__ = "medicines"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    patient_id = Column(String, ForeignKey("patients.id"))
    medicine_name = Column(String, index=True)
    morning = Column(Boolean, default=False)
    evening = Column(Boolean, default=False)
    night = Column(Boolean, default=False)
    duration_days = Column(Integer)
    start_date = Column(DateTime, default=datetime.utcnow)  # When medicine course started
    meal_time = Column(String, default="")  # "before_meal", "after_meal", or ""

    # Relationship to patient
    patient = relationship("Patient", back_populates="medicines")


class MessageLog(Base):
    __tablename__ = "message_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    owner_user_id = Column(String, index=True)
    patient_id = Column(String, ForeignKey("patients.id"), index=True)
    phone_number = Column(String, index=True)
    message_type = Column(String, index=True)  # thank_you, reminder_single, reminder_bulk
    status = Column(String, index=True, default="queued")  # queued, sent, delivered, read, failed
    direction = Column(String, default="outbound")  # outbound/webhook
    provider_message_id = Column(String, nullable=True, index=True)
    error_reason = Column(String, nullable=True)
    retry_count = Column(Integer, default=0)
    payload_json = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DoseLog(Base):
    __tablename__ = "dose_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    owner_user_id = Column(String, index=True)
    patient_id = Column(String, ForeignKey("patients.id"), index=True)
    medicine_id = Column(String, ForeignKey("medicines.id"), index=True)
    slot = Column(String, index=True)  # morning/evening/night
    status = Column(String, index=True)  # taken/missed
    taken_at = Column(DateTime, nullable=True)
    note = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
