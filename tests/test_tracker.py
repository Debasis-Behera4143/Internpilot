"""Unit tests for student application tracking."""

from backend.services.tracker_service import (
    get_all_applications,
    add_application,
    update_application_status
)


def test_tracker_lifecycle():
    """Verify application creation, listing, and status updates."""
    # 1. Add application
    app = add_application(
        company="Anthropic Labs",
        role="AI Research Fellow",
        status="Applied",
        notes="Applied with updated research resume"
    )
    assert app.id is not None
    assert app.company == "Anthropic Labs"
    assert app.status == "Applied"

    # 2. Update status
    updated = update_application_status(app.id, "Interviewing", notes="Interview scheduled for Monday")
    assert updated is not None
    assert updated.status == "Interviewing"
    assert "Monday" in updated.notes

    # 3. Retrieve all
    all_apps = get_all_applications()
    match = next((a for a in all_apps if a.id == app.id), None)
    assert match is not None
    assert match.status == "Interviewing"
