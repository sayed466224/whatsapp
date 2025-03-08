import frappe
from frappe.model.document import Document
import requests
import json
from urllib.parse import urljoin

class WhatsAppSettings(Document):
    def validate(self):
        if self.enabled:
            if not all([self.business_account_id, self.phone_number_id, self.access_token]):
                frappe.throw("Business Account ID, Phone Number ID and Access Token are required when WhatsApp is enabled")
        
        if not self.webhook_verify_token:
            self.webhook_verify_token = frappe.generate_hash(length=20)
        
        self.set_webhook_url()
    
    def set_webhook_url(self):
        site_url = frappe.utils.get_url()
        self.webhook_url = urljoin(site_url, "/api/method/whatsapp.whatsapp.doctype.whatsapp_settings.whatsapp_handler.handle_webhook")

    def send_message(self, to_number, message_content, message_type="text"):
        if not self.enabled:
            frappe.throw("WhatsApp integration is not enabled")

        api_url = f"https://graph.facebook.com/v18.0/{self.phone_number_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {self.get_password('access_token')}",
            "Content-Type": "application/json"
        }

        message_data = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
        }

        if message_type == "text":
            message_data["type"] = "text"
            message_data["text"] = {"body": message_content}
        # Add support for other message types (template, media, etc.) here

        try:
            response = requests.post(api_url, headers=headers, json=message_data)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            frappe.log_error(f"WhatsApp API Error: {str(e)}", "WhatsApp Message Error")
            frappe.throw("Failed to send WhatsApp message. Check error logs for details.")
