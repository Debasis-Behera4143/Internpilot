"""Tests for application tracker API, lifecycle transitions, and apply URL preservation."""

from fastapi.testclient import TestClient
from backend.api.app import app
from backend.utils.security import create_access_token

client = TestClient(app)
client.headers["Authorization"] = f"Bearer {create_access_token({'sub': 'default_student', 'email': 'student@example.com', 'role': 'STUDENT'})}"



def test_track_and_list_application():
    """Verify logging a new job application and listing it."""
    payload = {
        "company": "DeepMind Technologies",
        "role": "Research Scientist Intern",
        "status": "Applied",
        "notes": "Applied online via official careers portal",
        "opportunity_id": "opp_test_tracker_123",
        "apply_url": "https://careers.google.com/jobs/results/123"
    }

    res = client.post("/api/applications", json=payload)
    assert res.status_code == 200
    created = res.json()
    assert created["company"] == payload["company"]
    assert created["role"] == payload["role"]
    assert created["status"] == "Applied"
    assert created["apply_url"] == payload["apply_url"]

    # Verify listed in GET
    list_res = client.get("/api/applications")
    assert list_res.status_code == 200
    all_apps = list_res.json()
    assert any(a["id"] == created["id"] for a in all_apps)


def test_update_application_status_put_and_patch():
    """Verify updating application status via PUT and PATCH endpoints."""
    # Create application
    create_res = client.post("/api/applications", json={
        "company": "Stripe Labs",
        "role": "Backend Engineering Intern",
        "status": "Applied",
        "opportunity_id": "opp_stripe_test"
    })
    app_id = create_res.json()["id"]

    # 1. Update via PATCH
    patch_res = client.patch(f"/api/applications/{app_id}", json={
        "status": "Interviewing",
        "notes": "Technical screen completed"
    })
    assert patch_res.status_code == 200
    assert patch_res.json()["status"] == "Interviewing"
    assert "screen" in patch_res.json()["notes"]

    # 2. Update via PUT
    put_res = client.put(f"/api/applications/{app_id}", json={
        "status": "Offered",
        "notes": "Offer letter received!"
    })
    assert put_res.status_code == 200
    assert put_res.json()["status"] == "Offered"
    assert "Offer" in put_res.json()["notes"]


def test_duplicate_application_updates_existing():
    """Verify creating an application for an opportunity that is already tracked updates rather than duplicates."""
    opp_id = "opp_duplicate_check_test"

    res1 = client.post("/api/applications", json={
        "company": "GitHub",
        "role": "Systems Engineering Intern",
        "opportunity_id": opp_id,
        "status": "Applied"
    })
    assert res1.status_code == 200
    id1 = res1.json()["id"]

    # Apply again for same opportunity
    res2 = client.post("/api/applications", json={
        "company": "GitHub",
        "role": "Systems Engineering Intern",
        "opportunity_id": opp_id,
        "status": "Interviewing",
        "notes": "Updated note"
    })
    assert res2.status_code == 200
    id2 = res2.json()["id"]

    assert id1 == id2, "Expected duplicate application to reuse and update existing record"
    assert res2.json()["status"] == "Interviewing"
