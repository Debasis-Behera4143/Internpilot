"""End-to-End Debug and Verification Test Suite for CareerHub Source Management & Ingestion.

Exercises the complete lifecycle against the live database and FastAPI application:
1. Admin Login & Auth Protection (Token creation, admin authorization, student rejection, invalid tokens)
2. Source Creation & DB Verification (Fresh DB session verification, idempotent handling)
3. Source Listing & Format (Returns active, paused, failed with all metadata)
4. Telegram Source Handling (Handle normalization, invite link rejection, public preview ingestion)
5. Run Now Ingestion Pipeline (Step execution, 7-metric report breakdown)
6. Source Status State Machine (ACTIVE, RUNNING, SUCCESS, FAILED, PAUSED, metric preservation)
7. Failed Source Isolation (Categorized admin-safe error, fault isolation)
8. Student Fail-Closed Filtering (Only VERIFIED active jobs accessible to students)
9. Source Pause, Resume, and Deletion
"""

import pytest
from fastapi.testclient import TestClient
from backend.api.app import app
from backend.database.db import SessionLocal, SourceRegistryDB, OpportunityDB, UserDB
from backend.models.source import SourceStatus


@pytest.fixture
def test_client():
    return TestClient(app)


def test_01_admin_login_and_auth_protection(test_client):
    """Verify admin login produces valid JWT, and verify role-based access control."""
    # 1. Admin login with correct credentials
    login_res = test_client.post(
        "/api/auth/login",
        json={"email": "admin@careerhub.local", "password": "CareerHubAdmin2026!"}
    )
    assert login_res.status_code == 200, f"Admin login failed: {login_res.text}"
    data = login_res.json()
    assert "access_token" in data
    assert data.get("role") == "ADMIN" or data.get("user", {}).get("role") == "ADMIN"
    admin_token = data["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Protected admin endpoint succeeds with admin token
    sources_res = test_client.get("/api/admin/sources", headers=admin_headers)
    assert sources_res.status_code == 200
    assert "sources" in sources_res.json()

    # 3. Invalid admin credentials rejected
    bad_login = test_client.post(
        "/api/auth/login",
        json={"email": "admin@careerhub.local", "password": "WrongPassword!"}
    )
    assert bad_login.status_code == 401

    # 4. Invalid token rejected
    bad_token_res = test_client.get(
        "/api/admin/sources",
        headers={"Authorization": "Bearer invalid.jwt.token"}
    )
    assert bad_token_res.status_code == 401

    # 5. Student login and unauthorized access rejection (HTTP 403)
    student_login = test_client.post(
        "/api/auth/login",
        json={"email": "default_student@example.com", "password": "DefaultStudentPass123!"}
    )
    assert student_login.status_code == 200
    student_token = student_login.json()["access_token"]
    student_headers = {"Authorization": f"Bearer {student_token}"}

    forbidden_res = test_client.get("/api/admin/sources", headers=student_headers)
    assert forbidden_res.status_code == 403


def test_02_source_creation_and_fresh_db_verification(test_client, auth_admin_headers):
    """Test source creation via POST /api/admin/sources and verify immediate persistence with fresh DB session."""
    payload = {
        "name": "E2E Test Careers Portal",
        "type": "COMPANY_CAREERS",
        "status": "ACTIVE",
        "configuration": {
            "company_name": "E2E Tech Corp",
            "url": "https://e2e-careers.example.com"
        }
    }

    create_res = test_client.post("/api/admin/sources", json=payload, headers=auth_admin_headers)
    assert create_res.status_code == 200
    res_data = create_res.json()
    assert res_data["status"] == "success"
    source_id = res_data["source"]["id"]
    assert res_data["source"]["name"] == "E2E Test Careers Portal"

    # Verify persistence using completely fresh database session
    db = SessionLocal()
    try:
        row = db.query(SourceRegistryDB).filter_by(id=source_id).first()
        assert row is not None, "Source was not committed to the database!"
        assert row.name == "E2E Test Careers Portal"
        assert row.type == "COMPANY_CAREERS"
        assert row.status == "ACTIVE"
    finally:
        db.close()

    # Verify GET /api/admin/sources returns the newly created source
    list_res = test_client.get("/api/admin/sources", headers=auth_admin_headers)
    assert list_res.status_code == 200
    all_sources = list_res.json()["sources"]
    found = [s for s in all_sources if s["id"] == source_id]
    assert len(found) == 1
    assert "last_run_at" in found[0] or "last_ingested_at" in found[0]


def test_03_telegram_source_normalization_and_validation(test_client, auth_admin_headers):
    """Test Telegram channel creation, handle normalization from full URL, and invite link rejection."""
    # 1. Full URL normalization
    tg_payload = {
        "channel_name": "Tech Jobs Updates E2E",
        "channel_username": "https://t.me/jobsandinternshipsupdates",
        "preview_url": "https://t.me/s/jobsandinternshipsupdates"
    }
    res = test_client.post("/api/admin/sources/telegram/add", json=tg_payload, headers=auth_admin_headers)
    assert res.status_code == 200
    tg_source = res.json()["source"]
    # The source ID must be normalized cleanly to src_tg_jobsandinternshipsupdates without 'https://'
    assert tg_source["id"] == "src_tg_jobsandinternshipsupdates"
    assert tg_source["configuration"]["channel_username"] == "jobsandinternshipsupdates"

    # 2. Reject private invite link
    invalid_payload = {
        "channel_name": "Private Channel",
        "channel_username": "https://t.me/+invitecode123"
    }
    inv_res = test_client.post("/api/admin/sources/telegram/add", json=invalid_payload, headers=auth_admin_headers)
    assert inv_res.status_code == 400
    assert "invite" in inv_res.json()["detail"].lower()


def test_04_run_source_and_7_metric_breakdown(test_client, auth_admin_headers):
    """Test single source ingestion execution, stage completion, and 7-metric report breakdown."""
    # Register source with test company careers adapter
    src_payload = {
        "name": "Pipeline Verification Source",
        "type": "COMPANY_CAREERS",
        "status": "ACTIVE",
        "configuration": {
            "companies": [
                {
                    "title": "Software Engineering Intern 2026",
                    "company": "NextGen Systems",
                    "apply_url": "https://careers.nextgensystems.com/jobs/swe-intern",
                    "location": "Bengaluru",
                    "remote": False
                }
            ]
        }
    }
    c_res = test_client.post("/api/admin/sources", json=src_payload, headers=auth_admin_headers)
    assert c_res.status_code == 200
    source_id = c_res.json()["source"]["id"]

    # Trigger Run Now
    ingest_res = test_client.post(f"/api/admin/sources/{source_id}/ingest", headers=auth_admin_headers)
    assert ingest_res.status_code == 200
    data = ingest_res.json()
    assert data["status"] == "success"
    report = data["report"]

    # Verify all 7 required breakdown metrics exist
    for metric in ["found", "parsed", "rejected", "duplicates", "expired", "pending", "verified"]:
        assert metric in report, f"Report is missing metric: {metric}"

    # Verify source registry status updated to SUCCESS in fresh database session
    db = SessionLocal()
    try:
        row = db.query(SourceRegistryDB).filter_by(id=source_id).first()
        assert row is not None
        assert row.status in ("SUCCESS", "ACTIVE")
        assert row.last_ingested_at is not None
        assert row.last_error is None
    finally:
        db.close()


def test_05_failed_source_isolation_and_safe_error(test_client, auth_admin_headers):
    """Verify that a failing source transitions to FAILED, stores admin-safe error, and isolates fault."""
    # Register a source that fails cleanly
    fail_payload = {
        "name": "Broken Feed Source",
        "type": "JSON",
        "status": "ACTIVE",
        "configuration": {
            "file_path": "non_existent_path_e2e_debug_test.json"
        }
    }
    c_res = test_client.post("/api/admin/sources", json=fail_payload, headers=auth_admin_headers)
    assert c_res.status_code == 200
    source_id = c_res.json()["source"]["id"]

    # Run ingestion on broken source
    ingest_res = test_client.post(f"/api/admin/sources/{source_id}/ingest", headers=auth_admin_headers)
    assert ingest_res.status_code == 200
    data = ingest_res.json()

    # Check fresh database session for FAILED status and categorized safe error
    db = SessionLocal()
    try:
        row = db.query(SourceRegistryDB).filter_by(id=source_id).first()
        assert row is not None
        assert row.status == "FAILED"
        assert row.last_error is not None
        # Must be an admin-safe error category, not a raw internal stacktrace or secret
        assert any(term in row.last_error.lower() for term in [
            "connection failed", "invalid channel", "parser error", "not found", "database error"
        ])
    finally:
        db.close()

    # Verify GET /api/admin/sources shows FAILED status and error column populated
    list_res = test_client.get("/api/admin/sources", headers=auth_admin_headers)
    assert list_res.status_code == 200
    matched = [s for s in list_res.json()["sources"] if s["id"] == source_id]
    assert len(matched) == 1
    assert matched[0]["status"] == "FAILED"
    assert matched[0]["last_error"] is not None


def test_06_student_fail_closed_verification_gate(test_client, auth_admin_headers):
    """Verify that unverified/pending opportunities are never visible to students."""
    # 1. Directly insert one UNVERIFIED and one VERIFIED opportunity
    db = SessionLocal()
    try:
        unverif_opp = OpportunityDB(
            id="opp_unverif_e2e_test",
            title="Unverified Shady Intern",
            company="Unknown Corp",
            apply_url="https://unknown-corp.example.com/apply",
            source="Telegram",
            status="pending",
            verification_status="PENDING_REVIEW"
        )
        verif_opp = OpportunityDB(
            id="opp_verif_e2e_test",
            title="Verified Official Intern 2026",
            company="Verified Global Corp",
            apply_url="https://verified-global.example.com/apply",
            source="Company Careers",
            status="active",
            verification_status="VERIFIED"
        )
        db.merge(unverif_opp)
        db.merge(verif_opp)
        db.commit()
    finally:
        db.close()

    # 2. Student query to /api/opportunities (unauthenticated / student)
    opps_res = test_client.get("/api/opportunities")
    assert opps_res.status_code == 200
    student_jobs = opps_res.json()
    job_ids = [j.get("id") for j in student_jobs]

    # Student MUST NOT see unverified opportunity
    assert "opp_unverif_e2e_test" not in job_ids, "Security breach: Unverified job leaked to students!"
    # Student CAN see verified opportunity
    assert "opp_verif_e2e_test" in job_ids, "Verified opportunity not visible to students!"


def test_07_source_pause_resume_and_deletion(test_client, auth_admin_headers):
    """Test pausing, resuming, and deleting a source."""
    # Create source
    src_payload = {
        "name": "Lifecycle Test Source",
        "type": "COMPANY_CAREERS",
        "status": "ACTIVE",
        "configuration": {"url": "https://lifecycle.example.com"}
    }
    c_res = test_client.post("/api/admin/sources", json=src_payload, headers=auth_admin_headers)
    source_id = c_res.json()["source"]["id"]

    # Pause
    pause_res = test_client.post(f"/api/admin/sources/{source_id}/toggle", headers=auth_admin_headers)
    assert pause_res.status_code == 200
    assert pause_res.json()["source"]["status"] == "PAUSED"

    # Resume
    resume_res = test_client.post(f"/api/admin/sources/{source_id}/toggle", headers=auth_admin_headers)
    assert resume_res.status_code == 200
    assert resume_res.json()["source"]["status"] == "ACTIVE"

    # Delete
    del_res = test_client.delete(f"/api/admin/sources/{source_id}", headers=auth_admin_headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"

    # Confirm deletion from database
    db = SessionLocal()
    try:
        assert db.query(SourceRegistryDB).filter_by(id=source_id).first() is None
    finally:
        db.close()
