# Frappe WhatsApp Integration

A Frappe app that integrates WhatsApp Business API with your Frappe/ERPNext instance, enabling WhatsApp communication and automatic lead generation.

## Features

- WhatsApp Business API Integration
- Automatic Lead Generation from WhatsApp Messages
- Message History Tracking
- Automated Response System
- Webhook Integration for Real-time Updates
- Secure API Key Management

## Installation

```bash
bench get-app whatsapp https://github.com/yourusername/frappe-whatsapp
bench --site your-site install-app whatsapp
```

## Configuration

1. Get your WhatsApp Business API credentials:
   - Business Account ID
   - Phone Number ID
   - Access Token

2. In your Frappe instance:
   - Go to WhatsApp Settings
   - Enter your API credentials
   - Enable the integration
   - Copy the Webhook URL

3. Configure Webhook in Meta Developer Portal:
   - Use the Webhook URL from WhatsApp Settings
   - Set up the Webhook Verify Token

## Usage

### Automatic Lead Generation
When a customer sends a WhatsApp message:
- A new lead is automatically created (if not exists)
- Message is logged in lead's notes
- Automatic acknowledgment message is sent

### Sending Messages
```python
whatsapp_message = frappe.get_doc({
    "doctype": "WhatsApp Message",
    "to_number": "recipient_number",
    "content": "Your message",
    "message_type": "text",
    "direction": "outgoing"
})
whatsapp_message.insert()
```

## License

MIT License

## Credits

Developed by Abu Sayed

CRM Whatsapp integration

#### License

mit