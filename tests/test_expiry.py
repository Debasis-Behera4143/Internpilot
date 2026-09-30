"""Unit tests for opportunity expiry detection and lifecycle management."""

from datetime import date, timedelta
from backend.models.opportunity import Opportunity
from backend.services.expiry_service import (
    is_opportunity_expired,
    evaluate_opportunity_status
)


def test_expired_deadline():
    """Verify that opportunities with a past deadline are identified as expired."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    opp = Opportunity(
        title="AI Intern",
        company="Startup A",
        apply_url="https://example.com/apply",
        deadline=yesterday
    )

    expired, reason = is_opportunity_expired(opp)
    assert expired is True
    assert "deadline_passed" in reason
    assert evaluate_opportunity_status(opp) == "expired"


def test_active_future_deadline():
    """Verify that opportunities with a future deadline remain active."""
    next_month = (date.today() + timedelta(days=30)).isoformat()
    opp = Opportunity(
        title="AI Intern",
        company="Startup B",
        apply_url="https://example.com/apply2",
        deadline=next_month
    )

    expired, reason = is_opportunity_expired(opp)
    assert expired is False
    assert reason == "deadline_active"
    assert evaluate_opportunity_status(opp) == "active"


def test_stale_opportunity_without_deadline():
    """Verify that opportunities without a deadline older than max age are marked expired."""
    three_months_ago = (date.today() - timedelta(days=90)).isoformat()
    opp = Opportunity(
        title="Web Intern",
        company="Startup C",
        apply_url="https://example.com/apply3",
        deadline=None,
        posted_date=three_months_ago
    )

    expired, reason = is_opportunity_expired(opp, max_age_days=60)
    assert expired is True
    assert "stale_inactivity" in reason


def test_fresh_opportunity_without_deadline():
    """Verify that fresh opportunities without a deadline remain active."""
    five_days_ago = (date.today() - timedelta(days=5)).isoformat()
    opp = Opportunity(
        title="Web Intern",
        company="Startup D",
        apply_url="https://example.com/apply4",
        deadline=None,
        posted_date=five_days_ago
    )

    expired, reason = is_opportunity_expired(opp, max_age_days=60)
    assert expired is False
    assert evaluate_opportunity_status(opp, max_age_days=60) == "active"


def test_source_closed_opportunity():
    """Verify that opportunities with status closed are marked closed."""
    opp = Opportunity(
        title="Closed Role",
        company="Startup E",
        apply_url="https://example.com/apply5",
        status="closed"
    )

    assert evaluate_opportunity_status(opp) == "closed"
