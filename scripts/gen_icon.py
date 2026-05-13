"""
Generate a high-quality app icon for Sanitize V.

Design:
  • Rounded-square base in deep charcoal (#151820)
  • Outer glow ring in GTA-green (#3cb043)
  • Large bold "V" letterform in a green-to-lime vertical gradient
  • Small "S·" prefix in white to the upper-left of the V
  • Subtle inner highlight (top-centre white arc)

Run:  python scripts/gen_icon.py
Outputs:  assets/app_icon.png  (512×512)
          assets/app_icon.ico  (16,24,32,48,64,128,256)
"""

from __future__ import annotations

import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# ── resolve project root regardless of CWD ───────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)
ASSETS = os.path.join(ROOT, "assets")
os.makedirs(ASSETS, exist_ok=True)

SIZE = 512


def _rounded_rect_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def _make_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    s = size
    r = int(s * 0.22)          # corner radius

    # ── 1. Background rounded square ──────────────────────────────────
    bg_mask = _rounded_rect_mask(s, r)
    bg = Image.new("RGBA", (s, s), (21, 24, 32, 255))   # #151820
    img.paste(bg, mask=bg_mask)

    # ── 2. Outer glow ring ────────────────────────────────────────────
    ring_w = max(2, int(s * 0.038))
    draw.rounded_rectangle(
        [ring_w // 2, ring_w // 2, s - ring_w // 2 - 1, s - ring_w // 2 - 1],
        radius=r,
        outline=(60, 176, 67, 220),   # #3cb043 semi-transparent
        width=ring_w,
    )

    # ── 3. "V" letterform via polygon (vectorised, crisp at all sizes) ─
    #   Top-left arm: from upper-left → centre-bottom
    #   Top-right arm: from upper-right → centre-bottom
    pad_x = s * 0.14
    pad_top = s * 0.16
    pad_bot = s * 0.13
    arm_w = s * 0.155       # arm half-width at the top

    cx = s / 2
    top_y = pad_top
    bot_y = s - pad_bot

    # Left arm outer / inner
    lo_x1 = pad_x
    lo_x2 = lo_x1 + arm_w
    # Right arm outer / inner
    ro_x2 = s - pad_x
    ro_x1 = ro_x2 - arm_w

    # V tip thickness
    tip_half = s * 0.058

    v_poly = [
        (lo_x1,  top_y),
        (lo_x2,  top_y),
        (cx + tip_half, bot_y),
        (cx - tip_half, bot_y),
    ]

    v_poly_r = [
        (ro_x1, top_y),
        (ro_x2, top_y),
        (cx + tip_half, bot_y),
        (cx - tip_half, bot_y),
    ]

    # Draw V arms with gradient overlay:
    #   base colour = green (#3cb043) → lime (#8be04a) top-to-bottom
    # We render on a temp surface then composite

    v_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    vd = ImageDraw.Draw(v_layer)

    # solid green fill first
    vd.polygon([(x, y) for x, y in v_poly], fill=(60, 176, 67, 255))
    vd.polygon([(x, y) for x, y in v_poly_r], fill=(60, 176, 67, 255))

    # gradient: scanline-by-scanline blend (only for size >= 64 — skip for tiny)
    if size >= 64:
        grad_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        gd = ImageDraw.Draw(grad_layer)
        for iy in range(int(top_y), int(bot_y) + 1):
            t = (iy - top_y) / max(1, bot_y - top_y)
            # top = bright lime (139,224,74) → bottom = deep green (36,130,42)
            gr = int(139 + (36 - 139) * t)
            gg = int(224 + (130 - 224) * t)
            gb = int(74  + (42 - 74)  * t)
            gd.line([(0, iy), (s, iy)], fill=(gr, gg, gb, 255))
        # clip gradient to V shape
        v_mask = v_layer.split()[3]
        grad_layer.putalpha(v_mask)
        v_layer = grad_layer

    img = Image.alpha_composite(img, v_layer)
    draw = ImageDraw.Draw(img)

    # ── 4. Thin dark separator line in the V notch ────────────────────
    # (gives the illusion of a bevelled two-arm letter)
    notch_w = max(1, int(s * 0.018))
    draw.line(
        [(cx, int(top_y + (bot_y - top_y) * 0.18)), (cx, int(bot_y))],
        fill=(21, 24, 32, 160),
        width=notch_w,
    )

    # ── 5. Top highlight arc ──────────────────────────────────────────
    hl_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    hl_draw = ImageDraw.Draw(hl_layer)
    hl_draw.ellipse(
        [s * 0.1, -s * 0.45, s * 0.9, s * 0.25],
        fill=(255, 255, 255, 28),
    )
    # clip to rounded square
    hl_layer.putalpha(
        Image.composite(
            hl_layer.split()[3],
            Image.new("L", (s, s), 0),
            bg_mask,
        )
    )
    img = Image.alpha_composite(img, hl_layer)

    # ── 6. "S" badge (upper-left corner) ──────────────────────────────
    if size >= 48:
        badge_r = int(s * 0.155)
        badge_cx = int(s * 0.24)
        badge_cy = int(s * 0.245)

        # circle background
        draw = ImageDraw.Draw(img)
        draw.ellipse(
            [badge_cx - badge_r, badge_cy - badge_r,
             badge_cx + badge_r, badge_cy + badge_r],
            fill=(21, 24, 32, 210),
        )
        draw.ellipse(
            [badge_cx - badge_r, badge_cy - badge_r,
             badge_cx + badge_r, badge_cy + badge_r],
            outline=(200, 200, 200, 180),
            width=max(1, int(s * 0.012)),
        )

        # "S" text – use default font, scale to badge
        font_size = int(badge_r * 1.45)
        try:
            # Try to load a bundled font; fall back to default
            font = ImageFont.truetype("arialbd.ttf", font_size)
        except Exception:
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except Exception:
                font = ImageFont.load_default()

        draw.text(
            (badge_cx, badge_cy),
            "S",
            font=font,
            fill=(255, 255, 255, 245),
            anchor="mm",
        )

    return img


def main() -> None:
    print("Generating Sanitize V icon …")
    icon_512 = _make_icon(SIZE)

    png_path = os.path.join(ASSETS, "app_icon.png")
    icon_512.save(png_path, "PNG")
    print(f"  Saved {png_path}")

    # Build multi-size ICO
    ico_sizes = [16, 24, 32, 48, 64, 128, 256]
    frames: list[Image.Image] = []
    for sz in ico_sizes:
        frame = _make_icon(sz) if sz <= 64 else icon_512.resize((sz, sz), Image.LANCZOS)
        frames.append(frame)

    ico_path = os.path.join(ASSETS, "app_icon.ico")
    frames[0].save(
        ico_path,
        format="ICO",
        sizes=[(sz, sz) for sz in ico_sizes],
        append_images=frames[1:],
    )
    print(f"  Saved {ico_path}  ({len(ico_sizes)} sizes)")

    # Also save a sidebar logo at 64×64
    logo_64 = _make_icon(64)
    logo_path = os.path.join(ASSETS, "sidebar_logo.png")
    logo_64.save(logo_path, "PNG")
    print(f"  Saved {logo_path}")

    print("Done.")


if __name__ == "__main__":
    main()
