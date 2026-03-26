import io
import csv
import json
from datetime import date, datetime
from collections import defaultdict

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, send_file, jsonify, Response,
)

from config import Config
from extensions import db
import models  # noqa: F401
from scheduler import start_scheduler

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

with app.app_context():
    db.create_all()

start_scheduler(app)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _parse_date(raw: str):
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except Exception:
            continue
    return None


def _active_birthdays():
    from models import Birthday
    return Birthday.query.filter(Birthday.deleted_at.is_(None))


# ── Dashboard ────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    from models import Birthday, SentLog

    q = request.args.get("q", "").strip().lower()
    rel_filter = request.args.get("rel", "")
    sort = request.args.get("sort", "upcoming")

    all_bdays = _active_birthdays().all()
    all_bdays.sort(key=lambda b: b.days_until)

    if q:
        all_bdays = [b for b in all_bdays if q in b.name.lower() or q in b.email.lower()]
    if rel_filter:
        all_bdays = [b for b in all_bdays if b.relationship == rel_filter]
    if sort == "name":
        all_bdays.sort(key=lambda b: b.name.lower())
    elif sort == "streak":
        all_bdays.sort(key=lambda b: b.streak, reverse=True)

    today_bdays = [b for b in _active_birthdays().all() if b.is_today]
    total_sent = SentLog.query.filter_by(log_type="birthday").count()
    this_week = sum(1 for b in _active_birthdays().all() if 0 <= b.days_until <= 7)
    trash_count = Birthday.query.filter(Birthday.deleted_at.isnot(None)).count()

    stats = {
        "total": _active_birthdays().count(),
        "today": len(today_bdays),
        "this_week": this_week,
        "sent_total": total_sent,
    }

    return render_template(
        "index.html",
        birthdays=all_bdays,
        today_birthdays=today_bdays,
        stats=stats,
        trash_count=trash_count,
        q=q, rel_filter=rel_filter, sort=sort,
    )


# ── Add / Edit ───────────────────────────────────────────────────────────────

@app.route("/add", methods=["GET", "POST"])
def add_birthday():
    from models import Birthday
    import pytz

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        raw_date = request.form.get("birth_date", "")
        relationship = request.form.get("relationship", "Friend")
        custom_message = request.form.get("custom_message", "").strip()
        card_theme = request.form.get("card_theme", "sunset")
        timezone = request.form.get("timezone", "UTC")
        notes = request.form.get("notes", "").strip()
        phone = request.form.get("phone", "").strip()
        remind_days = request.form.get("remind_days", "3,7").strip()
        use_ai = request.form.get("use_ai_message") == "on"

        if not name or not email or not raw_date:
            flash("Name, email, and birthday are required.", "error")
            return redirect(url_for("add_birthday"))

        birth_date = _parse_date(raw_date)
        if not birth_date:
            flash("Invalid date format.", "error")
            return redirect(url_for("add_birthday"))

        bday = Birthday(
            name=name, email=email, birth_date=birth_date,
            relationship=relationship, custom_message=custom_message,
            card_theme=card_theme, timezone=timezone, notes=notes,
            phone=phone, remind_days=remind_days, use_ai_message=use_ai,
        )
        db.session.add(bday)
        db.session.commit()
        flash(f"🎂 {name}'s birthday added successfully!", "success")
        return redirect(url_for("index"))

    timezones = ["UTC", "US/Eastern", "US/Central", "US/Mountain", "US/Pacific",
                 "Europe/London", "Europe/Paris", "Europe/Berlin",
                 "Asia/Tokyo", "Asia/Shanghai", "Asia/Kolkata", "Australia/Sydney",
                 "Africa/Lagos", "Africa/Nairobi", "America/Sao_Paulo"]
    return render_template("birthday_form.html", birthday=None, timezones=timezones, config=Config)


@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_birthday(id):
    from models import Birthday

    bday = _active_birthdays().filter_by(id=id).first_or_404()

    if request.method == "POST":
        bday.name = request.form.get("name", bday.name).strip()
        bday.email = request.form.get("email", bday.email).strip()
        parsed = _parse_date(request.form.get("birth_date", ""))
        if parsed:
            bday.birth_date = parsed
        bday.relationship = request.form.get("relationship", bday.relationship)
        bday.custom_message = request.form.get("custom_message", "").strip()
        bday.card_theme = request.form.get("card_theme", bday.card_theme)
        bday.timezone = request.form.get("timezone", bday.timezone)
        bday.notes = request.form.get("notes", "").strip()
        bday.phone = request.form.get("phone", "").strip()
        bday.remind_days = request.form.get("remind_days", "3,7").strip()
        bday.use_ai_message = request.form.get("use_ai_message") == "on"
        db.session.commit()
        flash(f"✅ {bday.name}'s birthday updated!", "success")
        return redirect(url_for("index"))

    timezones = ["UTC", "US/Eastern", "US/Central", "US/Mountain", "US/Pacific",
                 "Europe/London", "Europe/Paris", "Europe/Berlin",
                 "Asia/Tokyo", "Asia/Shanghai", "Asia/Kolkata", "Australia/Sydney",
                 "Africa/Lagos", "Africa/Nairobi", "America/Sao_Paulo"]
    return render_template("birthday_form.html", birthday=bday, timezones=timezones, config=Config)


# ── Soft Delete / Trash ──────────────────────────────────────────────────────

@app.route("/delete/<int:id>", methods=["POST"])
def delete_birthday(id):
    from models import Birthday
    bday = Birthday.query.get_or_404(id)
    bday.deleted_at = datetime.utcnow()
    db.session.commit()
    flash(f"🗑️ {bday.name} moved to trash. <a href='/trash'>View trash</a>", "info")
    return redirect(url_for("index"))


@app.route("/trash")
def trash():
    from models import Birthday
    deleted = Birthday.query.filter(Birthday.deleted_at.isnot(None)).order_by(Birthday.deleted_at.desc()).all()
    return render_template("trash.html", deleted=deleted)


@app.route("/restore/<int:id>", methods=["POST"])
def restore_birthday(id):
    from models import Birthday
    bday = Birthday.query.get_or_404(id)
    bday.deleted_at = None
    db.session.commit()
    flash(f"✅ {bday.name}'s birthday restored!", "success")
    return redirect(url_for("trash"))


@app.route("/delete-permanent/<int:id>", methods=["POST"])
def delete_permanent(id):
    from models import Birthday
    bday = Birthday.query.get_or_404(id)
    name = bday.name
    db.session.delete(bday)
    db.session.commit()
    flash(f"🗑️ {name} permanently deleted.", "info")
    return redirect(url_for("trash"))


# ── Send ─────────────────────────────────────────────────────────────────────

@app.route("/send/<int:id>", methods=["POST"])
def send_now(id):
    from models import SentLog
    from email_sender import send_birthday_emails

    bday = _active_birthdays().filter_by(id=id).first_or_404()
    result = send_birthday_emails(bday)

    if result["success"]:
        log = SentLog(birthday_id=bday.id, recipient_email=bday.email, status="success", log_type="birthday")
        bday.last_sent = date.today()
        bday.streak = (bday.streak or 0) + 1
        db.session.add(log)
        db.session.commit()
        flash(f"🚀 Birthday message sent to {bday.name}! You also received a notification.", "success")
    else:
        log = SentLog(birthday_id=bday.id, recipient_email=bday.email, status="failed",
                      log_type="birthday", notes=result.get("error", ""))
        db.session.add(log)
        db.session.commit()
        flash(f"❌ Failed to send: {result.get('error', 'Unknown error')}", "error")

    return redirect(url_for("index"))


# ── Person history ────────────────────────────────────────────────────────────

@app.route("/person/<int:id>")
def person_history(id):
    from models import SentLog
    bday = _active_birthdays().filter_by(id=id).first_or_404()
    logs = SentLog.query.filter_by(birthday_id=id).order_by(SentLog.sent_at.desc()).all()
    return render_template("person_history.html", birthday=bday, logs=logs)


# ── Preview card ──────────────────────────────────────────────────────────────

@app.route("/preview-card")
def preview_card():
    from gift_card_generator import generate_gift_card
    name = request.args.get("name", "Friend")
    theme = request.args.get("theme", "sunset")
    card_bytes = generate_gift_card(name=name, message="Wishing you a magical birthday!", age=25, theme_name=theme)
    return send_file(io.BytesIO(card_bytes), mimetype="image/jpeg")


# ── AI message preview ────────────────────────────────────────────────────────

@app.route("/ai-message")
def ai_message():
    from email_sender import generate_ai_message
    name = request.args.get("name", "Friend")
    relationship = request.args.get("relationship", "Friend")
    age = int(request.args.get("age", 25))
    notes = request.args.get("notes", "")
    if not Config.OPENAI_API_KEY:
        return jsonify({"error": "OpenAI API key not configured."}), 400
    msg = generate_ai_message(name, relationship, age, notes)
    return jsonify({"message": msg})


# ── CSV Import ────────────────────────────────────────────────────────────────

@app.route("/import", methods=["GET", "POST"])
def import_csv():
    from models import Birthday

    if request.method == "POST":
        f = request.files.get("csv_file")
        if not f or not f.filename.endswith(".csv"):
            flash("Please upload a valid .csv file.", "error")
            return redirect(url_for("import_csv"))

        stream = io.StringIO(f.stream.read().decode("utf-8-sig"))
        reader = csv.DictReader(stream)

        added, skipped = 0, 0
        errors = []

        for i, row in enumerate(reader, start=2):
            name = (row.get("name") or row.get("Name") or "").strip()
            email = (row.get("email") or row.get("Email") or "").strip()
            raw_date = (row.get("birth_date") or row.get("birthday") or row.get("Birthday") or "").strip()
            relationship = (row.get("relationship") or row.get("Relationship") or "Friend").strip()
            card_theme = (row.get("card_theme") or row.get("theme") or "sunset").strip()
            notes = (row.get("notes") or row.get("Notes") or "").strip()

            if not name or not email or not raw_date:
                errors.append(f"Row {i}: missing required fields")
                skipped += 1
                continue

            birth_date = _parse_date(raw_date)
            if not birth_date:
                errors.append(f"Row {i}: invalid date '{raw_date}'")
                skipped += 1
                continue

            bday = Birthday(
                name=name, email=email, birth_date=birth_date,
                relationship=relationship, card_theme=card_theme, notes=notes,
            )
            db.session.add(bday)
            added += 1

        db.session.commit()

        if added:
            flash(f"✅ Imported {added} birthday{'s' if added != 1 else ''} successfully!", "success")
        if skipped:
            flash(f"⚠️ Skipped {skipped} row{'s' if skipped != 1 else ''}: {'; '.join(errors[:3])}", "error")

        return redirect(url_for("index"))

    return render_template("import.html")


@app.route("/export-csv")
def export_csv():
    all_bdays = _active_birthdays().all()

    def generate():
        yield "name,email,birth_date,relationship,card_theme,notes,timezone\n"
        for b in all_bdays:
            yield f'"{b.name}","{b.email}","{b.birth_date}","{b.relationship}","{b.card_theme}","{b.notes}","{b.timezone}"\n'

    return Response(generate(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=birthdays.csv"})


# ── Calendar ──────────────────────────────────────────────────────────────────

@app.route("/calendar")
def calendar_view():
    all_bdays = _active_birthdays().all()
    by_month = defaultdict(list)
    for b in all_bdays:
        by_month[b.birth_date.month].append(b)

    months = []
    for m in range(1, 13):
        bdays = sorted(by_month.get(m, []), key=lambda b: b.birth_date.day)
        months.append({
            "num": m,
            "name": date(2000, m, 1).strftime("%B"),
            "birthdays": bdays,
        })

    return render_template("calendar.html", months=months, today=date.today())


# ── Stats ─────────────────────────────────────────────────────────────────────

@app.route("/stats")
def stats_view():
    from models import SentLog

    all_bdays = _active_birthdays().all()
    all_logs = SentLog.query.all()

    by_relationship = defaultdict(int)
    for b in all_bdays:
        by_relationship[b.relationship] += 1

    by_month = defaultdict(int)
    for b in all_bdays:
        by_month[b.birth_date.month] += 1

    sent_by_month = defaultdict(int)
    for log in all_logs:
        if log.log_type == "birthday" and log.status == "success":
            sent_by_month[log.sent_at.month] += 1

    success_count = sum(1 for l in all_logs if l.status == "success" and l.log_type == "birthday")
    failed_count = sum(1 for l in all_logs if l.status == "failed")
    reminder_count = sum(1 for l in all_logs if l.log_type == "reminder")

    top_streak = sorted(all_bdays, key=lambda b: b.streak, reverse=True)[:5]
    upcoming = [b for b in sorted(all_bdays, key=lambda b: b.days_until) if b.days_until <= 30]

    themes_used = defaultdict(int)
    for b in all_bdays:
        themes_used[b.card_theme] += 1

    month_names = [date(2000, m, 1).strftime("%b") for m in range(1, 13)]

    chart_data = {
        "by_relationship": dict(by_relationship),
        "by_month": [by_month.get(m, 0) for m in range(1, 13)],
        "sent_by_month": [sent_by_month.get(m, 0) for m in range(1, 13)],
        "month_names": month_names,
        "themes": dict(themes_used),
    }

    return render_template(
        "stats.html",
        all_bdays=all_bdays,
        chart_data=json.dumps(chart_data),
        success_count=success_count,
        failed_count=failed_count,
        reminder_count=reminder_count,
        top_streak=top_streak,
        upcoming=upcoming,
    )


# ── Settings ──────────────────────────────────────────────────────────────────

@app.route("/settings")
def settings():
    from models import Birthday, SentLog
    from scheduler import scheduler

    logs_raw = (
        db.session.query(SentLog, Birthday.name)
        .join(Birthday, SentLog.birthday_id == Birthday.id)
        .order_by(SentLog.sent_at.desc())
        .limit(20)
        .all()
    )
    return render_template(
        "settings.html",
        config=Config,
        logs=[(log, name) for log, name in logs_raw],
        scheduler_running=scheduler.running,
    )


@app.route("/settings/test-email", methods=["POST"])
def test_email():
    from email_sender import send_birthday_emails

    class FakeBirthday:
        name = request.form.get("test_name", "Test Person")
        email = Config.SENDER_EMAIL
        relationship = "Friend"
        custom_message = ""
        card_theme = request.form.get("test_theme", "sunset")
        age_turning = 30
        streak = 0
        notes = ""
        use_ai_message = False
        last_sent = None

    result = send_birthday_emails(FakeBirthday())
    if result["success"]:
        flash("✅ Test email sent! Check your inbox.", "success")
    else:
        flash(f"❌ Test failed: {result.get('error')}", "error")
    return redirect(url_for("settings"))


if __name__ == "__main__":
    app.run(debug=True, port=5050, use_reloader=False)
