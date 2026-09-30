"""Unit tests for explainability generator and skill gap priority classification."""

from backend.ai.explanation import generate_recommendation_explanation
from backend.ai.skill_gap import classify_missing_skills, compute_detailed_skill_gap


def test_generate_recommendation_explanation():
    """Verify natural language explanation generation from subscore signals."""
    exp = generate_recommendation_explanation(
        match_score=88.5,
        matched_skills=["Python", "Machine Learning"],
        missing_skills=["TensorFlow", "Docker"],
        role_score=0.9,
        eligibility_status="eligible",
        location_score=1.0,
        is_remote=True,
        student_remote_pref=True,
        job_location="Remote",
        job_title="ML Intern",
        company="AI Research Co"
    )

    assert "Strong match" in exp["headline"]
    assert "Python" in exp["summary"]
    assert "remote" in exp["summary"].lower()
    assert len(exp["reasons"]) > 0
    assert len(exp["improvements"]) > 0
    assert exp["eligibility_badge"] == "Eligible"


def test_classify_missing_skills_priorities():
    """Verify missing skills are assigned to correct priority tiers."""
    missing = ["Docker", "Kubernetes", "Redis"]
    title = "Senior Docker Platform Engineer"
    desc = "Must have strong Docker experience. Good to have familiarity with Redis."

    categorized = classify_missing_skills(missing, job_title=title, job_description=desc)

    # Docker is in title and description "Must have" -> High
    assert "Docker" in categorized["high_priority"]
    # Redis has "Good to have" -> Optional
    assert "Redis" in categorized["optional"]
    # Kubernetes has no special keywords -> Medium
    assert "Kubernetes" in categorized["medium_priority"]


def test_compute_detailed_skill_gap():
    """Verify combined skill gap breakdown with categorized roadmap."""
    profile = ["Python", "PyTorch"]
    job_skills = ["Python", "PyTorch", "TensorFlow", "Docker"]

    res = compute_detailed_skill_gap(
        profile_skills=profile,
        job_skills=job_skills,
        job_title="Machine Learning Intern"
    )

    assert res["match_percentage"] == 50.0
    assert "Python" in res["matched_skills"]
    assert "TensorFlow" in res["missing_skills"]
    assert "categorized_missing" in res
