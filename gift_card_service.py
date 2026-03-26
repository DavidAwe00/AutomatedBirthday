"""
E-Gift Card Service
  - Manual: embed a pre-purchased code in the birthday email
  - Tremendous: automatically purchase & deliver a real gift card via API
    https://developers.tremendous.com/
"""
import json
import requests as http_requests
from config import Config

TREMENDOUS_BASE = "https://testflight.tremendous.com/api/v2"   # sandbox
TREMENDOUS_PROD  = "https://www.tremendous.com/api/v2"          # production

# ── Brand catalogue ───────────────────────────────────────────────────────────
BRANDS = {
    "amazon": {
        "label": "Amazon",
        "icon": "🛒",
        "color1": "#FF9900",
        "color2": "#232F3E",
        "text_color": "#FFFFFF",
        "tremendous_id": "OKMHM2X2OHYV",   # Amazon.com Gift Card
    },
    "visa": {
        "label": "Visa Prepaid",
        "icon": "💳",
        "color1": "#1A1F71",
        "color2": "#F7B600",
        "text_color": "#FFFFFF",
        "tremendous_id": "Q24BD9EZ332JT",   # Visa Virtual Card
    },
    "starbucks": {
        "label": "Starbucks",
        "icon": "☕",
        "color1": "#00704A",
        "color2": "#1E3932",
        "text_color": "#FFFFFF",
        "tremendous_id": "QCFZWL1LHQNXP",
    },
    "netflix": {
        "label": "Netflix",
        "icon": "🎬",
        "color1": "#E50914",
        "color2": "#141414",
        "text_color": "#FFFFFF",
        "tremendous_id": "QCFZWL1LHQNXP",   # placeholder
    },
    "apple": {
        "label": "Apple",
        "icon": "🍎",
        "color1": "#555555",
        "color2": "#1D1D1F",
        "text_color": "#FFFFFF",
        "tremendous_id": "QCFZWL1LHQNXP",   # placeholder
    },
    "google_play": {
        "label": "Google Play",
        "icon": "🎮",
        "color1": "#4285F4",
        "color2": "#34A853",
        "text_color": "#FFFFFF",
        "tremendous_id": "QCFZWL1LHQNXP",
    },
    "airbnb": {
        "label": "Airbnb",
        "icon": "🏠",
        "color1": "#FF5A5F",
        "color2": "#FF385C",
        "text_color": "#FFFFFF",
        "tremendous_id": "QCFZWL1LHQNXP",
    },
    "spotify": {
        "label": "Spotify",
        "icon": "🎵",
        "color1": "#1DB954",
        "color2": "#191414",
        "text_color": "#FFFFFF",
        "tremendous_id": "QCFZWL1LHQNXP",
    },
    "uber": {
        "label": "Uber",
        "icon": "🚗",
        "color1": "#000000",
        "color2": "#333333",
        "text_color": "#FFFFFF",
        "tremendous_id": "QCFZWL1LHQNXP",
    },
    "custom": {
        "label": "Custom",
        "icon": "🎁",
        "color1": "#7C3AED",
        "color2": "#4F46E5",
        "text_color": "#FFFFFF",
        "tremendous_id": None,
    },
}

BRAND_LIST = [(k, v["label"], v["icon"]) for k, v in BRANDS.items()]


def _tremendous_headers():
    base = TREMENDOUS_BASE if Config.TREMENDOUS_SANDBOX else TREMENDOUS_PROD
    return base, {"Authorization": f"Bearer {Config.TREMENDOUS_API_KEY}",
                  "Content-Type": "application/json"}


def send_tremendous_gift_card(recipient_name: str, recipient_email: str,
                               amount: float, brand: str) -> dict:
    """
    Purchase and deliver a Tremendous gift card.
    Returns {"success": bool, "order_id": str, "error": str}
    """
    if not Config.tremendous_configured():
        return {"success": False, "error": "Tremendous API not configured."}

    brand_info = BRANDS.get(brand, BRANDS["amazon"])
    product_id = brand_info.get("tremendous_id")
    if not product_id:
        return {"success": False, "error": f"Brand '{brand}' not available via Tremendous."}

    base, headers = _tremendous_headers()
    payload = {
        "payment": {
            "funding_source_id": Config.TREMENDOUS_FUNDING_SOURCE_ID,
        },
        "rewards": [{
            "value": {"denomination": amount, "currency_code": "USD"},
            "delivery": {"method": "EMAIL"},
            "recipient": {"name": recipient_name, "email": recipient_email},
            "products": [product_id],
        }],
    }
    try:
        resp = http_requests.post(f"{base}/orders", headers=headers,
                                  data=json.dumps(payload), timeout=15)
        data = resp.json()
        if resp.status_code in (200, 201):
            order_id = data.get("order", {}).get("id", "")
            return {"success": True, "order_id": order_id}
        else:
            errors = data.get("errors", [{}])
            msg = errors[0].get("message", str(data)) if errors else str(data)
            return {"success": False, "error": msg}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_tremendous_funding_sources() -> list:
    """List available funding sources (for settings display)."""
    if not Config.TREMENDOUS_API_KEY:
        return []
    try:
        base, headers = _tremendous_headers()
        resp = http_requests.get(f"{base}/funding_sources", headers=headers, timeout=10)
        if resp.ok:
            return resp.json().get("funding_sources", [])
    except Exception:
        pass
    return []


def build_gift_card_email_html(brand: str, amount: float, code: str,
                                note: str, delivery_type: str) -> str:
    """
    Returns a self-contained HTML block for embedding in the birthday email.
    Looks like a physical gift card with a reveal animation.
    """
    info = BRANDS.get(brand, BRANDS["custom"])
    c1, c2 = info["color1"], info["color2"]
    text_col = info["text_color"]
    icon = info["icon"]
    label = info["label"]
    amount_str = f"${amount:.2f}" if amount else ""
    note_html = f'<p style="margin:10px 0 0;font-size:14px;color:#555;font-style:italic;">"{note}"</p>' if note else ""

    if delivery_type == "tremendous":
        code_section = """
        <div style="margin-top:16px;padding:12px 16px;background:#f8f9ff;border-radius:8px;border:1px solid #e2e5f0;text-align:center;">
          <p style="margin:0;font-size:13px;color:#666;">✉️ Your gift card link has been sent directly to your email by <strong>Tremendous</strong>.</p>
        </div>"""
    elif code:
        code_section = f"""
        <div style="margin-top:16px;padding:12px 20px;background:#1a1d2e;border-radius:8px;text-align:center;">
          <p style="margin:0 0 6px;font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;">Your Gift Card Code</p>
          <p style="margin:0;font-size:22px;font-weight:800;color:#a5f3fc;letter-spacing:4px;font-family:'Courier New',monospace;">{code}</p>
          <p style="margin:6px 0 0;font-size:11px;color:#888;">Copy this code at checkout</p>
        </div>"""
    else:
        code_section = ""

    return f"""
    <!-- E-Gift Card Section -->
    <table width="100%" cellpadding="0" cellspacing="0" style="margin:24px 0;">
      <tr><td>
        <div style="border-radius:16px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,0.18);">
          <!-- Card top: gradient with brand -->
          <div style="background:linear-gradient(135deg,{c1},{c2});padding:28px 24px 24px;position:relative;">
            <div style="display:flex;align-items:center;justify-content:space-between;">
              <div>
                <p style="margin:0;font-size:11px;color:rgba(255,255,255,0.7);text-transform:uppercase;letter-spacing:1.5px;font-weight:600;">E-Gift Card</p>
                <h2 style="margin:4px 0 0;font-size:28px;font-weight:900;color:{text_col};">{icon} {label}</h2>
              </div>
              {f'<div style="text-align:right;"><p style="margin:0;font-size:11px;color:rgba(255,255,255,0.7);">Value</p><p style="margin:2px 0 0;font-size:36px;font-weight:900;color:{text_col};">{amount_str}</p></div>' if amount_str else ''}
            </div>
            <!-- Decorative circles -->
            <div style="position:absolute;top:-20px;right:-20px;width:80px;height:80px;border-radius:50%;background:rgba(255,255,255,0.08);"></div>
            <div style="position:absolute;bottom:-30px;left:40px;width:100px;height:100px;border-radius:50%;background:rgba(255,255,255,0.05);"></div>
          </div>
          <!-- Card bottom: white -->
          <div style="background:#fff;padding:20px 24px;">
            <p style="margin:0;font-size:13px;color:#888;">🎁 A special gift just for you, with love!</p>
            {note_html}
            {code_section}
            <p style="margin:14px 0 0;font-size:11px;color:#bbb;text-align:right;">Delivered via Birthday Bot</p>
          </div>
        </div>
      </td></tr>
    </table>"""
