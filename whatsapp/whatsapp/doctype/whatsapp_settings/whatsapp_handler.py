import frappe
from frappe import _
import json
import hmac
import hashlib

@frappe.whitelist(allow_guest=True)
def handle_webhook():
    """Handle incoming webhooks from WhatsApp Cloud API"""
    try:
        if frappe.request.method == "GET":
            # Handle the webhook verification request
            mode = frappe.local.form_dict.get("hub.mode")
            token = frappe.local.form_dict.get("hub.verify_token")
            challenge = frappe.local.form_dict.get("hub.challenge")

            # Log verification attempt
            frappe.logger().debug(
                message=f"Webhook verification attempt - Mode: {mode}, Token: {token}, Challenge: {challenge}",
                title="WhatsApp Webhook Verification"
            )

            try:
                settings = frappe.get_single("WhatsApp Settings")
                
                # Check if WhatsApp integration is enabled and configured
                if not settings.enabled:
                    frappe.logger().error(
                        message="WhatsApp integration is not enabled",
                        title="WhatsApp Webhook Error"
                    )
                    frappe.local.response.http_status_code = 503
                    return "Service Unavailable"

                if not all([settings.app_id, settings.app_secret, settings.webhook_verify_token]):
                    frappe.logger().error(
                        message="WhatsApp settings not fully configured",
                        title="WhatsApp Webhook Error"
                    )
                    frappe.local.response.http_status_code = 503
                    return "Service Unavailable"
                
                # Check if a token and mode were sent
                if mode and token:
                    # Check the mode and token sent are correct
                    if mode == "subscribe" and token == settings.webhook_verify_token:
                        # Return raw challenge value as plain text
                        frappe.local.response.http_status_code = 200
                        frappe.local.response.headers["Content-Type"] = "text/plain"
                        return str(challenge)
                    else:
                        # Log verification failure
                        frappe.logger().error(
                            message=f"Webhook verification failed - Expected token: {settings.webhook_verify_token}, Received token: {token}",
                            title="WhatsApp Webhook Verification Failed"
                        )
                        # Responds with '403 Forbidden' if verify tokens do not match
                        frappe.local.response.http_status_code = 403
                        return "Forbidden"

                # Log bad request
                frappe.logger().warning(
                    message=f"Invalid webhook verification request - Missing mode or token",
                    title="WhatsApp Webhook Bad Request"
                )
                frappe.local.response.http_status_code = 400
                return "Bad Request"

            except Exception as e:
                frappe.logger().error(
                    message=f"Error accessing WhatsApp settings: {str(e)}",
                    title="WhatsApp Webhook Error"
                )
                frappe.local.response.http_status_code = 500
                return "Internal Server Error"

        elif frappe.request.method == "POST":
            # Parse the request body from the POST
            try:
                body = json.loads(frappe.request.data) if frappe.request.data else {}
            except Exception as e:
                frappe.logger().error(
                    message=f"Error parsing webhook data: {str(e)}",
                    title="WhatsApp Webhook Error"
                )
                body = {}

            # Check if this is an event from a WhatsApp API
            if body.get("object") == "whatsapp_business_account":
                # Handle the message or status update
                try:
                    entry = body.get("entry", [])[0]
                    changes = entry.get("changes", [])[0]
                    value = changes.get("value", {})

                    # Handle different types of updates
                    if "messages" in value:
                        # Handle incoming message
                        messages = value.get("messages", [])
                        for message in messages:
                            handle_incoming_message(message)
                    elif "statuses" in value:
                        # Handle message status update
                        statuses = value.get("statuses", [])
                        for status in statuses:
                            handle_status_update(status)

                    # Return a '200 OK' response to all requests
                    frappe.local.response.http_status_code = 200
                    return "OK"

                except Exception as e:
                    frappe.logger().error(
                        message=f"Error processing webhook: {str(e)}\nPayload: {json.dumps(body, indent=2)}",
                        title="WhatsApp Webhook Error"
                    )
                    frappe.local.response.http_status_code = 500
                    return "Internal Server Error"

            else:
                # Return a '404 Not Found' if event is not from WhatsApp API
                frappe.local.response.http_status_code = 404
                return "Not Found"

        # Return a '405 Method Not Allowed' if not GET or POST
        frappe.local.response.http_status_code = 405
        return "Method Not Allowed"

    except Exception as e:
        frappe.logger().error(f"Webhook Error: {str(e)}")
        frappe.local.response.http_status_code = 500
        return "Internal Server Error"
    except Exception as e:
        frappe.logger().error(f"Webhook Verification Error: {str(e)}")
        frappe.local.response.http_status_code = 500
        return "Internal Server Error"

def handle_incoming_message(message):
    """Handle incoming WhatsApp message and create lead"""
    try:
        message_type = message.get("type")
        from_number = message.get("from")
        message_id = message.get("id")
        timestamp = message.get("timestamp")

        # Extract message content based on type
        content = ""
        if message_type == "text":
            content = message.get("text", {}).get("body", "")
        elif message_type == "image":
            content = message.get("image", {}).get("caption", "[Image]") or "[Image]"
        elif message_type == "document":
            content = message.get("document", {}).get("caption", "[Document]") or "[Document]"
        elif message_type == "video":
            content = message.get("video", {}).get("caption", "[Video]") or "[Video]"
        elif message_type == "audio":
            content = "[Audio]"
        elif message_type == "location":
            loc = message.get("location", {})
            content = f"[Location] Lat: {loc.get('latitude')}, Long: {loc.get('longitude')}"
        elif message_type == "contacts":
            content = "[Contact Card]"
        else:
            content = f"[{message_type} message]"

        # Create WhatsApp Message record
        whatsapp_message = create_whatsapp_message(
            message_id=message_id,
            from_number=from_number,
            message_type=message_type,
            content=content,
            timestamp=timestamp
        )

        # Create or update lead
        create_lead_from_message(whatsapp_message)

        # Send acknowledgment for new leads
        send_lead_acknowledgment(from_number)

    except Exception as e:
        frappe.logger().error(
            message=f"Error handling message: {str(e)}\nMessage: {json.dumps(message, indent=2)}",
            title="WhatsApp Message Handler Error"
        )
        raise

def handle_status_update(status):
    """Handle message status updates"""
    try:
        message_id = status.get("id")
        status_type = status.get("status")  # sent, delivered, read, failed
        timestamp = status.get("timestamp")

        # Update WhatsApp Message status
        if message_id:
            message = frappe.get_doc("WhatsApp Message", {"message_id": message_id})
            if message:
                message.status = status_type
                message.status_timestamp = timestamp
                message.save(ignore_permissions=True)

    except Exception as e:
        frappe.logger().error(
            message=f"Error handling status update: {str(e)}\nStatus: {json.dumps(status, indent=2)}",
            title="WhatsApp Status Handler Error"
        )
        raise
        frappe.log_error(f"WhatsApp Webhook Error: {str(e)}", "WhatsApp Webhook Handler")
        return "ok"

def verify_webhook_signature(signature):
    """Verify the signature of incoming webhook requests
    
    Args:
        signature (str): X-Hub-Signature-256 header from the request
        
    Returns:
        bool: True if signature is valid, False otherwise
    """
    if not signature:
        return False

    try:
        settings = frappe.get_single("WhatsApp Settings")
        app_secret = settings.get_password("app_secret")  # Get the app secret from settings
        
        # Parse the signature header
        elements = signature.split("=")
        if len(elements) != 2 or elements[0] != "sha256":
            return False
        
        received_hash = elements[1].lower()
        
        # Calculate expected hash
        expected_hash = hmac.new(
            app_secret.encode("utf-8"),
            frappe.request.data,
            hashlib.sha256
        ).hexdigest()
        
        # Use constant-time comparison
        return hmac.compare_digest(received_hash, expected_hash)
    except Exception as e:
        frappe.logger().error(
            message=f"Error verifying webhook signature: {str(e)}",
            title="WhatsApp Webhook Error"
        )
        return False



def create_lead_from_message(whatsapp_message):
    """Create or update lead from WhatsApp message"""
    try:
        # Check if lead exists with this WhatsApp number
        lead_name = frappe.db.get_value("Lead", {"whatsapp_number": whatsapp_message.from_number})
        
        if lead_name:
            # Update existing lead
            lead = frappe.get_doc("Lead", lead_name)
            lead.append("notes", {
                "note": f"WhatsApp Message ({whatsapp_message.message_type}): {whatsapp_message.content}",
                "added_by": frappe.session.user,
                "added_on": frappe.utils.now_datetime()
            })
            lead.save(ignore_permissions=True)
            return lead
        else:
            # Create new lead
            lead = frappe.get_doc({
                "doctype": "Lead",
                "lead_name": f"WhatsApp Lead {whatsapp_message.from_number}",
                "whatsapp_number": whatsapp_message.from_number,
                "source": "WhatsApp",
                "status": "Open",
                "notes": [{
                    "note": f"WhatsApp Message ({whatsapp_message.message_type}): {whatsapp_message.content}",
                    "added_by": frappe.session.user,
                    "added_on": frappe.utils.now_datetime()
                }]
            })
            lead.insert(ignore_permissions=True)
            return lead

    except Exception as e:
        frappe.logger().error(
            message=f"Error creating/updating lead: {str(e)}\nMessage: {whatsapp_message.as_dict()}",
            title="WhatsApp Lead Creation Error"
        )
        raise

def send_lead_acknowledgment(to_number):
    """Send acknowledgment message to new leads"""
    try:
        settings = frappe.get_single("WhatsApp Settings")
        if not settings.enabled or not settings.send_acknowledgment:
            return

        # Get the acknowledgment template
        template = settings.acknowledgment_template or {
            "name": "lead_welcome",
            "language": {
                "code": "en"
            },
            "components": [{
                "type": "body",
                "parameters": [{
                    "type": "text",
                    "text": "there"
                }]
            }]
        }

        # Send the template message
        settings.send_message(
            to_number=to_number,
            message_content=template,
            message_type="template"
        )

    except Exception as e:
        frappe.logger().error(
            message=f"Error sending acknowledgment: {str(e)}\nTo: {to_number}",
            title="WhatsApp Acknowledgment Error"
        )
        # Don't raise the error as this is a non-critical operation
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
