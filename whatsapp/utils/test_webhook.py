import frappe
import requests
import json
import click
from frappe.commands.utils import pass_context

@click.command('test-whatsapp-webhook')
@pass_context
def test_webhook(context):
    """Test WhatsApp webhook configuration"""
    try:
        site = context.sites[0]
        frappe.init(site=site)
        frappe.connect()

        settings = frappe.get_single("WhatsApp Settings")
        if not settings.enabled:
            click.echo("WhatsApp integration is not enabled")
            return

        # Test GET request (webhook verification)
        click.echo("Testing webhook verification...")
        response = requests.get(
            settings.webhook_url,
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": settings.webhook_verify_token,
                "hub.challenge": "test_challenge"
            }
        )

        if response.status_code == 200 and response.text == "test_challenge":
            click.echo("✓ Webhook verification successful")
        else:
            click.echo(f"✗ Webhook verification failed: {response.status_code} - {response.text}")

        # Test POST request (message handling)
        click.echo("\nTesting message handling...")
        test_message = {
            "object": "whatsapp_business_account",
            "entry": [{
                "id": "123456789",
                "changes": [{
                    "value": {
                        "messaging_product": "whatsapp",
                        "metadata": {
                            "display_phone_number": "1234567890",
                            "phone_number_id": settings.phone_number_id
                        },
                        "messages": [{
                            "from": "1234567890",
                            "id": "test_message_id",
                            "timestamp": "1234567890",
                            "type": "text",
                            "text": {
                                "body": "Test message"
                            }
                        }]
                    },
                    "field": "messages"
                }]
            }]
        }

        response = requests.post(
            settings.webhook_url,
            json=test_message,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            click.echo("✓ Message handling successful")
        else:
            click.echo(f"✗ Message handling failed: {response.status_code} - {response.text}")

        # Test webhook subscription
        click.echo("\nVerifying webhook subscription...")
        if settings.verify_webhook_configuration():
            click.echo("✓ Webhook subscription verified")
        else:
            click.echo("✗ Webhook subscription verification failed")

    except Exception as e:
        click.echo(f"Error testing webhook: {str(e)}")
    finally:
        frappe.destroy()

commands = [
    test_webhook
]
