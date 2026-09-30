"""Unit tests for hybrid AI career match scoring and multi-factor decomposition."""

from backend.ai.scorer import (
    calculate_semantic_score,
    calculate_skill_score,
    calculate_role_score,
    evaluate_eligibility,
    calculate_location_score,
    calculate_experience_score,
    calculate_match_details,
    score_job
)
from backend.models.student import Student
from backend.models.opportunity import Opportunity


def test_subscores_calculation():
    """Verify subscores compute proper fractional values [0.0, 1.0]."""
    student = Student(
        name="Candidate",
        skills=["Python", "Machine Learning", "PyTorch"],
        preferred_roles=["ML Intern"],
        preferred_locations=["Bengaluru"],
        remote_preference=True,
        cgpa=9.0,
        graduation_year=2026
    )

    opp = Opportunity(
        title="ML Engineering Intern",
        company="AI Tech",
        skills=["Python", "PyTorch", "Docker"],
        location="Bengaluru, India",
        remote=True,
        experience="Fresher / Student",
        eligibility="Open to 2026 batch",
        apply_url="https://example.com/apply"
    )

    sem_score = calculate_semantic_score(student, opp)
    assert 0.0 <= sem_score <= 1.0

    skill_score, matched, missing = calculate_skill_score(student.skills, opp.skills)
    assert 0.0 <= skill_score <= 1.0
    assert "Python" in matched
    assert "PyTorch" in matched
    assert "Docker" in missing

    role_score = calculate_role_score(student.preferred_roles, opp.title)
    assert role_score >= 0.7

    elig_score, elig_status = evaluate_eligibility(student, opp)
    assert elig_status == "eligible"
    assert elig_score >= 0.8

    loc_score = calculate_location_score(student, opp)
    assert loc_score == 1.0

    exp_score = calculate_experience_score(student, opp)
    assert exp_score == 1.0


def test_calculate_match_details_structure():
    """Verify full structure returned by calculate_match_details."""
    student = Student(
        name="Candidate",
        skills=["JavaScript", "React"],
        preferred_roles=["Frontend Intern"]
    )
    opp = Opportunity(
        title="Frontend React Intern",
        company="Web Lab",
        skills=["React", "JavaScript", "TypeScript"],
        apply_url="https://example.com"
    )

    details = calculate_match_details(opp, student=student)

    assert "match_score" in details
    assert "semantic_score" in details
    assert "skill_score" in details
    assert "role_score" in details
    assert "eligibility_score" in details
    assert "location_score" in details
    assert "matched_skills" in details
    assert "missing_skills" in details
    assert "eligibility" in details
    assert "explanation" in details

    assert 0.0 <= details["match_score"] <= 100.0
    assert "TypeScript" in details["missing_skills"]


def test_score_job_relative_ranking():
    """Verify relevant opportunity scores higher than an unrelated one."""
    student = Student(
        name="AIML Student",
        skills=["Python", "TensorFlow", "Deep Learning"],
        preferred_roles=["AI Intern"]
    )

    ai_opp = Opportunity(
        title="Deep Learning & AI Intern",
        company="Neural Labs",
        skills=["Python", "TensorFlow", "Deep Learning"],
        apply_url="https://example.com/ai"
    )

    sales_opp = Opportunity(
        title="Corporate Sales Executive",
        company="Sales Inc",
        skills=["Negotiation", "B2B Sales", "Cold Calling"],
        apply_url="https://example.com/sales"
    )

    ai_score = score_job(ai_opp, student=student)
    sales_score = score_job(sales_opp, student=student)

    assert ai_score > sales_score
    assert ai_score >= 60.0


def test_edge_cases_empty_data():
    """Verify system does not crash on empty student skills or minimal opportunity description."""
    empty_student = Student(name="Empty", skills=[])
    minimal_opp = Opportunity(title="Generic Intern", apply_url="https://example.com")

    score = score_job(minimal_opp, student=empty_student)
    assert isinstance(score, float)
    assert 0.0 <= score <= 100.0
