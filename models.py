from datetime import date, datetime
from extensions import db
from flask_login import UserMixin


class User(UserMixin, db.Model):
    """Single admin user for login authentication."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, default="admin")
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Birthday(db.Model):
    __tablename__ = "birthdays"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    relationship = db.Column(db.String(80), default="Friend")
    custom_message = db.Column(db.Text, default="")
    card_theme = db.Column(db.String(40), default="sunset")
    card_layout = db.Column(db.String(30), default="banner")   # banner|portrait|postcard|minimal
    timezone = db.Column(db.String(60), default="UTC")
    notes = db.Column(db.Text, default="")
    phone = db.Column(db.String(30), default="")
    sms_enabled = db.Column(db.Boolean, default=False)
    remind_days = db.Column(db.String(20), default="3,7")
    send_days_early = db.Column(db.Integer, default=0)         # send N days before actual birthday
    use_ai_message = db.Column(db.Boolean, default=False)
    streak = db.Column(db.Integer, default=0)
    created_at = db.Column(db.Date, default=date.today)
    last_sent = db.Column(db.Date, nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)

    # ── Gift card settings ─────────────────────────────────────────────────
    gift_card_enabled = db.Column(db.Boolean, default=False)
    gift_card_type = db.Column(db.String(20), default="manual")  # "manual" | "tremendous"
    gift_card_brand = db.Column(db.String(40), default="amazon") # amazon|visa|starbucks|etc.
    gift_card_amount = db.Column(db.Float, default=0.0)
    gift_card_code = db.Column(db.String(120), default="")       # manual code
    gift_card_note = db.Column(db.Text, default="")              # personal note with card

    logs = db.relationship("SentLog", backref="birthday", lazy=True, cascade="all, delete-orphan")
    past_messages = db.relationship("PastMessage", backref="birthday", lazy=True, cascade="all, delete-orphan")
    gift_card_sends = db.relationship("GiftCardSend", backref="birthday", lazy=True, cascade="all, delete-orphan")

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    @property
    def send_date(self):
        """Actual date on which the message should fire (respects send_days_early)."""
        return self.next_birthday - __import__("datetime").timedelta(days=self.send_days_early or 0)

    @property
    def next_birthday(self):
        today = date.today()
        this_year = self.birth_date.replace(year=today.year)
        if this_year < today:
            return this_year.replace(year=today.year + 1)
        return this_year

    @property
    def days_until(self):
        return (self.next_birthday - date.today()).days

    @property
    def age_turning(self):
        return self.next_birthday.year - self.birth_date.year

    @property
    def is_today(self):
        today = date.today()
        return self.birth_date.month == today.month and self.birth_date.day == today.day

    @property
    def remind_days_list(self):
        try:
            return [int(d.strip()) for d in self.remind_days.split(",") if d.strip().isdigit()]
        except Exception:
            return [3, 7]

    def used_message_hashes(self):
        return {pm.message_hash for pm in self.past_messages}

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "birth_date": self.birth_date.isoformat(),
            "relationship": self.relationship,
            "card_theme": self.card_theme,
            "card_layout": self.card_layout,
            "timezone": self.timezone,
            "streak": self.streak,
            "days_until": self.days_until,
            "age_turning": self.age_turning,
            "is_today": self.is_today,
            "last_sent": self.last_sent.isoformat() if self.last_sent else None,
        }


class SentLog(db.Model):
    __tablename__ = "sent_logs"

    id = db.Column(db.Integer, primary_key=True)
    birthday_id = db.Column(db.Integer, db.ForeignKey("birthdays.id"))
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    recipient_email = db.Column(db.String(200))
    status = db.Column(db.String(40), default="success")
    log_type = db.Column(db.String(20), default="birthday")  # birthday|reminder|sms
    days_before = db.Column(db.Integer, default=0)
    notes = db.Column(db.Text, default="")


class PastMessage(db.Model):
    """Tracks messages used per person per year to prevent repeats."""
    __tablename__ = "past_messages"

    id = db.Column(db.Integer, primary_key=True)
    birthday_id = db.Column(db.Integer, db.ForeignKey("birthdays.id"))
    year = db.Column(db.Integer, nullable=False)
    message_hash = db.Column(db.String(64), nullable=False)
    message_text = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class GiftCardSend(db.Model):
    """Tracks each e-gift card delivery (Tremendous order or manual)."""
    __tablename__ = "gift_card_sends"

    id = db.Column(db.Integer, primary_key=True)
    birthday_id = db.Column(db.Integer, db.ForeignKey("birthdays.id"))
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    brand = db.Column(db.String(40), default="amazon")
    amount = db.Column(db.Float, default=0.0)
    delivery_type = db.Column(db.String(20), default="manual")    # manual | tremendous
    code = db.Column(db.String(120), default="")                  # manual code (or masked)
    tremendous_order_id = db.Column(db.String(120), default="")
    status = db.Column(db.String(30), default="sent")             # sent | pending | failed
    recipient_email = db.Column(db.String(200), default="")
    notes = db.Column(db.Text, default="")


class PushSubscription(db.Model):
    """Web Push VAPID subscriptions."""
    __tablename__ = "push_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    endpoint = db.Column(db.Text, unique=True, nullable=False)
    p256dh = db.Column(db.Text, nullable=False)
    auth = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
