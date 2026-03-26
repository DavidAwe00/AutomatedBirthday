import io
import csv
import json
from datetime import date, datetime
from collections import defaultdict
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, send_file, jsonify, Response, abort,
)
from flask_login import login_user, logout_user, login_required, current_user

from config import Config
from extensions import db
import models  # noqa: F401
from auth import init_auth, create_admin, verify_password, admin_exists
from scheduler import start_scheduler
from gift_card_service import BRAND_LIST, BRANDS

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

with app.app_context():
    db.create_all()
    # Auto-create admin from env password if set and not yet created
    if Config.APP_PASSWORD and not admin_exists():
        create_admin(db, Config.APP_PASSWORD)

init_auth(app, db)
start_scheduler(app)


# ── Auth helpers ──────────────────────────────────────────────────────────────

def auth_required(f):
    """Apply login_required only when LOGIN_REQUIRED=true in .env."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if Config.LOGIN_REQUIRED and not current_user.is_authenticated:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def _parse_date(raw: str):
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except Exception:
            continue
    return None


def _active():
    from models import Birthday
    return Birthday.query.filter(Birthday.deleted_at.is_(None))


TIMEZONES = [
    "UTC", "US/Eastern", "US/Central", "US/Mountain", "US/Pacific",
    "Europe/London", "Europe/Paris", "Europe/Berlin",
    "Asia/Tokyo", "Asia/Shanghai", "Asia/Kolkata", "Australia/Sydney",
    "Africa/Lagos", "Africa/Nairobi", "America/Sao_Paulo",
]


# ── Auth routes ───────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if not Config.LOGIN_REQUIRED:
        return redirect(url_for("index"))
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        password = request.form.get("password", "")
        setup = request.form.get("setup") == "1"

        if setup and not admin_exists():
            if len(password) < 6:
                flash("Password must be at least 6 characters.", "error")
                return redirect(url_for("login"))
            create_admin(db, password)
            flash("Admin account created. Please log in.", "success")
            return redirect(url_for("login"))

        if verify_password(password):
            from models import User
            user = User.query.filter_by(username="admin").first()
            login_user(user, remember=True)
            return redirect(request.args.get("next") or url_for("index"))
        else:
            flash("Incorrect password.", "error")

    return render_template("login.html", needs_setup=not admin_exists())


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.route("/")
@auth_required
def index():
    from models import Birthday, SentLog

    q = request.args.get("q", "").strip().lower()
    rel_filter = request.args.get("rel", "")
    sort = request.args.get("sort", "upcoming")

    all_bdays = _active().all()
    all_bdays.sort(key=lambda b: b.days_until)
    if q:
        all_bdays = [b for b in all_bdays if q in b.name.lower() or q in b.email.lower()]
    if rel_filter:
        all_bdays = [b for b in all_bdays if b.relationship == rel_filter]
    if sort == "name":
        all_bdays.sort(key=lambda b: b.name.lower())
    elif sort == "streak":
        all_bdays.sort(key=lambda b: b.streak, reverse=True)

    today_bdays = [b for b in _active().all() if b.is_today]
    total_sent = SentLog.query.filter_by(log_type="birthday").count()
    this_week = sum(1 for b in _active().all() if 0 <= b.days_until <= 7)
    trash_count = Birthday.query.filter(Birthday.deleted_at.isnot(None)).count()

    return render_template(
        "index.html",
        birthdays=all_bdays,
        today_birthdays=today_bdays,
        stats={"total": _active().count(), "today": len(today_bdays),
               "this_week": this_week, "sent_total": total_sent},
        trash_count=trash_count,
        q=q, rel_filter=rel_filter, sort=sort,
    )


# ── Add / Edit ────────────────────────────────────────────────────────────────

@app.route("/add", methods=["GET", "POST"])
@auth_required
def add_birthday():
    from models import Birthday

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        raw_date = request.form.get("birth_date", "")
        if not name or not email or not raw_date:
            flash("Name, email, and birthday are required.", "error")
            return redirect(url_for("add_birthday"))
        birth_date = _parse_date(raw_date)
        if not birth_date:
            flash("Invalid date format.", "error")
            return redirect(url_for("add_birthday"))

        bday = Birthday(
            name=name, email=email, birth_date=birth_date,
            relationship=request.form.get("relationship", "Friend"),
            custom_message=request.form.get("custom_message", "").strip(),
            card_theme=request.form.get("card_theme", "sunset"),
            card_layout=request.form.get("card_layout", "banner"),
            timezone=request.form.get("timezone", "UTC"),
            notes=request.form.get("notes", "").strip(),
            phone=request.form.get("phone", "").strip(),
            sms_enabled=request.form.get("sms_enabled") == "on",
            remind_days=request.form.get("remind_days", "3,7").strip() or "3,7",
            send_days_early=int(request.form.get("send_days_early", 0) or 0),
            use_ai_message=request.form.get("use_ai_message") == "on",
            gift_card_enabled=request.form.get("gift_card_enabled") == "on",
            gift_card_type=request.form.get("gift_card_type", "manual"),
            gift_card_brand=request.form.get("gift_card_brand", "amazon"),
            gift_card_amount=float(request.form.get("gift_card_amount") or 0),
            gift_card_code=request.form.get("gift_card_code", "").strip(),
            gift_card_note=request.form.get("gift_card_note", "").strip(),
        )
        db.session.add(bday)
        db.session.commit()
        flash(f"🎂 {name}'s birthday added successfully!", "success")
        return redirect(url_for("index"))

    brands_js = json.dumps([[k, v["label"], v["icon"], v["color1"], v["color2"]] for k, v in BRANDS.items()])
    return render_template("birthday_form.html", birthday=None, timezones=TIMEZONES, config=Config,
                           gift_card_brands=BRAND_LIST, gift_card_brands_js=brands_js)


@app.route("/edit/<int:id>", methods=["GET", "POST"])
@auth_required
def edit_birthday(id):
    bday = _active().filter_by(id=id).first_or_404()
    if request.method == "POST":
        bday.name = request.form.get("name", bday.name).strip()
        bday.email = request.form.get("email", bday.email).strip()
        parsed = _parse_date(request.form.get("birth_date", ""))
        if parsed:
            bday.birth_date = parsed
        bday.relationship = request.form.get("relationship", bday.relationship)
        bday.custom_message = request.form.get("custom_message", "").strip()
        bday.card_theme = request.form.get("card_theme", bday.card_theme)
        bday.card_layout = request.form.get("card_layout", bday.card_layout)
        bday.timezone = request.form.get("timezone", bday.timezone)
        bday.notes = request.form.get("notes", "").strip()
        bday.phone = request.form.get("phone", "").strip()
        bday.sms_enabled = request.form.get("sms_enabled") == "on"
        bday.remind_days = request.form.get("remind_days", "3,7").strip() or "3,7"
        bday.send_days_early = int(request.form.get("send_days_early", 0) or 0)
        bday.use_ai_message = request.form.get("use_ai_message") == "on"
        bday.gift_card_enabled = request.form.get("gift_card_enabled") == "on"
        bday.gift_card_type = request.form.get("gift_card_type", "manual")
        bday.gift_card_brand = request.form.get("gift_card_brand", "amazon")
        bday.gift_card_amount = float(request.form.get("gift_card_amount") or 0)
        bday.gift_card_code = request.form.get("gift_card_code", "").strip()
        bday.gift_card_note = request.form.get("gift_card_note", "").strip()
        db.session.commit()
        flash(f"✅ {bday.name}'s birthday updated!", "success")
        return redirect(url_for("index"))
    brands_js = json.dumps([[k, v["label"], v["icon"], v["color1"], v["color2"]] for k, v in BRANDS.items()])
    return render_template("birthday_form.html", birthday=bday, timezones=TIMEZONES, config=Config,
                           gift_card_brands=BRAND_LIST, gift_card_brands_js=brands_js)


# ── Soft Delete / Trash ───────────────────────────────────────────────────────

@app.route("/delete/<int:id>", methods=["POST"])
@auth_required
def delete_birthday(id):
    from models import Birthday
    bday = Birthday.query.get_or_404(id)
    bday.deleted_at = datetime.utcnow()
    db.session.commit()
    flash(f"🗑️ {bday.name} moved to trash. <a href='/trash'>View trash</a>", "info")
    return redirect(url_for("index"))


@app.route("/trash")
@auth_required
def trash():
    from models import Birthday
    deleted = Birthday.query.filter(Birthday.deleted_at.isnot(None)).order_by(Birthday.deleted_at.desc()).all()
    return render_template("trash.html", deleted=deleted)


@app.route("/restore/<int:id>", methods=["POST"])
@auth_required
def restore_birthday(id):
    from models import Birthday
    bday = Birthday.query.get_or_404(id)
    bday.deleted_at = None
    db.session.commit()
    flash(f"✅ {bday.name}'s birthday restored!", "success")
    return redirect(url_for("trash"))


@app.route("/delete-permanent/<int:id>", methods=["POST"])
@auth_required
def delete_permanent(id):
    from models import Birthday
    bday = Birthday.query.get_or_404(id)
    name = bday.name
    db.session.delete(bday)
    db.session.commit()
    flash(f"🗑️ {name} permanently deleted.", "info")
    return redirect(url_for("trash"))


# ── Send ──────────────────────────────────────────────────────────────────────

@app.route("/send/<int:id>", methods=["POST"])
@auth_required
def send_now(id):
    from models import SentLog
    from email_sender import send_birthday_emails
    from notifications import send_birthday_sms, send_discord_notification, send_slack_notification, send_web_push_to_all

    bday = _active().filter_by(id=id).first_or_404()
    result = send_birthday_emails(bday)

    if result["success"]:
        log = SentLog(birthday_id=bday.id, recipient_email=bday.email, status="success", log_type="birthday")
        bday.last_sent = date.today()
        bday.streak = (bday.streak or 0) + 1
        db.session.add(log)
        db.session.commit()

        if bday.sms_enabled and bday.phone:
            send_birthday_sms(bday)

        send_discord_notification(bday, "birthday")
        send_slack_notification(bday, "birthday")
        send_web_push_to_all(
            title=f"🎂 {bday.name}'s Birthday!",
            body=f"Message sent to {bday.name} (turning {bday.age_turning}).",
        )
        flash(f"🚀 Birthday message sent to {bday.name}! Check your inbox for the owner notification.", "success")
    else:
        log = SentLog(birthday_id=bday.id, recipient_email=bday.email,
                      status="failed", log_type="birthday", notes=result.get("error", ""))
        db.session.add(log)
        db.session.commit()
        flash(f"❌ Failed: {result.get('error', 'Unknown error')}", "error")

    return redirect(url_for("index"))


# ── Person history ─────────────────────────────────────────────────────────────

@app.route("/person/<int:id>")
@auth_required
def person_history(id):
    from models import SentLog
    bday = _active().filter_by(id=id).first_or_404()
    logs = SentLog.query.filter_by(birthday_id=id).order_by(SentLog.sent_at.desc()).all()
    return render_template("person_history.html", birthday=bday, logs=logs)


# ── Preview card ──────────────────────────────────────────────────────────────

@app.route("/preview-card")
def preview_card():
    from gift_card_generator import generate_gift_card
    name = request.args.get("name", "Friend")
    theme = request.args.get("theme", "sunset")
    layout = request.args.get("layout", "banner")
    card_bytes = generate_gift_card(name=name, message="Wishing you a magical birthday!", age=25, theme_name=theme, layout=layout)
    return send_file(io.BytesIO(card_bytes), mimetype="image/jpeg")


# ── AI endpoints ──────────────────────────────────────────────────────────────

@app.route("/ai-message")
@auth_required
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


@app.route("/ai-theme")
@auth_required
def ai_theme():
    from email_sender import suggest_ai_theme
    name = request.args.get("name", "Friend")
    relationship = request.args.get("relationship", "Friend")
    notes = request.args.get("notes", "")
    if not Config.OPENAI_API_KEY:
        return jsonify({"theme": "sunset"})
    theme = suggest_ai_theme(name, relationship, notes)
    return jsonify({"theme": theme})


@app.route("/ai-gifts")
@auth_required
def ai_gifts():
    from email_sender import generate_ai_gift_suggestions
    name = request.args.get("name", "Friend")
    relationship = request.args.get("relationship", "Friend")
    age = int(request.args.get("age", 25))
    notes = request.args.get("notes", "")
    if not Config.OPENAI_API_KEY:
        return jsonify({"error": "OpenAI API key not configured."}), 400
    suggestions = generate_ai_gift_suggestions(name, relationship, age, notes)
    return jsonify({"suggestions": suggestions})


# ── CSV Import / Export ───────────────────────────────────────────────────────

@app.route("/import", methods=["GET", "POST"])
@auth_required
def import_csv():
    from models import Birthday
    if request.method == "POST":
        f = request.files.get("csv_file")
        if not f or not f.filename.endswith(".csv"):
            flash("Please upload a valid .csv file.", "error")
            return redirect(url_for("import_csv"))
        stream = io.StringIO(f.stream.read().decode("utf-8-sig"))
        reader = csv.DictReader(stream)
        added, skipped, errors = 0, 0, []
        for i, row in enumerate(reader, 2):
            name = (row.get("name") or row.get("Name") or "").strip()
            email = (row.get("email") or row.get("Email") or "").strip()
            raw_date = (row.get("birth_date") or row.get("birthday") or row.get("Birthday") or "").strip()
            relationship = (row.get("relationship") or "Friend").strip()
            card_theme = (row.get("card_theme") or "sunset").strip()
            notes = (row.get("notes") or "").strip()
            if not name or not email or not raw_date:
                errors.append(f"Row {i}: missing fields"); skipped += 1; continue
            birth_date = _parse_date(raw_date)
            if not birth_date:
                errors.append(f"Row {i}: invalid date '{raw_date}'"); skipped += 1; continue
            db.session.add(Birthday(name=name, email=email, birth_date=birth_date,
                                    relationship=relationship, card_theme=card_theme, notes=notes))
            added += 1
        db.session.commit()
        if added: flash(f"✅ Imported {added} birthday{'s' if added!=1 else ''}!", "success")
        if skipped: flash(f"⚠️ Skipped {skipped}: {'; '.join(errors[:3])}", "error")
        return redirect(url_for("index"))
    return render_template("import.html")


@app.route("/export-csv")
@auth_required
def export_csv():
    all_bdays = _active().all()
    def generate():
        yield "name,email,birth_date,relationship,card_theme,card_layout,notes,timezone\n"
        for b in all_bdays:
            yield f'"{b.name}","{b.email}","{b.birth_date}","{b.relationship}","{b.card_theme}","{b.card_layout}","{b.notes}","{b.timezone}"\n'
    return Response(generate(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=birthdays.csv"})


# ── Calendar & Stats ──────────────────────────────────────────────────────────

@app.route("/calendar")
@auth_required
def calendar_view():
    all_bdays = _active().all()
    by_month = defaultdict(list)
    for b in all_bdays:
        by_month[b.birth_date.month].append(b)
    months = [{"num": m, "name": date(2000, m, 1).strftime("%B"),
               "birthdays": sorted(by_month.get(m, []), key=lambda b: b.birth_date.day)}
              for m in range(1, 13)]
    return render_template("calendar.html", months=months, today=date.today())


@app.route("/stats")
@auth_required
def stats_view():
    from models import SentLog
    all_bdays = _active().all()
    all_logs = SentLog.query.all()
    by_rel, by_month, sent_by_month, themes_used = (defaultdict(int),) * 4
    by_rel = defaultdict(int); by_month = defaultdict(int); sent_by_month = defaultdict(int); themes_used = defaultdict(int)
    for b in all_bdays:
        by_rel[b.relationship] += 1
        by_month[b.birth_date.month] += 1
        themes_used[b.card_theme] += 1
    for log in all_logs:
        if log.log_type == "birthday" and log.status == "success":
            sent_by_month[log.sent_at.month] += 1
    success_count = sum(1 for l in all_logs if l.status == "success" and l.log_type == "birthday")
    failed_count = sum(1 for l in all_logs if l.status == "failed")
    reminder_count = sum(1 for l in all_logs if l.log_type == "reminder")
    chart_data = {
        "by_relationship": dict(by_rel),
        "by_month": [by_month.get(m, 0) for m in range(1, 13)],
        "sent_by_month": [sent_by_month.get(m, 0) for m in range(1, 13)],
        "month_names": [date(2000, m, 1).strftime("%b") for m in range(1, 13)],
        "themes": dict(themes_used),
    }
    return render_template("stats.html",
        all_bdays=all_bdays, chart_data=json.dumps(chart_data),
        success_count=success_count, failed_count=failed_count,
        reminder_count=reminder_count,
        top_streak=sorted(all_bdays, key=lambda b: b.streak, reverse=True)[:5],
        upcoming=[b for b in sorted(all_bdays, key=lambda b: b.days_until) if b.days_until <= 30],
    )


# ── Push notifications ────────────────────────────────────────────────────────

@app.route("/push/subscribe", methods=["POST"])
@auth_required
def push_subscribe():
    from models import PushSubscription
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400
    endpoint = data.get("endpoint")
    p256dh = data.get("keys", {}).get("p256dh")
    auth_key = data.get("keys", {}).get("auth")
    if not all([endpoint, p256dh, auth_key]):
        return jsonify({"error": "Missing fields"}), 400

    existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if not existing:
        sub = PushSubscription(endpoint=endpoint, p256dh=p256dh, auth=auth_key)
        db.session.add(sub)
        db.session.commit()
    return jsonify({"success": True})


@app.route("/push/unsubscribe", methods=["POST"])
@auth_required
def push_unsubscribe():
    from models import PushSubscription
    data = request.get_json()
    endpoint = data.get("endpoint") if data else None
    if endpoint:
        sub = PushSubscription.query.filter_by(endpoint=endpoint).first()
        if sub:
            db.session.delete(sub)
            db.session.commit()
    return jsonify({"success": True})


@app.route("/push/public-key")
def push_public_key():
    return jsonify({"public_key": Config.VAPID_PUBLIC_KEY or ""})


# ── Webhook trigger (outbound) ────────────────────────────────────────────────

@app.route("/webhook/trigger/<int:id>", methods=["POST"])
@auth_required
def webhook_trigger(id):
    """Manually trigger Discord + Slack notifications for a birthday."""
    from notifications import send_discord_notification, send_slack_notification
    bday = _active().filter_by(id=id).first_or_404()
    results = {
        "discord": send_discord_notification(bday, "birthday"),
        "slack": send_slack_notification(bday, "birthday"),
    }
    return jsonify(results)


# ── Settings ──────────────────────────────────────────────────────────────────

@app.route("/settings")
@auth_required
def settings():
    from models import SentLog, Birthday, PushSubscription
    from scheduler import scheduler
    logs_raw = (
        db.session.query(SentLog, Birthday.name)
        .join(Birthday, SentLog.birthday_id == Birthday.id)
        .order_by(SentLog.sent_at.desc()).limit(20).all()
    )
    push_count = PushSubscription.query.count()
    return render_template(
        "settings.html",
        config=Config, logs=[(l, n) for l, n in logs_raw],
        scheduler_running=scheduler.running,
        push_count=push_count,
    )


@app.route("/gift-cards")
@auth_required
def gift_cards():
    from models import GiftCardSend, Birthday
    sends = (
        db.session.query(GiftCardSend, Birthday.name)
        .join(Birthday, GiftCardSend.birthday_id == Birthday.id)
        .order_by(GiftCardSend.sent_at.desc())
        .limit(100).all()
    )
    from gift_card_service import BRANDS
    total_value = sum(s.amount for s, _ in sends if s.status == "sent")
    return render_template("gift_cards.html", sends=sends, brands=BRANDS, total_value=total_value)


@app.route("/settings/test-email", methods=["POST"])
@auth_required
def test_email():
    from email_sender import send_birthday_emails
    class FakeBirthday:
        name = request.form.get("test_name", "Test Person")
        email = Config.SENDER_EMAIL
        relationship = "Friend"
        custom_message = ""
        card_theme = request.form.get("test_theme", "sunset")
        card_layout = request.form.get("test_layout", "banner")
        age_turning = 30
        streak = 3
        notes = "loves reading and coffee"
        use_ai_message = False
        last_sent = None
        past_messages = []
        def used_message_hashes(self): return set()
    result = send_birthday_emails(FakeBirthday())
    if result["success"]:
        flash("✅ Test email sent! Check your inbox.", "success")
    else:
        flash(f"❌ Test failed: {result.get('error')}", "error")
    return redirect(url_for("settings"))


@app.route("/settings/send-digest", methods=["POST"])
@auth_required
def send_digest_now():
    from email_sender import send_digest_email
    today = date.today()
    bdays = [b for b in _active().all() if b.birth_date.month == today.month]
    bdays.sort(key=lambda b: b.birth_date.day)
    result = send_digest_email(today.month, bdays)
    if result["success"]:
        flash(f"📅 Digest sent for {today.strftime('%B')} ({len(bdays)} birthdays)!", "success")
    else:
        flash(f"❌ Digest failed: {result.get('error')}", "error")
    return redirect(url_for("settings"))


@app.route("/settings/setup-login", methods=["POST"])
def setup_login():
    if not Config.LOGIN_REQUIRED:
        flash("Enable LOGIN_REQUIRED=true in .env to activate login protection.", "info")
        return redirect(url_for("settings"))
    password = request.form.get("password", "")
    if len(password) < 6:
        flash("Password must be at least 6 characters.", "error")
        return redirect(url_for("settings"))
    create_admin(db, password)
    flash("✅ Admin password set! Add LOGIN_REQUIRED=true to .env to activate.", "success")
    return redirect(url_for("settings"))


if __name__ == "__main__":
    app.run(debug=True, port=5050, use_reloader=False)
