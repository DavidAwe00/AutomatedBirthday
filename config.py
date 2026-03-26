import os
from dotenv import load_dotenv

load_dotenv()

SMTP_PROVIDERS = {
    "gmail":   {"host": "smtp.gmail.com",     "port": 587},
    "outlook": {"host": "smtp.office365.com", "port": 587},
    "yahoo":   {"host": "smtp.mail.yahoo.com","port": 587},
    "custom":  {"host": os.environ.get("SMTP_HOST_CUSTOM", ""),
                "port": int(os.environ.get("SMTP_PORT_CUSTOM", 587))},
}


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = "sqlite:///birthdays.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ── Email ────────────────────────────────────────────────────────────
    SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
    SENDER_APP_PASSWORD = os.environ.get("SENDER_APP_PASSWORD", "")
    SENDER_NAME = os.environ.get("SENDER_NAME", "Birthday Bot")
    SIGNATURE = os.environ.get("SIGNATURE", "Warm wishes")
    EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "gmail")
    SMTP_HOST_CUSTOM = os.environ.get("SMTP_HOST_CUSTOM", "")
    SMTP_PORT_CUSTOM = int(os.environ.get("SMTP_PORT_CUSTOM", 587))

    # ── OpenAI ───────────────────────────────────────────────────────────
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

    # ── Twilio (SMS / WhatsApp) ───────────────────────────────────────────
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "")        # +1xxxxx
    TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "")    # whatsapp:+14155238886

    # ── Webhooks ─────────────────────────────────────────────────────────
    DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
    SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

    # ── Web Push (VAPID) ──────────────────────────────────────────────────
    VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
    VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
    VAPID_CLAIMS_EMAIL = os.environ.get("VAPID_CLAIMS_EMAIL", "")

    # ── Tremendous (e-gift cards) ─────────────────────────────────────────
    TREMENDOUS_API_KEY = os.environ.get("TREMENDOUS_API_KEY", "")
    TREMENDOUS_FUNDING_SOURCE_ID = os.environ.get("TREMENDOUS_FUNDING_SOURCE_ID", "")
    TREMENDOUS_SANDBOX = os.environ.get("TREMENDOUS_SANDBOX", "true").lower() == "true"

    # ── Auth ─────────────────────────────────────────────────────────────
    # Set APP_PASSWORD in .env to enable login protection
    APP_PASSWORD = os.environ.get("APP_PASSWORD", "")
    LOGIN_REQUIRED = os.environ.get("LOGIN_REQUIRED", "false").lower() == "true"

    # ── Scheduler ────────────────────────────────────────────────────────
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = "UTC"

    @classmethod
    def smtp_settings(cls):
        provider = cls.EMAIL_PROVIDER or "gmail"
        if provider == "custom":
            return cls.SMTP_HOST_CUSTOM, cls.SMTP_PORT_CUSTOM
        p = SMTP_PROVIDERS.get(provider, SMTP_PROVIDERS["gmail"])
        return p["host"], p["port"]

    @classmethod
    def twilio_configured(cls):
        return bool(cls.TWILIO_ACCOUNT_SID and cls.TWILIO_AUTH_TOKEN and cls.TWILIO_FROM_NUMBER)

    @classmethod
    def tremendous_configured(cls):
        return bool(cls.TREMENDOUS_API_KEY and cls.TREMENDOUS_FUNDING_SOURCE_ID)

    @classmethod
    def push_configured(cls):
        return bool(cls.VAPID_PRIVATE_KEY and cls.VAPID_PUBLIC_KEY)
