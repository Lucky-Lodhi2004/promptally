"""Regenerate the raster brand assets from the logo geometry (requires Pillow).

    backend/venv/bin/python frontend/scripts/generate-brand-assets.py

Writes: src/app/favicon.ico (16/32/48), src/app/apple-icon.png (180),
public/logo-512x512.png and public/og-home.png (1200x630).
"""
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
LEFT = "M29 6h-6c-7 0-9 4-9 10v5c0 4-2 7-7 7 5 0 7 3 7 7v5c0 6 2 10 9 10h6"
RIGHT = "M43 18h6c7 0 9 4 9 10v5c0 4 2 7 7 7-5 0-7 3-7 7v5c0 6-2 10-9 10h-6"
VIEW_W, VIEW_H, STROKE = 72, 68, 7


def points(path, steps=24):
    """Sample a relative M/h/v/c path into a polyline."""
    tokens = re.findall(r"[MhvcMHVC]|-?\d+(?:\.\d+)?", path)
    pts, i, x, y = [], 0, 0.0, 0.0
    while i < len(tokens):
        cmd = tokens[i]; i += 1
        if cmd == "M":
            x, y = float(tokens[i]), float(tokens[i + 1]); i += 2; pts.append((x, y))
        elif cmd == "h":
            x += float(tokens[i]); i += 1; pts.append((x, y))
        elif cmd == "v":
            y += float(tokens[i]); i += 1; pts.append((x, y))
        elif cmd == "c":
            while i < len(tokens) and tokens[i] not in "MhvcMHVC":
                a = [float(t) for t in tokens[i:i + 6]]; i += 6
                p0, p1, p2, p3 = (x, y), (x + a[0], y + a[1]), (x + a[2], y + a[3]), (x + a[4], y + a[5])
                for s in range(1, steps + 1):
                    t = s / steps; u = 1 - t
                    pts.append((u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                                u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1]))
                x, y = p3
    return pts


def mark(size, background=None, padding=0.16):
    """Render the bracket mark on a square canvas at 4x then downsample."""
    scale = 4
    canvas = size * scale
    image = Image.new("RGBA", (canvas, canvas), background or (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if background:
        draw.rounded_rectangle([0, 0, canvas - 1, canvas - 1], radius=canvas // 5, fill=background)
    inner = canvas * (1 - 2 * padding)
    k = inner / max(VIEW_W, VIEW_H)
    ox = (canvas - VIEW_W * k) / 2
    oy = (canvas - VIEW_H * k) / 2
    for path, color in ((LEFT, "#ffaa3d"), (RIGHT, "#e47a14")):
        pts = [(ox + px * k, oy + py * k) for px, py in points(path)]
        width = max(1, round(STROKE * k))
        # A round brush at every sample gives smooth joins at any stroke width.
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            for t in (0.0, 0.5):
                px, py = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                draw.ellipse([px - width / 2, py - width / 2, px + width / 2, py + width / 2], fill=color)
        px, py = pts[-1]
        draw.ellipse([px - width / 2, py - width / 2, px + width / 2, py + width / 2], fill=color)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def font(size, bold=False):
    for name in ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",):
        for base in ("/usr/share/fonts/truetype/dejavu/",):
            try:
                return ImageFont.truetype(base + name, size)
            except OSError:
                pass
    return ImageFont.load_default()


def main():
    (ROOT / "public").mkdir(exist_ok=True)
    white = (255, 255, 255, 255)
    ico_base = mark(256, background=white, padding=0.12)
    ico_base.save(ROOT / "src/app/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    mark(180, background=white, padding=0.14).convert("RGB").save(ROOT / "src/app/apple-icon.png")
    mark(512, background=white, padding=0.14).save(ROOT / "public/logo-512x512.png")

    card = Image.new("RGB", (1200, 630), "#fff8ef")
    draw = ImageDraw.Draw(card)
    card.paste(mark(190, padding=0.02), (90, 150), mark(190, padding=0.02))
    draw.text((320, 150), "promptally", font=font(120, True), fill="#4b4b4d")
    draw.text((324, 300), "The open registry for AI prompts,", font=font(44), fill="#d66f0f")
    draw.text((324, 360), "agentic skills & workflows", font=font(44), fill="#d66f0f")
    draw.text((90, 540), "Copy free blueprints · Sell your own · MCP & llms.txt ready", font=font(30), fill="#77777a")
    card.save(ROOT / "public/og-home.png", optimize=True)


if __name__ == "__main__":
    main()
