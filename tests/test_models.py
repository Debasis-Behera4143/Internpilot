"""Unit tests for Opportunity and Student domain models."""

import pytest
from backend.models.opportunity import Opportunity
from backend.models.student import Student
from backend.models.application import Application


def test_opportunity_model_all_required_fields():
    """Verify that an Opportunity instance contains and validates all required fields."""
    opp = Opportunity(
        title="ML Engineer Intern",
        company="NeuroTech Corp",
        description="Develop neural networks for signal processing.",
        opportunity_type="internship",
        skills=["Python", "PyTorch", "Signal Processing"],
        location="Remote",
        remote=True,
        stipend="₹40,000 / month",
        salary=None,
        experience="Fresher",
        eligibility="B.Tech CS/AI",
        deadline="2026-06-30",
        source="Campus Drive",
        source_url="https://example.com/jobs/1",
        apply_url="https://example.com/apply/1",
        posted_date="2026-05-01",
        collected_date="2026-05-02",
        status="open"
    )

    assert opp.title == "ML Engineer Intern"
    assert opp.company == "NeuroTech Corp"
    assert opp.remote is True
    assert "Python" in opp.skills
    assert opp.apply_url == "https://example.com/apply/1"
    assert opp.status == "open"
    assert opp.collected_date == "2026-05-02"


def test_opportunity_from_legacy_job():
    """Verify conversion from legacy InternPilot job dict {title, link, type, description, source}."""
    legacy = {
        "title": "AlphaCorp • Deep Learning Engineer",
        "link": "https://alphacorp.example/jobs/99",
        "type": "ai/ml",
        "description": "Requires Python and Machine Learning expertise",
        "source": "yc"
    }
    opp = Opportunity.from_legacy_job(legacy)

    assert opp.company == "AlphaCorp"
    assert opp.title == legacy["title"]
    assert opp.source == "yc"
    assert opp.apply_url == legacy["link"]
    assert "Python" in opp.skills
    assert "Machine Learning" in opp.skills


def test_student_model_all_required_fields():
    """Verify that a Student instance contains and validates all required student-centric fields."""
    student = Student(
        name="Alex Smith",
        email="alex@university.edu",
        education="B.Tech",
        branch="Computer Science",
        graduation_year=2026,
        cgpa=8.9,
        skills=["Python", "PyTorch", "FastAPI"],
        preferred_roles=["ML Intern", "Software Engineer"],
        preferred_locations=["Remote", "Bengaluru"],
        remote_preference=True,
        resume_path="/path/to/resume.pdf"
    )

    assert student.name == "Alex Smith"
    assert student.email == "alex@university.edu"
    assert student.education == "B.Tech"
    assert student.branch == "Computer Science"
    assert student.graduation_year == 2026
    assert student.cgpa == 8.9
    assert "Python" in student.skills
    assert student.remote_preference is True
    assert student.resume_path == "/path/to/resume.pdf"

    # Search text includes skills and education
    search_text = student.get_search_text()
    assert "Python" in search_text
    assert "Computer Science" in search_text


def test_application_model():
    """Verify Application model creation and defaults."""
    app = Application(
        company="Google",
        role="SWE Intern",
        status="Applied",
        notes="Applied via referral"
    )
    assert app.company == "Google"
    assert app.role == "SWE Intern"
    assert app.status == "Applied"
    assert app.notes == "Applied via referral"
