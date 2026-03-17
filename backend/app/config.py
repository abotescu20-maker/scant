from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    google_cloud_project: str
    google_cloud_location: str = "us-central1"
    google_api_key: str = ""
    gcs_bucket_name: str = "scanart-results"
    gemini_model: str = "gemini-2.0-flash"
    allowed_origins: list[str] = ["*"]

    # Veo tier config
    veo_model_standard: str = "veo-3.0-generate-preview"   # Veo 3 Fast
    veo_model_premium: str = "veo-3.0-generate-preview"    # Veo 3 Full
    veo_duration_standard: int = 4   # 4 sec ~$0.60
    veo_duration_premium: int = 8    # 8 sec ~$4.00
    veo_output_gcs_bucket: str = "scanart-results-1772986018"  # GCS bucket pentru output Veo

    # Hugging Face pentru tier free
    hf_api_token: str = ""
    hf_model: str = "stabilityai/stable-video-diffusion-img2vid-xt"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
