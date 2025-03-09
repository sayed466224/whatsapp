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
        self.webhook_url = urljoin(site_url, "/api/method/whatsapp.whatsapp.doctype.whatsapp_settings.whatsapp_handler.webhook")

    def send_message(self, to_number, message_content, message_type="text"):
        """Send a WhatsApp message
        
        Args:
            to_number (str): Recipient's WhatsApp number
            message_content (str|dict): For text messages, a string. For templates, a dict with template details
            message_type (str, optional): Message type ("text" or "template"). Defaults to "text".
        
        Returns:
            dict: WhatsApp API response
        """
        if not self.enabled:
            frappe.throw("WhatsApp integration is not enabled")

        api_url = f"https://graph.facebook.com/v22.0/{self.phone_number_id}/messages"
        
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

        try:
            response = requests.post(api_url, headers=headers, json=message_data)
            response.raise_for_status()
            
            # Create WhatsApp Message record
            whatsapp_message = frappe.get_doc({
                "doctype": "WhatsApp Message",
                "to_number": to_number,
                "message_type": message_type,
                "content": json.dumps(message_content) if isinstance(message_content, dict) else message_content,
                "direction": "Outgoing",
                "status": "Sent"
            })
            whatsapp_message.insert(ignore_permissions=True)
            
            return response.json()
        except requests.exceptions.RequestException as e:
            frappe.logger().error(
                message=f"WhatsApp API Error: {str(e)}\nPayload: {json.dumps(message_data, indent=2)}",
                title="WhatsApp Message Error"
            )
            raise

    def verify_webhook_configuration(self):
        """Verify the webhook configuration with WhatsApp Cloud API"""
        try:
            api_url = f"https://graph.facebook.com/v22.0/{self.phone_number_id}/subscribed_apps"
            
            headers = {
                "Authorization": f"Bearer {self.get_password('access_token')}",
                "Content-Type": "application/json"
            }

            # Subscribe to webhooks
            response = requests.post(api_url, headers=headers)
            response.raise_for_status()

            # Get webhook fields
            fields = [
                "messages",
                "message_deliveries",
                "message_reads",
                "message_templates"
            ]

            # Update webhook subscription
            update_response = requests.post(
                api_url,
                headers=headers,
                json={
                    "fields": fields
                }
            )
            update_response.raise_for_status()

            frappe.msgprint("WhatsApp webhook configuration verified successfully")
            return True

        except requests.exceptions.RequestException as e:
            frappe.logger().error(
                message=f"Webhook verification error: {str(e)}",
                title="WhatsApp Webhook Error"
            )
            frappe.msgprint(
                msg=f"Failed to verify webhook configuration: {str(e)}",
                title="WhatsApp Webhook Error",
                indicator="red"
            )
            return False
