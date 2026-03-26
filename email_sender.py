import io
import smtplib
import textwrap
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.audio import MIMEAudio
from datetime import date
from collections import defaultdict

from config import Config
from gift_card_generator import generate_gift_card


MESSAGES = {
    "Friend": [
        "Today the world got a little brighter because it's YOUR birthday! Wishing you a day overflowing with joy, laughter, and everything that makes you smile.",
        "Another trip around the sun — and you've made every single one of them more fun. Happy Birthday to an incredible friend!",
        "May this birthday mark the beginning of a spectacular new chapter filled with adventure, happiness, and endless good vibes. You deserve it all!",
        "There are people who light up every room they walk into — and you are absolutely one of them. Wishing you a birthday as radiant as you are.",
    ],
    "Family": [
        "Family is the greatest gift of all — and you are proof of that every single day. Wishing you a birthday as warm and beautiful as the love you give.",
        "Growing up with you has been one of the greatest privileges of my life. Happy Birthday! May this year bring you immeasurable joy.",
        "No distance can diminish the love we share. On your special day, know that you are deeply cherished and celebrated from near and far.",
        "The older we get, the more I treasure every moment with you. Happy Birthday — here's to many more years of laughter and memories together.",
    ],
    "Colleague": [
        "Working alongside someone as talented and kind as you is a true privilege. Happy Birthday! May this year bring you incredible success and well-deserved happiness.",
        "Wishing you a birthday as outstanding as your contributions. Thank you for the inspiration you bring every single day — here's to you!",
        "May your birthday be the perfect pause from the hustle — a day dedicated entirely to YOU. You've earned every moment of celebration!",
        "The office (or wherever we work!) is a genuinely better place because of you. Happy Birthday — here's to your health, happiness, and continued brilliance.",
    ],
    "Partner": [
        "Every day with you is a gift, but today is the day the world celebrates the most amazing person in my universe. Happy Birthday, my love!",
        "You make ordinary days feel magical. On your birthday, I hope you feel every ounce of the love and admiration I have for you.",
        "Here's to the person who makes me laugh, keeps me grounded, and fills every room with warmth. Happy Birthday — you are everything.",
        "Loving you is the easiest thing I've ever done. Today, I hope you feel as cherished and special as you make me feel every single day.",
    ],
    "default": [
        "Wishing you a birthday filled with all the things that bring you the most joy. Today is your day — celebrate it fully!",
        "May this special day remind you of just how loved and appreciated you truly are. Happy Birthday!",
        "Another year of amazing moments, growth, and memories — and the best is still yet to come. Happy Birthday!",
        "You only get one birthday a year, so make it extraordinary. Wishing you a day that matches exactly who you are — wonderful!",
    ],
}

THEME_COLORS = {
    "sunset":   ("#FF5E3A", "#FFB347"),
    "ocean":    ("#0A4BA3", "#00C3C8"),
    "forest":   ("#14703C", "#64C850"),
    "rose":     ("#B41E5A", "#FF78A0"),
    "midnight": ("#0F0F32", "#462882"),
    "gold":     ("#643C00", "#DCAA1E"),
}


# ── Message selection ─────────────────────────────────────────────────────────

def generate_ai_message(name: str, relationship: str, age: int, notes: str = "") -> str:
    if not Config.OPENAI_API_KEY:
        return ""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=Config.OPENAI_API_KEY)
        context = f"Notes: {notes}" if notes else ""
        prompt = (
            f"Write a warm, heartfelt, personal birthday message for {name}, "
            f"my {relationship.lower()}, turning {age}. {context} "
            f"2-3 sentences, no greeting/sign-off, avoid clichés, feel genuine."
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150, temperature=0.85,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return ""


def generate_ai_gift_suggestions(name: str, relationship: str, age: int, notes: str = "") -> str:
    if not Config.OPENAI_API_KEY:
        return ""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=Config.OPENAI_API_KEY)
        context = f"Interests/notes: {notes}" if notes else ""
        prompt = (
            f"Suggest 4 thoughtful, specific gift ideas for {name}, "
            f"a {relationship.lower()} turning {age}. {context} "
            f"Format: numbered list, one line each, be creative and personal."
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200, temperature=0.8,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return ""


def suggest_ai_theme(name: str, relationship: str, notes: str = "") -> str:
    if not Config.OPENAI_API_KEY:
        return "sunset"
    try:
        from openai import OpenAI
        client = OpenAI(api_key=Config.OPENAI_API_KEY)
        prompt = (
            f"Pick the best birthday card theme for {name}, my {relationship.lower()}. "
            f"Notes: {notes or 'none'}. "
            f"Choose ONLY one word from: sunset, ocean, forest, rose, midnight, gold. "
            f"Reply with just the single theme word."
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=5, temperature=0.3,
        )
        theme = resp.choices[0].message.content.strip().lower()
        return theme if theme in THEME_COLORS else "sunset"
    except Exception:
        return "sunset"


def _pick_message(person_name, relationship, custom_message, age,
                  sender_name, use_ai=False, notes="", birthday_obj=None):
    if custom_message and custom_message.strip():
        body = custom_message.strip()
    elif use_ai:
        ai_msg = generate_ai_message(person_name, relationship, age, notes)
        body = ai_msg if ai_msg else _fallback_message(person_name, relationship, birthday_obj)
    else:
        body = _fallback_message(person_name, relationship, birthday_obj)

    # Record used message to avoid repeats
    if birthday_obj:
        _record_message(birthday_obj, body)

    signature = Config.SIGNATURE or "Warm wishes"
    return f"{body}\n\n{signature},\n{sender_name}"


def _fallback_message(person_name, relationship, birthday_obj=None):
    import hashlib
    pool = MESSAGES.get(relationship, MESSAGES["default"])
    used_hashes = birthday_obj.used_message_hashes() if birthday_obj else set()

    # Try to pick an unused message
    for offset in range(len(pool)):
        idx = (int(hashlib.md5(f"{person_name}{date.today().year + offset}".encode()).hexdigest(), 16)) % len(pool)
        import hashlib as _h
        h = _h.md5(pool[idx].encode()).hexdigest()
        if h not in used_hashes:
            return pool[idx]
    # All used — just rotate by year
    idx = int(hashlib.md5(f"{person_name}{date.today().year}".encode()).hexdigest(), 16) % len(pool)
    return pool[idx]


def _record_message(birthday_obj, body: str):
    """Store message hash so it's not repeated in future years."""
    try:
        import hashlib
        from models import PastMessage
        from extensions import db
        h = hashlib.md5(body.encode()).hexdigest()
        if h not in birthday_obj.used_message_hashes():
            pm = PastMessage(birthday_id=birthday_obj.id, year=date.today().year,
                             message_hash=h, message_text=body[:500])
            db.session.add(pm)
            db.session.commit()
    except Exception:
        pass


# ── TTS Voice Greeting ────────────────────────────────────────────────────────

def generate_tts_audio(name: str, message: str) -> bytes | None:
    if not Config.OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=Config.OPENAI_API_KEY)
        text = f"Happy Birthday, {name}! {message.split(chr(10))[0]}"
        resp = client.audio.speech.create(model="tts-1", voice="nova", input=text)
        return resp.content
    except Exception:
        return None


# ── SMTP connection ───────────────────────────────────────────────────────────

def _smtp_connection():
    host, port = Config.smtp_settings()
    server = smtplib.SMTP(host, port)
    server.ehlo()
    server.starttls()
    server.login(Config.SENDER_EMAIL, Config.SENDER_APP_PASSWORD)
    return server


# ── HTML builders ─────────────────────────────────────────────────────────────

def _build_celebrant_html(name, message, age, theme, gift_card_html=""):
    c1, c2 = THEME_COLORS.get(theme, ("#FF5E3A", "#FFB347"))
    paragraphs = "".join(f"<p style='margin:8px 0;line-height:1.7;'>{p}</p>"
                         for p in message.split("\n\n"))
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f4f8;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f8;padding:30px 10px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;border-radius:20px;overflow:hidden;box-shadow:0 8px 40px rgba(0,0,0,0.15);">
        <tr><td style="background:linear-gradient(135deg,{c1},{c2});padding:40px 30px;text-align:center;">
          <p style="margin:0;font-size:40px;">🎂 🎉 🎈</p>
          <h1 style="margin:12px 0 4px;color:#fff;font-size:36px;font-weight:800;text-shadow:0 2px 8px rgba(0,0,0,0.2);">Happy Birthday!</h1>
          <h2 style="margin:0;color:rgba(255,255,255,0.9);font-size:22px;font-weight:400;">Dear {name} 🌟</h2>
        </td></tr>
        <tr><td style="background:#fff;padding:0;"><img src="cid:giftcard" alt="Birthday Gift Card" width="600" style="width:100%;display:block;"/></td></tr>
        <tr><td style="background:#fff;padding:30px 40px;">
          <div style="font-size:16px;color:#333;line-height:1.7;">{paragraphs}</div>
          <div style="margin-top:24px;padding:16px 20px;background:linear-gradient(135deg,{c1}18,{c2}18);border-left:4px solid {c1};border-radius:8px;">
            <p style="margin:0;font-size:14px;color:#555;">✨ Your special day is here — make it absolutely unforgettable!</p>
          </div>
          {gift_card_html}
        </td></tr>
        <tr><td style="background:linear-gradient(135deg,{c1},{c2});padding:20px 30px;text-align:center;">
          <p style="margin:0;color:rgba(255,255,255,0.85);font-size:13px;">Sent with ❤️ via Birthday Bot &nbsp;•&nbsp; {date.today().strftime('%B %d, %Y')}</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def _build_owner_html(name, email, age, relationship, theme, streak=0, gift_suggestions=""):
    c1, c2 = THEME_COLORS.get(theme, ("#FF5E3A", "#FFB347"))
    streak_html = (f'<tr style="background:#f8f9ff;"><td style="padding:10px 14px;color:#666;font-weight:600;">🔥 Streak</td>'
                   f'<td style="padding:10px 14px;color:#222;">{streak} year{"s" if streak != 1 else ""} in a row</td></tr>') if streak > 0 else ""
    gifts_html = ""
    if gift_suggestions:
        lines = "".join(f"<li style='margin:4px 0;'>{ln}</li>" for ln in gift_suggestions.split("\n") if ln.strip())
        gifts_html = f"""
        <div style="margin-top:20px;padding:16px 18px;background:#fffbeb;border-left:4px solid #f59e0b;border-radius:8px;">
          <p style="margin:0 0 8px;font-size:13px;font-weight:700;color:#854d0e;">🎁 AI Gift Suggestions for {name}:</p>
          <ul style="margin:0;padding-left:20px;font-size:13px;color:#555;">{lines}</ul>
        </div>"""

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f8;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f8;padding:30px 10px;">
    <tr><td align="center">
      <table width="580" cellpadding="0" cellspacing="0" style="max-width:580px;width:100%;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.12);">
        <tr><td style="background:linear-gradient(135deg,#1a1a2e,#16213e);padding:28px 30px;text-align:center;">
          <p style="margin:0;font-size:28px;">🔔</p>
          <h2 style="margin:8px 0 0;color:#fff;font-size:20px;font-weight:700;">Birthday Alert Sent!</h2>
        </td></tr>
        <tr><td style="background:#fff;padding:28px 36px;">
          <table width="100%" cellpadding="8" cellspacing="0" style="border-collapse:collapse;font-size:14px;">
            <tr style="background:#f8f9ff;"><td style="padding:10px 14px;color:#666;font-weight:600;">🎂 Name</td><td style="padding:10px 14px;color:#222;font-weight:700;">{name}</td></tr>
            <tr><td style="padding:10px 14px;color:#666;font-weight:600;">📧 Email</td><td style="padding:10px 14px;color:#222;">{email}</td></tr>
            <tr style="background:#f8f9ff;"><td style="padding:10px 14px;color:#666;font-weight:600;">🎁 Turning</td><td style="padding:10px 14px;color:#222;">{age} years old</td></tr>
            <tr><td style="padding:10px 14px;color:#666;font-weight:600;">💝 Relationship</td><td style="padding:10px 14px;color:#222;">{relationship}</td></tr>
            {streak_html}
            <tr><td style="padding:10px 14px;color:#666;font-weight:600;">📅 Sent</td><td style="padding:10px 14px;color:#222;">{date.today().strftime('%A, %B %d, %Y')}</td></tr>
          </table>
          <div style="margin-top:16px;padding:14px 18px;background:#f0fdf4;border-left:4px solid #22c55e;border-radius:8px;">
            <p style="margin:0;font-size:13px;color:#16a34a;font-weight:600;">✅ Message delivered!</p>
          </div>
          {gifts_html}
          <img src="cid:giftcard" alt="Gift Card Preview" width="508" style="width:100%;display:block;margin-top:20px;border-radius:10px;border:1px solid #eee;"/>
        </td></tr>
        <tr><td style="background:#1a1a2e;padding:16px 30px;text-align:center;">
          <p style="margin:0;color:rgba(255,255,255,0.6);font-size:12px;">Birthday Bot &nbsp;•&nbsp; {date.today().strftime('%B %d, %Y')}</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def _build_reminder_html(name, days_before, birthday_date, age, theme):
    c1, c2 = THEME_COLORS.get(theme, ("#FF5E3A", "#FFB347"))
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f8;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f8;padding:30px 10px;">
    <tr><td align="center">
      <table width="580" cellpadding="0" cellspacing="0" style="max-width:580px;width:100%;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.12);">
        <tr><td style="background:linear-gradient(135deg,#f59e0b,#ef4444);padding:28px 30px;text-align:center;">
          <p style="margin:0;font-size:32px;">⏰</p>
          <h2 style="margin:8px 0 4px;color:#fff;font-size:22px;font-weight:800;">Birthday Reminder!</h2>
          <p style="margin:0;color:rgba(255,255,255,0.9);font-size:15px;">{name}'s birthday is in {days_before} day{'s' if days_before!=1 else ''}</p>
        </td></tr>
        <tr><td style="background:#fff;padding:28px 36px;">
          <table width="100%" cellpadding="8" cellspacing="0" style="border-collapse:collapse;font-size:14px;">
            <tr style="background:#f8f9ff;"><td style="padding:10px 14px;color:#666;font-weight:600;">🎂 Name</td><td style="padding:10px 14px;color:#222;font-weight:700;">{name}</td></tr>
            <tr><td style="padding:10px 14px;color:#666;font-weight:600;">📅 Birthday</td><td style="padding:10px 14px;color:#222;">{birthday_date.strftime('%A, %B %d')}</td></tr>
            <tr style="background:#f8f9ff;"><td style="padding:10px 14px;color:#666;font-weight:600;">🎁 Turning</td><td style="padding:10px 14px;color:#222;">{age} years old</td></tr>
            <tr><td style="padding:10px 14px;color:#666;font-weight:600;">⏳ In</td><td style="padding:10px 14px;font-weight:700;color:#ef4444;">{days_before} day{'s' if days_before!=1 else ''}</td></tr>
          </table>
          <div style="margin-top:16px;padding:14px 18px;background:linear-gradient(135deg,{c1}18,{c2}18);border-left:4px solid {c1};border-radius:8px;">
            <p style="margin:0;font-size:13px;color:#555;">💡 Great time to personalise their message!</p>
          </div>
        </td></tr>
        <tr><td style="background:#1a1a2e;padding:16px;text-align:center;">
          <p style="margin:0;color:rgba(255,255,255,0.6);font-size:12px;">Birthday Bot &nbsp;•&nbsp; {date.today().strftime('%B %d, %Y')}</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def _build_digest_html(month_name: str, birthdays: list) -> str:
    rows = ""
    for b in birthdays:
        rows += f"""<tr>
          <td style="padding:10px 12px;font-weight:600;">{b.birth_date.day}</td>
          <td style="padding:10px 12px;">{b.name}</td>
          <td style="padding:10px 12px;color:#666;">{b.relationship}</td>
          <td style="padding:10px 12px;color:#7c3aed;font-weight:600;">Turning {b.age_turning}</td>
          <td style="padding:10px 12px;{'color:#ef4444;font-weight:700;' if b.is_today else 'color:#888;'}">
            {'🎂 Today!' if b.is_today else f'{b.days_until}d away'}
          </td>
        </tr>"""
    empty = f'<tr><td colspan="5" style="padding:24px;text-align:center;color:#888;">No birthdays in {month_name}.</td></tr>' if not birthdays else ""

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f8;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f8;padding:30px 10px;">
    <tr><td align="center">
      <table width="620" cellpadding="0" cellspacing="0" style="max-width:620px;width:100%;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.12);">
        <tr><td style="background:linear-gradient(135deg,#7c3aed,#4f46e5);padding:30px;text-align:center;">
          <p style="margin:0;font-size:32px;">📅</p>
          <h2 style="margin:8px 0 4px;color:#fff;font-size:24px;font-weight:800;">Monthly Birthday Digest</h2>
          <p style="margin:0;color:rgba(255,255,255,0.85);font-size:16px;">{month_name} — {len(birthdays)} birthday{'s' if len(birthdays)!=1 else ''}</p>
        </td></tr>
        <tr><td style="background:#fff;padding:0;">
          <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:14px;">
            <thead><tr style="background:#f8f9ff;">
              <th style="padding:10px 12px;text-align:left;color:#666;font-size:11px;text-transform:uppercase;">Day</th>
              <th style="padding:10px 12px;text-align:left;color:#666;font-size:11px;text-transform:uppercase;">Name</th>
              <th style="padding:10px 12px;text-align:left;color:#666;font-size:11px;text-transform:uppercase;">Relationship</th>
              <th style="padding:10px 12px;text-align:left;color:#666;font-size:11px;text-transform:uppercase;">Age</th>
              <th style="padding:10px 12px;text-align:left;color:#666;font-size:11px;text-transform:uppercase;">Status</th>
            </tr></thead>
            <tbody>{rows}{empty}</tbody>
          </table>
        </td></tr>
        <tr><td style="background:#1a1a2e;padding:16px;text-align:center;">
          <p style="margin:0;color:rgba(255,255,255,0.6);font-size:12px;">Birthday Bot Monthly Digest &nbsp;•&nbsp; {date.today().strftime('%B %Y')}</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def _build_year_review_html(year: int, birthdays: list, sent_count: int, reminder_count: int) -> str:
    from collections import Counter
    by_rel = Counter(b.relationship for b in birthdays)
    top_streak = sorted(birthdays, key=lambda b: b.streak, reverse=True)[:3]
    streak_items = "".join(
        f"<li>🔥 <strong>{b.name}</strong> — {b.streak} year streak</li>"
        for b in top_streak if b.streak > 0
    ) or "<li>Start sending messages to build streaks!</li>"
    rel_items = "".join(f"<li><strong>{k}:</strong> {v}</li>" for k, v in by_rel.most_common())

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f8;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f8;padding:30px 10px;">
    <tr><td align="center">
      <table width="620" cellpadding="0" cellspacing="0" style="max-width:620px;width:100%;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.12);">
        <tr><td style="background:linear-gradient(135deg,#1a1a2e,#7c3aed);padding:36px 30px;text-align:center;">
          <p style="margin:0;font-size:36px;">🎊</p>
          <h1 style="margin:10px 0 4px;color:#fff;font-size:28px;font-weight:800;">{year} Year in Review</h1>
          <p style="margin:0;color:rgba(255,255,255,0.8);font-size:15px;">What a year of celebrations!</p>
        </td></tr>
        <tr><td style="background:#fff;padding:30px 36px;">
          <div style="display:flex;gap:12px;justify-content:center;margin-bottom:24px;flex-wrap:wrap;">
            <div style="text-align:center;padding:16px 24px;background:#f8f9ff;border-radius:12px;min-width:120px;">
              <div style="font-size:28px;font-weight:800;color:#7c3aed;">{len(birthdays)}</div>
              <div style="font-size:12px;color:#888;text-transform:uppercase;letter-spacing:0.5px;">Birthdays</div>
            </div>
            <div style="text-align:center;padding:16px 24px;background:#f0fdf4;border-radius:12px;min-width:120px;">
              <div style="font-size:28px;font-weight:800;color:#059669;">{sent_count}</div>
              <div style="font-size:12px;color:#888;text-transform:uppercase;letter-spacing:0.5px;">Sent</div>
            </div>
            <div style="text-align:center;padding:16px 24px;background:#fffbeb;border-radius:12px;min-width:120px;">
              <div style="font-size:28px;font-weight:800;color:#d97706;">{reminder_count}</div>
              <div style="font-size:12px;color:#888;text-transform:uppercase;letter-spacing:0.5px;">Reminders</div>
            </div>
          </div>
          <h3 style="font-size:15px;margin-bottom:8px;">🔥 Top Streaks</h3>
          <ul style="font-size:14px;color:#444;padding-left:20px;margin-bottom:20px;">{streak_items}</ul>
          <h3 style="font-size:15px;margin-bottom:8px;">💝 Relationships</h3>
          <ul style="font-size:14px;color:#444;padding-left:20px;">{rel_items}</ul>
          <div style="margin-top:20px;padding:14px 18px;background:linear-gradient(135deg,#7c3aed18,#4f46e518);border-left:4px solid #7c3aed;border-radius:8px;">
            <p style="margin:0;font-size:13px;color:#5b21b6;font-weight:600;">✨ You made {sent_count} people feel special this year. Keep it up in {year+1}!</p>
          </div>
        </td></tr>
        <tr><td style="background:#1a1a2e;padding:16px;text-align:center;">
          <p style="margin:0;color:rgba(255,255,255,0.6);font-size:12px;">Birthday Bot &nbsp;•&nbsp; {year} Year in Review</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


# ── Public send functions ─────────────────────────────────────────────────────

def _handle_gift_card(birthday) -> tuple[str, dict]:
    """
    Returns (gift_card_html_block, gc_result_dict).
    Sends via Tremendous if configured; otherwise returns manual code block.
    """
    from gift_card_service import build_gift_card_email_html, send_tremendous_gift_card

    if not getattr(birthday, "gift_card_enabled", False):
        return "", {}

    brand = getattr(birthday, "gift_card_brand", "amazon") or "amazon"
    amount = float(getattr(birthday, "gift_card_amount", 0) or 0)
    code = getattr(birthday, "gift_card_code", "") or ""
    note = getattr(birthday, "gift_card_note", "") or ""
    gc_type = getattr(birthday, "gift_card_type", "manual") or "manual"

    gc_result = {"delivery_type": gc_type, "brand": brand, "amount": amount}

    if gc_type == "tremendous":
        result = send_tremendous_gift_card(birthday.name, birthday.email, amount, brand)
        gc_result.update(result)
        # Tremendous sends its own email; we just add a notice in ours
        html_block = build_gift_card_email_html(brand, amount, "", note, "tremendous")
    else:
        # Manual: embed the code directly in the email
        html_block = build_gift_card_email_html(brand, amount, code, note, "manual")
        gc_result["success"] = True

    return html_block, gc_result


def send_birthday_emails(birthday) -> dict:
    if not Config.SENDER_EMAIL or not Config.SENDER_APP_PASSWORD:
        return {"success": False, "error": "Email credentials not configured."}

    message_text = _pick_message(
        birthday.name, birthday.relationship,
        getattr(birthday, "custom_message", ""),
        birthday.age_turning, Config.SENDER_NAME,
        use_ai=getattr(birthday, "use_ai_message", False),
        notes=getattr(birthday, "notes", ""),
        birthday_obj=birthday if hasattr(birthday, "past_messages") else None,
    )

    gift_card_html, gc_result = _handle_gift_card(birthday)

    card_bytes = generate_gift_card(
        name=birthday.name,
        message=message_text.split("\n\n")[0],
        age=birthday.age_turning,
        theme_name=birthday.card_theme,
        layout=getattr(birthday, "card_layout", "banner"),
    )

    # Optional AI gift suggestions for owner notification
    gift_suggestions = ""
    if Config.OPENAI_API_KEY and getattr(birthday, "use_ai_message", False):
        gift_suggestions = generate_ai_gift_suggestions(
            birthday.name, birthday.relationship,
            birthday.age_turning, getattr(birthday, "notes", ""),
        )

    # Optional TTS voice greeting
    tts_audio = generate_tts_audio(birthday.name, message_text.split("\n\n")[0]) if Config.OPENAI_API_KEY else None

    errors = []

    # Email to celebrant
    try:
        msg = MIMEMultipart("related")
        msg["Subject"] = f"🎂 Happy Birthday, {birthday.name}! 🎉"
        msg["From"] = f"{Config.SENDER_NAME} <{Config.SENDER_EMAIL}>"
        msg["To"] = birthday.email
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(f"Happy Birthday, {birthday.name}!\n\n{message_text}", "plain"))
        alt.attach(MIMEText(_build_celebrant_html(birthday.name, message_text, birthday.age_turning, birthday.card_theme, gift_card_html), "html"))
        msg.attach(alt)
        img = MIMEImage(card_bytes, "jpeg")
        img.add_header("Content-ID", "<giftcard>")
        img.add_header("Content-Disposition", "inline", filename="birthday_card.jpg")
        msg.attach(img)
        if tts_audio:
            aud = MIMEAudio(tts_audio, "mpeg")
            aud.add_header("Content-Disposition", "attachment", filename="birthday_greeting.mp3")
            msg.attach(aud)
        with _smtp_connection() as server:
            server.sendmail(Config.SENDER_EMAIL, birthday.email, msg.as_string())
    except Exception as e:
        errors.append(f"Celebrant email failed: {e}")

    # Notification to owner
    try:
        msg2 = MIMEMultipart("related")
        msg2["Subject"] = f"🔔 Birthday Alert: {birthday.name}'s birthday today!"
        msg2["From"] = f"Birthday Bot <{Config.SENDER_EMAIL}>"
        msg2["To"] = Config.SENDER_EMAIL
        alt2 = MIMEMultipart("alternative")
        alt2.attach(MIMEText(f"Birthday alert: sent to {birthday.name}.", "plain"))
        alt2.attach(MIMEText(_build_owner_html(
            birthday.name, birthday.email, birthday.age_turning,
            birthday.relationship, birthday.card_theme,
            getattr(birthday, "streak", 0), gift_suggestions,
        ), "html"))
        msg2.attach(alt2)
        img2 = MIMEImage(card_bytes, "jpeg")
        img2.add_header("Content-ID", "<giftcard>")
        img2.add_header("Content-Disposition", "inline", filename="birthday_card_preview.jpg")
        msg2.attach(img2)
        with _smtp_connection() as server:
            server.sendmail(Config.SENDER_EMAIL, Config.SENDER_EMAIL, msg2.as_string())
    except Exception as e:
        errors.append(f"Owner notification failed: {e}")

    success = not errors

    # Log gift card delivery
    if success and gc_result:
        try:
            from models import GiftCardSend
            from extensions import db
            gcs = GiftCardSend(
                birthday_id=birthday.id,
                brand=gc_result.get("brand", ""),
                amount=gc_result.get("amount", 0),
                delivery_type=gc_result.get("delivery_type", "manual"),
                code=getattr(birthday, "gift_card_code", "") or "",
                tremendous_order_id=gc_result.get("order_id", ""),
                status="sent" if gc_result.get("success") else "failed",
                recipient_email=birthday.email,
                notes=gc_result.get("error", ""),
            )
            db.session.add(gcs)
            db.session.commit()
        except Exception:
            pass

    return {"success": success, "error": "; ".join(errors) if errors else "",
            "gift_card": gc_result}


def send_reminder_email(birthday, days_before: int) -> dict:
    if not Config.SENDER_EMAIL or not Config.SENDER_APP_PASSWORD:
        return {"success": False, "error": "Email credentials not configured."}
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"⏰ Reminder: {birthday.name}'s birthday in {days_before} day{'s' if days_before!=1 else ''}!"
        msg["From"] = f"Birthday Bot <{Config.SENDER_EMAIL}>"
        msg["To"] = Config.SENDER_EMAIL
        msg.attach(MIMEText(f"Reminder: {birthday.name}'s birthday in {days_before} days.", "plain"))
        msg.attach(MIMEText(_build_reminder_html(
            birthday.name, days_before, birthday.next_birthday, birthday.age_turning, birthday.card_theme
        ), "html"))
        with _smtp_connection() as server:
            server.sendmail(Config.SENDER_EMAIL, Config.SENDER_EMAIL, msg.as_string())
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_digest_email(month: int, birthdays: list) -> dict:
    if not Config.SENDER_EMAIL or not Config.SENDER_APP_PASSWORD:
        return {"success": False, "error": "Email credentials not configured."}
    try:
        from datetime import date as _date
        month_name = _date(2000, month, 1).strftime("%B")
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"📅 Birthday Digest: {month_name} — {len(birthdays)} upcoming"
        msg["From"] = f"Birthday Bot <{Config.SENDER_EMAIL}>"
        msg["To"] = Config.SENDER_EMAIL
        msg.attach(MIMEText(f"{month_name} Birthday Digest: {len(birthdays)} birthdays.", "plain"))
        msg.attach(MIMEText(_build_digest_html(month_name, birthdays), "html"))
        with _smtp_connection() as server:
            server.sendmail(Config.SENDER_EMAIL, Config.SENDER_EMAIL, msg.as_string())
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_year_in_review_email(year: int, birthdays: list) -> dict:
    if not Config.SENDER_EMAIL or not Config.SENDER_APP_PASSWORD:
        return {"success": False, "error": "Email credentials not configured."}
    try:
        from models import SentLog
        from extensions import db
        sent_count = SentLog.query.filter(
            SentLog.log_type == "birthday",
            SentLog.status == "success",
        ).count()
        reminder_count = SentLog.query.filter(SentLog.log_type == "reminder").count()

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🎊 Your {year} Birthday Bot Year in Review"
        msg["From"] = f"Birthday Bot <{Config.SENDER_EMAIL}>"
        msg["To"] = Config.SENDER_EMAIL
        msg.attach(MIMEText(f"{year} Year in Review: {sent_count} messages sent.", "plain"))
        msg.attach(MIMEText(_build_year_review_html(year, birthdays, sent_count, reminder_count), "html"))
        with _smtp_connection() as server:
            server.sendmail(Config.SENDER_EMAIL, Config.SENDER_EMAIL, msg.as_string())
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}
