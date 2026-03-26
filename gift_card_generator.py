import io
import math
import random
from PIL import Image, ImageDraw, ImageFont

THEMES = {
    "sunset": {
        "bg_start": (255, 94, 58),
        "bg_end": (255, 179, 71),
        "accent": (255, 255, 255),
        "text_primary": (255, 255, 255),
        "text_secondary": (255, 235, 200),
        "particle": (255, 220, 150),
    },
    "ocean": {
        "bg_start": (10, 75, 163),
        "bg_end": (0, 195, 200),
        "accent": (255, 255, 255),
        "text_primary": (255, 255, 255),
        "text_secondary": (200, 240, 255),
        "particle": (150, 220, 255),
    },
    "forest": {
        "bg_start": (20, 110, 60),
        "bg_end": (100, 200, 80),
        "accent": (255, 255, 255),
        "text_primary": (255, 255, 255),
        "text_secondary": (210, 255, 210),
        "particle": (180, 240, 180),
    },
    "rose": {
        "bg_start": (180, 30, 90),
        "bg_end": (255, 120, 160),
        "accent": (255, 255, 255),
        "text_primary": (255, 255, 255),
        "text_secondary": (255, 210, 230),
        "particle": (255, 180, 210),
    },
    "midnight": {
        "bg_start": (15, 15, 50),
        "bg_end": (70, 40, 130),
        "accent": (200, 170, 255),
        "text_primary": (255, 255, 255),
        "text_secondary": (200, 180, 255),
        "particle": (180, 150, 255),
    },
    "gold": {
        "bg_start": (100, 60, 0),
        "bg_end": (220, 170, 30),
        "accent": (255, 240, 180),
        "text_primary": (255, 255, 255),
        "text_secondary": (255, 235, 160),
        "particle": (255, 220, 100),
    },
}

WIDTH, HEIGHT = 800, 480


def _lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _draw_gradient(draw, c1, c2, w, h):
    for y in range(h):
        t = y / h
        color = _lerp_color(c1, c2, t)
        draw.line([(0, y), (w, y)], fill=color)


def _draw_confetti(draw, particle_color, seed=42):
    rng = random.Random(seed)
    shapes = ["circle", "rect", "star"]
    colors = [
        particle_color,
        _lerp_color(particle_color, (255, 255, 255), 0.4),
        _lerp_color(particle_color, (255, 255, 255), 0.7),
    ]
    for _ in range(60):
        x = rng.randint(0, WIDTH)
        y = rng.randint(0, HEIGHT)
        size = rng.randint(4, 14)
        color = rng.choice(colors) + (rng.randint(120, 220),)
        shape = rng.choice(shapes)
        if shape == "circle":
            draw.ellipse([x, y, x + size, y + size], fill=color)
        elif shape == "rect":
            draw.rectangle([x, y, x + size, y + size // 2], fill=color)
        else:
            _draw_star(draw, x + size // 2, y + size // 2, size // 2, color)


def _draw_star(draw, cx, cy, r, color):
    points = []
    for i in range(10):
        angle = math.pi / 5 * i - math.pi / 2
        radius = r if i % 2 == 0 else r * 0.45
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    draw.polygon(points, fill=color)


def _draw_decorative_circles(draw, theme):
    alpha_img = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    adraw = ImageDraw.Draw(alpha_img)
    c = theme["accent"]
    adraw.ellipse([-80, -80, 200, 200], outline=c + (40,), width=3)
    adraw.ellipse([-50, -50, 150, 150], outline=c + (25,), width=2)
    adraw.ellipse([650, 300, 950, 600], outline=c + (40,), width=3)
    adraw.ellipse([670, 320, 920, 570], outline=c + (25,), width=2)
    return alpha_img


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


def _wrap_text(text, font, max_width, draw):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def generate_gift_card(name: str, message: str, age: int, theme_name: str = "sunset") -> bytes:
    theme = THEMES.get(theme_name, THEMES["sunset"])

    base = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))
    gradient_layer = Image.new("RGBA", (WIDTH, HEIGHT))
    gd = ImageDraw.Draw(gradient_layer)
    _draw_gradient(gd, theme["bg_start"], theme["bg_end"], WIDTH, HEIGHT)

    confetti_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    cd = ImageDraw.Draw(confetti_layer)
    _draw_confetti(cd, theme["particle"], seed=hash(name) % 1000)

    circle_layer = _draw_decorative_circles(ImageDraw.Draw(Image.new("RGBA", (WIDTH, HEIGHT))), theme)

    base = Image.alpha_composite(base, gradient_layer)
    base = Image.alpha_composite(base, circle_layer)
    base = Image.alpha_composite(base, confetti_layer)

    draw = ImageDraw.Draw(base)

    # --- Banner strip ---
    banner_y = 30
    banner_h = 60
    banner_color = tuple(int(c * 0.6) for c in theme["bg_start"]) + (180,)
    banner_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    bd = ImageDraw.Draw(banner_layer)
    bd.rectangle([0, banner_y, WIDTH, banner_y + banner_h], fill=banner_color)
    base = Image.alpha_composite(base, banner_layer)
    draw = ImageDraw.Draw(base)

    # --- Emoji balloons row ---
    emoji_font = _get_font(32)
    balloon_text = "🎂  🎉  🎈  🎁  🥳  🎊  🎈  🎉  🎂"
    draw.text((WIDTH // 2, banner_y + banner_h // 2), balloon_text, font=emoji_font,
              fill=theme["text_primary"], anchor="mm")

    # --- Happy Birthday headline ---
    hb_font = _get_font(62, bold=True)
    shadow_offset = 3
    draw.text((WIDTH // 2 + shadow_offset, 115 + shadow_offset), "Happy Birthday!",
              font=hb_font, fill=(0, 0, 0, 80), anchor="mm")
    draw.text((WIDTH // 2, 115), "Happy Birthday!",
              font=hb_font, fill=theme["text_primary"], anchor="mm")

    # --- Name ---
    name_font = _get_font(44, bold=True)
    draw.text((WIDTH // 2 + 2, 182), f"Dear {name} 🌟",
              font=name_font, fill=(0, 0, 0, 70), anchor="mm")
    draw.text((WIDTH // 2, 180), f"Dear {name} 🌟",
              font=name_font, fill=theme["text_secondary"], anchor="mm")

    # --- Age badge ---
    badge_cx, badge_cy, badge_r = 90, 240, 55
    badge_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    bad = ImageDraw.Draw(badge_layer)
    bad.ellipse(
        [badge_cx - badge_r, badge_cy - badge_r, badge_cx + badge_r, badge_cy + badge_r],
        fill=theme["accent"] + (220,),
    )
    base = Image.alpha_composite(base, badge_layer)
    draw = ImageDraw.Draw(base)
    age_num_font = _get_font(34, bold=True)
    age_label_font = _get_font(14)
    draw.text((badge_cx, badge_cy - 8), str(age), font=age_num_font,
              fill=theme["bg_start"], anchor="mm")
    draw.text((badge_cx, badge_cy + 22), "years", font=age_label_font,
              fill=theme["bg_start"], anchor="mm")

    # --- Message body ---
    msg_font = _get_font(20)
    msg_lines = _wrap_text(message, msg_font, WIDTH - 240, draw)
    msg_x = (WIDTH + 160) // 2
    msg_y_start = 220
    line_h = 30
    for i, line in enumerate(msg_lines[:6]):
        draw.text((msg_x, msg_y_start + i * line_h), line,
                  font=msg_font, fill=theme["text_primary"], anchor="mm")

    # --- Bottom divider + footer ---
    div_y = HEIGHT - 70
    div_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    dd = ImageDraw.Draw(div_layer)
    dd.rectangle([40, div_y, WIDTH - 40, div_y + 2], fill=theme["accent"] + (120,))
    base = Image.alpha_composite(base, div_layer)
    draw = ImageDraw.Draw(base)

    footer_font = _get_font(16)
    from datetime import date
    draw.text((WIDTH // 2, HEIGHT - 40),
              f"With love & best wishes  •  {date.today().strftime('%B %d, %Y')}  •  🎀",
              font=footer_font, fill=theme["text_secondary"], anchor="mm")

    # Convert to RGB for JPEG output
    final = base.convert("RGB")
    buf = io.BytesIO()
    final.save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return buf.read()
