"""Test demo database seeding and system health check diagnostics (Step 5 Verification)."""

from backend.database.seed_demo import seed_demo_database, generate_realistic_csv
from backend.services.health_service import check_system_health
from backend.services.student_service import get_current_student
from backend.services.opportunity_service import get_all_opportunities
from backend.database.db import SessionLocal, SavedOpportunityDB, ApplicationDB


def test_seed_demo_database_execution():
    """Verify seed_demo_database resets environment and populates demo opportunities."""
    report = seed_demo_database(force_refresh=True)
    assert report["status"] == "success"
    assert report["total_in_csv"] >= 75
    assert report["newly_saved_to_db"] >= 75

    # Check active student is reset to Student A
    student = get_current_student()
    assert "Debasis" in student.name
    assert "AIML" in student.branch or "Artificial Intelligence" in student.branch

    # Check demo bookmarks and applications were cleared for fresh demo
    session = SessionLocal()
    try:
        saved_count = session.query(SavedOpportunityDB).count()
        app_count = session.query(ApplicationDB).count()
        assert saved_count == 0, "Demo bookmarks should be 0 on fresh reset"
        assert app_count == 0, "Demo applications should be 0 on fresh reset"
    finally:
        session.close()

    # Check database has opportunities
    all_opps = get_all_opportunities()
    assert len(all_opps) >= 75


def test_check_system_health_all_ok():
    """Verify check_system_health() reports HEALTHY across all 6 diagnostic pillars."""
    health = check_system_health()
    assert health["status"] == "HEALTHY"

    checks = health["checks"]
    assert checks.get("Database") == "OK"
    assert "OK" in checks.get("AI module", "")
    assert "OK" in checks.get("Embedding", "")
    assert "OK" in checks.get("Opportunity DB", "")
    assert "OK" in checks.get("Demo data", "")
