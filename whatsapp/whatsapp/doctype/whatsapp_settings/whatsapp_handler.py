import frappe
from frappe import _
import json
import hmac
import hashlib

@frappe.whitelist(allow_guest=True)
def handle_webhook():
    if frappe.request.method == "GET":
        return handle_webhook_verification()
    elif frappe.request.method == "POST":
        return handle_webhook_event()
    
    frappe.throw(_("Method not allowed"), exc=frappe.PermissionError)

def handle_webhook_verification():
    settings = frappe.get_single("WhatsApp Settings")
    
    mode = frappe.form_dict.get("hub.mode")
    token = frappe.form_dict.get("hub.verify_token")
    challenge = frappe.form_dict.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == settings.webhook_verify_token:
            return challenge
        else:
            frappe.throw(_("Webhook verification failed"), exc=frappe.PermissionError)

def handle_webhook_event():
    try:
        # Verify request signature
        signature = frappe.get_request_header("X-Hub-Signature-256", "")
        if not verify_webhook_signature(signature):
            frappe.throw(_("Invalid webhook signature"), exc=frappe.PermissionError)

        data = json.loads(frappe.request.data)
        
        if "entry" not in data or not data["entry"]:
            return "ok"

        for entry in data["entry"]:
            if "changes" in entry:
                for change in entry["changes"]:
                    handle_status_update(change["value"])
            
            if "messages" in entry:
                for message in entry["messages"]:
                    handle_incoming_message(message)

        return "ok"
    except Exception as e:
        frappe.log_error(f"WhatsApp Webhook Error: {str(e)}", "WhatsApp Webhook Handler")
        return "ok"

def verify_webhook_signature(signature):
    if not signature:
        return False

    try:
        settings = frappe.get_single("WhatsApp Settings")
        app_secret = settings.get_password("access_token")  # You might want to store this separately
        
        elements = signature.split("=")
        if len(elements) != 2:
            return False
        
        sig_hash = elements[1]
        
        expected_hash = hmac.new(
            app_secret.encode("utf-8"),
            frappe.request.data,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(sig_hash, expected_hash)
    except Exception:
        return False

def handle_status_update(data):
    """Handle message status updates (sent, delivered, read, etc.)"""
    try:
        status = data.get("status", [])
        message_id = data.get("id")
        
        if status and message_id:
            # Update your message tracking system here
            frappe.db.set_value("WhatsApp Message", {"message_id": message_id}, "status", status[0])
            frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"WhatsApp Status Update Error: {str(e)}", "WhatsApp Status Handler")

def handle_incoming_message(message):
    """Handle incoming WhatsApp messages and create leads"""
    try:
        # Extract message details
        message_id = message.get("id")
        from_number = message.get("from")
        timestamp = message.get("timestamp")
        
        # Handle different message types
        if "text" in message:
            text = message["text"].get("body", "")
            # Create WhatsApp message record
            whatsapp_message = create_whatsapp_message(
                message_id=message_id,
                from_number=from_number,
                message_type="text",
                content=text,
                timestamp=timestamp
            )
            
            # Create or update lead
            create_lead_from_message(whatsapp_message)
            
        # Add support for other message types here (media, location, etc.)
        
    except Exception as e:
        frappe.log_error(f"WhatsApp Message Handler Error: {str(e)}", "WhatsApp Message Handler")

def create_lead_from_message(whatsapp_message):
    """Create or update lead from WhatsApp message"""
    try:
        # Check if lead exists with this phone number
        existing_lead = frappe.get_list(
            "Lead",
            filters={
                "whatsapp_number": whatsapp_message.from_number
            },
            limit=1
        )
        
        if existing_lead:
            # Update existing lead
            lead = frappe.get_doc("Lead", existing_lead[0].name)
            lead.append("notes", {
                "note": f"WhatsApp Message: {whatsapp_message.content}",
                "added_by": frappe.session.user,
                "added_on": frappe.utils.now_datetime()
            })
            lead.save(ignore_permissions=True)
            return lead
        
        # Create new lead
        lead = frappe.get_doc({
            "doctype": "Lead",
            "lead_name": f"WhatsApp Lead {whatsapp_message.from_number}",
            "source": "WhatsApp",
            "whatsapp_number": whatsapp_message.from_number,
            "notes": [{
                "note": f"Initial WhatsApp Message: {whatsapp_message.content}",
                "added_by": frappe.session.user,
                "added_on": frappe.utils.now_datetime()
            }],
            "status": "Open"
        })
        lead.insert(ignore_permissions=True)
        
        # Send acknowledgment message
        send_lead_acknowledgment(whatsapp_message.from_number)
        
        return lead
    except Exception as e:
        frappe.log_error(f"Lead Creation Error: {str(e)}", "WhatsApp Lead Creation")

def send_lead_acknowledgment(to_number):
    """Send acknowledgment message to new leads"""
    try:
        settings = frappe.get_single("WhatsApp Settings")
        message = "Thank you for contacting us! Our team will get back to you shortly."
        
        whatsapp_message = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "to_number": to_number,
            "content": message,
            "message_type": "text",
            "direction": "outgoing"
        })
        whatsapp_message.insert(ignore_permissions=True)
    except Exception as e:
        frappe.log_error(f"Acknowledgment Error: {str(e)}", "WhatsApp Acknowledgment")

def create_whatsapp_message(message_id, from_number, message_type, content, timestamp):
    """Create a record for the incoming WhatsApp message"""
    message = frappe.get_doc({
        "doctype": "WhatsApp Message",
        "message_id": message_id,
        "from_number": from_number,
        "message_type": message_type,
        "content": content,
        "timestamp": timestamp,
        "direction": "incoming"
    })
    message.insert(ignore_permissions=True)
