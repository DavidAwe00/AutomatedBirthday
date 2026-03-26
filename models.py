from datetime import date, datetime
from extensions import db


class Birthday(db.Model):
    __tablename__ = "birthdays"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    birth_date = db.Column(db.Date, nullable=False)
    relationship = db.Column(db.String(80), default="Friend")
    custom_message = db.Column(db.Text, default="")
    card_theme = db.Column(db.String(40), default="sunset")
    timezone = db.Column(db.String(60), default="UTC")
    notes = db.Column(db.Text, default="")
    phone = db.Column(db.String(30), default="")
    remind_days = db.Column(db.String(20), default="3,7")  # comma-separated days before
    use_ai_message = db.Column(db.Boolean, default=False)
    streak = db.Column(db.Integer, default=0)
    created_at = db.Column(db.Date, default=date.today)
    last_sent = db.Column(db.Date, nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)

    logs = db.relationship("SentLog", backref="birthday", lazy=True, cascade="all, delete-orphan")

    @property
    def is_deleted(self):
        return self.deleted_at is not None

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

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "birth_date": self.birth_date.isoformat(),
            "relationship": self.relationship,
            "custom_message": self.custom_message,
            "card_theme": self.card_theme,
            "timezone": self.timezone,
            "notes": self.notes,
            "phone": self.phone,
            "use_ai_message": self.use_ai_message,
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
    log_type = db.Column(db.String(20), default="birthday")  # "birthday" or "reminder"
    days_before = db.Column(db.Integer, default=0)  # 0 = on the day, 3/7 = reminder
    notes = db.Column(db.Text, default="")
