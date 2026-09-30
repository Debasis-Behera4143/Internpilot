"""Integration tests for AI matching, recommendation, and resume upload endpoints."""

import io
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from backend.api.app import app
from backend.utils.security import create_access_token

client = TestClient(app)
client.headers["Authorization"] = f"Bearer {create_access_token({'sub': 'default_student', 'email': 'student@example.com', 'role': 'STUDENT'})}"



def _create_sample_pdf_bytes() -> bytes:
    """Generate in-memory PDF resume bytes for HTTP upload testing."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(100, 750, "Priya Patel")
    c.drawString(100, 730, "Email: priya.test@example.edu | Phone: +91 9123456780")
    c.drawString(100, 700, "EDUCATION: B.Tech Computer Science, 2026, CGPA: 8.8")
    c.drawString(100, 670, "SKILLS: React, Node.js, TypeScript, PostgreSQL, Docker")
    c.drawString(100, 640, "PROJECTS: E-commerce web application with REST APIs")
    c.save()
    buf.seek(0)
    return buf.read()


def test_api_recommendations_endpoint():
    """Verify GET /api/matching/recommendations returns ranked opportunities with explanations."""
    response = client.get("/api/matching/recommendations?limit=10")
    assert response.status_code == 200
    recs = response.json()
    assert isinstance(recs, list)

    if len(recs) > 0:
        first = recs[0]
        assert "opportunity_id" in first
        assert "match_score" in first
        assert "matched_skills" in first
        assert "missing_skills" in first
        assert "explanation" in first
        assert "eligibility" in first
        assert 0.0 <= first["match_score"] <= 100.0


def test_api_recommendations_min_score_filter():
    """Verify min_score query filter."""
    response = client.get("/api/matching/recommendations?min_score=50")
    assert response.status_code == 200
    recs = response.json()
    for r in recs:
        assert r["match_score"] >= 50.0


def test_api_batch_matching_endpoint():
    """Verify POST /api/matching/run executes batch matching across all active opportunities."""
    response = client.post("/api/matching/run")
    assert response.status_code == 200
    data = response.json()
    assert "student" in data
    assert "opportunities_processed" in data
    assert "recommendations_generated" in data
    assert "average_score" in data


def test_api_resume_upload_success():
    """Verify POST /api/students/resume extracts structured skills and contact data from PDF."""
    pdf_bytes = _create_sample_pdf_bytes()
    files = {
        "file": ("priya_resume.pdf", pdf_bytes, "application/pdf")
    }

    response = client.post("/api/students/resume?apply_to_profile=true", files=files)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert "extracted_data" in data
    extracted = data["extracted_data"]
    assert extracted["name"] == "Priya Patel"
    assert "priya.test@example.edu" in extracted["email"]
    assert "React" in extracted["skills"]
    assert "TypeScript" in extracted["skills"]


def test_api_resume_upload_invalid_type():
    """Verify POST /api/students/resume rejects non-PDF files with 400 Bad Request."""
    files = {
        "file": ("malicious.exe", b"binary content", "application/octet-stream")
    }
    response = client.post("/api/students/resume", files=files)
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]
