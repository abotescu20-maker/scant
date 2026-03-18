"""
Admin endpoints for ScanArt — analytics, trending recomputation, challenge management.
All admin endpoints require ?key=ADMIN_API_KEY query param.
Public endpoints: GET /api/challenge
"""
import asyncio
from datetime import datetime, timezone, timedelta
from collections import Counter

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from google.cloud import firestore

from app.config import settings

router = APIRouter()


def _check_admin_key(key: str | None) -> None:
    if not settings.admin_api_key or key != settings.admin_api_key:
        raise HTTPException(status_code=403, detail="Invalid admin key")


def _get_db() -> firestore.Client:
    return firestore.Client(project=settings.google_cloud_project)


# ─── Analytics ────────────────────────────────────────────────────────────────

def _get_stats_sync(days: int) -> dict:
    db = _get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    docs = (
        db.collection("creations")
        .where(filter=firestore.FieldFilter("created_at", ">=", cutoff))
        .stream()
    )

    style_counts = Counter()
    quality_counts = Counter()
    total = 0
    for d in docs:
        item = d.to_dict()
        style_counts[item.get("style_id", "unknown")] += 1
        quality_counts[item.get("quality", "free")] += 1
        total += 1

    # Count referrals in same period
    ref_docs = (
        db.collection("referrals")
        .where(filter=firestore.FieldFilter("timestamp", ">=", cutoff))
        .stream()
    )
    referral_count = sum(1 for _ in ref_docs)

    return {
        "period_days": days,
        "total_creations": total,
        "style_breakdown": dict(style_counts.most_common()),
        "quality_breakdown": dict(quality_counts),
        "referral_count": referral_count,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/admin/stats")
async def get_stats(key: str = Query(None), days: int = Query(7)):
    _check_admin_key(key)
    loop = asyncio.get_event_loop()
    stats = await loop.run_in_executor(None, _get_stats_sync, days)
    return stats


# ─── Daily Snapshot ───────────────────────────────────────────────────────────

def _save_snapshot_sync(stats: dict) -> str:
    db = _get_db()
    doc_id = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    db.collection("analytics_daily").document(doc_id).set(stats)
    return doc_id


@router.post("/admin/snapshot")
async def save_snapshot(key: str = Query(None)):
    _check_admin_key(key)
    loop = asyncio.get_event_loop()
    stats = await loop.run_in_executor(None, _get_stats_sync, 1)
    doc_id = await loop.run_in_executor(None, _save_snapshot_sync, stats)
    return {"snapshot_id": doc_id, "stats": stats}


# ─── Trending Recomputation ──────────────────────────────────────────────────

def _recompute_trending_sync() -> int:
    db = _get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    now = datetime.now(timezone.utc)

    # Get all creations from last 7 days
    creations = []
    for d in db.collection("creations").where(
        filter=firestore.FieldFilter("created_at", ">=", cutoff)
    ).stream():
        creations.append(d.to_dict())

    # Count referrals per share_code
    ref_counts = Counter()
    for d in db.collection("referrals").where(
        filter=firestore.FieldFilter("timestamp", ">=", cutoff)
    ).stream():
        item = d.to_dict()
        ref_counts[item.get("share_code", "")] += 1

    # Score each creation
    scored = []
    for c in creations:
        created_at = c.get("created_at")
        if hasattr(created_at, "timestamp"):
            age_hours = (now - created_at).total_seconds() / 3600
        else:
            age_hours = 168  # max 7 days
        recency_score = max(0, 1.0 - (age_hours / 168))  # decay over 7 days
        referral_score = ref_counts.get(c.get("share_code", ""), 0) * 10
        c["_score"] = recency_score * 50 + referral_score
        # Strip sensitive fields
        c.pop("session_id", None)
        c.pop("prompt_used", None)
        if "created_at" in c and hasattr(c["created_at"], "isoformat"):
            c["created_at"] = c["created_at"].isoformat()
        scored.append(c)

    # Sort by score, take top 50
    scored.sort(key=lambda x: x.get("_score", 0), reverse=True)
    top = scored[:50]

    # Clean score field before saving
    for item in top:
        item.pop("_score", None)

    # Save to trending_cache
    db.collection("trending_cache").document("current").set({
        "items": top,
        "updated_at": datetime.now(timezone.utc),
    })

    return len(top)


@router.post("/admin/recompute-trending")
async def recompute_trending(key: str = Query(None)):
    _check_admin_key(key)
    loop = asyncio.get_event_loop()
    count = await loop.run_in_executor(None, _recompute_trending_sync)
    return {"status": "ok", "items_cached": count}


# ─── Weekly Challenge ─────────────────────────────────────────────────────────

def _get_challenge_sync() -> dict | None:
    db = _get_db()
    doc = db.collection("config").document("weekly_challenge").get()
    if doc.exists:
        data = doc.to_dict()
        if "set_at" in data and hasattr(data["set_at"], "isoformat"):
            data["set_at"] = data["set_at"].isoformat()
        return data
    return None


def _set_challenge_sync(challenge: dict) -> None:
    db = _get_db()
    challenge["set_at"] = datetime.now(timezone.utc)
    db.collection("config").document("weekly_challenge").set(challenge)


@router.get("/challenge")
async def get_challenge():
    """Public endpoint — returns current weekly challenge."""
    loop = asyncio.get_event_loop()
    challenge = await loop.run_in_executor(None, _get_challenge_sync)
    if not challenge:
        # Fallback default
        return {
            "filter": "ghibli",
            "emoji": "🍃",
            "name": "Ghibli Portrait",
            "hashtag": "#GhibliScanArt",
            "description": "Transformă-te în personaj Ghibli",
        }
    return challenge


@router.post("/admin/challenge")
async def set_challenge(
    key: str = Query(None),
    filter: str = Query(...),
    emoji: str = Query(...),
    name: str = Query(...),
    hashtag: str = Query(...),
    description: str = Query(""),
):
    _check_admin_key(key)
    challenge = {
        "filter": filter,
        "emoji": emoji,
        "name": name,
        "hashtag": hashtag,
        "description": description,
    }
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _set_challenge_sync, challenge)
    return {"status": "ok", "challenge": challenge}


# ─── Admin Dashboard ─────────────────────────────────────────────────────────

def _get_dashboard_data_sync() -> dict:
    """Fetch all data needed for the dashboard in one call."""
    db = _get_db()
    now = datetime.now(timezone.utc)

    # Stats 7 days
    cutoff_7 = now - timedelta(days=7)
    cutoff_30 = now - timedelta(days=30)

    style_counts_7 = Counter()
    style_counts_30 = Counter()
    quality_counts_7 = Counter()
    total_7 = 0
    total_30 = 0
    daily_counts = Counter()  # date string → count

    for d in db.collection("creations").where(
        filter=firestore.FieldFilter("created_at", ">=", cutoff_30)
    ).stream():
        item = d.to_dict()
        sid = item.get("style_id", "unknown")
        qual = item.get("quality", "free")
        created = item.get("created_at")
        total_30 += 1
        style_counts_30[sid] += 1

        # Daily bucket
        if hasattr(created, "strftime"):
            day_key = created.strftime("%Y-%m-%d")
        else:
            day_key = "unknown"
        daily_counts[day_key] += 1

        if hasattr(created, "timestamp") and created >= cutoff_7:
            total_7 += 1
            style_counts_7[sid] += 1
            quality_counts_7[qual] += 1
        elif not hasattr(created, "timestamp"):
            total_7 += 1
            style_counts_7[sid] += 1
            quality_counts_7[qual] += 1

    # All-time count
    total_all = 0
    for _ in db.collection("creations").select([]).stream():
        total_all += 1

    # Referrals 7 days
    ref_7 = 0
    for _ in db.collection("referrals").where(
        filter=firestore.FieldFilter("timestamp", ">=", cutoff_7)
    ).stream():
        ref_7 += 1

    # Challenge
    challenge = None
    cdoc = db.collection("config").document("weekly_challenge").get()
    if cdoc.exists:
        challenge = cdoc.to_dict()

    # Recent 12 creations
    recent = []
    for d in db.collection("creations").order_by(
        "created_at", direction=firestore.Query.DESCENDING
    ).limit(12).stream():
        item = d.to_dict()
        if "created_at" in item and hasattr(item["created_at"], "isoformat"):
            item["created_at"] = item["created_at"].isoformat()
        item.pop("session_id", None)
        item.pop("prompt_used", None)
        recent.append(item)

    # Build daily timeline (last 30 days)
    timeline = []
    for i in range(29, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        timeline.append({"date": day, "count": daily_counts.get(day, 0)})

    return {
        "total_7": total_7,
        "total_30": total_30,
        "total_all": total_all,
        "ref_7": ref_7,
        "conversion": round(ref_7 / max(total_7, 1) * 100, 1),
        "styles_7": dict(style_counts_7.most_common()),
        "styles_30": dict(style_counts_30.most_common()),
        "quality_7": dict(quality_counts_7),
        "challenge": challenge,
        "recent": recent,
        "timeline": timeline,
    }


def _build_dashboard_html(data: dict) -> str:
    """Build the full HTML dashboard."""
    # KPI values
    t7 = data["total_7"]
    t30 = data["total_30"]
    t_all = data["total_all"]
    ref7 = data["ref_7"]
    conv = data["conversion"]

    # Style bars (top 15 for 7 days)
    styles = data["styles_7"]
    max_count = max(styles.values()) if styles else 1
    style_bars = ""
    for sid, cnt in list(styles.items())[:15]:
        pct = round(cnt / max(t7, 1) * 100, 1)
        w = round(cnt / max_count * 100)
        style_bars += f'''
        <div class="bar-row">
          <span class="bar-label">{sid}</span>
          <div class="bar-track"><div class="bar-fill" style="width:{w}%"></div></div>
          <span class="bar-val">{cnt} <small>({pct}%)</small></span>
        </div>'''

    # Quality donut segments
    q = data["quality_7"]
    q_free = q.get("free", 0)
    q_std = q.get("standard", 0)
    q_prem = q.get("premium", 0)
    q_total = max(q_free + q_std + q_prem, 1)
    deg_free = round(q_free / q_total * 360)
    deg_std = round(q_std / q_total * 360)
    # conic-gradient
    donut_grad = f"conic-gradient(#06b6d4 0deg {deg_free}deg, #a855f7 {deg_free}deg {deg_free + deg_std}deg, #f59e0b {deg_free + deg_std}deg 360deg)"

    # Timeline SVG
    tl = data["timeline"]
    max_day = max((d["count"] for d in tl), default=1) or 1
    svg_w, svg_h = 700, 120
    points = []
    for i, d in enumerate(tl):
        x = round(i / 29 * svg_w, 1) if len(tl) > 1 else svg_w / 2
        y = round(svg_h - (d["count"] / max_day * (svg_h - 20)) - 10, 1)
        points.append(f"{x},{y}")
    polyline = " ".join(points)
    # X-axis labels (every 7 days)
    x_labels = ""
    for i in [0, 7, 14, 21, 29]:
        if i < len(tl):
            lx = round(i / 29 * svg_w)
            x_labels += f'<text x="{lx}" y="{svg_h + 14}" fill="rgba(255,255,255,.35)" font-size="10" text-anchor="middle">{tl[i]["date"][5:]}</text>'

    # Challenge card
    ch = data["challenge"]
    challenge_html = ""
    if ch:
        ch_emoji = ch.get("emoji", "🎨")
        ch_name = ch.get("name", "—")
        ch_tag = ch.get("hashtag", "")
        challenge_html = f'''
        <div class="card challenge-card">
          <div class="card-title">Challenge Curent</div>
          <div style="font-size:2.5rem;margin:.5rem 0">{ch_emoji}</div>
          <div style="font-size:1.1rem;font-weight:700">{ch_name}</div>
          <div style="color:rgba(255,255,255,.4);font-size:.85rem;margin-top:.3rem">{ch_tag}</div>
        </div>'''

    # Recent creations grid
    grid_items = ""
    backend_url = "https://scanart-backend-603810013022.us-central1.run.app"
    for c in data["recent"]:
        thumb = c.get("thumbnail_url", "")
        sc = c.get("share_code", "")
        sid = c.get("style_id", "?")
        ts = c.get("created_at", "")[:16].replace("T", " ")
        grid_items += f'''
        <a href="{backend_url}/api/share/{sc}" target="_blank" class="grid-item">
          <img src="{thumb}" alt="{sid}" loading="lazy">
          <div class="grid-meta">{sid} · {ts}</div>
        </a>'''

    html = f'''<!DOCTYPE html>
<html lang="ro">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="300">
<title>ScanArt Admin Dashboard</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{
  background:#000;
  background-image:radial-gradient(ellipse at 50% 10%,#1a0840 0%,#000 70%);
  color:#fff;
  font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display','Segoe UI',sans-serif;
  min-height:100vh;padding:1.5rem;
  -webkit-font-smoothing:antialiased;
}}
h1{{
  font-size:1.6rem;font-weight:800;margin-bottom:.3rem;
  background:linear-gradient(135deg,#a855f7,#06b6d4);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}}
.subtitle{{color:rgba(255,255,255,.4);font-size:.85rem;margin-bottom:1.5rem}}
.kpi-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.8rem;margin-bottom:1.5rem}}
.kpi{{
  background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.08);
  border-radius:12px;padding:1rem;text-align:center;
  backdrop-filter:blur(10px);
}}
.kpi-val{{font-size:1.8rem;font-weight:800;line-height:1.1}}
.kpi-label{{font-size:.75rem;color:rgba(255,255,255,.4);margin-top:.3rem;text-transform:uppercase;letter-spacing:.05em}}
.kpi-accent{{color:#06b6d4}}
.kpi-purple{{color:#a855f7}}
.kpi-orange{{color:#f59e0b}}
.card{{
  background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);
  border-radius:12px;padding:1.2rem;margin-bottom:1rem;
}}
.card-title{{font-size:.85rem;font-weight:700;color:rgba(255,255,255,.5);margin-bottom:.8rem;text-transform:uppercase;letter-spacing:.05em}}
.bar-row{{display:flex;align-items:center;gap:.5rem;margin-bottom:.4rem}}
.bar-label{{width:110px;font-size:.78rem;color:rgba(255,255,255,.6);text-align:right;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.bar-track{{flex:1;height:18px;background:rgba(255,255,255,.06);border-radius:9px;overflow:hidden}}
.bar-fill{{height:100%;border-radius:9px;background:linear-gradient(90deg,#7c3aed,#06b6d4);transition:width .3s}}
.bar-val{{width:80px;font-size:.75rem;color:rgba(255,255,255,.5);flex-shrink:0}}
.bar-val small{{color:rgba(255,255,255,.3)}}
.donut-wrap{{display:flex;align-items:center;gap:1.5rem;flex-wrap:wrap}}
.donut{{width:100px;height:100px;border-radius:50%;position:relative}}
.donut-hole{{position:absolute;inset:20px;border-radius:50%;background:#0a0a10}}
.legend{{display:flex;flex-direction:column;gap:.4rem}}
.legend-item{{display:flex;align-items:center;gap:.5rem;font-size:.82rem}}
.legend-dot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}
.timeline-svg{{width:100%;max-width:700px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:.6rem;margin-top:.6rem}}
.grid-item{{
  border-radius:10px;overflow:hidden;
  border:1px solid rgba(255,255,255,.08);
  text-decoration:none;color:#fff;
  transition:border-color .15s;
}}
.grid-item:hover{{border-color:rgba(124,58,237,.5)}}
.grid-item img{{width:100%;aspect-ratio:1;object-fit:cover;display:block}}
.grid-meta{{padding:.4rem .5rem;font-size:.68rem;color:rgba(255,255,255,.4);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.challenge-card{{text-align:center}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:1rem}}
@media(max-width:600px){{.two-col{{grid-template-columns:1fr}}}}
.refresh-btn{{
  position:fixed;bottom:1.2rem;right:1.2rem;
  background:rgba(124,58,237,.8);border:none;color:#fff;
  width:44px;height:44px;border-radius:50%;font-size:1.2rem;
  cursor:pointer;backdrop-filter:blur(10px);
  border:1px solid rgba(124,58,237,.5);
  z-index:100;
}}
.refresh-btn:active{{transform:scale(.9)}}
</style>
</head>
<body>

<h1>ScanArt Dashboard</h1>
<div class="subtitle">Auto-refresh: 5 min · Generat: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")} UTC</div>

<!-- KPI Cards -->
<div class="kpi-grid">
  <div class="kpi">
    <div class="kpi-val kpi-accent">{t7}</div>
    <div class="kpi-label">Creații 7 zile</div>
  </div>
  <div class="kpi">
    <div class="kpi-val kpi-purple">{t30}</div>
    <div class="kpi-label">Creații 30 zile</div>
  </div>
  <div class="kpi">
    <div class="kpi-val">{t_all}</div>
    <div class="kpi-label">Total all-time</div>
  </div>
  <div class="kpi">
    <div class="kpi-val kpi-orange">{ref7}</div>
    <div class="kpi-label">Referrals 7 zile</div>
  </div>
  <div class="kpi">
    <div class="kpi-val" style="color:#10b981">{conv}%</div>
    <div class="kpi-label">Conversie Ref</div>
  </div>
</div>

<!-- Timeline -->
<div class="card">
  <div class="card-title">Creații pe zi (30 zile)</div>
  <svg viewBox="0 0 {svg_w} {svg_h + 20}" class="timeline-svg" preserveAspectRatio="none">
    <defs>
      <linearGradient id="tg" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stop-color="#7c3aed"/>
        <stop offset="100%" stop-color="#06b6d4"/>
      </linearGradient>
      <linearGradient id="tfill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#7c3aed" stop-opacity="0.3"/>
        <stop offset="100%" stop-color="#7c3aed" stop-opacity="0"/>
      </linearGradient>
    </defs>
    <polygon points="0,{svg_h - 10} {polyline} {svg_w},{svg_h - 10}" fill="url(#tfill)" />
    <polyline points="{polyline}" fill="none" stroke="url(#tg)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
    {x_labels}
  </svg>
</div>

<div class="two-col">
  <!-- Style Popularity -->
  <div class="card">
    <div class="card-title">Stiluri populare (7 zile)</div>
    {style_bars}
  </div>

  <div>
    <!-- Quality Distribution -->
    <div class="card">
      <div class="card-title">Distribuție Quality</div>
      <div class="donut-wrap">
        <div class="donut" style="background:{donut_grad}">
          <div class="donut-hole"></div>
        </div>
        <div class="legend">
          <div class="legend-item"><div class="legend-dot" style="background:#06b6d4"></div>Free: {q_free} ({round(q_free/q_total*100)}%)</div>
          <div class="legend-item"><div class="legend-dot" style="background:#a855f7"></div>Standard: {q_std} ({round(q_std/q_total*100)}%)</div>
          <div class="legend-item"><div class="legend-dot" style="background:#f59e0b"></div>Premium: {q_prem} ({round(q_prem/q_total*100)}%)</div>
        </div>
      </div>
    </div>

    <!-- Challenge -->
    {challenge_html}
  </div>
</div>

<!-- Recent Creations -->
<div class="card">
  <div class="card-title">Creații recente</div>
  <div class="grid">
    {grid_items}
  </div>
</div>

<button class="refresh-btn" onclick="location.reload()" title="Refresh">↻</button>

</body>
</html>'''
    return html


@router.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(key: str = Query(None)):
    _check_admin_key(key)
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _get_dashboard_data_sync)
    html = _build_dashboard_html(data)
    return HTMLResponse(content=html)
