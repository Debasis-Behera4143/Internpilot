"""Unit tests for AI semantic matching and scoring."""

from backend.ai.scorer import score_job
from backend.models.opportunity import Opportunity
from backend.models.student import Student


def test_score_job_with_opportunity_model():
    """Verify semantic similarity calculation using Opportunity and Student models."""
    student = Student(
        name="Candidate",
        education="B.Tech",
        branch="AI & Data Science",
        skills=["Python", "Machine Learning", "PyTorch", "FastAPI"],
        preferred_roles=["ML Intern", "AI Engineer"]
    )

    relevant_opp = Opportunity(
        title="Machine Learning Engineering Intern",
        company="AI Labs",
        description="Seeking an intern with Python, PyTorch, and ML experience to build models.",
        opportunity_type="ai/ml",
        skills=["Python", "PyTorch", "Machine Learning"],
        apply_url="https://example.com/apply"
    )

    unrelated_opp = Opportunity(
        title="Graphic Design & Illustrator Intern",
        company="Design Studio",
        description="Create vector illustrations, branding kits, and Figma mockups.",
        opportunity_type="design",
        skills=["Photoshop", "Illustrator", "Figma"],
        apply_url="https://example.com/apply2"
    )

    relevant_score = score_job(relevant_opp, student=student)
    unrelated_score = score_job(unrelated_opp, student=student)

    assert relevant_score > 0.0
    assert relevant_score > unrelated_score
    print(f"Relevant score: {relevant_score}%, Unrelated score: {unrelated_score}%")


def test_score_job_with_legacy_dict():
    """Verify backwards-compatibility with legacy dictionary representation."""
    legacy_job = {
        "title": "Python Machine Learning Intern",
        "type": "ai/ml",
        "description": "Python, data analysis, and machine learning models.",
        "source": "yc"
    }

    score = score_job(legacy_job)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0
