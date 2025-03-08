import frappe
import json
import hmac
import hashlib
import requests
from urllib.parse import urljoin

@frappe.whitelist()
def test_webhook_verification():
    """Test the webhook verification endpoint"""
    try:
        settings = frappe.get_single("WhatsApp Settings")
        site_url = frappe.utils.get_url()
        webhook_url = urljoin(site_url, "/api/method/whatsapp.whatsapp.doctype.whatsapp_settings.whatsapp_handler.handle_webhook")

        # Test GET request (verification)
        params = {
            "hub.mode": "subscribe",
            "hub.verify_token": settings.webhook_verify_token,
            "hub.challenge": "test_challenge_123"
        }
        
        response = requests.get(webhook_url, params=params)
        
        results = {
            "verification_test": {
                "status": response.status_code,
                "response": response.text,
                "success": response.status_code == 200 and response.text == "test_challenge_123"
            }
        }
        
        # Test POST request (message webhook)
        test_message = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "test_id",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "1234567890",
                            "phone_number_id": "test_phone_id"
                        },
                        "messages": [{
                            "from": "9876543210",
                            "id": "test_message_id",
                            "timestamp": "1678322788",
                            "text": {
                                "body": "Test message"
                            },
                            "type": "text"
                        }]
                    }
                }]
            }]
        }
        
        # Calculate signature
        signature = hmac.new(
            settings.get_password("access_token").encode("utf-8"),
            json.dumps(test_message).encode(),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            "X-Hub-Signature-256": f"sha256={signature}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(webhook_url, json=test_message, headers=headers)
        
        results["message_test"] = {
            "status": response.status_code,
            "response": response.text,
            "success": response.status_code == 200 and response.text == "ok"
        }
        
        # Add webhook URL to results
        results["webhook_url"] = webhook_url
        results["verification_token"] = settings.webhook_verify_token
        
        return results
        
    except Exception as e:
        frappe.logger().error(f"Webhook Test Error: {str(e)}")
        return {
            "error": str(e),
            "success": False
        }
