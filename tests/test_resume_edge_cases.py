"""Test resume parsing edge cases, malformed PDFs, and error resiliency (Step 5 Verification)."""

import io
from pathlib import Path
from fastapi.testclient import TestClient
from backend.api.app import app
from backend.ai.resume_parser import parse_resume, extract_raw_text_from_pdf
from backend.utils.config import settings
from backend.utils.security import create_access_token

import pytest
from scripts.create_test_resumes import generate_all_test_resumes

client = TestClient(app)
client.headers["Authorization"] = f"Bearer {create_access_token({'sub': 'default_student', 'email': 'student@example.com', 'role': 'STUDENT'})}"
RESUMES_DIR = settings.DATA_DIR / "test_resumes"


@pytest.fixture(scope="session", autouse=True)
def ensure_test_resumes():
    """Ensure minimal synthetic test PDF fixtures are present in data/test_resumes/."""
    generate_all_test_resumes()



def test_resume_a_aiml_full_extraction():
    """Verify detailed extraction of complete AI/ML student resume."""
    pdf_path = RESUMES_DIR / "resume_a_aiml.pdf"
    assert pdf_path.exists(), "test_resumes/resume_a_aiml.pdf must exist"

    data = parse_resume(pdf_path)
    assert data["name"] == "Debasis Behera"
    assert "debasis.behera@example.edu" in data["email"]
    assert "9876543210" in (data["phone"] or "")

    # Education extraction
    assert len(data["education"]) > 0
    edu = data["education"][0]
    assert "B.Tech" in edu["degree"]
    assert "Artificial Intelligence" in edu["branch"]
    assert edu["graduation_year"] == 2026
    assert edu["cgpa"] == 9.2

    # Technical skills
    skills_lower = [s.lower() for s in data["skills"]]
    assert "python" in skills_lower
    assert "pytorch" in skills_lower
    assert any("machine learning" in s for s in skills_lower)
    assert any("computer vision" in s for s in skills_lower)

    # Sections
    assert len(data["projects"]) > 0
    assert len(data["experience"]) > 0


def test_resume_b_web_full_extraction():
    """Verify detailed extraction of complete Web/Backend student resume."""
    pdf_path = RESUMES_DIR / "resume_b_web.pdf"
    assert pdf_path.exists()

    data = parse_resume(pdf_path)
    assert data["name"] == "Priya Patel"
    assert "priya.web@example.edu" in data["email"]
    assert "9123456780" in (data["phone"] or "")

    skills_lower = [s.lower() for s in data["skills"]]
    assert "react" in skills_lower
    assert "javascript" in skills_lower
    assert any("node" in s for s in skills_lower)
    assert "docker" in skills_lower


def test_resume_c_incomplete_graceful_handling():
    """Verify incomplete resume does not crash and extracts whatever fields are available."""
    pdf_path = RESUMES_DIR / "resume_c_incomplete.pdf"
    assert pdf_path.exists()

    data = parse_resume(pdf_path)
    assert data is not None
    assert data["name"] == "Rahul Verma"
    # Incomplete resume has no phone; should be None without raising an error
    assert data["phone"] is None
    # Still extracts available skills
    skills_lower = [s.lower() for s in data["skills"]]
    assert "python" in skills_lower or "javascript" in skills_lower


def test_upload_non_pdf_rejected():
    """Upload endpoint must reject non-PDF file formats with HTTP 400."""
    fake_txt = io.BytesIO(b"Hello world I am a text resume")
    response = client.post(
        "/api/student/resume",
        files={"file": ("resume.txt", fake_txt, "text/plain")}
    )
    assert response.status_code == 400
    assert "Only PDF documents" in response.json()["detail"]


def test_upload_empty_file_rejected():
    """Upload endpoint must reject empty 0-byte PDF files with HTTP 400."""
    empty_pdf = io.BytesIO(b"")
    response = client.post(
        "/api/student/resume",
        files={"file": ("empty.pdf", empty_pdf, "application/pdf")}
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_upload_valid_pdf_and_apply_to_profile():
    """Verify uploading a valid PDF and setting apply_to_profile=True updates the profile."""
    pdf_path = RESUMES_DIR / "resume_a_aiml.pdf"
    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    response = client.post(
        "/api/student/resume?apply_to_profile=true",
        files={"file": ("resume_a_aiml.pdf", io.BytesIO(file_bytes), "application/pdf")}
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "success"
    assert res_data["applied_to_profile"] is True

    # Verify student profile got updated
    student_res = client.get("/api/student")
    assert student_res.status_code == 200
    st_data = student_res.json()
    assert "PyTorch" in st_data["skills"]
    assert "Python" in st_data["skills"]


def test_upload_scanned_or_empty_text_pdf(tmp_path):
    """Verify that uploading a PDF without extractable text returns 422 with a clear explanation."""
    from reportlab.pdfgen import canvas
    blank_pdf = tmp_path / "blank_page.pdf"
    c = canvas.Canvas(str(blank_pdf))
    c.showPage()
    c.save()

    with open(blank_pdf, "rb") as f:
        content = f.read()

    response = client.post(
        "/api/students/resume?apply_to_profile=false",
        files={"file": ("blank_page.pdf", io.BytesIO(content), "application/pdf")}
    )
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    assert "Unable to extract text from this PDF" in data["detail"]


def test_upload_invalid_signature_pdf():
    """Verify that uploading a non-PDF file disguised as .pdf returns 400."""
    fake_pdf = io.BytesIO(b"NOT_A_REAL_PDF_CONTENT")
    response = client.post(
        "/api/students/resume",
        files={"file": ("fake.pdf", fake_pdf, "application/pdf")}
    )
    assert response.status_code == 400
    assert "Invalid file signature" in response.json()["detail"]

