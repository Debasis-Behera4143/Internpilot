"""Tests for notification and alert preferences API."""

from fastapi.testclient import TestClient
from backend.api.app import app
from backend.utils.security import create_access_token

client = TestClient(app)
client.headers["Authorization"] = f"Bearer {create_access_token({'sub': 'default_student', 'email': 'student@example.com', 'role': 'STUDENT'})}"



def test_get_and_update_notification_preferences():
    """Verify getting default notification preferences and updating them."""
    # 1. GET preferences
    get_res = client.get("/api/student/preferences")
    assert get_res.status_code == 200
    prefs = get_res.json()
    assert "new_matching_opportunity" in prefs
    assert "deadline_approaching" in prefs
    assert "application_reminder" in prefs

    # 2. PUT preferences
    update_payload = {
        "new_matching_opportunity": False,
        "deadline_approaching": True,
        "application_reminder": True,
        "email_digest": True
    }
    put_res = client.put("/api/student/preferences", json=update_payload)
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["new_matching_opportunity"] is False
    assert updated["email_digest"] is True

    # 3. GET again to ensure persistence
    get_res2 = client.get("/api/student/preferences")
    assert get_res2.json()["new_matching_opportunity"] is False
    assert get_res2.json()["email_digest"] is True
