import os
from dotenv import load_dotenv

load_dotenv()


SMTP_PROVIDERS = {
    "gmail":   {"host": "smtp.gmail.com",   "port": 587},
    "outlook": {"host": "smtp.office365.com", "port": 587},
    "yahoo":   {"host": "smtp.mail.yahoo.com", "port": 587},
    "custom":  {"host": os.environ.get("SMTP_HOST_CUSTOM", ""), "port": int(os.environ.get("SMTP_PORT_CUSTOM", 587))},
}


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = "sqlite:///birthdays.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "")
    SENDER_APP_PASSWORD = os.environ.get("SENDER_APP_PASSWORD", "")
    SENDER_NAME = os.environ.get("SENDER_NAME", "Birthday Bot")
    SIGNATURE = os.environ.get("SIGNATURE", "Warm wishes")

    EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "gmail")  # gmail|outlook|yahoo|custom
    SMTP_HOST_CUSTOM = os.environ.get("SMTP_HOST_CUSTOM", "")
    SMTP_PORT_CUSTOM = int(os.environ.get("SMTP_PORT_CUSTOM", 587))

    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = "UTC"

    @classmethod
    def smtp_settings(cls):
        provider = cls.EMAIL_PROVIDER or "gmail"
        if provider == "custom":
            return cls.SMTP_HOST_CUSTOM, cls.SMTP_PORT_CUSTOM
        p = SMTP_PROVIDERS.get(provider, SMTP_PROVIDERS["gmail"])
        return p["host"], p["port"]
