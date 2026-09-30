"""Test deterministic AI matching and explainability for Student A and Student B personas (Step 5 Verification)."""

from fastapi.testclient import TestClient
from backend.api.app import app
from backend.services.student_service import get_current_student
from backend.utils.security import create_access_token

client = TestClient(app)
client.headers["Authorization"] = f"Bearer {create_access_token({'sub': 'default_student', 'email': 'student@example.com', 'role': 'STUDENT'})}"



def test_student_a_aiml_personalization():
    """Verify Student A (Debasis Behera - AIML) receives top recommendations in AI/ML domains."""
    res_switch = client.post("/api/student/demo/student_a")
    assert res_switch.status_code == 200
    student_data = res_switch.json()["student"]
    assert "Debasis" in student_data["name"]

    recs_res = client.get("/api/matching/recommendations?min_score=35&limit=10")
    assert recs_res.status_code == 200
    recs = recs_res.json()
    assert len(recs) > 0

    top_rec = recs[0]
    # Check that top recommendation is an AI/ML, Vision, NLP, or Data Science role
    top_title_skills = (top_rec["title"] + " " + " ".join(top_rec.get("skills", []))).lower()
    assert any(term in top_title_skills for term in [
        "machine learning", "ai", "vision", "deep learning", "nlp", "python", "data science"
    ]), f"Expected top recommendation to be AI/ML related, got: {top_rec['title']}"


def test_student_b_web_personalization():
    """Verify Student B (Priya Patel - Web/Backend) receives top recommendations in Web domains."""
    res_switch = client.post("/api/student/demo/student_b")
    assert res_switch.status_code == 200
    student_data = res_switch.json()["student"]
    assert "Priya" in student_data["name"]

    recs_res = client.get("/api/matching/recommendations?min_score=35&limit=10")
    assert recs_res.status_code == 200
    recs = recs_res.json()
    assert len(recs) > 0

    top_rec = recs[0]
    # Check that top recommendation is a Web, Frontend, Backend, or Full-Stack role
    top_title_skills = (top_rec["title"] + " " + " ".join(top_rec.get("skills", []))).lower()
    assert any(term in top_title_skills for term in [
        "web", "react", "node", "full stack", "frontend", "backend", "javascript", "typescript"
    ]), f"Expected top recommendation to be Web related, got: {top_rec['title']}"


def test_personas_receive_different_recommendations():
    """Verify Student A and Student B receive distinct top recommendation feeds."""
    # Run Student A
    client.post("/api/student/demo/student_a")
    recs_a = client.get("/api/matching/recommendations?min_score=35&limit=5").json()

    # Run Student B
    client.post("/api/student/demo/student_b")
    recs_b = client.get("/api/matching/recommendations?min_score=35&limit=5").json()

    assert len(recs_a) > 0 and len(recs_b) > 0
    # Top opportunity IDs must be different for the two distinct personas
    assert recs_a[0]["opportunity_id"] != recs_b[0]["opportunity_id"]


def test_explainability_consistency():
    """Verify that match details, matched skills, missing skills, and explanations are strictly truthful."""
    # Set to Student A
    client.post("/api/student/demo/student_a")
    student = get_current_student()
    student_skills_lower = {s.lower() for s in student.skills}

    recs = client.get("/api/matching/recommendations?min_score=35&limit=5").json()
    assert len(recs) > 0

    for rec in recs[:3]:
        opp_id = rec["opportunity_id"]
        insights = client.get(f"/api/matching/insights/{opp_id}").json()

        assert "match_score" in insights
        assert 0 <= insights["match_score"] <= 100
        assert "explanation" in insights
        assert len(insights["explanation"]) > 10

        details = insights.get("match_details", {})
        matched = details.get("matched_skills", [])
        missing = details.get("missing_skills", [])

        # Crucial Explainability Check:
        # Every matched skill MUST actually be in the student's skill profile
        for skill in matched:
            assert skill.lower() in student_skills_lower, (
                f"Explainability bug: claimed student has matched skill '{skill}', "
                f"but it is NOT in student's profile skills: {student.skills}"
            )

        # Every missing skill must NOT be in the student's skill profile
        for skill in missing:
            assert skill.lower() not in student_skills_lower, (
                f"Explainability bug: claimed skill '{skill}' is missing, "
                f"but student actually has it!"
            )
