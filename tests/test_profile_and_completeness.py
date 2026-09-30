"""Tests for student profile editing, completeness breakdown, and demo mode switching."""

from fastapi.testclient import TestClient
from backend.api.app import app
from backend.utils.security import create_access_token

client = TestClient(app)
client.headers["Authorization"] = f"Bearer {create_access_token({'sub': 'default_student', 'email': 'student@example.com', 'role': 'STUDENT'})}"



def test_get_and_update_student_profile():
    """Verify retrieving and saving student profile details."""
    get_res = client.get("/api/student")
    assert get_res.status_code == 200
    current_prof = get_res.json()
    assert "name" in current_prof
    assert "skills" in current_prof

    # Update profile
    updated_payload = dict(current_prof)
    updated_payload["bio"] = "Updated engineering portfolio pitch for career platform tests."
    updated_payload["skills"] = list(set(current_prof.get("skills", []) + ["Docker", "Kubernetes"]))

    put_res = client.put("/api/student", json=updated_payload)
    assert put_res.status_code == 200
    saved = put_res.json()
    assert saved["bio"] == updated_payload["bio"]
    assert "Docker" in saved["skills"]


def test_profile_completeness_breakdown():
    """Verify profile completeness score calculation and section breakdown."""
    comp_res = client.get("/api/student/completeness")
    assert comp_res.status_code == 200
    data = comp_res.json()

    assert "score" in data
    assert isinstance(data["score"], (int, float))
    assert 0 <= data["score"] <= 100
    assert "completed" in data
    assert "missing" in data
    assert isinstance(data["completed"], list)
    assert isinstance(data["missing"], list)


def test_demo_profile_switching():
    """Verify switching active profile between Demo Student A and Student B."""
    # Switch to Student A (AI/ML)
    res_a = client.post("/api/student/demo/student_a")
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert "Debasis" in data_a["student"]["name"]
    assert "PyTorch" in data_a["student"]["skills"]

    # Switch to Student B (Web/Backend)
    res_b = client.post("/api/student/demo/student_b")
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert "Priya" in data_b["student"]["name"]
    assert "React" in data_b["student"]["skills"]
    assert "JavaScript" in data_b["student"]["skills"]


def test_invalid_demo_profile():
    """Verify requesting an unknown demo profile returns 404."""
    res = client.post("/api/student/demo/unknown_persona_xyz")
    assert res.status_code == 404
