import uuid
import asyncio
import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse, Response, HTMLResponse
from app.models.schemas import (
    StyleId, QualityTier, AnimationMode,
    RegenerateRequest, InspireRequest, StorycardRequest,
    GenerateResponse, StatusResponse,
)
from app.services.gemini_service import generate_creative_prompt, generate_prompt_variations
from app.services.veo_service import generate_video_from_image
from app.services.hf_service import generate_video_free, suggest_styles
from app.services.storage_service import upload_video, upload_thumbnail, upload_original, generate_share_code
from app.services import db_service
from app.services import share_service

router = APIRouter()

APP_URL = "https://storage.googleapis.com/scanart-frontend-1772986018/index.html"

# Store simplu in-memory pentru status job-uri
_jobs: dict[str, dict] = {}

# Rate limiting: per-IP daily quota (testing phase: 100/day/IP)
DAILY_IP_LIMIT = 100
_ip_counters: dict[str, dict] = {}  # {ip: {"date": "2026-04-16", "count": 5}}

# Master IPs bypass rate limit (unlimited). Add via env var MASTER_IPS (comma-separated).
import os
_hardcoded_master_ips = {"82.78.233.115"}  # Andrei's IP
_env_master_ips = set(filter(None, (ip.strip() for ip in os.getenv("MASTER_IPS", "").split(","))))
MASTER_IPS = _hardcoded_master_ips | _env_master_ips

def _extract_client_ips(request: Request) -> list[str]:
    """Extract ALL possible client IPs from headers (Cloud Run adds multiple)."""
    ips = []
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        ips.extend(ip.strip() for ip in xff.split(",") if ip.strip())
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        ips.append(real_ip)
    if request.client:
        ips.append(request.client.host)
    return ips

def _check_rate_limit(request: Request) -> None:
    """Raise HTTPException 429 if IP has exceeded daily quota. Master IPs bypass."""
    ips = _extract_client_ips(request)

    # Master IPs: unlimited (check ALL headers)
    if any(ip in MASTER_IPS for ip in ips):
        return

    # Use first IP as counter key (original client)
    primary_ip = ips[0] if ips else "unknown"
    print(f"[RATE_LIMIT] ips={ips} primary={primary_ip}")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = _ip_counters.get(primary_ip)
    if entry is None or entry["date"] != today:
        _ip_counters[primary_ip] = {"date": today, "count": 0}
        entry = _ip_counters[primary_ip]

    if entry["count"] >= DAILY_IP_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Limita zilnica atinsa ({DAILY_IP_LIMIT} generari/IP). Revino maine.",
        )
    entry["count"] += 1


@router.get("/tiers")
async def get_tiers():
    return {
        "tiers": [
            {"id": "free",     "label": "Gratuit",  "desc": "Imagen 3 Art + animatie",  "cost": "$0",     "duration": "GIF", "emoji": "🎨"},
            {"id": "standard", "label": "Standard", "desc": "Veo 3 Fast",               "cost": "~$0.60", "duration": "4s",  "emoji": "⚡"},
            {"id": "premium",  "label": "Premium",  "desc": "Veo 3 Full HD",            "cost": "~$4.00", "duration": "8s",  "emoji": "👑"},
        ]
    }


@router.post("/generate", response_model=dict)
async def start_generation(
    request: Request,
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    style_id: StyleId = Form(...),
    quality: QualityTier = Form(QualityTier.standard),
    session_id: str = Form(...),
    animation_mode: AnimationMode = Form(AnimationMode.life),
    frame_delay: int = Form(80),
    ref_source: str = Form(None),  # referral viral tracking (optional)
):
    _check_rate_limit(request)

    import re
    if image.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Format imagine invalid.")
    image_bytes = await image.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Imaginea e prea mare (max 10MB).")

    # Sanitize ref_source: only accept valid 8-char hex share codes
    if ref_source and not re.match(r'^[0-9a-f]{8}$', ref_source.strip()):
        ref_source = None

    job_id = str(uuid.uuid4())
    creation_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "pending", "progress": 0, "result": None, "error": None}

    background_tasks.add_task(
        _run_generation_pipeline,
        job_id=job_id,
        creation_id=creation_id,
        image_bytes=image_bytes,
        style_id=style_id,
        quality=quality,
        session_id=session_id,
        animation_mode=animation_mode,
        frame_delay=max(20, min(200, frame_delay)),
        ref_source=ref_source,
    )
    return {"job_id": job_id}


@router.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job negasit.")
    return StatusResponse(**job)


@router.get("/history/{session_id}")
async def get_history(session_id: str):
    items = await db_service.get_session_history(session_id, limit=30)
    return {"history": items}


@router.get("/suggest-styles")
async def api_suggest_styles(subject_type: str = "object", mood: str = ""):
    """Suggest best art styles for a subject type + optional mood keywords.
    Example: /api/suggest-styles?subject_type=face&mood=dark,dramatic"""
    mood_kw = [m.strip() for m in mood.split(",") if m.strip()] if mood else None
    results = suggest_styles(subject_type, mood_kw, top_n=5)
    return {"suggestions": results}


@router.get("/style-stats")
async def get_style_stats():
    """Style performance analytics — success rate, avg time, subject breakdown per style."""
    stats = await db_service.get_style_stats()
    return {"styles": stats}


@router.get("/trending")
async def get_trending(period: str = "week", limit: int = 20):
    """Returnează creațiile trending din perioada specificată (public)."""
    if period not in ("week", "month", "all"):
        period = "week"
    limit = max(1, min(50, limit))
    items = await db_service.get_trending(period=period, limit=limit)
    return {"items": items}


@router.get("/share/{share_code}", response_class=HTMLResponse)
async def share_page(share_code: str):
    """Landing page viral pentru share link — HTML embed cu Open Graph + preview GIF."""
    item = await db_service.get_by_share_code(share_code)

    if not item:
        # Fallback graceful: redirect la app
        return HTMLResponse(content=f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="0;url={APP_URL}">
  <title>ScanArt</title>
</head>
<body>
  <script>window.location.href = "{APP_URL}";</script>
</body>
</html>""", status_code=200)

    video_url = item.get("video_url", "")
    thumbnail_url = item.get("thumbnail_url", "")
    style_id = item.get("style_id", "warhol")
    quality = item.get("quality", "free")

    # Label pentru filtru
    style_labels = {
        # Original 10
        "warhol": "Warhol Pop Art", "hokusai": "Hokusai Ukiyo-e", "klimt": "Klimt Gold",
        "ghibli": "Ghibli Animation", "banksy": "Banksy Stencil", "dali": "Dalí Surreal",
        "vangogh": "Van Gogh Impasto", "baroque": "Baroque Chiaroscuro", "mondrian": "Mondrian De Stijl",
        "mucha": "Mucha Nouveau",
        # 20 new styles
        "meiji_print": "Meiji Print", "persian_mini": "Persian Miniature", "mughal_mini": "Mughal Miniature",
        "byzantine": "Byzantine Mosaic", "preraphaelite": "Pre-Raphaelite", "expressionism": "Expressionist",
        "futurism": "Futurist", "constructivism": "Constructivist", "swiss_poster": "Swiss Grid Poster",
        "pointillism": "Pointillist", "risograph": "Risograph Print", "woodcut": "Woodcut",
        "ligne_claire": "Ligne Claire", "daguerreotype": "Daguerreotype", "infrared": "Infrared Film",
        "lomography": "Lomography", "cyberpunk": "Cyberpunk Neon", "brutalist": "Brutalist",
        "wpa_poster": "WPA Poster", "zine_collage": "Zine Collage",
    }
    style_label = style_labels.get(style_id, style_id.replace("_", " ").title())
    quality_label = {"free": "GIF Animat", "standard": "Video HD", "premium": "Video Full HD"}.get(quality, "")

    og_image = thumbnail_url or video_url
    og_title = f"Am creat o operă de artă cu ScanArt — {style_label}!"
    og_desc = f"Transformă orice fotografie într-o operă animată în stil {style_label}. {quality_label}. Gratuit."
    install_url = APP_URL

    is_gif = video_url.endswith(".gif")
    # Video element — autoplay pentru ambele formate (GIF servit ca video source)
    if video_url:
        media_el = f'<video autoplay loop muted playsinline class="bg-video"><source src="{video_url}" /></video>'
    else:
        media_el = f'<div class="bg-video" style="background:linear-gradient(135deg,#1a0840,#000)"></div>'

    html = f"""<!DOCTYPE html>
<html lang="ro">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <title>{og_title}</title>
  <!-- Open Graph -->
  <meta property="og:title" content="{og_title}" />
  <meta property="og:description" content="{og_desc}" />
  <meta property="og:image" content="{og_image}" />
  <meta property="og:url" content="https://scanart-backend-603810013022.us-central1.run.app/api/share/{share_code}" />
  <meta property="og:type" content="website" />
  <!-- Twitter Card -->
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{og_title}" />
  <meta name="twitter:description" content="{og_desc}" />
  <meta name="twitter:image" content="{og_image}" />
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #000; color: #fff; overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      height: 100dvh; position: relative;
    }}
    .bg-video {{
      position: fixed; inset: 0; width: 100%; height: 100%;
      object-fit: cover; z-index: 0;
    }}
    .overlay {{
      position: fixed; inset: 0; z-index: 1;
      background: linear-gradient(to top, rgba(0,0,0,.92) 0%, rgba(0,0,0,.15) 50%, transparent 100%);
    }}
    .cta-panel {{
      position: fixed; bottom: 0; left: 0; right: 0; z-index: 2;
      padding: 1.5rem 1.5rem env(safe-area-inset-bottom, 1.5rem);
    }}
    .style-badge {{
      display: inline-flex; align-items: center; gap: .4rem;
      background: rgba(124,58,237,.3); border: 1px solid rgba(124,58,237,.5);
      border-radius: 100px; padding: .3rem .9rem; font-size: .82rem; color: #c4b5fd;
      margin-bottom: .9rem;
    }}
    h1 {{
      font-size: clamp(1.4rem, 6vw, 1.9rem); font-weight: 800; line-height: 1.2;
      margin-bottom: .5rem;
    }}
    p {{ color: rgba(255,255,255,.6); font-size: .9rem; line-height: 1.5; margin-bottom: 1.4rem; }}
    .cta-btn {{
      display: block; width: 100%; background: #fff; color: #000;
      border: none; border-radius: 100px; padding: 1rem 2rem;
      font-size: 1.05rem; font-weight: 800; cursor: pointer; text-decoration: none;
      text-align: center; margin-bottom: .65rem;
      transition: transform .15s, opacity .15s;
    }}
    .cta-btn:active {{ transform: scale(.96); opacity: .85; }}
    .cta-sub {{ font-size: .76rem; color: rgba(255,255,255,.35); text-align: center; margin-bottom: .8rem; }}
    .challenge-btn {{
      display: block; width: 100%; text-align: center; padding: .75rem;
      border: 1px solid rgba(124,58,237,.5); border-radius: 100px;
      color: #c4b5fd; font-size: .9rem; font-weight: 700; text-decoration: none;
      background: rgba(124,58,237,.15); margin-top: .2rem;
      transition: background .15s;
    }}
    .challenge-btn:active {{ background: rgba(124,58,237,.35); }}
    .scan-logo {{
      position: fixed; top: env(safe-area-inset-top, 1rem); left: 50%;
      transform: translateX(-50%); z-index: 3;
      font-size: .8rem; font-weight: 700; color: rgba(255,255,255,.55);
      letter-spacing: .1em; text-transform: uppercase;
    }}
  </style>
</head>
<body>
  {media_el}
  <div class="overlay"></div>
  <div class="scan-logo">🎨 ScanArt</div>
  <div class="cta-panel">
    <div class="style-badge">🎨 {style_label} · {quality_label}</div>
    <h1>Uimitoare, nu-i așa?<br>Creează și tu!</h1>
    <p>ScanArt transformă orice fotografie într-o operă animată cu AI. Gratuit, în 30 de secunde.</p>
    <a href="{install_url}?ref={share_code}" class="cta-btn">📷 Încearcă ScanArt Gratuit →</a>
    <div class="cta-sub">PWA · Fără instalare · Funcționează instant</div>
    <a href="{install_url}?challenge={style_id}&ref={share_code}" class="challenge-btn">
      🎯 Poți face asta în alt stil? →
    </a>
  </div>
</body>
</html>"""

    return HTMLResponse(content=html, headers={
        "Cache-Control": "public, max-age=3600",
    })


@router.post("/generate-multi", response_model=dict)
async def start_generation_multi(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    style_id: StyleId = Form(...),
    quality: QualityTier = Form(QualityTier.free),
    session_id: str = Form(...),
    animation_mode: AnimationMode = Form(AnimationMode.life),
    frame_delay: int = Form(80),
    variants: int = Form(3),
):
    """Generează N variante simultan ale aceluiași stil (doar pentru tier free)."""
    if image.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Format imagine invalid.")
    image_bytes = await image.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Imaginea e prea mare (max 10MB).")

    # Forțăm free pentru multi-variant (cost control)
    quality = QualityTier.free
    n = max(1, min(3, variants))  # max 3 variante

    job_ids = []
    for _ in range(n):
        job_id = str(uuid.uuid4())
        creation_id = str(uuid.uuid4())
        _jobs[job_id] = {"status": "pending", "progress": 0, "result": None, "error": None}
        background_tasks.add_task(
            _run_generation_pipeline,
            job_id=job_id,
            creation_id=creation_id,
            image_bytes=image_bytes,
            style_id=style_id,
            quality=quality,
            session_id=session_id,
            animation_mode=animation_mode,
            frame_delay=max(20, min(200, frame_delay)),
        )
        job_ids.append(job_id)

    return {"job_ids": job_ids, "variants": n}


@router.post("/generate-blend", response_model=dict)
async def start_blend_generation(
    request: Request,
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    style_a: StyleId = Form(...),
    style_b: StyleId = Form(...),
    blend_ratio: float = Form(0.5),  # 0.0 = all A, 1.0 = all B, 0.5 = even mix
    session_id: str = Form(...),
    animation_mode: AnimationMode = Form(AnimationMode.life),
    frame_delay: int = Form(80),
):
    """Generează artwork care combină 2 stiluri cu un ratio (style blending)."""
    _check_rate_limit(request)
    if image.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Format imagine invalid.")
    image_bytes = await image.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Imaginea e prea mare (max 10MB).")

    blend_ratio = max(0.0, min(1.0, blend_ratio))
    job_id = str(uuid.uuid4())
    creation_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "pending", "progress": 0, "result": None, "error": None}

    background_tasks.add_task(
        _run_blend_pipeline,
        job_id=job_id,
        creation_id=creation_id,
        image_bytes=image_bytes,
        style_a=style_a,
        style_b=style_b,
        blend_ratio=blend_ratio,
        session_id=session_id,
        animation_mode=animation_mode,
        frame_delay=max(20, min(200, frame_delay)),
    )
    return {"job_id": job_id, "style_a": style_a.value, "style_b": style_b.value, "blend_ratio": blend_ratio}


async def _run_blend_pipeline(
    job_id: str, creation_id: str, image_bytes: bytes,
    style_a: StyleId, style_b: StyleId, blend_ratio: float,
    session_id: str, animation_mode: AnimationMode, frame_delay: int,
):
    """Pipeline pentru style blending: combinăm prompturile a 2 stiluri."""
    try:
        from app.services.hf_service import generate_video_blend
        _jobs[job_id]["status"] = "processing"
        _jobs[job_id]["progress"] = 10

        def _cb(pct):
            _jobs[job_id]["progress"] = pct

        video_bytes, prompt = await generate_video_blend(
            image_bytes, style_a.value, style_b.value, blend_ratio,
            progress_cb=_cb,
            animation_mode=animation_mode.value,
            frame_delay=frame_delay,
            session_id=session_id,
        )

        _jobs[job_id]["progress"] = 85
        video_url, thumbnail_url, original_url = await asyncio.gather(
            upload_video(video_bytes, creation_id),
            upload_thumbnail(video_bytes, creation_id),
            upload_original(image_bytes, creation_id),
        )

        # Use combined style label for display
        blend_style_id = f"{style_a.value}+{style_b.value}"
        share_code = generate_share_code()

        result = GenerateResponse(
            creation_id=creation_id,
            video_url=video_url,
            thumbnail_url=thumbnail_url,
            prompt_used=prompt or "",
            style_id=blend_style_id,
            quality="free",
            share_code=share_code,
        )

        await db_service.save_creation(
            creation_id=creation_id,
            session_id=session_id,
            style_id=blend_style_id,
            quality="free",
            prompt_used=prompt or "",
            video_url=video_url,
            thumbnail_url=thumbnail_url,
            share_code=share_code,
            original_url=original_url,
        )

        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["progress"] = 100
        _jobs[job_id]["result"] = result.model_dump()
    except Exception as e:
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(e)


# Refinement loop: user says "make it more X" → Gemini rewrites → Imagen regenerates
REFINE_DIRECTIONS = {
    "darker": "darker, moodier, deeper shadows, more dramatic chiaroscuro, richer blacks",
    "brighter": "brighter, more luminous, higher key lighting, glowing highlights, airier feel",
    "more_color": "more saturated colors, bolder palette, vibrant contrasts, intense hues",
    "less_color": "desaturated, muted palette, restrained colors, earthy tones",
    "more_abstract": "more abstract, looser interpretation, simplified forms, less literal",
    "more_detailed": "more detailed, richer textures, finer brushwork, more visible material quality",
    "softer": "softer, dreamier, smoother transitions, more painterly, less crisp",
    "sharper": "sharper, more defined edges, stronger contrasts, crisper lines",
}

@router.post("/refine", response_model=dict)
async def start_refine(
    request: Request,
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    style_id: StyleId = Form(...),
    direction: str = Form(...),  # preset key OR free text (custom refinement)
    session_id: str = Form(...),
    animation_mode: AnimationMode = Form(AnimationMode.life),
    frame_delay: int = Form(80),
):
    """Refinement loop: regenerate with creative direction modifier.
    Accepts preset keys (darker, brighter, etc.) OR free text (e.g. 'make it glow with neon')."""
    _check_rate_limit(request)
    if image.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Format imagine invalid.")
    image_bytes = await image.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Imaginea e prea mare.")

    # Resolve direction: preset key → expanded hint, OR free text → sanitized + used directly
    direction_clean = (direction or "").strip()
    if not direction_clean:
        raise HTTPException(status_code=400, detail="Direction cannot be empty.")
    if len(direction_clean) > 200:
        raise HTTPException(status_code=400, detail="Direction too long (max 200 chars).")

    if direction_clean in REFINE_DIRECTIONS:
        refine_hint = REFINE_DIRECTIONS[direction_clean]
        direction_key = direction_clean
    else:
        # Free text — use as-is (sanitized)
        refine_hint = direction_clean
        direction_key = "custom"

    job_id = str(uuid.uuid4())
    creation_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "pending", "progress": 0, "result": None, "error": None}

    background_tasks.add_task(
        _run_generation_pipeline,
        job_id=job_id,
        creation_id=creation_id,
        image_bytes=image_bytes,
        style_id=style_id,
        quality=QualityTier.free,
        session_id=f"{session_id}-refine-{direction_key}",  # unique session = unique anti-repetition
        animation_mode=animation_mode,
        frame_delay=max(20, min(200, frame_delay)),
        ref_source=refine_hint,  # pass through as prompt addition
    )
    return {"job_id": job_id, "direction": direction_key, "hint": refine_hint}


@router.get("/refine-directions")
async def get_refine_directions():
    """Return available refinement directions with labels for UI."""
    return {
        "directions": [
            {"key": "darker", "label": "Mai întunecat", "icon": "🌑"},
            {"key": "brighter", "label": "Mai luminos", "icon": "☀️"},
            {"key": "more_color", "label": "Mai colorat", "icon": "🎨"},
            {"key": "less_color", "label": "Mai discret", "icon": "🖤"},
            {"key": "more_abstract", "label": "Mai abstract", "icon": "🌀"},
            {"key": "more_detailed", "label": "Mai detaliat", "icon": "🔍"},
            {"key": "softer", "label": "Mai moale", "icon": "☁️"},
            {"key": "sharper", "label": "Mai dur", "icon": "⚡"},
        ]
    }


@router.delete("/creation/{creation_id}")
async def delete_creation(creation_id: str, session_id: str):
    """Sterge o creatie din Firestore (verifica session_id)."""
    deleted = await db_service.delete_creation(creation_id, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Creatia nu a fost gasita sau nu ai permisiuni.")
    return {"ok": True}


@router.post("/regenerate", response_model=dict)
async def regenerate(background_tasks: BackgroundTasks, req: RegenerateRequest):
    job_id = str(uuid.uuid4())
    creation_id = str(uuid.uuid4())
    _jobs[job_id] = {"status": "pending", "progress": 0, "result": None, "error": None}

    try:
        style_id = StyleId(req.style_id)
        quality = QualityTier(req.quality)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        anim_mode = AnimationMode(req.animation_mode)
    except ValueError:
        anim_mode = AnimationMode.life

    background_tasks.add_task(
        _run_regenerate_pipeline,
        job_id=job_id,
        creation_id=creation_id,
        prompt=req.prompt,
        style_id=style_id,
        quality=quality,
        session_id=req.session_id,
        thumbnail_url=req.thumbnail_url,
        animation_mode=anim_mode,
        frame_delay=max(20, min(200, req.frame_delay)),
    )
    return {"job_id": job_id}


@router.post("/inspire")
async def inspire(req: InspireRequest):
    """Genereaza 3 variante creative ale promptului curent via Gemini."""
    try:
        style_id = StyleId(req.style_id)
    except ValueError:
        style_id = StyleId.dali

    variations = await generate_prompt_variations(req.prompt, style_id)
    return {"variations": variations}


@router.post("/storycard")
async def storycard(req: StorycardRequest):
    """Genereaza un JPEG 9:16 pentru Instagram Stories cu watermark ScanArt."""
    try:
        jpeg_bytes = await share_service.generate_story_card(
            result_url=req.result_url,
            filter_label=req.filter_label,
            prompt_used=req.prompt_used,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Story card generation failed: {e}")

    return Response(
        content=jpeg_bytes,
        media_type="image/jpeg",
        headers={
            "Content-Disposition": 'attachment; filename="scanart-story.jpg"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/media")
async def proxy_media(url: str):
    if not url.startswith("https://storage.googleapis.com/scanart-results-"):
        raise HTTPException(status_code=400, detail="URL invalid.")
    is_gif = url.endswith(".gif")
    content_type = "image/gif" if is_gif else "video/mp4"
    async with httpx.AsyncClient() as client:
        r = await client.get(url)
        if r.status_code != 200:
            raise HTTPException(status_code=404, detail="Fisier negasit.")
        data = r.content
    return StreamingResponse(
        iter([data]),
        media_type=content_type,
        headers={
            "Content-Disposition": "inline",
            "Cache-Control": "public, max-age=86400",
            "Access-Control-Allow-Origin": "*",
        }
    )


# ─── Pipeline generare ────────────────────────────────────────────────────────

async def _run_generation_pipeline(
    job_id: str,
    creation_id: str,
    image_bytes: bytes,
    style_id: StyleId,
    quality: QualityTier,
    session_id: str,
    animation_mode: AnimationMode = AnimationMode.life,
    frame_delay: int = 80,
    ref_source: str = None,
):
    try:
        import time as _time
        _gen_start = _time.monotonic()

        _jobs[job_id]["status"] = "processing"
        _jobs[job_id]["progress"] = 10

        if quality != QualityTier.free:
            prompt = await generate_creative_prompt(image_bytes, style_id)
        else:
            prompt = None
        _jobs[job_id]["progress"] = 25

        _jobs[job_id]["progress"] = 35

        _fallback_used = False
        if quality == QualityTier.free:
            def _cb(pct):
                _jobs[job_id]["progress"] = pct
            video_bytes, prompt = await generate_video_free(
                image_bytes, style_id.value, progress_cb=_cb,
                animation_mode=animation_mode.value,
                frame_delay=frame_delay,
                session_id=session_id,
            )
        else:
            video_bytes = await generate_video_from_image(image_bytes, prompt, quality)

        _gen_time_ms = int((_time.monotonic() - _gen_start) * 1000)
        _jobs[job_id]["progress"] = 85
        # Parallel uploads: video + thumbnail + original simultaneously
        video_url, thumbnail_url, original_url = await asyncio.gather(
            upload_video(video_bytes, creation_id),
            upload_thumbnail(video_bytes, creation_id),
            upload_original(image_bytes, creation_id),
        )
        _jobs[job_id]["progress"] = 95

        share_code = generate_share_code()
        # Extract subject_type from prompt
        _subject = "object"
        if prompt:
            for st in ["face", "cup", "animal", "plant", "food", "text", "sign", "number"]:
                if st in prompt[:50].lower():
                    _subject = st
                    break
        result = GenerateResponse(
            creation_id=creation_id,
            video_url=video_url,
            thumbnail_url=thumbnail_url,
            prompt_used=prompt or "",
            style_id=style_id.value,
            quality=quality.value,
            share_code=share_code,
            subject_type=_subject,
        )

        await db_service.save_creation(
            creation_id=creation_id,
            session_id=session_id,
            style_id=style_id.value,
            quality=quality.value,
            prompt_used=prompt or "",
            video_url=video_url,
            thumbnail_url=thumbnail_url,
            share_code=share_code,
            original_url=original_url,
        )

        # Referral tracking: dacă userul a venit de pe un share link
        if ref_source:
            await db_service.track_referral(ref_source, creation_id)

        # Style performance tracking (non-blocking)
        # Detect subject_type from prompt
        _subject = "object"
        if prompt:
            for st in ["face", "cup", "animal", "plant", "food", "text", "sign", "number"]:
                if st in prompt[:50].lower():
                    _subject = st
                    break
        await db_service.track_style_performance(
            style_id=style_id.value,
            subject_type=_subject,
            success=True,
            generation_time_ms=_gen_time_ms,
            model_used="imagen-4-ultra" if quality == QualityTier.free else "veo-3",
        )

        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["progress"] = 100
        _jobs[job_id]["result"] = result.model_dump()

    except Exception as e:
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(e)
        # Track failure
        _gen_time_ms = int((_time.monotonic() - _gen_start) * 1000) if '_gen_start' in dir() else 0
        await db_service.track_style_performance(
            style_id=style_id.value, subject_type="unknown",
            success=False, generation_time_ms=_gen_time_ms,
        )


async def _run_regenerate_pipeline(
    job_id: str,
    creation_id: str,
    prompt: str,
    style_id: StyleId,
    quality: QualityTier,
    session_id: str,
    thumbnail_url: str,
    animation_mode: AnimationMode = AnimationMode.life,
    frame_delay: int = 80,
):
    try:
        _jobs[job_id]["status"] = "processing"
        _jobs[job_id]["progress"] = 15
        _jobs[job_id]["progress"] = 35

        # Descarcă thumbnail-ul original ca sursă pentru style transfer
        source_image_bytes = b""
        if thumbnail_url:
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(thumbnail_url, timeout=10)
                    if r.status_code == 200:
                        source_image_bytes = r.content
                        print(f"Regenerate: downloaded thumbnail ({len(source_image_bytes)} bytes)")
            except Exception as dl_err:
                print(f"Regenerate: failed to download thumbnail: {dl_err}")

        if quality == QualityTier.free:
            def _cb(pct):
                _jobs[job_id]["progress"] = pct
            video_bytes, _ = await generate_video_free(
                source_image_bytes, style_id.value, custom_prompt=prompt, progress_cb=_cb,
                animation_mode=animation_mode.value,
                frame_delay=frame_delay,
                session_id=session_id,
            )
        else:
            video_bytes = await generate_video_from_image(source_image_bytes, prompt, quality)

        _jobs[job_id]["progress"] = 85
        video_url = await upload_video(video_bytes, creation_id)

        # Thumbnail din GIF/video artistic (primul frame)
        new_thumbnail_url = await upload_thumbnail(video_bytes, creation_id)
        _jobs[job_id]["progress"] = 95

        share_code = generate_share_code()
        result = GenerateResponse(
            creation_id=creation_id,
            video_url=video_url,
            thumbnail_url=new_thumbnail_url,
            prompt_used=prompt,
            style_id=style_id.value,
            quality=quality.value,
            share_code=share_code,
        )

        await db_service.save_creation(
            creation_id=creation_id,
            session_id=session_id,
            style_id=style_id.value,
            quality=quality.value,
            prompt_used=prompt,
            video_url=video_url,
            thumbnail_url=new_thumbnail_url,
            share_code=share_code,
        )

        _jobs[job_id]["status"] = "done"
        _jobs[job_id]["progress"] = 100
        _jobs[job_id]["result"] = result.model_dump()

    except Exception as e:
        _jobs[job_id]["status"] = "error"
        _jobs[job_id]["error"] = str(e)
