import uuid
import io
from google.cloud import storage
from PIL import Image
from app.config import settings


def _get_client() -> storage.Client:
    return storage.Client(project=settings.google_cloud_project)


def _public_url(bucket_name: str, blob_name: str) -> str:
    return f"https://storage.googleapis.com/{bucket_name}/{blob_name}"


async def upload_video(video_bytes: bytes, creation_id: str) -> str:
    """Uploadeaza video/GIF pe GCS si returneaza URL public."""
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _upload_video_sync, video_bytes, creation_id)


def _upload_video_sync(video_bytes: bytes, creation_id: str) -> str:
    client = _get_client()
    bucket = client.bucket(settings.gcs_bucket_name)

    # Detecteaza daca e GIF sau MP4
    is_gif = video_bytes[:6] in (b'GIF87a', b'GIF89a')
    if is_gif:
        blob_name = f"videos/{creation_id}.gif"
        content_type = "image/gif"
    else:
        blob_name = f"videos/{creation_id}.mp4"
        content_type = "video/mp4"

    blob = bucket.blob(blob_name)
    blob.upload_from_string(video_bytes, content_type=content_type)
    blob.make_public()
    return _public_url(settings.gcs_bucket_name, blob_name)


async def upload_thumbnail(image_bytes: bytes, creation_id: str) -> str:
    """Genereaza thumbnail JPEG din primul frame si uploadeaza.
    Accepta GIF (extrage primul frame artistic) sau JPEG/PNG brut.
    """
    import asyncio
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _upload_thumbnail_sync, image_bytes, creation_id)


def _upload_thumbnail_sync(image_bytes: bytes, creation_id: str) -> str:
    img = Image.open(io.BytesIO(image_bytes))

    # Daca e GIF animat, extrage primul frame (opera artistica, nu poza bruta)
    if getattr(img, 'is_animated', False) or img.format == 'GIF':
        img.seek(0)

    img = img.convert("RGB")

    # Resize si crop patrat centrat la 640px
    w, h = img.size
    size = min(w, h)
    left = (w - size) // 2
    top = (h - size) // 2
    img = img.crop((left, top, left + size, top + size))
    img = img.resize((640, 640), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88, optimize=True)
    thumb_bytes = buf.getvalue()

    client = _get_client()
    bucket = client.bucket(settings.gcs_bucket_name)
    blob_name = f"thumbnails/{creation_id}.jpg"
    blob = bucket.blob(blob_name)
    blob.upload_from_string(thumb_bytes, content_type="image/jpeg")
    blob.make_public()
    return _public_url(settings.gcs_bucket_name, blob_name)


def generate_share_code() -> str:
    return uuid.uuid4().hex[:8]
