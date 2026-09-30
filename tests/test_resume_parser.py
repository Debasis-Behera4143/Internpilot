"""Unit tests for PDF resume parser and heuristic structured extraction."""

import pytest
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from backend.ai.resume_parser import (
    parse_resume,
    extract_contact_info,
    extract_education,
    extract_sections,
    extract_raw_text_from_pdf
)


@pytest.fixture
def sample_pdf_resume(tmp_path) -> Path:
    """Generate a clean synthetic PDF resume for testing using reportlab."""
    pdf_path = tmp_path / "test_student_resume.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=letter)
    
    # Header & Contact
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "Debasis Behera")
    c.setFont("Helvetica", 10)
    c.drawString(50, 735, "Email: debasis.behera@example.edu | Phone: +91 9876543210")
    
    # Education
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 700, "EDUCATION")
    c.setFont("Helvetica", 10)
    c.drawString(50, 685, "B.Tech in Artificial Intelligence & Machine Learning, 2026")
    c.drawString(50, 670, "National Institute of Technology | CGPA: 9.2 / 10")
    
    # Skills
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 640, "SKILLS")
    c.setFont("Helvetica", 10)
    c.drawString(50, 625, "Languages: Python, C++, SQL")
    c.drawString(50, 610, "Machine Learning: PyTorch, TensorFlow, Scikit-learn, Deep Learning, NLP")
    c.drawString(50, 595, "Tools: Docker, Git, Linux, FastAPI")
    
    # Projects
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 565, "PROJECTS")
    c.setFont("Helvetica", 10)
    c.drawString(50, 550, "* Multimodal VQA System using Vision Transformers and PyTorch")
    c.drawString(50, 535, "* Intelligent Real-time Defect Segmentation with OpenCV and CNNs")
    
    # Experience
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, 505, "EXPERIENCE")
    c.setFont("Helvetica", 10)
    c.drawString(50, 490, "* Undergraduate AI Research Intern at Vision Computing Lab (2025)")
    
    c.save()
    return pdf_path


def test_parse_resume_end_to_end(sample_pdf_resume):
    """Verify end-to-end PDF parsing and entity extraction."""
    parsed = parse_resume(sample_pdf_resume)

    assert parsed["name"] == "Debasis Behera"
    assert parsed["email"] == "debasis.behera@example.edu"
    assert "9876543210" in (parsed["phone"] or "")

    # Education checks
    assert len(parsed["education"]) > 0
    edu = parsed["education"][0]
    assert edu["graduation_year"] == 2026
    assert edu["cgpa"] >= 9.0

    # Skills checks
    skills = parsed["skills"]
    assert "Python" in skills
    assert "PyTorch" in skills
    assert "TensorFlow" in skills
    assert "Docker" in skills
    assert "FastAPI" in skills

    # Projects & Experience
    assert len(parsed["projects"]) > 0
    assert len(parsed["experience"]) > 0


def test_contact_info_extraction_heuristics():
    """Verify phone and email extraction against diverse formats."""
    text = (
        "Jane Doe\n"
        "Contact: jane.doe@university.ac.in\n"
        "Phone: +91-9812345678\n"
        "Github: https://github.com/janedoe"
    )
    contact = extract_contact_info(text)
    assert contact["name"] == "Jane Doe"
    assert contact["email"] == "jane.doe@university.ac.in"
    assert "9812345678" in contact["phone"]


def test_missing_file_handling():
    """Verify FileNotFoundError on non-existent file."""
    with pytest.raises(FileNotFoundError):
        parse_resume("data/resumes/non_existent_file.pdf")
