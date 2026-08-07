"""
WhatsApp Service using Meta Cloud API.
Supports both free-form text and template messaging.
"""
import logging
import os

import requests

logger = logging.getLogger(__name__)


META_TOKEN = os.environ.get("META_WHATSAPP_TOKEN", "")
META_PHONE_NUMBER_ID = os.environ.get("META_PHONE_NUMBER_ID", "")
META_WHATSAPP_BUSINESS_ID = os.environ.get("META_WHATSAPP_BUSINESS_ID", "")
META_API_VERSION = "v18.0"

WHATSAPP_USE_TEMPLATES = os.environ.get("WHATSAPP_USE_TEMPLATES", "true").lower() == "true"
WA_TEMPLATE_LANGUAGE_CODE = os.environ.get("WA_TEMPLATE_LANGUAGE_CODE", "en")
WA_TEMPLATE_THANK_YOU = os.environ.get("WA_TEMPLATE_THANK_YOU", "")
WA_TEMPLATE_REMINDER = os.environ.get("WA_TEMPLATE_REMINDER", "")


class WhatsAppService:
    def __init__(self):
        self.token = META_TOKEN
        self.phone_number_id = META_PHONE_NUMBER_ID
        self.business_id = META_WHATSAPP_BUSINESS_ID
        self.api_version = META_API_VERSION
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    def _post_payload(self, payload):
        if not self.token or not self.phone_number_id:
            logger.error("WhatsApp credentials not configured")
            return {"success": False, "error": "WhatsApp not configured"}

        url = f"{self.base_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            result = response.json()
            if response.status_code in (200, 201):
                logger.info("WhatsApp message sent")
                return {"success": True, "message_id": result.get("messages", [{}])[0].get("id")}
            logger.error("WhatsApp API error: %s", result)
            return {"success": False, "error": result.get("error", {}).get("message", "Unknown error")}
        except Exception as exc:
            logger.exception("Failed to send WhatsApp: %s", exc)
            return {"success": False, "error": str(exc)}

    def send_template(self, phone_number, template_name, body_params=None, language_code=None):
        """Send a WhatsApp template message."""
        if not template_name:
            return {"success": False, "error": "Template name is not configured"}

        payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code or WA_TEMPLATE_LANGUAGE_CODE},
            },
        }
        if body_params:
            payload["template"]["components"] = [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": str(v)} for v in body_params],
                }
            ]
        return self._post_payload(payload)

    def send_message(self, phone_number, message):
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "text",
            "text": {"body": message},
        }
        return self._post_payload(payload)

    @staticmethod
    def _reminder_summary(medicines):
        lines = []
        for med in medicines:
            times = []
            if med.get("morning"):
                times.append("Morning")
            if med.get("evening"):
                times.append("Evening")
            if med.get("night"):
                times.append("Night")
            timing = ", ".join(times) if times else "No specific time"
            meal = med.get("meal_time") or ""
            if meal == "before_meal":
                timing = f"{timing} (before meal)"
            elif meal == "after_meal":
                timing = f"{timing} (after meal)"
            lines.append(f"{med.get('medicine_name')} - {timing}")
        return "; ".join(lines)

    def send_thank_you(self, patient_name, phone_number, use_templates=None, template_name=None, language_code=None):
        """Send thank-you, preferring template mode when configured."""
        resolved_use_templates = WHATSAPP_USE_TEMPLATES if use_templates is None else bool(use_templates)
        resolved_template = template_name if template_name is not None else WA_TEMPLATE_THANK_YOU
        if resolved_use_templates and resolved_template:
            return self.send_template(phone_number, resolved_template, [patient_name], language_code=language_code)

        message = (
            "Thank you for visiting.\n\n"
            f"Dear {patient_name},\n\n"
            "Thank you for registering with PatientLink. "
            "We will send your medicine reminders as prescribed.\n\n"
            "Stay healthy."
        )
        return self.send_message(phone_number, message)

    def send_medicine_reminder(self, patient_name, phone_number, medicines, use_templates=None, template_name=None, language_code=None):
        """Send reminder, preferring template mode when configured."""
        resolved_use_templates = WHATSAPP_USE_TEMPLATES if use_templates is None else bool(use_templates)
        resolved_template = template_name if template_name is not None else WA_TEMPLATE_REMINDER
        if resolved_use_templates and resolved_template:
            summary = self._reminder_summary(medicines)
            return self.send_template(phone_number, resolved_template, [patient_name, summary], language_code=language_code)

        message = f"*Medicine Reminder* for {patient_name}\n\n"
        for med in medicines:
            times = []
            if med.get("morning"):
                times.append("Morning")
            if med.get("evening"):
                times.append("Evening")
            if med.get("night"):
                times.append("Night")
            timing = ", ".join(times) if times else "No specific time"
            message += f"- {med.get('medicine_name')} - {timing} for {med.get('duration_days')} days\n"
        message += "\nStay healthy."
        return self.send_message(phone_number, message)


whatsapp_service = WhatsAppService()
