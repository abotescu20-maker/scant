"""
Tier FREE: Gemini descrie → Imagen 3 Fast transformă artistic → NumPy animează cinematic.
10 filtre artistice: warhol, hokusai, klimt, ghibli, banksy, dali, vangogh, baroque, mondrian, mucha
2 moduri animatie: life (natural - clipit fata, shimmer cana, sway planta) | cinemagraph (o zona animata)
MediaPipe FaceMesh pentru detecție față → blink realist.
GIF 400x400px, 16 frame-uri, 80ms/frame (optimizat v18).
"""
import asyncio
import io
import math
import numpy as np
from PIL import Image, ImageFilter, ImageDraw, ImageFont
import google.generativeai as genai
from app.config import settings

N_FRAMES = 16  # Optimized: 16 frames × 80ms = 1.28s playback (was 24 × 60ms = 1.44s)


# ─── Mapare filtru → direcție artistică pentru Gemini ────────────────────────
STYLE_ARTISTIC_DIRECTION = {
    "warhol":   "Andy Warhol pop art silkscreen prints, bold flat colors, repetitive grid, vivid contrasting fills, Ben-Day dots, CMYK separation, commercial art aesthetic",
    "hokusai":  "Katsushika Hokusai ukiyo-e woodblock print, bold ink outlines, flat color washes, dynamic wave composition, Japanese traditional art, The Great Wave",
    "klimt":    "Gustav Klimt oil painting, gold leaf Byzantine mosaic patterns, ornate geometric borders, rich jewel tones, decorative symbolism, Portrait of Adele",
    "ghibli":   "Studio Ghibli hand-drawn animation cel, soft watercolor washes, Miyazaki pastoral fantasy, clean crisp linework, warm gentle lighting",
    "banksy":   "Banksy street art stencil, high contrast black and white spray paint, minimal color palette, single accent color, urban commentary, grunge texture",
    "dali":     "Salvador Dali surrealism, dreamlike impossible landscape, melting distorted objects, hyperrealistic precision, vast desert setting, The Persistence of Memory",
    "vangogh":  "Vincent van Gogh post-impressionist, thick swirling impasto brushstrokes, vibrant complementary colors, expressive texture, Starry Night turbulent sky",
    "baroque":  "Dutch Golden Age Baroque portrait, dramatic Caravaggio chiaroscuro, deep shadows, Rembrandt golden candlelight, rich textures, old master technique",
    "mondrian": "Piet Mondrian De Stijl geometric abstraction, primary colors red blue yellow, bold black grid lines, flat rectangular blocks, strict geometric composition",
    "mucha":    "Alphonse Mucha Art Nouveau poster, flowing ornate floral border, soft pastel palette, decorative circular halo, sinuous lines, feminine elegance",
}

# Gradient colors pentru preview filtre (start, end)
STYLE_GRADIENTS = {
    "warhol":   ("#ff0080", "#ffff00"),
    "hokusai":  ("#0066cc", "#00ccff"),
    "klimt":    ("#b8860b", "#ffd700"),
    "ghibli":   ("#2d8a4e", "#87ceeb"),
    "banksy":   ("#1a1a1a", "#555555"),
    "dali":     ("#c8a060", "#f0e070"),
    "vangogh":  ("#1a3a6b", "#f4a900"),
    "baroque":  ("#1a0a00", "#8b4513"),
    "mondrian": ("#cc0000", "#0033cc"),
    "mucha":    ("#d4a0b0", "#f5e0c0"),
}


# ─── Entry point async ───────────────────────────────────────────────────────
async def generate_video_free(
    image_bytes: bytes,
    style_id: str = "warhol",
    custom_prompt: str = None,
    progress_cb=None,
    animation_mode: str = "life",
    frame_delay: int = 80,
) -> tuple:
    """Returns (gif_bytes, prompt_used)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _generate_free_sync, image_bytes, style_id, custom_prompt, progress_cb, animation_mode, frame_delay
    )


def _generate_free_sync(
    image_bytes: bytes,
    style_id: str,
    custom_prompt: str = None,
    progress_cb=None,
    animation_mode: str = "life",
    frame_delay: int = 80,
) -> tuple:
    """Returns (gif_bytes, full_prompt_used)."""
    # Pas 1: Gemini construiește promptul artistic complet + detectează subject_type
    if progress_cb:
        progress_cb(42)
    if custom_prompt:
        full_prompt = custom_prompt
        subject_type = "object"  # default pentru custom prompt
    else:
        full_prompt, subject_type = _build_artistic_prompt(image_bytes, style_id)

    # Pas 2: Imagen 3 Fast generează imaginea artistică
    if progress_cb:
        progress_cb(55)
    art_image, full_prompt = _imagen_fast(full_prompt, style_id, prompt_is_final=True)

    # Pas 3: Animăm în funcție de mod
    if progress_cb:
        progress_cb(75)
    gif_bytes = _animate_artistic(art_image, style_id, subject_type, animation_mode, frame_delay)
    return gif_bytes, full_prompt


# ─── Gemini: prompt artistic + subject detection ──────────────────────────────
def _build_artistic_prompt(image_bytes: bytes, style_id: str) -> tuple:
    """Returns (artistic_prompt, subject_type).

    subject_type: face | cup | animal | plant | food | object
    """
    art_directions = STYLE_ARTISTIC_DIRECTION.get(style_id, STYLE_ARTISTIC_DIRECTION["dali"])

    PROMPT = f"""You are an art director creating an AI image generation prompt. Look at this photo and create a single Imagen prompt that reimagines the subject in a specific famous artist's style.

STEP 1 - On the VERY FIRST LINE, write ONLY one of these subject type words (nothing else on that line):
face | cup | animal | plant | food | object

Choose based on the main subject:
- face: if a person's face or portrait is prominent
- cup: if it's a mug, cup, glass, bottle, or drink container
- animal: if it's a pet, cat, dog, bird, or any animal
- plant: if it's a plant, flower, tree, or vegetation
- food: if it's food, meal, fruit, or edible item
- object: for everything else (building, car, gadget, furniture, etc.)

STEP 2 - Identify the subject precisely:
- People: age, gender, exact hair (color, cut style), facial hair, eye color, skin tone, clothing, expression
- Objects: exact material, precise color, shape, texture
- Animals: species, breed, colors, pose

STEP 3 - Write the final Imagen prompt combining subject + artwork reference.

Art movement to use: {art_directions}

Rules for the prompt:
- Mention the SPECIFIC artist name or artwork title
- Keep the subject RECOGNIZABLE and CENTRAL
- Include visual details: color palette, texture, technique, lighting
- 40-60 words total
- NO generic terms like "artistic", "beautiful", "stunning"

Examples:
- face on line 1, then: "young woman with curly red hair, reimagined as a Gustav Klimt portrait with gold leaf mosaic patterns, Byzantine ornamental borders, jewel tones of emerald and sapphire, oil on canvas, decorative symbolism"
- cup on line 1, then: "white ceramic coffee mug reimagined as Andy Warhol's Campbell's Soup Can pop art silkscreen print, bold flat colors, black outline, repetitive pattern, vivid red and white"
- animal on line 1, then: "orange tabby cat reimagined in Hiroshige ukiyo-e woodblock print style, bold ink outlines, flat color washes, cherry blossom background"

Return ONLY subject_type on line 1, then the final prompt on line 2+. Nothing else."""

    # Vertex AI (ADC - funcționează pe Cloud Run)
    try:
        import vertexai
        from vertexai.generative_models import GenerativeModel, Part

        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )
        model = GenerativeModel("gemini-2.0-flash-001")
        image_part = Part.from_data(data=image_bytes, mime_type="image/jpeg")
        response = model.generate_content([PROMPT, image_part])
        result = response.text.strip()
        return _parse_gemini_response(result)
    except Exception as e1:
        print(f"Gemini Vertex failed: {e1}")
        # Fallback: google-genai cu API key
        try:
            genai.configure(api_key=settings.google_api_key or None)
            model2 = genai.GenerativeModel("gemini-2.0-flash")
            response2 = model2.generate_content([
                PROMPT,
                {"mime_type": "image/jpeg", "data": image_bytes}
            ])
            result2 = response2.text.strip()
            return _parse_gemini_response(result2)
        except Exception as e2:
            print(f"Gemini API key also failed: {e2}")
            return "subject reimagined as a surreal Salvador Dali painting, melting forms, dreamlike landscape, vivid colors", "object"


def _parse_gemini_response(text: str) -> tuple:
    """Parsează răspunsul Gemini: prima linie = subject_type, restul = prompt."""
    VALID_SUBJECTS = {"face", "cup", "animal", "plant", "food", "object"}
    lines = text.strip().splitlines()
    if not lines:
        return text, "object"

    first_line = lines[0].strip().lower()
    if first_line in VALID_SUBJECTS:
        subject_type = first_line
        artistic_prompt = "\n".join(lines[1:]).strip()
    else:
        # Gemini nu a respectat formatul - detectăm subiectul din text
        subject_type = "object"
        for subj in VALID_SUBJECTS:
            if subj in text.lower():
                subject_type = subj
                break
        artistic_prompt = text

    print(f"Subject: {subject_type} | Prompt: {artistic_prompt[:80]}...")
    return artistic_prompt, subject_type


# ─── Imagen 3 Fast ────────────────────────────────────────────────────────────
def _imagen_fast(prompt: str, style_id: str, prompt_is_final: bool = False) -> tuple:
    """Imagen 3 Fast - generează imaginea artistică (~5s, quota separată).
    Returns (PIL Image, prompt_str)."""
    try:
        import vertexai
        from vertexai.preview.vision_models import ImageGenerationModel

        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.google_cloud_location,
        )

        full_prompt = prompt if prompt_is_final else prompt + ", masterpiece, highly detailed, 4k"

        model = ImageGenerationModel.from_pretrained("imagen-3.0-fast-generate-001")
        response = model.generate_images(
            prompt=full_prompt,
            number_of_images=1,
            aspect_ratio="1:1",
            safety_filter_level="block_few",
            person_generation="allow_all",
        )
        img = Image.open(io.BytesIO(response.images[0]._image_bytes)).convert("RGB")
        return img, full_prompt

    except Exception as e:
        print(f"Imagen Fast failed: {e}")
        return _color_gradient_fallback(style_id), f"[fallback] {prompt[:80]}"


def _color_gradient_fallback(style_id: str) -> Image.Image:
    colors = {
        "warhol":   [(255, 0, 128),  (255, 255, 0)],
        "hokusai":  [(0, 40, 140),   (0, 180, 220)],
        "klimt":    [(80, 50, 5),    (200, 160, 20)],
        "ghibli":   [(30, 100, 60),  (120, 190, 220)],
        "banksy":   [(15, 15, 15),   (70, 70, 70)],
        "dali":     [(160, 120, 60), (240, 210, 90)],
        "vangogh":  [(15, 30, 90),   (220, 140, 0)],
        "baroque":  [(20, 8, 0),     (110, 50, 15)],
        "mondrian": [(180, 0, 0),    (0, 40, 160)],
        "mucha":    [(200, 140, 160),(240, 220, 190)],
    }.get(style_id, [(20, 20, 50), (100, 50, 150)])
    h, w = 400, 400
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    c0, c1 = colors
    for y in range(h):
        t = y / h
        arr[y] = [int(c0[i] * (1 - t) + c1[i] * t) for i in range(3)]
    return Image.fromarray(arr)


# ─── Router animație ──────────────────────────────────────────────────────────
def _animate_artistic(
    img: Image.Image,
    style_id: str,
    subject_type: str = "object",
    animation_mode: str = "life",
    frame_delay: int = 80,
) -> bytes:
    """Animație cinematică - 400px, N_FRAMES frame-uri, frame_delay ms/fr."""
    img = img.resize((400, 400), Image.LANCZOS)

    if animation_mode == "cinemagraph":
        frames = _frames_cinemagraph(img, subject_type, style_id)
    else:
        frames = _frames_life(img, subject_type, style_id)

    # Adaugă watermark ScanArt pe fiecare frame
    frames = [_add_watermark(f) for f in frames]

    output = io.BytesIO()
    frames[0].save(
        output, format="GIF", save_all=True,
        append_images=frames[1:], loop=0, duration=frame_delay, optimize=False,
    )
    return output.getvalue()


def _add_watermark(img: Image.Image) -> Image.Image:
    """Adaugă watermark semi-transparent 'ScanArt' în colțul dreapta-jos."""
    img = img.convert("RGBA")
    w, h = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    text = "ScanArt.app"
    font_size = max(10, int(w * 0.030))  # ~12px la 400px — vizibil dar discret

    # Încearcă să folosești un font truetype; fallback la default PIL
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except Exception:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    margin = int(w * 0.025)
    x = w - tw - margin
    y = h - th - margin

    # Umbra (negru semi-transparent)
    draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0, 120))
    # Text alb semi-transparent
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 160))

    combined = Image.alpha_composite(img, overlay)
    return combined.convert("RGB")


# ─── MOD LIFE: animație naturală per subject ──────────────────────────────────
def _frames_life(img: Image.Image, subject_type: str, style_id: str) -> list:
    """Dispatcher: animație naturală bazată pe subiect + stil vizual."""
    # Animație specifică subiectului
    if subject_type == "face":
        return _frames_blink(img, style_id)
    elif subject_type == "cup":
        return _frames_shimmer(img, style_id)
    elif subject_type == "animal":
        return _frames_animal(img, style_id)
    elif subject_type in ("plant", "flower"):
        return _frames_sway(img, style_id)
    elif subject_type == "food":
        return _frames_glow_pulse(img, style_id)
    else:
        # Animație vizuală per filtru
        return _frames_style_visual(img, style_id)


def _frames_blink(img: Image.Image, style_id: str) -> list:
    """MediaPipe FaceMesh → clipit realist N_FRAMES frame-uri.
    Fallback la _frames_style_visual dacă nu detectează față."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]

    # Detectare față cu MediaPipe
    eye_mask = _detect_eye_mask(arr, h, w)
    if eye_mask is None:
        print("FaceMesh: no face detected, fallback to style visual")
        return _frames_style_visual(img, style_id)

    # 16 frame-uri: 6 open + 1 closing + 2 closed + 1 opening + 6 open
    blink_curve = (
        [0.0] * 6 +          # open
        [0.7] +              # closing
        [1.0, 1.0] +         # closed
        [0.7] +              # opening
        [0.0] * 6            # open
    )
    # Culoarea pleoapelor = media fruntii (top 15% din imagine)
    forehead = arr[:int(h * 0.15)]
    lid_color = forehead.mean(axis=(0, 1))

    frames = []
    for alpha in blink_curve:
        f = arr.copy()
        if alpha > 0.0:
            # Blend zona ochilor cu culoarea pleoapelor
            blend = eye_mask[:, :, np.newaxis] * alpha
            f = f * (1 - blend) + lid_color * blend
            # Linie subtire pentru pleoapa inchisa
            if alpha >= 0.8:
                rows = np.where(eye_mask.max(axis=1) > 0.3)[0]
                if len(rows) > 0:
                    mid_row = rows[len(rows) // 2]
                    lh = max(1, int(eye_mask.shape[0] * 0.008))
                    f[mid_row:mid_row + lh] *= 0.3
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _detect_eye_mask(arr: np.ndarray, h: int, w: int) -> np.ndarray | None:
    """Detectare ochi cu MediaPipe FaceMesh. Returns float32 mask (h,w) sau None."""
    try:
        import mediapipe as mp
        import cv2

        mp_face_mesh = mp.solutions.face_mesh
        img_uint8 = arr.astype(np.uint8)
        img_bgr = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2BGR)

        with mp_face_mesh.FaceMesh(
            static_image_mode=True,
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.3,
        ) as face_mesh:
            results = face_mesh.process(img_bgr)

        if not results.multi_face_landmarks:
            return None

        landmarks = results.multi_face_landmarks[0].landmark

        # Landmark-uri ochi (stâng + drept)
        LEFT_EYE  = [33, 160, 158, 133, 153, 144, 163, 7]
        RIGHT_EYE = [362, 385, 387, 263, 373, 380, 384, 398]

        mask = np.zeros((h, w), dtype=np.float32)
        for eye_pts in [LEFT_EYE, RIGHT_EYE]:
            xs = [int(landmarks[i].x * w) for i in eye_pts]
            ys = [int(landmarks[i].y * h) for i in eye_pts]
            cx, cy = sum(xs) // len(xs), sum(ys) // len(ys)
            rx = max(int((max(xs) - min(xs)) * 0.8), 10)
            ry = max(int((max(ys) - min(ys)) * 1.6), 6)
            # Elipsă Gaussian blur pentru tranziție naturală
            Y, X = np.ogrid[:h, :w]
            ellipse = np.clip(1.0 - ((X - cx) / rx) ** 2 - ((Y - cy) / ry) ** 2, 0, 1)
            mask = np.maximum(mask, ellipse)

        # Blur pentru margini moi
        from scipy.ndimage import gaussian_filter
        mask = gaussian_filter(mask, sigma=3)
        return mask

    except Exception as e:
        print(f"MediaPipe eye detection failed: {e}")
        return None


def _frames_shimmer(img: Image.Image, style_id: str) -> list:
    """Shimmer + abur pentru cup/drink - 16 frame-uri."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        f = arr.copy()
        # Highlight circular pe suprafata (shimmer)
        cx = int(w * (0.45 + 0.08 * math.sin(phase)))
        cy = int(h * 0.22)
        rx, ry = int(w * 0.12), int(h * 0.04)
        Y, X = np.ogrid[:h, :w]
        shimmer_mask = np.clip(1.0 - ((X - cx) / rx) ** 2 - ((Y - cy) / ry) ** 2, 0, 1)
        shimmer_intensity = 0.35 * (0.5 + 0.5 * math.sin(phase))
        f = f + shimmer_mask[:, :, np.newaxis] * shimmer_intensity * 255
        # Linii de abur (3 linii ascendente sinusoidal)
        steam_top = int(h * 0.05)
        steam_bot = int(h * 0.18)
        for k in range(3):
            sx = int(w * (0.35 + k * 0.12 + 0.03 * math.sin(phase + k * 1.2)))
            for sy in range(steam_top, steam_bot):
                px = sx + int(4 * math.sin((sy - steam_top) * 0.4 + phase + k))
                px = np.clip(px, 0, w - 1)
                alpha = 0.15 * (1 - (sy - steam_top) / (steam_bot - steam_top))
                if 0 <= sy < h:
                    f[sy, px] = np.clip(f[sy, px] + alpha * 255, 0, 255)
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_animal(img: Image.Image, style_id: str) -> list:
    """Urechi + coada animate - 16 frame-uri."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        f = arr.copy()
        # Zona superioara 20% (urechi) - warp sinusoidal
        ear_h = int(h * 0.20)
        shift = int(5 * math.sin(phase))
        f[:ear_h] = np.roll(f[:ear_h], shift, axis=1)
        # Zona dreapta-jos 15% (coada) - arc rotatie
        tail_h = int(h * 0.15)
        tail_w = int(w * 0.20)
        tail_shift = int(8 * math.sin(phase * 1.5))
        f[h - tail_h:, w - tail_w:] = np.roll(
            f[h - tail_h:, w - tail_w:], tail_shift, axis=0
        )
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_sway(img: Image.Image, style_id: str) -> list:
    """Legănat natural pentru plante - 16 frame-uri cu scipy."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    try:
        from scipy.ndimage import map_coordinates
    except ImportError:
        return _frames_style_visual(img, style_id)

    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        # Amplitudine scade de sus (varf ±10px) la baza (0px)
        amplitude = 10.0 * (1 - yc / h)
        dx = amplitude * np.sin(phase + yc * 0.03)
        src_x = np.clip(xc + dx, 0, w - 1)
        src_y = yc
        f = np.zeros_like(arr)
        for ch in range(3):
            f[:, :, ch] = map_coordinates(arr[:, :, ch], [src_y, src_x], order=1, mode='reflect')
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_glow_pulse(img: Image.Image, style_id: str) -> list:
    """Glow pulse radial pentru food - 16 frame-uri."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    dist = np.sqrt((xc - w / 2) ** 2 + (yc - h / 2) ** 2)
    max_dist = math.sqrt((w / 2) ** 2 + (h / 2) ** 2)
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        f = arr.copy()
        # Radial glow pulse
        glow_factor = 1.0 + 0.12 * math.sin(phase)
        radial_weight = np.clip(1.0 - dist / max_dist, 0, 1)[:, :, np.newaxis]
        f = f * (1.0 + (glow_factor - 1.0) * radial_weight)
        # Shimmer pe suprafata
        shimmer = 0.08 * np.sin(phase + dist * 0.08)[:, :, np.newaxis]
        f = f * (1 + shimmer)
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


# ─── Animații vizuale per filtru (mod "life" fallback + style flavor) ─────────
def _frames_style_visual(img: Image.Image, style_id: str) -> list:
    """Animație vizuală specifică filtrului - 16 frame-uri."""
    dispatch = {
        "warhol":   _frames_warhol,
        "hokusai":  _frames_hokusai,
        "klimt":    _frames_klimt,
        "ghibli":   _frames_ghibli,
        "banksy":   _frames_banksy,
        "dali":     _frames_dali,
        "vangogh":  _frames_vangogh,
        "baroque":  _frames_baroque,
        "mondrian": _frames_mondrian,
        "mucha":    _frames_mucha,
    }
    fn = dispatch.get(style_id, _frames_dali)
    return fn(img)


def _frames_warhol(img: Image.Image) -> list:
    """4-color grid flash alternativ (CMYK simulat pe 4 cadrane) - 24fr."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    hh, hw = h // 2, w // 2
    # 4 palette-uri Warhol
    palettes = [
        [(255, 0, 128), (255, 255, 0)],   # magenta/yellow
        [(0, 200, 255), (255, 100, 0)],   # cyan/orange
        [(150, 0, 255), (0, 255, 128)],   # purple/green
        [(255, 50, 0),  (0, 100, 255)],   # red/blue
    ]
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        f = arr.copy()
        quadrant_palette = palettes[i % 4]
        # Flash pe un cadran la rand
        q = i % 4
        if q == 0:
            region = f[:hh, :hw]
        elif q == 1:
            region = f[:hh, hw:]
        elif q == 2:
            region = f[hh:, :hw]
        else:
            region = f[hh:, hw:]
        # Colorizare puternică Warhol
        color = np.array(quadrant_palette[i // 6 % 2], dtype=np.float32)
        alpha = 0.35 * abs(math.sin(t * 2 * math.pi * 2))
        region_colored = region * (1 - alpha) + color * alpha
        if q == 0: f[:hh, :hw] = region_colored
        elif q == 1: f[:hh, hw:] = region_colored
        elif q == 2: f[hh:, :hw] = region_colored
        else: f[hh:, hw:] = region_colored
        # Contrast dur
        f = (f - 100) * 1.4 + 100
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_hokusai(img: Image.Image) -> list:
    """Wave sinusoidal de jos în sus (amplitudine 12px, frecvență) - 24fr."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        # Unda dinspre baza catre varf
        wave_amp = 12.0 * (yc / h)  # amplitudine creste spre baza
        dx = wave_amp * np.sin(2 * math.pi * xc / w * 3 + phase)
        src_x = np.clip(xc + dx, 0, w - 1).astype(int)
        src_y = yc.astype(int)
        f = arr[src_y, src_x].copy().astype(np.float32)
        # Albastru intens Hokusai
        f[:, :, 2] *= 1.0 + 0.15 * math.sin(phase)
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_klimt(img: Image.Image) -> list:
    """Golden shimmer diagonal - layer auriu semi-transparent - 24fr."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    gold = np.array([212, 175, 55], dtype=np.float32)  # gold color
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        f = arr.copy()
        # Shimmer diagonal care se deplasează
        diag = (xc + yc) / (h + w)
        shimmer = 0.28 * np.clip(np.sin(diag * 6 * math.pi + phase), 0, 1)[:, :, np.newaxis]
        f = f * (1 - shimmer) + gold * shimmer
        # Pattern geometric usor pulsant
        geo_mask = (np.sin(xc * 0.15) * np.sin(yc * 0.15) + 1) * 0.5
        geo_alpha = 0.08 * abs(math.sin(phase * 2))
        f = f * (1 - geo_alpha * geo_mask[:, :, np.newaxis]) + gold * (geo_alpha * geo_mask[:, :, np.newaxis])
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_ghibli(img: Image.Image) -> list:
    """Ken Burns zoom 1.0→1.08 + sway natural ±4px - 24fr."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    vx, vy = np.linspace(-1, 1, w), np.linspace(-1, 1, h)
    xg, yg = np.meshgrid(vx, vy)
    vignette = np.clip(1.0 - 0.4 * (xg ** 2 + yg ** 2), 0.4, 1.0)[:, :, np.newaxis]
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        # Ken Burns lent
        zoom = 1.0 + 0.08 * t
        pan_x = int(w * 0.04 * math.sin(t * math.pi))
        pan_y = int(h * 0.02 * (1 - math.cos(t * math.pi)))
        nw, nh = int(w * zoom), int(h * zoom)
        tmp = Image.fromarray(arr.astype(np.uint8)).resize((nw, nh), Image.LANCZOS)
        lx = max(0, min((nw - w) // 2 + pan_x, nw - w))
        ty = max(0, min((nh - h) // 2 + pan_y, nh - h))
        f = np.array(tmp.crop((lx, ty, lx + w, ty + h)), dtype=np.float32)
        # Warm shimmer
        f[:, :, 0] *= 1.0 + 0.06 * math.sin(t * 2 * math.pi)
        f[:, :, 1] *= 1.0 + 0.04 * math.sin(t * 2 * math.pi + 0.5)
        # Soft glow
        glow_img = Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(3))
        glow = np.array(glow_img, dtype=np.float32)
        f = f * 0.85 + glow * 0.15
        f *= vignette
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_banksy(img: Image.Image) -> list:
    """High contrast flicker + grain noise - 24fr."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    frames = []
    rng = np.random.default_rng(42)
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        f = arr.copy()
        # High contrast B&W flicker
        gray = 0.299 * f[:, :, 0] + 0.587 * f[:, :, 1] + 0.114 * f[:, :, 2]
        contrast = 1.5 + 0.3 * math.sin(phase)
        gray = np.clip((gray - 128) * contrast + 128, 0, 255)
        # Accent color (roscat)
        accent_mask = (f[:, :, 0] > f[:, :, 1] + 40).astype(np.float32)
        f[:, :, 0] = gray * (1 - accent_mask * 0.5) + f[:, :, 0] * accent_mask * 0.5
        f[:, :, 1] = gray * (1 - accent_mask * 0.3)
        f[:, :, 2] = gray * (1 - accent_mask * 0.3)
        # Grain noise
        noise = rng.normal(0, 8 + 4 * abs(math.sin(phase * 3)), (h, w, 3))
        f = f + noise
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_dali(img: Image.Image) -> list:
    """Wave fluid lent + color rotation - 24fr."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        # Distorsiune fluid Dali
        dx = (14 * np.sin(3 * math.pi * yc / h + phase)).astype(int)
        dy = (10 * np.cos(3 * math.pi * xc / w + phase * 0.7)).astype(int)
        sx = np.clip(xc.astype(int) + dx, 0, w - 1)
        sy = np.clip(yc.astype(int) + dy, 0, h - 1)
        f = arr[sy, sx].copy().astype(np.float32)
        # Color rotation subtila
        mix = 0.18 * abs(math.sin(phase))
        r, b = f[:, :, 0].copy(), f[:, :, 2].copy()
        f[:, :, 0] = r * (1 - mix) + b * mix
        f[:, :, 2] = b * (1 - mix) + r * mix
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_vangogh(img: Image.Image) -> list:
    """Swirl spiral simulat prin warp + brushstroke texture - 24fr."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    cy, cx = h / 2, w / 2
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    dist = np.sqrt((xc - cx) ** 2 + (yc - cy) ** 2)
    angle = np.arctan2(yc - cy, xc - cx)
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        # Swirl: rotatie progresiva care scade cu distanta
        swirl_strength = 0.25 * math.sin(phase)
        swirl_angle = angle + swirl_strength * np.exp(-dist / (h * 0.4))
        src_x = np.clip(cx + dist * np.cos(swirl_angle), 0, w - 1).astype(int)
        src_y = np.clip(cy + dist * np.sin(swirl_angle), 0, h - 1).astype(int)
        f = arr[src_y, src_x].copy().astype(np.float32)
        # Saturatie ridicata Van Gogh
        gray = 0.299 * f[:, :, 0] + 0.587 * f[:, :, 1] + 0.114 * f[:, :, 2]
        sat = 1.3 + 0.1 * math.sin(phase)
        f = gray[:, :, np.newaxis] + (f - gray[:, :, np.newaxis]) * sat
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_baroque(img: Image.Image) -> list:
    """Candlelight flicker: vignette brightness ±18% pulsatie - 24fr."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    vx, vy = np.linspace(-1, 1, w), np.linspace(-1, 1, h)
    xg, yg = np.meshgrid(vx, vy)
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        f = arr.copy()
        # Flicker lumina lumanare
        flicker = 1.0 + 0.18 * math.sin(phase) + 0.06 * math.sin(phase * 3.7)
        # Vigneta dramatica Baroque
        vignette = np.clip(1.0 - 0.7 * (xg ** 2 + yg ** 2), 0.08, 1.0)[:, :, np.newaxis]
        f = f * flicker * vignette
        # Warm tone (portocaliu/galben)
        f[:, :, 0] *= 1.0 + 0.08 * math.sin(phase)
        f[:, :, 1] *= 1.0 + 0.04 * math.sin(phase)
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_mondrian(img: Image.Image) -> list:
    """Random dreptunghiuri color care flash-uiesc - 24fr."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    # Mondrian primary colors
    mondrian_colors = [
        np.array([220, 20, 20], dtype=np.float32),   # red
        np.array([20, 60, 200], dtype=np.float32),    # blue
        np.array([240, 210, 20], dtype=np.float32),   # yellow
        np.array([240, 240, 240], dtype=np.float32),  # white
    ]
    # Grid Mondrian fix (5x5 celule)
    cells_y = np.linspace(0, h, 5, dtype=int)
    cells_x = np.linspace(0, w, 5, dtype=int)
    rng = np.random.default_rng(77)
    cell_colors = rng.integers(0, len(mondrian_colors), (4, 4))

    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        f = arr.copy()
        # Flash celule rand pe rand
        active_cell = i % (4 * 4)
        cy_idx, cx_idx = divmod(active_cell, 4)
        y0, y1 = cells_y[cy_idx], cells_y[cy_idx + 1]
        x0, x1 = cells_x[cx_idx], cells_x[cx_idx + 1]
        color = mondrian_colors[cell_colors[cy_idx, cx_idx]]
        alpha = 0.45 * abs(math.sin(phase * 2))
        f[y0:y1, x0:x1] = f[y0:y1, x0:x1] * (1 - alpha) + color * alpha
        # Linii negre Mondrian
        for gy in cells_y:
            thickness = 3
            f[max(0, gy - 1):min(h, gy + thickness)] = f[max(0, gy - 1):min(h, gy + thickness)] * 0.1
        for gx in cells_x:
            thickness = 3
            f[:, max(0, gx - 1):min(w, gx + thickness)] = f[:, max(0, gx - 1):min(w, gx + thickness)] * 0.1
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


def _frames_mucha(img: Image.Image) -> list:
    """Soft glow pastelat + color shimmer radial - 24fr."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)
    dist = np.sqrt((xc - w / 2) ** 2 + (yc - h / 2) ** 2)
    max_dist = math.sqrt((w / 2) ** 2 + (h / 2) ** 2)
    # Pastel Mucha colors
    mucha_pastel = np.array([245, 215, 195], dtype=np.float32)
    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi
        f = arr.copy()
        # Radial shimmer pastelat
        radial = np.clip(1.0 - dist / max_dist, 0, 1)[:, :, np.newaxis]
        shimmer_alpha = 0.20 * (0.5 + 0.5 * math.sin(phase))
        f = f * (1 - shimmer_alpha * radial) + mucha_pastel * (shimmer_alpha * radial)
        # Soft glow Gaussian
        glow_img = Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5))
        glow = np.array(glow_img, dtype=np.float32)
        f = f * 0.80 + glow * 0.20
        # Brightness puls subtil
        f *= 1.0 + 0.06 * math.sin(phase)
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))
    return frames


# ─── MOD CINEMAGRAPH: o singură zonă animată ──────────────────────────────────
def _frames_cinemagraph(img: Image.Image, subject_type: str, style_id: str) -> list:
    """Cinemagraph: base frame static + o zonă animată per subject_type."""
    arr = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]

    # Definim zona animată (mask normalizată 0.0-1.0)
    motion_mask = _get_cinemagraph_mask(subject_type, h, w)

    frames = []
    for i in range(N_FRAMES):
        t = i / N_FRAMES
        phase = t * 2 * math.pi

        # Animație pentru zona respectivă
        animated = _apply_cinemagraph_motion(arr, subject_type, style_id, phase, h, w)

        # Composite: static + animated
        mask3 = motion_mask[:, :, np.newaxis]
        f = arr * (1 - mask3) + animated * mask3
        frames.append(Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)))

    return frames


def _get_cinemagraph_mask(subject_type: str, h: int, w: int) -> np.ndarray:
    """Returns soft float32 mask (h,w) pentru zona animată cinemagraph."""
    try:
        from scipy.ndimage import gaussian_filter
    except ImportError:
        gaussian_filter = None

    mask = np.zeros((h, w), dtype=np.float32)
    yc, xc = np.mgrid[0:h, 0:w].astype(np.float32)

    if subject_type == "face":
        # Zona ochilor (25-40% height, 20-80% width)
        cy, cx = h * 0.32, w * 0.5
        ry, rx = h * 0.08, w * 0.30
        mask = np.clip(1.0 - ((xc - cx) / rx) ** 2 - ((yc - cy) / ry) ** 2, 0, 1)
    elif subject_type == "cup":
        # Zona superioara 0-18%
        mask[:int(h * 0.18)] = 1.0
        # Fade lin
        fade_rows = int(h * 0.05)
        for row in range(int(h * 0.13), int(h * 0.18)):
            mask[row] = max(0, 1.0 - (row - int(h * 0.13)) / fade_rows)
    elif subject_type == "animal":
        # Colturi sus (urechi)
        mask[:int(h * 0.22), :int(w * 0.30)] = 0.8
        mask[:int(h * 0.22), int(w * 0.70):] = 0.8
    elif subject_type in ("plant", "flower"):
        # Zona superioara 30%
        mask[:int(h * 0.30)] = 1.0
        fade_rows = int(h * 0.08)
        for row in range(int(h * 0.22), int(h * 0.30)):
            mask[row] = max(0, 1.0 - (row - int(h * 0.22)) / fade_rows)
    else:
        # Centru oval
        cy, cx = h * 0.5, w * 0.5
        ry, rx = h * 0.25, w * 0.25
        mask = np.clip(1.0 - ((xc - cx) / rx) ** 2 - ((yc - cy) / ry) ** 2, 0, 1)

    if gaussian_filter is not None:
        mask = gaussian_filter(mask, sigma=8)
    return np.clip(mask, 0, 1).astype(np.float32)


def _apply_cinemagraph_motion(
    arr: np.ndarray, subject_type: str, style_id: str,
    phase: float, h: int, w: int
) -> np.ndarray:
    """Aplică mișcarea animată pe toată imaginea (mascat ulterior)."""
    f = arr.copy()
    yc_mg, xc_mg = np.mgrid[0:h, 0:w].astype(np.float32)

    if subject_type == "face":
        # Brightness oscillation in zona ochilor
        brightness = 1.0 + 0.18 * math.sin(phase)
        f = f * brightness
    elif subject_type == "cup":
        # Shimmer horizontal sus
        shift = int(6 * math.sin(phase))
        f[:int(h * 0.18)] = np.roll(f[:int(h * 0.18)], shift, axis=1)
    elif subject_type == "animal":
        # Warp subtil ±3px
        dx = (3 * np.sin(phase + yc_mg * 0.05)).astype(int)
        src_x = np.clip(xc_mg.astype(int) + dx, 0, w - 1)
        src_y = yc_mg.astype(int)
        f = f[src_y, src_x].copy()
    elif subject_type in ("plant", "flower"):
        # Horizontal wave ±3px
        amplitude = 3.0 * (1 - yc_mg / h)
        dx = (amplitude * np.sin(phase + yc_mg * 0.04)).astype(int)
        src_x = np.clip(xc_mg.astype(int) + dx, 0, w - 1)
        src_y = yc_mg.astype(int)
        f = f[src_y, src_x].copy()
    else:
        # Contrast pulse
        contrast = 1.0 + 0.15 * math.sin(phase)
        f = (f - 128) * contrast + 128

    return f.astype(np.float32)
