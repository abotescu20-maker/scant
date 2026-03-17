"""
Admin endpoints for ScanArt — analytics, trending recomputation, challenge management.
All admin endpoints require ?key=ADMIN_API_KEY query param.
Public endpoints: GET /api/challenge
"""
import asyncio
from datetime import datetime, timezone, timedelta
from collections import Counter

from fastapi import APIRouter, HTTPException, Query
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
