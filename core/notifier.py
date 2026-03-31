import smtplib
from email.mime.text import MIMEText
import os
from typing import Any, Dict, Optional

from core.config import AppConfig, load_config

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")

def _safe_get(d: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def send_alerts(new_items, search_keyword, config: Optional[AppConfig] = None):
    if not new_items:
        return

    cfg = config or load_config(CONFIG_PATH)

    message_body = f"eBay Alert for '{search_keyword}': Found {len(new_items)} new items!\n\n"
    for item in new_items:
        price = item.get('price', {}).get('value', 'N/A')
        message_body += f"- {item['title'][:40]}... | ${price}\n{item['itemWebUrl']}\n\n"

    # Send Email
    if _safe_get(cfg.notifications, "email", "enabled", default=False):
        try:
            em_conf = _safe_get(cfg.notifications, "email", default={}) or {}
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
    if _safe_get(cfg.notifications, "sms", "enabled", default=False):
        try:
            try:
                from twilio.rest import Client  # optional dependency
            except Exception as e:
                raise RuntimeError(
                    "SMS notifications enabled but 'twilio' is not installed. Install requirements.txt or disable SMS."
                ) from e

            sms_conf = _safe_get(cfg.notifications, "sms", default={}) or {}
            client = Client(sms_conf['twilio_account_sid'], sms_conf['twilio_auth_token'])
            client.messages.create(
                body=message_body[:1600], # Twilio max length safety
                from_=sms_conf['from_number'],
                to=sms_conf['to_number']
            )
            print("[✓] SMS alert sent.")
        except Exception as e:
            print(f"[x] SMS failed: {e}")