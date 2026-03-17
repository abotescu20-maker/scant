import asyncio
import time
import uuid
import vertexai
from google import genai as vertex_genai
from google.genai import types as genai_types
from google.cloud import storage
from app.config import settings
from app.models.schemas import QualityTier


def _init_vertex():
    vertexai.init(project=settings.google_cloud_project, location=settings.google_cloud_location)


async def generate_video_from_image(image_bytes: bytes, prompt: str, quality: QualityTier = QualityTier.standard) -> bytes:
    """
    Apeleaza Veo 3 pe Vertex AI cu image-to-video.
    - standard: 4 secunde ~$0.60
    - premium:  8 secunde ~$4.00
    """
    loop = asyncio.get_event_loop()
    duration = settings.veo_duration_standard if quality == QualityTier.standard else settings.veo_duration_premium
    model = settings.veo_model_standard if quality == QualityTier.standard else settings.veo_model_premium
    return await loop.run_in_executor(None, _generate_video_sync, image_bytes, prompt, model, duration)


def _generate_video_sync(image_bytes: bytes, prompt: str, model: str, duration: int) -> bytes:
    _init_vertex()

    client = vertex_genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
    )

    # Veo necesita GCS output URI
    job_id = str(uuid.uuid4())
    output_gcs_uri = f"gs://{settings.veo_output_gcs_bucket}/veo-outputs/{job_id}"

    operation = client.models.generate_videos(
        model=model,
        prompt=prompt,
        image=genai_types.Image(
            image_bytes=image_bytes,
            mime_type="image/jpeg",
        ),
        config=genai_types.GenerateVideosConfig(
            aspect_ratio="9:16",
            duration_seconds=duration,
            number_of_videos=1,
            enhance_prompt=True,
            output_gcs_uri=output_gcs_uri,
        ),
    )

    # Polling pana cand operatia e gata
    while not operation.done:
        time.sleep(5)
        operation = client.operations.get(operation)

    # Verificam eroarea
    if operation.error:
        err = operation.error
        msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
        raise RuntimeError(f"Veo generation failed: {msg}")

    video = operation.result.generated_videos[0]

    # Daca avem video_bytes direct, returnam
    if video.video.video_bytes:
        return video.video.video_bytes

    # Altfel descarcam din GCS
    gcs_uri = video.video.uri
    if not gcs_uri:
        raise RuntimeError("Veo nu a returnat video bytes sau GCS URI")

    # Parse gs://bucket/path
    gcs_path = gcs_uri.replace("gs://", "")
    bucket_name, blob_path = gcs_path.split("/", 1)

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    return blob.download_as_bytes()
