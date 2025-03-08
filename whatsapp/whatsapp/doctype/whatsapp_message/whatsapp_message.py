import frappe
from frappe.model.document import Document

class WhatsAppMessage(Document):
    def validate(self):
        if not self.timestamp:
            self.timestamp = frappe.utils.now_datetime()
        
        if self.direction == "outgoing" and not self.to_number:
            frappe.throw("To Number is required for outgoing messages")
        elif self.direction == "incoming" and not self.from_number:
            frappe.throw("From Number is required for incoming messages")
        
        if self.message_type in ["image", "video", "document"] and not self.media_url:
            frappe.throw(f"Media URL is required for {self.message_type} messages")

    def after_insert(self):
        if self.direction == "outgoing":
            self.send_message()

    def send_message(self):
        try:
            settings = frappe.get_single("WhatsApp Settings")
            
            if self.message_type == "text":
                response = settings.send_message(
                    to_number=self.to_number,
                    message_content=self.content,
                    message_type="text"
                )
            # Add support for other message types here
            
            if response and response.get("messages"):
                self.message_id = response["messages"][0]["id"]
                self.status = "sent"
                self.save()
        except Exception as e:
            self.status = "failed"
            self.save()
            frappe.log_error(f"WhatsApp Send Message Error: {str(e)}", "WhatsApp Message Send")
