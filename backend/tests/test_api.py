from app.core.config import get_settings
from app import models
from app.db import SessionLocal

from conftest import make_zip


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_valid_zip_upload(client):
    archive = make_zip(
        {
            "sample/package.json": '{"scripts":{"build":"vite build"},"dependencies":{"react":"19.0.0","vite":"6.0.5"},"devDependencies":{"typescript":"5.6.3","vitest":"2.0.0"}}',
            "sample/package-lock.json": "{}",
            "sample/requirements.txt": "fastapi==0.115.6\npytest==8.3.4\n",
            "sample/README.md": "# Sample\n\n## Tech Stack\nReact FastAPI\n\n## Setup\nRun docker compose up.\n\n## API\nOpen docs.\n\n## Screenshots\n![dashboard](screenshots/dashboard.png)\n",
            "sample/.gitignore": ".env\nnode_modules\n",
            "sample/Dockerfile": "FROM python:3.12-slim\nEXPOSE 8000\nHEALTHCHECK CMD python -V\n",
            "sample/docker-compose.yml": "services:\n  backend:\n    build: .\n  postgres:\n    image: postgres:16\n",
            "sample/.dockerignore": "__pycache__\n",
            "sample/tests/test_app.py": "def test_ok():\n    assert True\n",
            "sample/pytest.ini": "[pytest]\n",
        }
    )

    response = client.post("/analyses/upload", files={"file": ("sample.zip", archive, "application/zip")})

    assert response.status_code == 201
    payload = response.json()
    assert payload["project_name"] == "sample"
    assert "web app" in payload["project_type"].lower()
    technologies = {technology["name"] for technology in payload["technologies"]}
    assert {"React", "Vite", "TypeScript", "FastAPI", "Pytest", "Docker", "Docker Compose"}.issubset(technologies)
    tech_by_name = {technology["name"]: technology for technology in payload["technologies"]}
    assert tech_by_name["Docker Compose"]["evidence_file"] == "docker-compose.yml"
    assert "was found" in tech_by_name["Docker Compose"]["reason"]
    assert tech_by_name["React"]["evidence_file"] == "package.json"
    assert tech_by_name["FastAPI"]["evidence_file"] == "requirements.txt"
    assert tech_by_name["Python"]["evidence_file"] == "requirements.txt"
    assert payload["score_explanations"]["security"]["explanation"]


def test_unsupported_file_type_rejected(client):
    response = client.post("/analyses/upload", files={"file": ("project.tar", b"not a zip", "application/x-tar")})

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported archive type."


def test_unsafe_zip_path_rejected(client):
    archive = make_zip({"../evil.txt": "bad"})

    response = client.post("/analyses/upload", files={"file": ("bad.zip", archive, "application/zip")})

    assert response.status_code == 400
    assert response.json()["detail"] == "ZIP archive contains unsafe paths."


def test_oversized_zip_rejected(client, monkeypatch):
    monkeypatch.setenv("PROJECTSENTINEL_MAX_UPLOAD_SIZE_BYTES", "10")
    get_settings.cache_clear()
    archive = make_zip({"README.md": "x" * 100})
    response = client.post("/analyses/upload", files={"file": ("big.zip", archive, "application/zip")})

    assert response.status_code == 413
    assert response.json()["detail"] == "Project archive is too large."


def test_report_endpoint_returns_pdf(client):
    archive = make_zip({"README.md": "# Project\n\n## Setup\nRun it.\n\n## Tech Stack\nPython\n\n## Screenshots\n![x](x.png)\n"})
    upload = client.post("/analyses/upload", files={"file": ("report.zip", archive, "application/zip")})
    analysis_id = upload.json()["id"]

    response = client.get(f"/analyses/{analysis_id}/report")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")


def test_delete_analysis_removes_related_rows(client):
    archive = make_zip(
        {
            "project/package.json": '{"scripts":{"test":"vitest"},"dependencies":{"react":"19.0.0"}}',
            "project/README.md": "# Project\n",
            "project/.env": "API_KEY=abc12345678901234567890\n",
        }
    )
    upload = client.post("/analyses/upload", files={"file": ("project.zip", archive, "application/zip")})
    analysis_id = upload.json()["id"]

    response = client.delete(f"/analyses/{analysis_id}")

    assert response.status_code == 200
    assert response.json() == {"deleted": True, "analysis_id": analysis_id}
    with SessionLocal() as session:
        assert session.get(models.Analysis, analysis_id) is None
        assert session.query(models.Finding).filter(models.Finding.analysis_id == analysis_id).count() == 0
        assert session.query(models.DetectedTechnology).filter(models.DetectedTechnology.analysis_id == analysis_id).count() == 0
        assert session.query(models.FileSummary).filter(models.FileSummary.analysis_id == analysis_id).count() == 0


def test_delete_missing_analysis_returns_404(client):
    response = client.delete("/analyses/999999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Analysis not found."


def test_reset_all_analyses_removes_related_rows(client):
    archive = make_zip({"project/README.md": "# Project\n"})
    first = client.post("/analyses/upload", files={"file": ("one.zip", archive, "application/zip")})
    second = client.post("/analyses/upload", files={"file": ("two.zip", archive, "application/zip")})
    assert first.status_code == 201
    assert second.status_code == 201

    response = client.delete("/analyses/reset")

    assert response.status_code == 200
    assert response.json()["deleted_count"] == 2
    assert client.get("/analyses").json() == []
    with SessionLocal() as session:
        assert session.query(models.Analysis).count() == 0
        assert session.query(models.Finding).count() == 0
        assert session.query(models.DetectedTechnology).count() == 0
        assert session.query(models.FileSummary).count() == 0
