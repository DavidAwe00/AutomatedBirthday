import io
import math
import random
from PIL import Image, ImageDraw, ImageFont

THEMES = {
    "sunset":   {"bg_start":(255,94,58),  "bg_end":(255,179,71), "accent":(255,255,255), "text_primary":(255,255,255), "text_secondary":(255,235,200), "particle":(255,220,150)},
    "ocean":    {"bg_start":(10,75,163),  "bg_end":(0,195,200),  "accent":(255,255,255), "text_primary":(255,255,255), "text_secondary":(200,240,255), "particle":(150,220,255)},
    "forest":   {"bg_start":(20,110,60),  "bg_end":(100,200,80), "accent":(255,255,255), "text_primary":(255,255,255), "text_secondary":(210,255,210), "particle":(180,240,180)},
    "rose":     {"bg_start":(180,30,90),  "bg_end":(255,120,160),"accent":(255,255,255), "text_primary":(255,255,255), "text_secondary":(255,210,230), "particle":(255,180,210)},
    "midnight": {"bg_start":(15,15,50),   "bg_end":(70,40,130),  "accent":(200,170,255), "text_primary":(255,255,255), "text_secondary":(200,180,255), "particle":(180,150,255)},
    "gold":     {"bg_start":(100,60,0),   "bg_end":(220,170,30), "accent":(255,240,180), "text_primary":(255,255,255), "text_secondary":(255,235,160), "particle":(255,220,100)},
}

BANNER_W, BANNER_H = 800, 480
PORTRAIT_W, PORTRAIT_H = 480, 680
POSTCARD_W, POSTCARD_H = 800, 480
MINIMAL_W, MINIMAL_H = 800, 400


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

def _gradient(draw, c1, c2, w, h, horizontal=False):
    steps = w if horizontal else h
    for i in range(steps):
        t = i / steps
        color = _lerp(c1, c2, t)
        if horizontal:
            draw.line([(i, 0), (i, h)], fill=color)
        else:
            draw.line([(0, i), (w, i)], fill=color)

def _get_font(size, bold=False):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()

def _wrap(text, font, max_w, draw):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        bb = draw.textbbox((0, 0), test, font=font)
        if bb[2] - bb[0] <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines

def _confetti(draw, color, w, h, seed=42, count=50):
    rng = random.Random(seed)
    bright = _lerp(color, (255, 255, 255), 0.4)
    pale   = _lerp(color, (255, 255, 255), 0.7)
    for _ in range(count):
        x, y = rng.randint(0, w), rng.randint(0, h)
        s = rng.randint(4, 12)
        c = rng.choice([color, bright, pale]) + (rng.randint(120, 200),)
        shape = rng.choice(["circle", "rect", "star"])
        if shape == "circle":
            draw.ellipse([x, y, x + s, y + s], fill=c)
        elif shape == "rect":
            draw.rectangle([x, y, x + s, y + s // 2], fill=c)
        else:
            pts = []
            for i in range(10):
                a = math.pi / 5 * i - math.pi / 2
                r = s // 2 if i % 2 == 0 else s // 4
                pts.append((x + r * math.cos(a), y + r * math.sin(a)))
            draw.polygon(pts, fill=c)

def _age_badge(img, cx, cy, r, text_color_bg, age):
    """Draw a circular age badge on an RGBA image."""
    badge = Image.new("RGBA", img.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(badge)
    bd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 220))
    img = Image.alpha_composite(img, badge)
    draw = ImageDraw.Draw(img)
    draw.text((cx, cy - 8), str(age), font=_get_font(30, bold=True), fill=text_color_bg, anchor="mm")
    draw.text((cx, cy + 18), "years", font=_get_font(12), fill=text_color_bg, anchor="mm")
    return img

def _to_jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return buf.read()


# ── Layout 1: Banner (original horizontal) ────────────────────────────────────

def _layout_banner(name, message, age, theme):
    t = theme
    base = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 255))

    g = Image.new("RGBA", (BANNER_W, BANNER_H))
    _gradient(ImageDraw.Draw(g), t["bg_start"], t["bg_end"], BANNER_W, BANNER_H)
    base = Image.alpha_composite(base, g)

    conf = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
    _confetti(ImageDraw.Draw(conf), t["particle"], BANNER_W, BANNER_H, seed=hash(name) % 1000)
    base = Image.alpha_composite(base, conf)

    draw = ImageDraw.Draw(base)

    # Banner strip
    strip = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(strip)
    bg = tuple(int(c * 0.6) for c in t["bg_start"]) + (180,)
    sd.rectangle([0, 28, BANNER_W, 88], fill=bg)
    base = Image.alpha_composite(base, strip)
    draw = ImageDraw.Draw(base)

    draw.text((BANNER_W // 2, 58), "Happy Birthday!", font=_get_font(60, bold=True),
              fill=t["text_primary"], anchor="mm")
    draw.text((BANNER_W // 2 + 2, 130), f"Dear {name}", font=_get_font(42, bold=True),
              fill=(0, 0, 0, 60), anchor="mm")
    draw.text((BANNER_W // 2, 128), f"Dear {name}", font=_get_font(42, bold=True),
              fill=t["text_secondary"], anchor="mm")

    base = _age_badge(base, 85, 240, 52, t["bg_start"], age)
    draw = ImageDraw.Draw(base)

    msg_font = _get_font(19)
    lines = _wrap(message, msg_font, BANNER_W - 220, draw)
    mx = (BANNER_W + 150) // 2
    for i, ln in enumerate(lines[:6]):
        draw.text((mx, 210 + i * 29), ln, font=msg_font, fill=t["text_primary"], anchor="mm")

    div = Image.new("RGBA", (BANNER_W, BANNER_H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(div)
    dd.rectangle([40, BANNER_H - 68, BANNER_W - 40, BANNER_H - 66], fill=t["accent"] + (120,))
    base = Image.alpha_composite(base, div)
    draw = ImageDraw.Draw(base)

    from datetime import date
    draw.text((BANNER_W // 2, BANNER_H - 40),
              f"With love & best wishes  •  {date.today().strftime('%B %d, %Y')}",
              font=_get_font(14), fill=t["text_secondary"], anchor="mm")

    return _to_jpeg(base)


# ── Layout 2: Portrait (tall elegant card) ────────────────────────────────────

def _layout_portrait(name, message, age, theme):
    t = theme
    base = Image.new("RGBA", (PORTRAIT_W, PORTRAIT_H), (255, 255, 255, 255))

    # Gradient top third
    top = Image.new("RGBA", (PORTRAIT_W, PORTRAIT_H), (0, 0, 0, 0))
    td = ImageDraw.Draw(top)
    _gradient(td, t["bg_start"], t["bg_end"], PORTRAIT_W, PORTRAIT_H // 3)
    base = Image.alpha_composite(base, top)

    conf = Image.new("RGBA", (PORTRAIT_W, PORTRAIT_H), (0, 0, 0, 0))
    _confetti(ImageDraw.Draw(conf), t["particle"], PORTRAIT_W, PORTRAIT_H // 3, count=30, seed=hash(name) % 999)
    base = Image.alpha_composite(base, conf)
    draw = ImageDraw.Draw(base)

    # Age circle in gradient zone
    base = _age_badge(base, PORTRAIT_W // 2, 100, 56, t["bg_start"], age)
    draw = ImageDraw.Draw(base)

    # Decorative line
    draw.rectangle([40, PORTRAIT_H // 3, PORTRAIT_W - 40, PORTRAIT_H // 3 + 3],
                   fill=t["bg_start"])

    # Main text on white
    draw.text((PORTRAIT_W // 2, PORTRAIT_H // 3 + 44), "Happy Birthday!",
              font=_get_font(38, bold=True), fill=t["bg_start"], anchor="mm")
    draw.text((PORTRAIT_W // 2, PORTRAIT_H // 3 + 90), name,
              font=_get_font(26, bold=True), fill="#333333", anchor="mm")

    msg_font = _get_font(17)
    lines = _wrap(message, msg_font, PORTRAIT_W - 60, draw)
    for i, ln in enumerate(lines[:8]):
        draw.text((PORTRAIT_W // 2, PORTRAIT_H // 3 + 130 + i * 27), ln,
                  font=msg_font, fill="#555555", anchor="mm")

    # Bottom color band
    bot = Image.new("RGBA", (PORTRAIT_W, PORTRAIT_H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bot)
    _gradient(bd, t["bg_start"], t["bg_end"], PORTRAIT_W, 60)
    bd_shifted = Image.new("RGBA", (PORTRAIT_W, PORTRAIT_H), (0, 0, 0, 0))
    bd_shifted.paste(bot.crop((0, 0, PORTRAIT_W, 60)), (0, PORTRAIT_H - 60))
    base = Image.alpha_composite(base, bd_shifted)
    draw = ImageDraw.Draw(base)

    from datetime import date
    draw.text((PORTRAIT_W // 2, PORTRAIT_H - 30),
              date.today().strftime("%B %d, %Y"),
              font=_get_font(13), fill=(255, 255, 255), anchor="mm")

    return _to_jpeg(base)


# ── Layout 3: Postcard (split left/right) ─────────────────────────────────────

def _layout_postcard(name, message, age, theme):
    t = theme
    split = POSTCARD_W * 2 // 5

    base = Image.new("RGBA", (POSTCARD_W, POSTCARD_H), (255, 255, 255, 255))

    # Left gradient panel
    left = Image.new("RGBA", (POSTCARD_W, POSTCARD_H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(left)
    _gradient(ld, t["bg_start"], t["bg_end"], split, POSTCARD_H)
    base = Image.alpha_composite(base, left)

    conf = Image.new("RGBA", (POSTCARD_W, POSTCARD_H), (0, 0, 0, 0))
    _confetti(ImageDraw.Draw(conf), t["particle"], split, POSTCARD_H, count=35, seed=hash(name) % 777)
    base = Image.alpha_composite(base, conf)

    draw = ImageDraw.Draw(base)

    # Age badge on left panel
    base = _age_badge(base, split // 2, POSTCARD_H // 2, 62, t["bg_start"], age)
    draw = ImageDraw.Draw(base)

    # Vertical divider
    draw.rectangle([split, 0, split + 4, POSTCARD_H], fill=t["bg_start"])

    # Right side — text on white
    rx = split + (POSTCARD_W - split) // 2
    draw.text((rx, 55), "Happy Birthday!", font=_get_font(36, bold=True),
              fill=t["bg_start"], anchor="mm")
    draw.text((rx, 100), f"Dear {name}", font=_get_font(22), fill="#444444", anchor="mm")

    draw.rectangle([split + 30, 118, POSTCARD_W - 30, 121], fill=t["bg_start"])

    msg_font = _get_font(17)
    lines = _wrap(message, msg_font, POSTCARD_W - split - 60, draw)
    for i, ln in enumerate(lines[:7]):
        draw.text((rx, 145 + i * 27), ln, font=msg_font, fill="#555555", anchor="mm")

    from datetime import date
    draw.text((rx, POSTCARD_H - 28), date.today().strftime("%B %d, %Y"),
              font=_get_font(12), fill="#aaaaaa", anchor="mm")

    return _to_jpeg(base)


# ── Layout 4: Minimal (clean typographic) ─────────────────────────────────────

def _layout_minimal(name, message, age, theme):
    t = theme
    base = Image.new("RGBA", (MINIMAL_W, MINIMAL_H), (252, 252, 253, 255))
    draw = ImageDraw.Draw(base)

    # Top accent bar
    bar = Image.new("RGBA", (MINIMAL_W, MINIMAL_H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bar)
    _gradient(bd, t["bg_start"], t["bg_end"], MINIMAL_W, 10, horizontal=True)
    base = Image.alpha_composite(base, bar)
    draw = ImageDraw.Draw(base)

    # Soft colored circle behind age
    circle = Image.new("RGBA", (MINIMAL_W, MINIMAL_H), (0, 0, 0, 0))
    cd = ImageDraw.Draw(circle)
    bg_circle = t["bg_start"] + (25,)
    cd.ellipse([MINIMAL_W - 180, 30, MINIMAL_W - 30, 180], fill=bg_circle)
    base = Image.alpha_composite(base, circle)
    draw = ImageDraw.Draw(base)

    # Age text in corner
    draw.text((MINIMAL_W - 105, 105), str(age), font=_get_font(52, bold=True),
              fill=t["bg_start"], anchor="mm")
    draw.text((MINIMAL_W - 105, 148), "today", font=_get_font(12), fill="#aaaaaa", anchor="mm")

    # Main headline
    draw.text((54, 60), "Happy", font=_get_font(56, bold=True), fill=t["bg_start"])
    draw.text((54, 118), "Birthday,", font=_get_font(56, bold=True), fill="#222222")
    draw.text((54, 176), f"{name}.", font=_get_font(40, bold=True), fill="#444444")

    # Divider
    draw.rectangle([54, 228, 300, 231], fill=t["bg_start"])

    msg_font = _get_font(17)
    lines = _wrap(message, msg_font, MINIMAL_W - 120, draw)
    for i, ln in enumerate(lines[:5]):
        draw.text((54, 248 + i * 27), ln, font=msg_font, fill="#666666")

    from datetime import date
    draw.text((54, MINIMAL_H - 28), date.today().strftime("%B %d, %Y"),
              font=_get_font(12), fill="#bbbbbb")

    return _to_jpeg(base)


# ── Public API ─────────────────────────────────────────────────────────────────

LAYOUTS = {
    "banner":   _layout_banner,
    "portrait": _layout_portrait,
    "postcard": _layout_postcard,
    "minimal":  _layout_minimal,
}


def generate_gift_card(name: str, message: str, age: int,
                       theme_name: str = "sunset", layout: str = "banner") -> bytes:
    theme = THEMES.get(theme_name, THEMES["sunset"])
    fn = LAYOUTS.get(layout, _layout_banner)
    return fn(name, message, age, theme)
