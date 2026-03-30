import smtplib
from email.mime.text import MIMEText
from twilio.rest import Client
import json
import os

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
with open(CONFIG_PATH) as f:
    config = json.load(f)

def send_alerts(new_items, search_keyword):
    if not new_items:
        return

    message_body = f"eBay Alert for '{search_keyword}': Found {len(new_items)} new items!\n\n"
    for item in new_items:
        price = item.get('price', {}).get('value', 'N/A')
        message_body += f"- {item['title'][:40]}... | ${price}\n{item['itemWebUrl']}\n\n"

    # Send Email
    if config['notifications']['email']['enabled']:
        try:
            em_conf = config['notifications']['email']
            msg = MIMEText(message_body)
            msg['Subject'] = f"eBay Sniper Alert: {search_keyword}"
            msg['From'] = em_conf['sender_email']
            msg['To'] = em_conf['recipient_email']

            server = smtplib.SMTP(em_conf['smtp_server'], em_conf['smtp_port'])
            server.starttls()
            server.login(em_conf['sender_email'], em_conf['sender_password'])
            server.send_message(msg)
            server.quit()
            print("[✓] Email alert sent.")
        except Exception as e:
            print(f"[x] Email failed: {e}")

    # Send SMS
    if config['notifications']['sms']['enabled']:
        try:
            sms_conf = config['notifications']['sms']
            client = Client(sms_conf['twilio_account_sid'], sms_conf['twilio_auth_token'])
            client.messages.create(
                body=message_body[:1600], # Twilio max length safety
                from_=sms_conf['from_number'],
                to=sms_conf['to_number']
            )
            print("[✓] SMS alert sent.")
        except Exception as e:
            print(f"[x] SMS failed: {e}")