"""
generate_merch_designs.py — Pillow compositing for Arion World merch designs.

Takes an episode scene image and overlays branding:
  - Semi-transparent dark bar at top with "ARION WORLD" in white/gold
  - Episode number + title at bottom
  - "AW" watermark in corner
Returns paths to both a 16:9 poster crop and a square crop.
"""

import os
from pathlib import Path
from typing import Optional

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    print("WARNING: Pillow not installed. Merch design generation will be skipped.")


# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------

def _load_font(size: int, bold: bool = False) -> "ImageFont.FreeTypeFont | ImageFont.ImageFont":
    """Try to load a system font; fall back to PIL default."""
    candidates = []
    if bold:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:/Windows/Fonts/arial.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Core compositing
# ---------------------------------------------------------------------------

def _add_branding_overlay(img: "Image.Image", episode_number: int, episode_title: str) -> "Image.Image":
    """Add ARION WORLD header, episode info footer, and AW corner watermark."""
    draw = ImageDraw.Draw(img, "RGBA")
    w, h = img.size

    # ---- Top bar (semi-transparent black, 20% opacity) ----
    bar_height = max(60, h // 8)
    overlay = Image.new("RGBA", (w, bar_height), (0, 0, 0, 51))  # 51 ≈ 20% of 255
    img.paste(overlay, (0, 0), overlay)

    # ---- "ARION WORLD" text — white with gold outline effect ----
    font_title = _load_font(max(28, h // 20), bold=True)
    text_title = "ARION WORLD"

    # Gold outline — draw text offset in 4 directions
    gold = (212, 175, 55, 220)  # gold RGBA
    white = (255, 255, 255, 255)
    outline_offset = max(2, h // 200)

    title_bbox = draw.textbbox((0, 0), text_title, font=font_title)
    title_w = title_bbox[2] - title_bbox[0]
    title_x = (w - title_w) // 2
    title_y = (bar_height - (title_bbox[3] - title_bbox[1])) // 2

    for dx, dy in [(-outline_offset, 0), (outline_offset, 0), (0, -outline_offset), (0, outline_offset)]:
        draw.text((title_x + dx, title_y + dy), text_title, font=font_title, fill=gold)
    draw.text((title_x, title_y), text_title, font=font_title, fill=white)

    # ---- Bottom bar ----
    bottom_bar_height = max(60, h // 8)
    bottom_overlay = Image.new("RGBA", (w, bottom_bar_height), (0, 0, 0, 178))  # 70% opacity
    img.paste(bottom_overlay, (0, h - bottom_bar_height), bottom_overlay)

    # ---- Episode number + title at bottom ----
    font_ep = _load_font(max(20, h // 28), bold=True)
    font_sub = _load_font(max(16, h // 36), bold=False)

    ep_text = f"Episode {episode_number}"
    ep_bbox = draw.textbbox((0, 0), ep_text, font=font_ep)
    ep_w = ep_bbox[2] - ep_bbox[0]
    ep_x = (w - ep_w) // 2
    ep_y = h - bottom_bar_height + (bottom_bar_height // 5)
    draw.text((ep_x, ep_y), ep_text, font=font_ep, fill=gold)

    title_sub_bbox = draw.textbbox((0, 0), episode_title, font=font_sub)
    title_sub_w = title_sub_bbox[2] - title_sub_bbox[0]
    title_sub_x = (w - title_sub_w) // 2
    title_sub_y = ep_y + (ep_bbox[3] - ep_bbox[1]) + 6
    # Truncate if too wide
    max_chars = max(20, w // 14)
    display_title = episode_title if len(episode_title) <= max_chars else episode_title[:max_chars - 1] + "…"
    if display_title != episode_title:
        title_sub_bbox = draw.textbbox((0, 0), display_title, font=font_sub)
        title_sub_w = title_sub_bbox[2] - title_sub_bbox[0]
        title_sub_x = (w - title_sub_w) // 2
    draw.text((title_sub_x, title_sub_y), display_title, font=font_sub, fill=(220, 220, 220, 230))

    # ---- "AW" corner watermark ----
    font_wm = _load_font(max(18, h // 40), bold=True)
    wm_text = "AW"
    wm_bbox = draw.textbbox((0, 0), wm_text, font=font_wm)
    wm_x = w - (wm_bbox[2] - wm_bbox[0]) - 12
    wm_y = h - bottom_bar_height - (wm_bbox[3] - wm_bbox[1]) - 8
    draw.text((wm_x, wm_y), wm_text, font=font_wm, fill=(212, 175, 55, 80))

    return img


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_merch_designs(
    image_path: Path,
    episode_number: int,
    episode_title: str,
    output_dir: Optional[Path] = None,
) -> dict[str, Path]:
    """
    Generate branded merch designs from a scene image.

    Returns a dict with keys:
      - "poster"  — 16:9 (or original aspect) branded image (PNG)
      - "square"  — 1:1 square crop with branding (PNG)

    Both are written to output_dir (defaults to image_path's parent).
    """
    if not PIL_AVAILABLE:
        print("WARNING: Pillow not available — skipping design generation.")
        return {}

    image_path = Path(image_path)
    output_dir = Path(output_dir) if output_dir else image_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = image_path.stem
    ep_slug = f"ep{episode_number:03d}"

    # ---- Load source image ----
    src = Image.open(image_path).convert("RGBA")
    src_w, src_h = src.size

    # ---- Poster version (keep original size/aspect, add branding) ----
    poster_img = src.copy()
    poster_img = _add_branding_overlay(poster_img, episode_number, episode_title)
    poster_path = output_dir / f"{stem}_{ep_slug}_poster.png"
    poster_img.convert("RGB").save(poster_path, "PNG")
    print(f"  Generated poster design: {poster_path}")

    # ---- Square version (centre-crop to 1:1) ----
    if src_w > src_h:
        # Landscape → crop width
        offset = (src_w - src_h) // 2
        square_src = src.crop((offset, 0, offset + src_h, src_h))
    elif src_h > src_w:
        # Portrait → crop height
        offset = (src_h - src_w) // 2
        square_src = src.crop((0, offset, src_w, offset + src_w))
    else:
        square_src = src.copy()

    # Resize square to 1200×1200 for print quality
    square_img = square_src.resize((1200, 1200), Image.LANCZOS)
    square_img = _add_branding_overlay(square_img, episode_number, episode_title)
    square_path = output_dir / f"{stem}_{ep_slug}_square.png"
    square_img.convert("RGB").save(square_path, "PNG")
    print(f"  Generated square design: {square_path}")

    return {"poster": poster_path, "square": square_path}
