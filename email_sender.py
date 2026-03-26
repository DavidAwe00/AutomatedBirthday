import smtplib
import textwrap
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import date

from config import Config
from gift_card_generator import generate_gift_card


MESSAGES = {
    "Friend": [
        "Today the world got a little brighter because it's YOUR birthday! Wishing you a day overflowing with joy, laughter, and everything that makes you smile.",
        "Another trip around the sun — and you've made every single one of them more fun. Happy Birthday to an incredible friend!",
        "May this birthday mark the beginning of a spectacular new chapter filled with adventure, happiness, and endless good vibes. You deserve it all!",
    ],
    "Family": [
        "Family is the greatest gift of all — and you are proof of that every single day. Wishing you a birthday as warm and beautiful as the love you give.",
        "Growing up with you has been one of the greatest privileges of my life. Happy Birthday! May this year bring you immeasurable joy.",
        "No distance can diminish the love we share. On your special day, know that you are deeply cherished and celebrated from near and far.",
    ],
    "Colleague": [
        "Working alongside someone as talented and kind as you is a true privilege. Happy Birthday! May this year bring you incredible success and well-deserved happiness.",
        "Wishing you a birthday as outstanding as your contributions. Thank you for the inspiration you bring every single day — here's to you!",
        "May your birthday be the perfect pause from the hustle — a day dedicated entirely to YOU. You've earned every moment of celebration!",
    ],
    "Partner": [
        "Every day with you is a gift, but today is the day the world celebrates the most amazing person in my universe. Happy Birthday, my love!",
        "You make ordinary days feel magical. On your birthday, I hope you feel every ounce of the love and admiration I have for you.",
        "Here's to the person who makes me laugh, keeps me grounded, and fills every room with warmth. Happy Birthday — you are everything.",
    ],
    "default": [
        "Wishing you a birthday filled with all the things that bring you the most joy. Today is your day — celebrate it fully!",
        "May this special day remind you of just how loved and appreciated you truly are. Happy Birthday!",
        "Another year of amazing moments, growth, and memories — and the best is still yet to come. Happy Birthday!",
    ],
}


def generate_ai_message(name: str, relationship: str, age: int, notes: str = "") -> str:
    api_key = Config.OPENAI_API_KEY
    if not api_key:
        return ""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        context = f"Notes about them: {notes}" if notes else ""
        prompt = (
            f"Write a warm, heartfelt, and personal birthday message for {name}, "
            f"who is my {relationship.lower()} and is turning {age}. "
            f"{context} "
            f"Keep it to 2–3 sentences. Do not include a greeting like 'Dear' or a sign-off. "
            f"Be genuinely warm, avoid clichés, and make it feel personal."
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.85,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return ""


def _pick_message(person_name: str, relationship: str, custom_message: str, age: int,
                  sender_name: str, use_ai: bool = False, notes: str = "") -> str:
    if custom_message and custom_message.strip():
        body = custom_message.strip()
    elif use_ai:
        ai_msg = generate_ai_message(person_name, relationship, age, notes)
        body = ai_msg if ai_msg else _fallback_message(person_name, relationship)
    else:
        body = _fallback_message(person_name, relationship)

    signature = Config.SIGNATURE or "Warm wishes"
    return f"{body}\n\n{signature},\n{sender_name}"


def _fallback_message(person_name: str, relationship: str) -> str:
    import hashlib
    pool = MESSAGES.get(relationship, MESSAGES["default"])
    idx = int(hashlib.md5(f"{person_name}{date.today().year}".encode()).hexdigest(), 16) % len(pool)
    return pool[idx]


def _smtp_connection():
    host, port = Config.smtp_settings()
    server = smtplib.SMTP(host, port)
    server.ehlo()
    server.starttls()
    server.login(Config.SENDER_EMAIL, Config.SENDER_APP_PASSWORD)
    return server


# ── HTML builders ─────────────────────────────────────────────────────────────

THEME_COLORS = {
    "sunset":   ("#FF5E3A", "#FFB347"),
    "ocean":    ("#0A4BA3", "#00C3C8"),
    "forest":   ("#14703C", "#64C850"),
    "rose":     ("#B41E5A", "#FF78A0"),
    "midnight": ("#0F0F32", "#462882"),
    "gold":     ("#643C00", "#DCAA1E"),
}


def _build_celebrant_html(name: str, message: str, age: int, theme: str) -> str:
    c1, c2 = THEME_COLORS.get(theme, ("#FF5E3A", "#FFB347"))
    paragraphs = "".join(f"<p style='margin:8px 0;line-height:1.7;'>{p}</p>" for p in message.split("\n\n"))
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f4f8;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f8;padding:30px 10px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;border-radius:20px;overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,0.15);">
        <tr>
          <td style="background:linear-gradient(135deg,{c1},{c2});padding:40px 30px;text-align:center;">
            <p style="margin:0;font-size:40px;letter-spacing:4px;">🎂 🎉 🎈</p>
            <h1 style="margin:12px 0 4px;color:#fff;font-size:38px;font-weight:800;text-shadow:0 2px 8px rgba(0,0,0,0.2);">Happy Birthday!</h1>
            <h2 style="margin:0;color:rgba(255,255,255,0.9);font-size:22px;font-weight:400;">Dear {name} 🌟</h2>
          </td>
        </tr>
        <tr><td style="background:#fff;padding:0;"><img src="cid:giftcard" alt="Birthday Gift Card" width="600" style="width:100%;display:block;"/></td></tr>
        <tr>
          <td style="background:#fff;padding:30px 40px;">
            <div style="font-size:16px;color:#333;line-height:1.7;">{paragraphs}</div>
            <div style="margin-top:24px;padding:16px 20px;background:linear-gradient(135deg,{c1}18,{c2}18);border-left:4px solid {c1};border-radius:8px;">
              <p style="margin:0;font-size:14px;color:#555;">🎁 Your special day is here — make it absolutely unforgettable!</p>
            </div>
          </td>
        </tr>
        <tr>
          <td style="background:linear-gradient(135deg,{c1},{c2});padding:20px 30px;text-align:center;">
            <p style="margin:0;color:rgba(255,255,255,0.85);font-size:13px;">Sent with ❤️ via Birthday Bot &nbsp;•&nbsp; {date.today().strftime('%B %d, %Y')}</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def _build_reminder_html(name: str, days_before: int, birthday_date, age: int, theme: str) -> str:
    c1, c2 = THEME_COLORS.get(theme, ("#FF5E3A", "#FFB347"))
    date_str = birthday_date.strftime("%A, %B %d")
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f8;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f8;padding:30px 10px;">
    <tr><td align="center">
      <table width="580" cellpadding="0" cellspacing="0" style="max-width:580px;width:100%;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.12);">
        <tr>
          <td style="background:linear-gradient(135deg,#f59e0b,#ef4444);padding:28px 30px;text-align:center;">
            <p style="margin:0;font-size:32px;">⏰</p>
            <h2 style="margin:8px 0 4px;color:#fff;font-size:22px;font-weight:800;">Birthday Reminder!</h2>
            <p style="margin:0;color:rgba(255,255,255,0.9);font-size:15px;">{name}'s birthday is in {days_before} day{'s' if days_before != 1 else ''}</p>
          </td>
        </tr>
        <tr>
          <td style="background:#fff;padding:28px 36px;">
            <table width="100%" cellpadding="8" cellspacing="0" style="border-collapse:collapse;font-size:14px;">
              <tr style="background:#f8f9ff;">
                <td style="padding:10px 14px;color:#666;font-weight:600;">🎂 Name</td>
                <td style="padding:10px 14px;color:#222;font-weight:700;">{name}</td>
              </tr>
              <tr>
                <td style="padding:10px 14px;color:#666;font-weight:600;">📅 Birthday</td>
                <td style="padding:10px 14px;color:#222;">{date_str}</td>
              </tr>
              <tr style="background:#f8f9ff;">
                <td style="padding:10px 14px;color:#666;font-weight:600;">🎁 Turning</td>
                <td style="padding:10px 14px;color:#222;">{age} years old</td>
              </tr>
              <tr>
                <td style="padding:10px 14px;color:#666;font-weight:600;">⏳ In</td>
                <td style="padding:10px 14px;color:#222;font-weight:700;color:#ef4444;">{days_before} day{'s' if days_before != 1 else ''}</td>
              </tr>
            </table>
            <div style="margin-top:20px;padding:14px 18px;background:linear-gradient(135deg,{c1}18,{c2}18);border-left:4px solid {c1};border-radius:8px;">
              <p style="margin:0;font-size:13px;color:#555;">💡 Now's a great time to write a personal message or double-check their details.</p>
            </div>
          </td>
        </tr>
        <tr>
          <td style="background:#1a1a2e;padding:16px 30px;text-align:center;">
            <p style="margin:0;color:rgba(255,255,255,0.6);font-size:12px;">Birthday Bot Reminder &nbsp;•&nbsp; {date.today().strftime('%B %d, %Y')}</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def _build_owner_html(name: str, email: str, age: int, relationship: str, theme: str, streak: int = 0) -> str:
    streak_html = f'<tr style="background:#f8f9ff;"><td style="padding:10px 14px;color:#666;font-weight:600;">🔥 Streak</td><td style="padding:10px 14px;color:#222;">{streak} year{"s" if streak != 1 else ""} in a row</td></tr>' if streak > 0 else ""
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f8;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f8;padding:30px 10px;">
    <tr><td align="center">
      <table width="580" cellpadding="0" cellspacing="0" style="max-width:580px;width:100%;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.12);">
        <tr>
          <td style="background:linear-gradient(135deg,#1a1a2e,#16213e);padding:28px 30px;text-align:center;">
            <p style="margin:0;font-size:28px;">🔔</p>
            <h2 style="margin:8px 0 0;color:#fff;font-size:20px;font-weight:700;">Birthday Alert Sent!</h2>
          </td>
        </tr>
        <tr>
          <td style="background:#fff;padding:28px 36px;">
            <p style="margin:0 0 16px;font-size:15px;color:#444;line-height:1.6;">Your automated birthday message has been dispatched!</p>
            <table width="100%" cellpadding="8" cellspacing="0" style="border-collapse:collapse;font-size:14px;">
              <tr style="background:#f8f9ff;"><td style="padding:10px 14px;color:#666;font-weight:600;">🎂 Name</td><td style="padding:10px 14px;color:#222;font-weight:700;">{name}</td></tr>
              <tr><td style="padding:10px 14px;color:#666;font-weight:600;">📧 Email</td><td style="padding:10px 14px;color:#222;">{email}</td></tr>
              <tr style="background:#f8f9ff;"><td style="padding:10px 14px;color:#666;font-weight:600;">🎁 Turning</td><td style="padding:10px 14px;color:#222;">{age} years old</td></tr>
              <tr><td style="padding:10px 14px;color:#666;font-weight:600;">💝 Relationship</td><td style="padding:10px 14px;color:#222;">{relationship}</td></tr>
              {streak_html}
              <tr><td style="padding:10px 14px;color:#666;font-weight:600;">📅 Sent</td><td style="padding:10px 14px;color:#222;">{date.today().strftime('%A, %B %d, %Y')}</td></tr>
            </table>
            <div style="margin-top:20px;padding:14px 18px;background:#f0fdf4;border-left:4px solid #22c55e;border-radius:8px;">
              <p style="margin:0;font-size:13px;color:#16a34a;font-weight:600;">✅ Message delivered — your thoughtfulness is on its way!</p>
            </div>
            <img src="cid:giftcard" alt="Gift Card Preview" width="508" style="width:100%;display:block;margin-top:20px;border-radius:10px;border:1px solid #eee;"/>
          </td>
        </tr>
        <tr>
          <td style="background:#1a1a2e;padding:16px 30px;text-align:center;">
            <p style="margin:0;color:rgba(255,255,255,0.6);font-size:12px;">Birthday Bot &nbsp;•&nbsp; {date.today().strftime('%B %d, %Y')}</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


# ── Public functions ──────────────────────────────────────────────────────────

def send_birthday_emails(birthday) -> dict:
    cfg = Config
    if not cfg.SENDER_EMAIL or not cfg.SENDER_APP_PASSWORD:
        return {"success": False, "error": "Email credentials not configured. Please set SENDER_EMAIL and SENDER_APP_PASSWORD in your .env file."}

    message_text = _pick_message(
        birthday.name, birthday.relationship, birthday.custom_message,
        birthday.age_turning, cfg.SENDER_NAME,
        use_ai=getattr(birthday, "use_ai_message", False),
        notes=getattr(birthday, "notes", ""),
    )

    card_bytes = generate_gift_card(
        name=birthday.name,
        message=message_text.split("\n\n")[0],
        age=birthday.age_turning,
        theme_name=birthday.card_theme,
    )

    errors = []

    # Email to celebrant
    try:
        msg = MIMEMultipart("related")
        msg["Subject"] = f"🎂 Happy Birthday, {birthday.name}! 🎉"
        msg["From"] = f"{cfg.SENDER_NAME} <{cfg.SENDER_EMAIL}>"
        msg["To"] = birthday.email
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(f"Happy Birthday, {birthday.name}!\n\n{message_text}", "plain"))
        alt.attach(MIMEText(_build_celebrant_html(birthday.name, message_text, birthday.age_turning, birthday.card_theme), "html"))
        msg.attach(alt)
        img = MIMEImage(card_bytes, "jpeg")
        img.add_header("Content-ID", "<giftcard>")
        img.add_header("Content-Disposition", "inline", filename="birthday_card.jpg")
        msg.attach(img)
        with _smtp_connection() as server:
            server.sendmail(cfg.SENDER_EMAIL, birthday.email, msg.as_string())
    except Exception as e:
        errors.append(f"Celebrant email failed: {e}")

    # Notification to owner
    try:
        msg2 = MIMEMultipart("related")
        msg2["Subject"] = f"🔔 Birthday Alert: {birthday.name}'s birthday today!"
        msg2["From"] = f"Birthday Bot <{cfg.SENDER_EMAIL}>"
        msg2["To"] = cfg.SENDER_EMAIL
        alt2 = MIMEMultipart("alternative")
        alt2.attach(MIMEText(f"Birthday alert!\nSent to {birthday.name} ({birthday.email}). Turning {birthday.age_turning}.", "plain"))
        streak = getattr(birthday, "streak", 0)
        alt2.attach(MIMEText(_build_owner_html(birthday.name, birthday.email, birthday.age_turning, birthday.relationship, birthday.card_theme, streak), "html"))
        msg2.attach(alt2)
        img2 = MIMEImage(card_bytes, "jpeg")
        img2.add_header("Content-ID", "<giftcard>")
        img2.add_header("Content-Disposition", "inline", filename="birthday_card_preview.jpg")
        msg2.attach(img2)
        with _smtp_connection() as server:
            server.sendmail(cfg.SENDER_EMAIL, cfg.SENDER_EMAIL, msg2.as_string())
    except Exception as e:
        errors.append(f"Owner notification failed: {e}")

    if errors:
        return {"success": False, "error": "; ".join(errors)}
    return {"success": True}


def send_reminder_email(birthday, days_before: int) -> dict:
    cfg = Config
    if not cfg.SENDER_EMAIL or not cfg.SENDER_APP_PASSWORD:
        return {"success": False, "error": "Email credentials not configured."}
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"⏰ Reminder: {birthday.name}'s birthday in {days_before} day{'s' if days_before != 1 else ''}!"
        msg["From"] = f"Birthday Bot <{cfg.SENDER_EMAIL}>"
        msg["To"] = cfg.SENDER_EMAIL
        plain = f"Reminder: {birthday.name}'s birthday is in {days_before} days ({birthday.next_birthday.strftime('%B %d')})."
        msg.attach(MIMEText(plain, "plain"))
        msg.attach(MIMEText(_build_reminder_html(birthday.name, days_before, birthday.next_birthday, birthday.age_turning, birthday.card_theme), "html"))
        with _smtp_connection() as server:
            server.sendmail(cfg.SENDER_EMAIL, cfg.SENDER_EMAIL, msg.as_string())
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
