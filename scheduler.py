"""
Scheduler jobs:
  - Hourly birthday check (timezone-aware, respects send_days_early)
  - Hourly reminder check
  - Monthly digest (1st of each month, 7 AM UTC)
  - Year-in-review (December 31, 8 PM UTC)
"""
from datetime import date, datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import pytz

scheduler = BackgroundScheduler()


def _local_hour(tz_name: str) -> int:
    """Return the current hour in the given IANA timezone."""
    try:
        tz = pytz.timezone(tz_name)
        return datetime.now(tz).hour
    except Exception:
        return datetime.utcnow().hour


def check_birthdays(app):
    """Timezone-aware birthday check — fires when it's 8 AM in the person's timezone."""
    with app.app_context():
        from models import Birthday, SentLog, PastMessage
        from email_sender import send_birthday_emails
        from notifications import send_birthday_sms, send_discord_notification, send_slack_notification, send_web_push_to_all
        from extensions import db

        today = date.today()
        all_active = Birthday.query.filter(Birthday.deleted_at.is_(None)).all()

        for bday in all_active:
            # Determine the send date (adjusted for send_days_early)
            send_on = bday.next_birthday - timedelta(days=bday.send_days_early or 0)
            if send_on != today:
                continue

            # Check if it's 8 AM in the person's timezone (±1 hour window)
            local_hr = _local_hour(bday.timezone or "UTC")
            if local_hr not in (7, 8, 9):
                continue

            # Skip if already sent today
            already = SentLog.query.filter_by(birthday_id=bday.id, log_type="birthday").filter(
                db.func.date(SentLog.sent_at) == today
            ).first()
            if already:
                continue

            result = send_birthday_emails(bday)
            status = "success" if result["success"] else "failed"

            log = SentLog(birthday_id=bday.id, recipient_email=bday.email,
                          status=status, log_type="birthday", notes=result.get("error", ""))
            db.session.add(log)

            if result["success"]:
                bday.last_sent = today
                bday.streak = (bday.streak or 0) + 1

            db.session.commit()

            # Optional SMS
            if result["success"] and bday.sms_enabled and bday.phone:
                send_birthday_sms(bday)

            # Discord / Slack / Push notifications
            if result["success"]:
                send_discord_notification(bday, "birthday")
                send_slack_notification(bday, "birthday")
                send_web_push_to_all(
                    title=f"🎂 {bday.name}'s Birthday!",
                    body=f"A birthday message was just sent to {bday.name} (turning {bday.age_turning}).",
                    url="/",
                )


def check_reminders(app):
    """Send advance reminder emails for upcoming birthdays."""
    with app.app_context():
        from models import Birthday, SentLog
        from email_sender import send_reminder_email
        from notifications import send_discord_notification, send_slack_notification
        from extensions import db

        today = date.today()
        for bday in Birthday.query.filter(Birthday.deleted_at.is_(None)).all():
            days_until = bday.days_until
            if days_until not in bday.remind_days_list:
                continue

            already = SentLog.query.filter_by(
                birthday_id=bday.id, log_type="reminder", days_before=days_until
            ).filter(db.func.date(SentLog.sent_at) == today).first()
            if already:
                continue

            result = send_reminder_email(bday, days_until)
            log = SentLog(
                birthday_id=bday.id, recipient_email=bday.email,
                status="success" if result["success"] else "failed",
                log_type="reminder", days_before=days_until,
                notes=result.get("error", ""),
            )
            db.session.add(log)
            db.session.commit()

            if result["success"]:
                send_discord_notification(bday, "reminder")
                send_slack_notification(bday, "reminder")


def send_monthly_digest(app):
    """Send a monthly birthday digest on the 1st of each month."""
    with app.app_context():
        from email_sender import send_digest_email
        from models import Birthday

        today = date.today()
        if today.day != 1:
            return

        # All birthdays this month
        bdays_this_month = [
            b for b in Birthday.query.filter(Birthday.deleted_at.is_(None)).all()
            if b.birth_date.month == today.month
        ]
        bdays_this_month.sort(key=lambda b: b.birth_date.day)

        send_digest_email(today.month, bdays_this_month)


def send_year_in_review(app):
    """Send a year-in-review summary on December 31."""
    with app.app_context():
        from email_sender import send_year_in_review_email
        from models import Birthday, SentLog

        today = date.today()
        if today.month != 12 or today.day != 31:
            return

        all_bdays = Birthday.query.filter(Birthday.deleted_at.is_(None)).all()
        sent_this_year = SentLog.query.filter(
            SentLog.log_type == "birthday",
            SentLog.status == "success",
            db.func.strftime("%Y", SentLog.sent_at) == str(today.year),
        ).count() if False else 0  # will be calculated inside the email function

        send_year_in_review_email(today.year, all_bdays)


def start_scheduler(app):
    if not scheduler.running:
        # Hourly checks
        scheduler.add_job(check_birthdays, "cron", minute=0, args=[app],
                          id="birthday_check", replace_existing=True)
        scheduler.add_job(check_reminders, "cron", minute=5, args=[app],
                          id="reminder_check", replace_existing=True)
        # Monthly digest: 1st of month at 7 AM UTC
        scheduler.add_job(send_monthly_digest, "cron", hour=7, minute=0, args=[app],
                          id="monthly_digest", replace_existing=True)
        # Year-in-review: Dec 31 at 8 PM UTC
        scheduler.add_job(send_year_in_review, "cron", month=12, day=31, hour=20,
                          args=[app], id="year_in_review", replace_existing=True)
        scheduler.start()
