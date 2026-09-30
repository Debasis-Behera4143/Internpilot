"""Tests for aggregated skill gaps endpoint and priority categorization."""

from fastapi.testclient import TestClient
from backend.api.app import app
from backend.utils.security import create_access_token

client = TestClient(app)
client.headers["Authorization"] = f"Bearer {create_access_token({'sub': 'default_student', 'email': 'student@example.com', 'role': 'STUDENT'})}"



def test_aggregated_skill_gaps_endpoint():
    """Verify GET /api/matching/skill-gaps returns aggregated market statistics and priority tiers."""
    res = client.get("/api/matching/skill-gaps?limit=25")
    assert res.status_code == 200
    data = res.json()

    assert "student" in data
    assert "recommendations_analyzed" in data
    assert "missing_skills_frequency" in data
    assert "high_priority" in data
    assert "medium_priority" in data
    assert "optional" in data
    assert "matched_skills_frequency" in data

    # Check structure of frequency items
    if data["missing_skills_frequency"]:
        first = data["missing_skills_frequency"][0]
        assert "skill" in first
        assert "count" in first
        assert "percentage" in first
        assert "priority" in first
        assert first["priority"] in ("high", "medium", "optional")


def test_skill_gaps_persona_personalization():
    """Verify skill gaps dynamically reflect the active student's missing capabilities."""
    # 1. Check Student A (AI/ML persona)
    client.post("/api/student/demo/student_a")
    res_a = client.get("/api/matching/skill-gaps")
    assert res_a.status_code == 200
    gaps_a = res_a.json()
    assert gaps_a["student"] == "Debasis Behera"

    # 2. Check Student B (Web/Backend persona)
    client.post("/api/student/demo/student_b")
    res_b = client.get("/api/matching/skill-gaps")
    assert res_b.status_code == 200
    gaps_b = res_b.json()
    assert gaps_b["student"] == "Priya Patel"
