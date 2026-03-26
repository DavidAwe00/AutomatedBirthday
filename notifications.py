"""
Multi-channel notification dispatchers:
  - SMS via Twilio
  - WhatsApp via Twilio
  - Discord webhook
  - Slack webhook
  - Web Push (VAPID)
"""
import json
import requests as http_requests
from config import Config


# ── SMS & WhatsApp ────────────────────────────────────────────────────────────

def send_sms(to_number: str, body: str) -> dict:
    if not Config.twilio_configured():
        return {"success": False, "error": "Twilio not configured."}
    try:
        from twilio.rest import Client
        client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
        msg = client.messages.create(body=body, from_=Config.TWILIO_FROM_NUMBER, to=to_number)
        return {"success": True, "sid": msg.sid}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_whatsapp(to_number: str, body: str) -> dict:
    if not Config.twilio_configured() or not Config.TWILIO_WHATSAPP_FROM:
        return {"success": False, "error": "Twilio WhatsApp not configured."}
    try:
        from twilio.rest import Client
        client = Client(Config.TWILIO_ACCOUNT_SID, Config.TWILIO_AUTH_TOKEN)
        msg = client.messages.create(
            body=body,
            from_=Config.TWILIO_WHATSAPP_FROM,
            to=f"whatsapp:{to_number}",
        )
        return {"success": True, "sid": msg.sid}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_birthday_sms(birthday) -> dict:
    """Send an SMS birthday greeting to the celebrant."""
    if not birthday.phone or not birthday.sms_enabled:
        return {"success": False, "error": "SMS not enabled or no phone number."}
    body = (
        f"🎂 Happy Birthday, {birthday.name}! "
        f"Wishing you an absolutely amazing {birthday.age_turning}th birthday. "
        f"You deserve all the joy today brings! 🎉"
    )
    return send_sms(birthday.phone, body)


# ── Discord & Slack ───────────────────────────────────────────────────────────

def send_discord_notification(birthday, event: str = "birthday") -> dict:
    url = Config.DISCORD_WEBHOOK_URL
    if not url:
        return {"success": False, "error": "Discord webhook URL not configured."}
    try:
        if event == "birthday":
            embed = {
                "title": f"🎂 Happy Birthday, {birthday.name}!",
                "description": (
                    f"**{birthday.name}** is celebrating their **{birthday.age_turning}th birthday** today!\n"
                    f"Relationship: {birthday.relationship}\n"
                    f"A birthday message has been sent to {birthday.email} 🚀"
                ),
                "color": 0x7C3AED,
                "footer": {"text": "Birthday Bot"},
            }
        else:
            embed = {
                "title": f"⏰ Birthday Reminder: {birthday.name}",
                "description": f"{birthday.name}'s birthday is in {birthday.days_until} days ({birthday.next_birthday.strftime('%B %d')}).",
                "color": 0xF59E0B,
            }
        payload = {"embeds": [embed]}
        resp = http_requests.post(url, json=payload, timeout=8)
        return {"success": resp.status_code in (200, 204)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_slack_notification(birthday, event: str = "birthday") -> dict:
    url = Config.SLACK_WEBHOOK_URL
    if not url:
        return {"success": False, "error": "Slack webhook URL not configured."}
    try:
        if event == "birthday":
            text = (
                f":birthday: *Happy Birthday, {birthday.name}!* "
                f"They're turning {birthday.age_turning} today. "
                f"A birthday message has been sent to {birthday.email}."
            )
        else:
            text = (
                f":alarm_clock: *Reminder:* {birthday.name}'s birthday is in "
                f"{birthday.days_until} days ({birthday.next_birthday.strftime('%B %d')})."
            )
        resp = http_requests.post(url, json={"text": text}, timeout=8)
        return {"success": resp.ok}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ── Web Push ──────────────────────────────────────────────────────────────────

def send_web_push_to_all(title: str, body: str, url: str = "/") -> dict:
    if not Config.push_configured():
        return {"success": False, "error": "VAPID keys not configured."}
    try:
        from pywebpush import webpush, WebPushException
        from models import PushSubscription

        subs = PushSubscription.query.all()
        if not subs:
            return {"success": True, "sent": 0}

        claims = {
            "sub": f"mailto:{Config.VAPID_CLAIMS_EMAIL or Config.SENDER_EMAIL or 'admin@example.com'}"
        }
        data = json.dumps({"title": title, "body": body, "url": url})
        sent, failed = 0, 0

        for sub in subs:
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=data,
                    vapid_private_key=Config.VAPID_PRIVATE_KEY,
                    vapid_claims=claims,
                )
                sent += 1
            except WebPushException as e:
                if "410" in str(e) or "404" in str(e):
                    from extensions import db
                    db.session.delete(sub)
                    db.session.commit()
                failed += 1

        return {"success": True, "sent": sent, "failed": failed}
    except Exception as e:
        return {"success": False, "error": str(e)}


def generate_vapid_keys() -> dict:
    """Generate a new VAPID key pair (call once, store in .env)."""
    try:
        from py_vapid import Vapid
        v = Vapid()
        v.generate_keys()
        return {
            "private_key": v.private_pem().decode(),
            "public_key": v.public_key.public_bytes(
                __import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding", "PublicFormat"]).Encoding.PEM,
                __import__("cryptography.hazmat.primitives.serialization", fromlist=["Encoding", "PublicFormat"]).PublicFormat.SubjectPublicKeyInfo
            ).decode(),
        }
    except Exception as e:
        return {"error": str(e)}
