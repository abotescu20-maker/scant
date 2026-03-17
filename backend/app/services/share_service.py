"""
Share Service - generează carduri vizuale pentru sharing social.
Story Card: JPEG 1080x1920 (9:16) pentru Instagram Stories cu watermark ScanArt.
"""
import asyncio
import io
import textwrap
import httpx
from PIL import Image, ImageDraw, ImageFont


async def generate_story_card(
    result_url: str,
    filter_label: str,
    prompt_used: str,
) -> bytes:
    """Generează un JPEG 1080x1920 (9:16) pentru Instagram Stories.

    Layout:
    - Fundal negru
    - Imaginea artistică centrată (1080x1080) cu rounding
    - Filtru name mare
    - Primele 60 chars din prompt
    - Watermark "Made with ScanArt 🎨"
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _generate_story_card_sync, result_url, filter_label, prompt_used
    )


def _generate_story_card_sync(
    result_url: str,
    filter_label: str,
    prompt_used: str,
) -> bytes:
    W, H = 1080, 1920

    # ── Canvas negru ──────────────────────────────────────────────────────────
    canvas = Image.new("RGB", (W, H), (0, 0, 0))

    # ── Descarcă imaginea artistică ───────────────────────────────────────────
    art_img = _fetch_first_frame(result_url)

    # Resize să umple 1000x1000 (margini 40px pe fiecare parte)
    art_size = 1000
    art_img = art_img.resize((art_size, art_size), Image.LANCZOS)

    # Rounded corners pe artă (radius 40px)
    art_img = _add_rounded_corners(art_img, radius=40)

    # Paste centrat vertical (mai spre sus: top la 120px)
    art_y = 120
    art_x = (W - art_size) // 2
    canvas.paste(art_img, (art_x, art_y), art_img if art_img.mode == "RGBA" else None)

    # ── Gradient overlay jos ──────────────────────────────────────────────────
    grad_y = art_y + art_size - 200
    _draw_bottom_gradient(canvas, grad_y, H, (0, 0, 0))

    # ── Text ──────────────────────────────────────────────────────────────────
    draw = ImageDraw.Draw(canvas)
    font_large = _get_font(72)
    font_medium = _get_font(36)
    font_small = _get_font(28)

    text_y = art_y + art_size + 40

    # Filtru name
    draw.text((W // 2, text_y), filter_label, font=font_large, fill=(255, 255, 255), anchor="mt")
    text_y += 90

    # Prompt (trunchiat 80 chars, wrapped la 42 chars/linie)
    prompt_short = prompt_used[:80] + ("..." if len(prompt_used) > 80 else "")
    for line in textwrap.wrap(prompt_short, width=40):
        draw.text((W // 2, text_y), line, font=font_medium, fill=(180, 180, 180), anchor="mt")
        text_y += 46

    # Watermark jos centrat
    watermark = "Made with ScanArt"
    draw.text((W // 2, H - 80), watermark, font=font_small, fill=(100, 100, 100), anchor="mb")

    # Punct decorativ accent
    draw.ellipse(
        [(W // 2 - 3, H - 56), (W // 2 + 3, H - 50)],
        fill=(124, 58, 237)
    )

    # ── Encode JPEG ───────────────────────────────────────────────────────────
    output = io.BytesIO()
    canvas.save(output, format="JPEG", quality=92, optimize=True)
    return output.getvalue()


def _fetch_first_frame(url: str) -> Image.Image:
    """Descarcă URL-ul și extrage primul frame (funcționează cu GIF și JPEG/PNG)."""
    try:
        import httpx as _httpx
        response = _httpx.get(url, timeout=15)
        response.raise_for_status()
        img = Image.open(io.BytesIO(response.content))
        # Pentru GIF - extrage primul frame
        if hasattr(img, "n_frames") and img.n_frames > 1:
            img.seek(0)
        return img.convert("RGB")
    except Exception as e:
        print(f"share_service: could not fetch image {url}: {e}")
        # Fallback: gradient violet
        fallback = Image.new("RGB", (400, 400), (20, 5, 50))
        return fallback


def _add_rounded_corners(img: Image.Image, radius: int = 40) -> Image.Image:
    """Adaugă colțuri rotunjite unei imagini PIL (returnează RGBA)."""
    img = img.convert("RGBA")
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), (w - 1, h - 1)], radius=radius, fill=255)
    img.putalpha(mask)
    return img


def _draw_bottom_gradient(canvas: Image.Image, y_start: int, y_end: int, color: tuple):
    """Desenează un gradient de transparență de la transparent la negru."""
    draw = ImageDraw.Draw(canvas)
    total = y_end - y_start
    for i, y in enumerate(range(y_start, y_end)):
        alpha = int(255 * (i / total) ** 1.5)
        r = int(color[0] * (alpha / 255))
        g = int(color[1] * (alpha / 255))
        b = int(color[2] * (alpha / 255))
        draw.line([(0, y), (canvas.width, y)], fill=(r, g, b))


def _get_font(size: int) -> ImageFont.ImageFont:
    """Încearcă să încarce un font system, fallback la PIL default."""
    # Încearcă fonturi comune pe Linux/Alpine (Cloud Run)
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    # Fallback PIL default (nu suportă size pe versiunile vechi)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()
