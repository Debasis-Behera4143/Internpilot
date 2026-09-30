"""Test opportunity expiry and lifecycle evaluation (Step 5 Verification)."""

from datetime import date, timedelta
from backend.models.opportunity import Opportunity
from backend.services.expiry_service import (
    is_opportunity_expired,
    evaluate_opportunity_status,
    evaluate_and_update_expiry_in_db,
    DEFAULT_MAX_OPPORTUNITY_AGE_DAYS
)
from backend.database.db import SessionLocal, OpportunityDB
from backend.services.opportunity_service import save_opportunity


def test_future_deadline_remains_active():
    """Opportunities with future deadlines must remain active."""
    today = date(2026, 9, 17)
    opp = Opportunity(
        title="AI Intern",
        company="TechCorp",
        apply_url="https://example.com/apply1",
        deadline="2026-11-30",
        posted_date="2026-09-01",
        status="active"
    )
    is_expired, reason = is_opportunity_expired(opp, reference_date=today)
    assert not is_expired
    assert reason == "deadline_active"
    assert evaluate_opportunity_status(opp, reference_date=today) == "active"


def test_todays_deadline_remains_active():
    """An opportunity closing today is still open until end of day."""
    today = date(2026, 9, 17)
    opp = Opportunity(
        title="Frontend Intern",
        company="WebStudio",
        apply_url="https://example.com/apply2",
        deadline="2026-09-17",
        posted_date="2026-09-01",
        status="active"
    )
    is_expired, reason = is_opportunity_expired(opp, reference_date=today)
    assert not is_expired
    assert reason == "deadline_active"


def test_past_deadline_marks_expired():
    """An opportunity with past deadline must be marked expired."""
    today = date(2026, 9, 17)
    opp = Opportunity(
        title="Summer Intern",
        company="OldCorp",
        apply_url="https://example.com/apply3",
        deadline="2026-05-15",
        posted_date="2026-03-01",
        status="active"
    )
    is_expired, reason = is_opportunity_expired(opp, reference_date=today)
    assert is_expired
    assert "deadline_passed" in reason
    assert evaluate_opportunity_status(opp, reference_date=today) == "expired"


def test_no_deadline_recent_remains_active():
    """Rolling opportunities without explicit deadlines remain active if recent."""
    today = date(2026, 9, 17)
    opp = Opportunity(
        title="Open Source Fellow",
        company="OS Org",
        apply_url="https://example.com/apply4",
        deadline=None,
        posted_date="2026-09-05",
        status="active"
    )
    is_expired, reason = is_opportunity_expired(opp, reference_date=today)
    assert not is_expired
    assert reason == "active"


def test_no_deadline_stale_marks_expired():
    """Opportunities without deadlines older than 60 days must be flagged as stale."""
    today = date(2026, 9, 17)
    stale_date = (today - timedelta(days=75)).isoformat()
    opp = Opportunity(
        title="Old Job Posting",
        company="SlowCorp",
        apply_url="https://example.com/apply5",
        deadline=None,
        posted_date=stale_date,
        status="active"
    )
    is_expired, reason = is_opportunity_expired(opp, reference_date=today, max_age_days=60)
    assert is_expired
    assert "stale_inactivity" in reason


def test_expiry_never_deletes_records():
    """Verification that expiry preserves all historical records in SQLite."""
    session = SessionLocal()
    try:
        initial_count = session.query(OpportunityDB).count()
        rep = evaluate_and_update_expiry_in_db()
        post_count = session.query(OpportunityDB).count()
        # Count must remain exactly the same; no deletions allowed!
        assert post_count == initial_count, "Expiry evaluation must never delete database records"
    finally:
        session.close()
