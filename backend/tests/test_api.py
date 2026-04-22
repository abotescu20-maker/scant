"""Tests: API endpoint validation (no live calls, just structure).

Run: cd backend && python -m pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"

    def test_health_has_project(self):
        r = client.get("/health")
        data = r.json()
        assert "project" in data


class TestTiersEndpoint:
    def test_tiers_returns_200(self):
        r = client.get("/api/tiers")
        assert r.status_code == 200

    def test_tiers_has_three(self):
        r = client.get("/api/tiers")
        data = r.json()
        assert len(data["tiers"]) == 3

    def test_tiers_ids(self):
        r = client.get("/api/tiers")
        ids = [t["id"] for t in r.json()["tiers"]]
        assert ids == ["free", "standard", "premium"]


class TestGenerateValidation:
    def test_generate_no_image_returns_422(self):
        r = client.post("/api/generate", data={"style_id": "warhol", "quality": "free", "session_id": "test"})
        assert r.status_code == 422

    def test_generate_invalid_style_returns_422(self):
        # Invalid style should be caught by enum validation
        from io import BytesIO
        fake_img = BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 100)  # minimal JPEG header
        r = client.post("/api/generate",
            data={"style_id": "nonexistent_style", "quality": "free", "session_id": "test"},
            files={"image": ("test.jpg", fake_img, "image/jpeg")})
        assert r.status_code == 422


class TestStatusEndpoint:
    def test_nonexistent_job_returns_404(self):
        r = client.get("/api/status/nonexistent-job-id")
        assert r.status_code == 404


class TestShareEndpoint:
    def test_nonexistent_share_returns_404(self):
        r = client.get("/api/share/00000000")
        assert r.status_code == 404
