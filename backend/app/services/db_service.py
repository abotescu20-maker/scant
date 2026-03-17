"""
Firestore DB service - salvează și citește creațiile per sesiune.
Colecție: 'creations'
Document ID: creation_id (UUID)
"""
import asyncio
from datetime import datetime, timezone, timedelta
from google.cloud import firestore
from app.config import settings

COLLECTION = "creations"


def _get_db() -> firestore.Client:
    return firestore.Client(project=settings.google_cloud_project)


def _save_sync(data: dict) -> None:
    db = _get_db()
    db.collection(COLLECTION).document(data["creation_id"]).set(data)


def _get_history_sync(session_id: str, limit: int) -> list:
    db = _get_db()
    try:
        docs = (
            db.collection(COLLECTION)
            .where(filter=firestore.FieldFilter("session_id", "==", session_id))
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        results = []
        for d in docs:
            item = d.to_dict()
            # Convertim Timestamp Firestore → ISO string pentru JSON
            if "created_at" in item and hasattr(item["created_at"], "isoformat"):
                item["created_at"] = item["created_at"].isoformat()
            results.append(item)
        return results
    except Exception as e:
        print(f"Firestore get_history failed: {e}")
        return []


async def save_creation(
    creation_id: str,
    session_id: str,
    style_id: str,
    quality: str,
    prompt_used: str,
    video_url: str,
    thumbnail_url: str,
    share_code: str,
) -> None:
    """Salvează creația în Firestore. Non-blocking - nu aruncă excepții."""
    data = {
        "creation_id": creation_id,
        "session_id": session_id,
        "style_id": style_id,
        "quality": quality,
        "prompt_used": prompt_used,
        "video_url": video_url,
        "thumbnail_url": thumbnail_url,
        "share_code": share_code,
        "created_at": datetime.now(timezone.utc),
    }
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _save_sync, data)
        print(f"Firestore saved: {creation_id}")
    except Exception as e:
        # Logăm eroarea dar NU blocăm pipeline-ul
        print(f"Firestore save failed (non-critical): {e}")


async def get_session_history(session_id: str, limit: int = 20) -> list:
    """Returnează ultimele N creații ale sesiunii, descrescător după dată."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_history_sync, session_id, limit)


def _delete_sync(creation_id: str, session_id: str) -> bool:
    db = _get_db()
    ref = db.collection(COLLECTION).document(creation_id)
    doc = ref.get()
    if not doc.exists:
        return False
    data = doc.to_dict()
    # Verifică că aparține sesiunii curente
    if data.get("session_id") != session_id:
        return False
    ref.delete()
    return True


async def delete_creation(creation_id: str, session_id: str) -> bool:
    """Șterge o creație. Returnează True dacă a fost ștearsă, False dacă nu a fost găsită."""
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _delete_sync, creation_id, session_id)
    except Exception as e:
        print(f"Firestore delete failed: {e}")
        return False


def _get_trending_sync(period: str, limit: int) -> list:
    db = _get_db()
    try:
        now = datetime.now(timezone.utc)
        if period == "week":
            cutoff = now - timedelta(days=7)
        elif period == "month":
            cutoff = now - timedelta(days=30)
        else:
            cutoff = now - timedelta(days=3650)  # "all time" = 10 ani

        query = (
            db.collection(COLLECTION)
            .where(filter=firestore.FieldFilter("created_at", ">=", cutoff))
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
        )
        results = []
        for d in query.stream():
            item = d.to_dict()
            if "created_at" in item and hasattr(item["created_at"], "isoformat"):
                item["created_at"] = item["created_at"].isoformat()
            # Excludem câmpuri sensibile
            item.pop("session_id", None)
            item.pop("prompt_used", None)
            results.append(item)
        return results
    except Exception as e:
        print(f"Firestore get_trending failed: {e}")
        return []


async def get_trending(period: str = "week", limit: int = 20) -> list:
    """Returnează cele mai recente creații din perioada specificată (public, fără session_id)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_trending_sync, period, limit)


def _get_by_share_code_sync(share_code: str) -> dict | None:
    db = _get_db()
    try:
        docs = (
            db.collection(COLLECTION)
            .where(filter=firestore.FieldFilter("share_code", "==", share_code))
            .limit(1)
            .stream()
        )
        for d in docs:
            item = d.to_dict()
            if "created_at" in item and hasattr(item["created_at"], "isoformat"):
                item["created_at"] = item["created_at"].isoformat()
            # Excludem câmpuri sensibile
            item.pop("session_id", None)
            item.pop("prompt_used", None)
            return item
        return None
    except Exception as e:
        print(f"Firestore get_by_share_code failed: {e}")
        return None


async def get_by_share_code(share_code: str) -> dict | None:
    """Returnează o creație după share_code (public, fără session_id/prompt)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _get_by_share_code_sync, share_code)


# ─── Referral tracking ────────────────────────────────────────────────────────

def _track_referral_sync(ref_share_code: str, referred_creation_id: str) -> None:
    """Salvează un referral în Firestore. Colecție: 'referrals'."""
    db = _get_db()
    data = {
        "share_code": ref_share_code,          # share code-ul originalului (sursa)
        "referred_creation_id": referred_creation_id,  # creația nou generată
        "timestamp": datetime.now(timezone.utc),
    }
    # Folosim auto-ID pentru documente referral (nu avem nevoie de lookup)
    db.collection("referrals").add(data)
    print(f"Referral tracked: {ref_share_code} → {referred_creation_id}")


async def track_referral(ref_share_code: str, referred_creation_id: str) -> None:
    """Tracking viral referral. Non-blocking — nu aruncă excepții."""
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _track_referral_sync, ref_share_code, referred_creation_id)
    except Exception as e:
        print(f"Referral tracking failed (non-critical): {e}")
