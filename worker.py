#!/usr/bin/env python3

import time
import json
import os
import smtplib
import ssl
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from core.db import init_db, get_active_searches, item_seen, mark_item_seen, record_alerts
from core.config import load_config
from core.ebay_api import search_ebay
from core.notifier import send_alerts

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

def log(msg):
    print(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


def verifyemail():
    """
    Sends a test email using the SMTP credentials in config.json.
    Run this directly to confirm your email setup is working before
    relying on live alerts:

        python worker.py --verifyemail
    """
    log("Loading config...")
    config = load_config(CONFIG_PATH)

    email_cfg = config.notifications["email"]

    smtp_server   = email_cfg["smtp_server"]
    smtp_port     = email_cfg["smtp_port"]
    sender_email  = email_cfg["sender_email"]
    sender_pass   = email_cfg["sender_password"]
    recipient     = email_cfg["recipient_email"]
    enabled       = email_cfg.get("enabled", False)

    if not enabled:
        log("⚠️  WARNING: Email notifications are currently DISABLED in config.json "
            "(notifications.email.enabled = false).")
        log("    The test email will still be attempted so you can verify credentials,")
        log("    but remember to set 'enabled': true when you want live alerts to send.")

    log(f"Attempting to send test email via {smtp_server}:{smtp_port}...")
    log(f"  From : {sender_email}")
    log(f"  To   : {recipient}")

    # Build the message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "✅ eBayBot — Email Verification Test"
    msg["From"]    = sender_email
    msg["To"]      = recipient

    text_body = (
        "This is a test email from your eBayBot worker.\n\n"
        "If you're reading this, your SMTP credentials are correct and "
        "email alerts will be delivered successfully.\n\n"
        f"Config used:\n"
        f"  SMTP server : {smtp_server}\n"
        f"  SMTP port   : {smtp_port}\n"
        f"  Sender      : {sender_email}\n"
        f"  Recipient   : {recipient}\n"
        f"  Enabled flag: {enabled}\n"
    )

    html_body = f"""
    <html><body style="font-family:sans-serif;max-width:520px;margin:auto;">
      <h2 style="color:#2ecc71;">✅ eBayBot Email Verification</h2>
      <p>This is a test email from your <strong>eBayBot worker</strong>.</p>
      <p>If you're reading this, your SMTP credentials are correct and
         email alerts will be delivered successfully.</p>
      <table style="border-collapse:collapse;width:100%;font-size:14px;">
        <tr><td style="padding:6px;color:#555;">SMTP server</td>
            <td style="padding:6px;"><code>{smtp_server}</code></td></tr>
        <tr style="background:#f9f9f9;">
            <td style="padding:6px;color:#555;">SMTP port</td>
            <td style="padding:6px;"><code>{smtp_port}</code></td></tr>
        <tr><td style="padding:6px;color:#555;">Sender</td>
            <td style="padding:6px;"><code>{sender_email}</code></td></tr>
        <tr style="background:#f9f9f9;">
            <td style="padding:6px;color:#555;">Recipient</td>
            <td style="padding:6px;"><code>{recipient}</code></td></tr>
        <tr><td style="padding:6px;color:#555;">Enabled flag</td>
            <td style="padding:6px;"><code>{enabled}</code></td></tr>
      </table>
      {"<p style='color:#e67e22;'><strong>⚠️ Note:</strong> The <code>enabled</code> flag is currently <code>false</code>. Set it to <code>true</code> in config.json to receive live alerts.</p>" if not enabled else ""}
    </body></html>
    """

    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    # Port 465 = implicit SSL (SMTP_SSL); port 587/25 = STARTTLS upgrade.
    use_ssl = (smtp_port == 465)
    log(f"  Mode : {'SSL (port 465)' if use_ssl else 'STARTTLS (port 587/25)'}")

    try:
        if use_ssl:
            ctx = smtplib.ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp_server, smtp_port, context=ctx) as server:
                server.login(sender_email, sender_pass)
                server.sendmail(sender_email, recipient, msg.as_string())
        else:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(sender_email, sender_pass)
                server.sendmail(sender_email, recipient, msg.as_string())
        log("✅ Test email sent successfully! Check your inbox.")
    except smtplib.SMTPAuthenticationError:
        log("❌ Authentication failed. Double-check your sender_email and sender_password.")
        log("   For Gmail, make sure you're using an App Password, not your regular password.")
        log("   Generate one at: https://myaccount.google.com/apppasswords")
    except smtplib.SMTPConnectError:
        log(f"❌ Could not connect to {smtp_server}:{smtp_port}. Check smtp_server and smtp_port in config.json.")
    except smtplib.SMTPRecipientsRefused:
        log(f"❌ Recipient address '{recipient}' was refused by the server. Check recipient_email in config.json.")
    except Exception as e:
        log(f"❌ Unexpected error while sending test email: {e}")


def run_loop():
    init_db()
    config = load_config(CONFIG_PATH)
    poll_seconds = config.poll_interval_minutes * 60

    log("eBay Sniper Worker Started...")

    while True:
        searches = get_active_searches()

        if not searches:
            log("No active searches found. Sleeping...")

        for search in searches:
            search_id = search['id']
            keyword   = search['keyword']

            log(f"Running search: {keyword}")

            items = search_ebay(
                keyword=keyword,
                min_price=search['min_price'],
                max_price=search['max_price'],
                category_id=search['category_id'],
                buying_option=search['buying_option']
            )

            new_items = []
            for item in items:
                item_id = item['itemId']
                if not item_seen(search_id, item_id):
                    mark_item_seen(item_id, search_id)
                    new_items.append(item)

            if new_items:
                log(f"Found {len(new_items)} new items for '{keyword}'! Sending alerts...")
                record_alerts(search_id, new_items)
                send_alerts(new_items, keyword, config=config)

            time.sleep(1)  # Tiny sleep to avoid slamming the API instantly if you have many searches

        log(f"Cycle complete. Sleeping for {poll_seconds / 60} minutes.")
        time.sleep(poll_seconds)


if __name__ == "__main__":
    import sys

    if "--verifyemail" in sys.argv:
        verifyemail()
    else:
        try:
            run_loop()
        except KeyboardInterrupt:
            log("Worker terminated by user.")
