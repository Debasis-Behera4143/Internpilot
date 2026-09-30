"""Unit tests for skill gap detection and analysis."""

from backend.ai.skill_gap import find_skill_gaps, analyze_skill_gap


def test_find_skill_gaps():
    """Verify detection of missing skills with case-insensitivity."""
    profile_skills = ["Python", "TensorFlow", "Machine Learning"]
    job_skills = ["python", "PyTorch", "Docker", "Machine Learning"]

    missing = find_skill_gaps(profile_skills, job_skills)
    assert "PyTorch" in missing
    assert "Docker" in missing
    assert "Python" not in missing
    assert "Machine Learning" not in missing


def test_analyze_skill_gap():
    """Verify comprehensive skill gap analysis breakdown."""
    profile = ["Python", "SQL", "Git"]
    required = ["Python", "SQL", "Docker", "FastAPI"]

    res = analyze_skill_gap(profile, required)
    assert res["match_percentage"] == 50.0
    assert len(res["matching_skills"]) == 2
    assert len(res["missing_skills"]) == 2
    assert "Docker" in res["missing_skills"]
