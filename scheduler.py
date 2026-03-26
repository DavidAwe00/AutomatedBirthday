from datetime import date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()


def check_birthdays(app):
    with app.app_context():
        from models import Birthday, SentLog
        from email_sender import send_birthday_emails
        from extensions import db

        today = date.today()
        birthdays_today = Birthday.query.filter(
            Birthday.deleted_at.is_(None),
            db.extract("month", Birthday.birth_date) == today.month,
            db.extract("day", Birthday.birth_date) == today.day,
        ).all()

        for bday in birthdays_today:
            already_sent = SentLog.query.filter_by(birthday_id=bday.id, log_type="birthday").filter(
                db.func.date(SentLog.sent_at) == today
            ).first()
            if already_sent:
                continue

            result = send_birthday_emails(bday)
            status = "success" if result["success"] else "failed"

            log = SentLog(
                birthday_id=bday.id,
                recipient_email=bday.email,
                status=status,
                log_type="birthday",
                notes=result.get("error", ""),
            )
            db.session.add(log)

            if result["success"]:
                bday.last_sent = today
                bday.streak = (bday.streak or 0) + 1

            db.session.commit()


def check_reminders(app):
    with app.app_context():
        from models import Birthday, SentLog
        from email_sender import send_reminder_email
        from extensions import db

        today = date.today()
        all_birthdays = Birthday.query.filter(Birthday.deleted_at.is_(None)).all()

        for bday in all_birthdays:
            days_until = bday.days_until
            if days_until not in bday.remind_days_list:
                continue

            already_reminded = SentLog.query.filter_by(
                birthday_id=bday.id,
                log_type="reminder",
                days_before=days_until,
            ).filter(
                db.func.date(SentLog.sent_at) == today
            ).first()
            if already_reminded:
                continue

            result = send_reminder_email(bday, days_until)
            log = SentLog(
                birthday_id=bday.id,
                recipient_email=bday.email,
                status="success" if result["success"] else "failed",
                log_type="reminder",
                days_before=days_until,
                notes=result.get("error", ""),
            )
            db.session.add(log)
            db.session.commit()


def start_scheduler(app):
    if not scheduler.running:
        scheduler.add_job(
            check_birthdays, "cron", hour=8, minute=0,
            args=[app], id="daily_birthday_check", replace_existing=True,
        )
        scheduler.add_job(
            check_reminders, "cron", hour=8, minute=5,
            args=[app], id="daily_reminder_check", replace_existing=True,
        )
        scheduler.start()
