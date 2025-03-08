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

    @frappe.whitelist()
    def verify_configuration(self):
        """Verify WhatsApp Business Account and Phone Number configuration"""
        if not self.enabled:
            return {
                "success": False,
                "message": "WhatsApp integration is not enabled"
            }

        try:
            api_base_url = "https://graph.facebook.com/v22.0"
            headers = {
                "Authorization": f"Bearer {self.get_password('access_token')}",
                "Content-Type": "application/json"
            }

            # Verify Business Account
            business_url = f"{api_base_url}/{self.business_account_id}"
            business_response = requests.get(business_url, headers=headers)
            business_response.raise_for_status()
            business_data = business_response.json()

            # Verify Phone Number
            phone_url = f"{api_base_url}/{self.phone_number_id}"
            phone_response = requests.get(phone_url, headers=headers)
            phone_response.raise_for_status()
            phone_data = phone_response.json()

            return {
                "success": True,
                "business_account": {
                    "id": business_data.get("id"),
                    "name": business_data.get("name"),
                    "currency": business_data.get("currency")
                },
                "phone_number": {
                    "id": phone_data.get("id"),
                    "display_phone_number": phone_data.get("display_phone_number"),
                    "quality_rating": phone_data.get("quality_rating")
                }
            }
        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if hasattr(e.response, 'json'):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", {}).get("message", str(e))
                except:
                    pass
            
            frappe.log_error(
                message=f"WhatsApp Configuration Error: {error_msg}",
                title="WhatsApp Verification Error"
            )
            
            return {
                "success": False,
                "message": f"Configuration verification failed: {error_msg}"
            }

    def send_message(self, to_number, message_content, message_type="text"):
        if not self.enabled:
            frappe.throw("WhatsApp integration is not enabled")

        api_base_url = "https://graph.facebook.com/v22.0"
        api_url = f"{api_base_url}/{self.phone_number_id}/messages"
        
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
        elif message_type == "template":
            message_data["type"] = "template"
            message_data["template"] = message_content
        elif message_type == "media":
            message_data["type"] = message_content.get("type")
            message_data[message_content["type"]] = {
                "link": message_content.get("url"),
                "caption": message_content.get("caption")
            }

        try:
            # First verify the phone number ID
            verify_url = f"{api_base_url}/{self.phone_number_id}"
            verify_response = requests.get(verify_url, headers=headers)
            verify_response.raise_for_status()

            # Send the message
            response = requests.post(api_url, headers=headers, json=message_data)
            response_data = response.json()

            if response.status_code != 200:
                error_msg = response_data.get("error", {}).get("message", "Unknown error")
                frappe.log_error(
                    message=f"WhatsApp API Error: {error_msg}\nPayload: {json.dumps(message_data, indent=2)}",
                    title="WhatsApp Message Error"
                )
                frappe.throw(f"Failed to send WhatsApp message: {error_msg}")

            return response_data

        except requests.exceptions.RequestException as e:
            error_msg = str(e)
            if hasattr(e.response, 'json'):
                try:
                    error_data = e.response.json()
                    error_msg = error_data.get("error", {}).get("message", str(e))
                except:
                    pass
            
            frappe.log_error(
                message=f"WhatsApp API Error: {error_msg}\nPayload: {json.dumps(message_data, indent=2)}",
                title="WhatsApp Message Error"
            )
            frappe.throw(f"Failed to send WhatsApp message: {error_msg}")
