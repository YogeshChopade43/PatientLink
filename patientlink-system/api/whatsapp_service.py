"""
WhatsApp Service using Meta Cloud API
Sends medicine reminders to patients
"""
import os
import requests
import logging

logger = logging.getLogger(__name__)

# Meta Cloud API Configuration
META_TOKEN = os.environ.get('META_WHATSAPP_TOKEN', '')
META_PHONE_NUMBER_ID = os.environ.get('META_PHONE_NUMBER_ID', '')
META_WHATSAPP_BUSINESS_ID = os.environ.get('META_WHATSAPP_BUSINESS_ID', '')
META_API_VERSION = 'v18.0'

class WhatsAppService:
    def __init__(self):
        self.token = META_TOKEN
        self.phone_number_id = META_PHONE_NUMBER_ID
        self.business_id = META_WHATSAPP_BUSINESS_ID
        self.api_version = META_API_VERSION
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
    
    def send_message(self, phone_number, message):
        """Send a WhatsApp message to a patient"""
        if not self.token or not self.phone_number_id:
            logger.error("WhatsApp credentials not configured")
            return {"success": False, "error": "WhatsApp not configured"}
        
        url = f"{self.base_url}/{self.phone_number_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "text",
            "text": {"body": message}
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            result = response.json()
            
            if response.status_code in [200, 201]:
                logger.info(f"WhatsApp message sent to {phone_number}")
                return {"success": True, "message_id": result.get('messages', [{}])[0].get('id')}
            else:
                logger.error(f"WhatsApp API error: {result}")
                return {"success": False, "error": result.get('error', {}).get('message', 'Unknown error')}
                
        except Exception as e:
            logger.exception(f"Failed to send WhatsApp: {e}")
            return {"success": False, "error": str(e)}
    
    def send_medicine_reminder(self, patient_name, phone_number, medicines):
        """Send medicine reminder to a patient"""
        message = f"🔔 *Medicine Reminder* for {patient_name}\n\n"
        
        for med in medicines:
            times = []
            if med.get('morning'): times.append("🌅 Morning")
            if med.get('evening'): times.append("☀️ Evening")
            if med.get('night'): times.append("🌙 Night")
            
            timing = ", ".join(times) if times else "No specific time"
            message += f"• {med.get('medicine_name')} - {timing} for {med.get('duration_days')} days\n"
        
        message += "\n_Stay healthy! Get well soon!_"
        
        return self.send_message(phone_number, message)

# Create singleton instance
whatsapp_service = WhatsAppService()
