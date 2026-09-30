"""End-to-end integration test validating the entire student journey (Step 4 Demo Scenario)."""

from fastapi.testclient import TestClient
from backend.api.app import app
from backend.utils.security import create_access_token

client = TestClient(app)
client.headers["Authorization"] = f"Bearer {create_access_token({'sub': 'default_student', 'email': 'student@example.com', 'role': 'STUDENT'})}"



def test_full_student_journey_scenario():
    """Perform the exact Step 4 End-to-End Demo Scenario:
    1. Select Student A (AI/ML) demo profile.
    2. Verify AI/ML recommendations appear at top.
    3. Open an opportunity: verify match score, matched skills, missing skills, explanation.
    4. Save the opportunity: verify saved in database.
    5. Open Saved: verify saved opportunity appears.
    6. Mark application as Applied (simulating Apply Now flow).
    7. Open Applications: verify application appears.
    8. Change status to Interviewing: verify status changes.
    9. Open Skill Gaps: verify missing skills appear.
    10. Switch to Student B (Web/Backend): verify recommendations change completely.
    """
    # 1. Select Student A / AI-ML demo profile
    res_a = client.post("/api/student/demo/student_a")
    assert res_a.status_code == 200
    student_a = res_a.json()["student"]
    assert "Debasis" in student_a["name"]

    # 2. Verify AI/ML recommendations appear
    recs_a = client.get("/api/matching/recommendations?min_score=30&limit=5").json()
    assert len(recs_a) > 0
    top_opp_a = recs_a[0]
    # AI/ML role should be top for Student A
    assert any(ml_term in (top_opp_a["title"] + " " + " ".join(top_opp_a.get("skills", []))).lower()
               for ml_term in ["machine learning", "ai", "vision", "deep learning", "nlp", "python"])

    # 3. Open opportunity insights / details
    insights = client.get(f"/api/matching/insights/{top_opp_a['opportunity_id']}").json()
    assert "match_score" in insights
    assert "matched_skills" in insights
    assert "missing_skills" in insights
    assert "explanation" in insights
    assert insights["match_score"] > 0
    assert len(insights["explanation"]) > 10

    # 4. Save the opportunity
    save_res = client.post(f"/api/opportunities/{top_opp_a['opportunity_id']}/save")
    assert save_res.status_code == 200

    # 5. Open Saved and verify it appears
    saved_list = client.get("/api/student/saved").json()
    assert any(o["id"] == top_opp_a["opportunity_id"] for o in saved_list)

    # 6. Apply Now Flow -> Track Application
    apply_res = client.post("/api/applications", json={
        "company": top_opp_a["company"],
        "role": top_opp_a["title"],
        "opportunity_id": top_opp_a["opportunity_id"],
        "status": "Applied",
        "apply_url": top_opp_a["apply_url"],
        "notes": "Applied via official portal"
    })
    assert apply_res.status_code == 200
    app_id = apply_res.json()["id"]

    # 7. Open Applications and verify it appears
    all_apps = client.get("/api/applications").json()
    tracked = next((a for a in all_apps if a["id"] == app_id), None)
    assert tracked is not None
    assert tracked["status"] == "Applied"
    assert tracked["company"] == top_opp_a["company"]
    # Verify original URL is preserved
    assert tracked["apply_url"] == top_opp_a["apply_url"]

    # 8. Change status to Interview
    update_res = client.put(f"/api/applications/{app_id}", json={
        "status": "Interviewing",
        "notes": "Technical screening scheduled"
    })
    assert update_res.status_code == 200
    assert update_res.json()["status"] == "Interviewing"

    # 9. Open Skill Gaps and verify missing skills appear
    gaps_a = client.get("/api/matching/skill-gaps").json()
    assert gaps_a["student"] == "Debasis Behera"
    assert "missing_skills_frequency" in gaps_a
    assert "high_priority" in gaps_a

    # 10. Switch to Student B (Web/Backend)
    res_b = client.post("/api/student/demo/student_b")
    assert res_b.status_code == 200
    student_b = res_b.json()["student"]
    assert "Priya" in student_b["name"]

    # Verify recommendations change
    recs_b = client.get("/api/matching/recommendations?min_score=30&limit=5").json()
    assert len(recs_b) > 0
    top_opp_b = recs_b[0]
    # Web/Backend role should be top for Student B
    assert any(web_term in (top_opp_b["title"] + " " + " ".join(top_opp_b.get("skills", []))).lower()
               for web_term in ["web", "full", "frontend", "backend", "react", "javascript", "node", "typescript"])
    # The top recommended opportunity for Student A should differ from Student B
    assert top_opp_a["opportunity_id"] != top_opp_b["opportunity_id"]
