from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from app.api.generate import router as generate_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"ScanArt backend pornit. Project: {settings.google_cloud_project}")
    yield
    # Shutdown
    print("ScanArt backend oprit.")


app = FastAPI(
    title="ScanArt API",
    description="Scaneaza obiecte si genereaza video animat cu Gemini + Veo 3",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate_router, prefix="/api", tags=["generate"])


@app.get("/health")
async def health():
    return {"status": "ok", "project": settings.google_cloud_project}
