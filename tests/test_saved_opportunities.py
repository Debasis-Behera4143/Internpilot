"""Tests for student saved/bookmarked opportunities."""

import pytest
from fastapi.testclient import TestClient
from backend.api.app import app
from backend.services.opportunity_service import get_all_opportunities
from backend.services.saved_service import get_saved_opportunity_ids
from backend.utils.security import create_access_token

client = TestClient(app)
client.headers["Authorization"] = f"Bearer {create_access_token({'sub': 'default_student', 'email': 'student@example.com', 'role': 'STUDENT'})}"



def test_save_and_list_saved_opportunity():
    """Verify bookmarking an opportunity and listing it."""
    opps = get_all_opportunities()
    assert len(opps) > 0, "Requires at least one opportunity in DB"
    target_opp = opps[0]

    # Save opportunity
    save_res = client.post(f"/api/opportunities/{target_opp.id}/save")
    assert save_res.status_code == 200
    save_data = save_res.json()
    assert save_data["status"] == "success"
    assert save_data["bookmark"]["opportunity_id"] == target_opp.id

    # Check in saved list
    list_res = client.get("/api/student/saved")
    assert list_res.status_code == 200
    saved_list = list_res.json()
    assert any(o["id"] == target_opp.id for o in saved_list)

    # Check in IDs list
    ids_res = client.get("/api/opportunities/saved/ids")
    assert ids_res.status_code == 200
    assert target_opp.id in ids_res.json()["saved_ids"]


def test_duplicate_save_prevention():
    """Verify saving the same opportunity multiple times is idempotent and creates no duplicate rows."""
    opps = get_all_opportunities()
    target_opp = opps[0]

    # Save twice
    res1 = client.post(f"/api/opportunities/{target_opp.id}/save")
    res2 = client.post(f"/api/opportunities/{target_opp.id}/save")
    assert res1.status_code == 200
    assert res2.status_code == 200

    # Retrieve all saved
    list_res = client.get("/api/student/saved")
    matches = [o for o in list_res.json() if o["id"] == target_opp.id]
    assert len(matches) == 1, "Expected exactly 1 record for this saved opportunity"


def test_unsave_opportunity():
    """Verify unsaving / removing an opportunity bookmark."""
    opps = get_all_opportunities()
    target_opp = opps[0]

    # Ensure saved first
    client.post(f"/api/opportunities/{target_opp.id}/save")

    # Unsave
    del_res = client.delete(f"/api/opportunities/{target_opp.id}/save")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"

    # Verify no longer in saved IDs
    ids_res = client.get("/api/opportunities/saved/ids")
    assert target_opp.id not in ids_res.json()["saved_ids"]


def test_save_nonexistent_opportunity():
    """Verify attempting to save an invalid opportunity ID returns 404."""
    res = client.post("/api/opportunities/non_existent_id_9999/save")
    assert res.status_code == 404
