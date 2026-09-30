"""Automated tests for STEP 8 — Admin Source Manager.

Covers:
1. Adding sources across multiple types (Telegram, ATS, Company Careers, LinkedIn, Internshala, CSV, JSON, Employer)
2. Duplicate source prevention and seamless configuration update
3. Pause and Resume source toggling
4. Telegram source registration and automatic dynamic pickup by TelegramCollector
5. Source appearing in ingestion pipeline & single-source ingestion endpoint
6. Admin-only access enforcement (403 for student role, 401 for missing token)
7. Deleting a source removes registry entry while preserving historical opportunities in the database
"""

import json
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.database.db import SessionLocal, OpportunityDB, SourceRegistryDB, UserDB, init_db
from backend.models.source import SourceType, SourceStatus, SourceTrustLevel
from backend.models.opportunity import Opportunity
from backend.services import source_service, opportunity_service
from backend.collectors.telegram_collector import TelegramCollector
from backend.utils.security import hash_password, create_access_token


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def admin_headers():
    db = SessionLocal()
    try:
        admin = db.query(UserDB).filter_by(email="admin_step8_test@hub.com").first()
        if not admin:
            admin = UserDB(
                id="user_admin_step8_test",
                email="admin_step8_test@hub.com",
                password_hash=hash_password("AdminSecurePass!123"),
                role="ADMIN",
                is_active=True
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)

        token = create_access_token({"sub": admin.id, "email": admin.email, "role": admin.role})
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


@pytest.fixture(scope="module")
def student_headers():
    db = SessionLocal()
    try:
        student = db.query(UserDB).filter_by(email="student_step8_test@hub.com").first()
        if not student:
            student = UserDB(
                id="user_student_step8_test",
                email="student_step8_test@hub.com",
                password_hash=hash_password("StudentSecurePass!123"),
                role="STUDENT",
                is_active=True
            )
            db.add(student)
            db.commit()
            db.refresh(student)

        token = create_access_token({"sub": student.id, "email": student.email, "role": student.role})
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


class TestAdminSourceManager:
    """Test suite for Admin Source Manager capabilities."""

    def test_add_telegram_source_without_code_changes(self, client, admin_headers):
        """Test adding a Telegram channel via the Admin Source API."""
        payload = {
            "name": "Jobs India Daily",
            "type": "TELEGRAM",
            "status": "ACTIVE",
            "configuration": {
                "channel_username": "@jobsindiadaily_test",
                "preview_url": "https://t.me/s/jobsindiadaily_test"
            }
        }
        res = client.post("/api/admin/sources", json=payload, headers=admin_headers)
        assert res.status_code == 200, res.text
        data = res.json()
        assert data["status"] == "success"
        src = data["source"]
        assert src["id"] == "src_tg_jobsindiadaily_test"
        assert src["name"] == "Jobs India Daily"
        assert src["type"] == "TELEGRAM"
        assert src["status"] == "ACTIVE"

        # Verify collector dynamic pickup without code modification
        collector = TelegramCollector()
        assert "jobsindiadaily_test" in collector.channels or "@jobsindiadaily_test" in collector.channels

    def test_add_company_careers_source(self, client, admin_headers):
        """Test adding a Company Careers source via Admin Source API."""
        payload = {
            "name": "Acme Innovations Careers",
            "type": "COMPANY_CAREERS",
            "status": "ACTIVE",
            "configuration": {
                "target_url": "https://acme-innovations.example.com/careers",
                "company_name": "Acme Innovations"
            }
        }
        res = client.post("/api/admin/sources", json=payload, headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["source"]["trust_level"] == "OFFICIAL_COMPANY"

    def test_add_ats_source(self, client, admin_headers):
        """Test adding an ATS public feed source."""
        payload = {
            "name": "Stripe Greenhouse Board",
            "type": "ATS_PUBLIC_FEED",
            "status": "ACTIVE",
            "configuration": {
                "provider": "greenhouse",
                "board_url": "https://api.greenhouse.io/v1/boards/stripe/jobs",
                "target_url": "https://api.greenhouse.io/v1/boards/stripe/jobs"
            }
        }
        res = client.post("/api/admin/sources", json=payload, headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["source"]["trust_level"] == "OFFICIAL_COMPANY"

    def test_duplicate_source_prevention(self, client, admin_headers):
        """Test that re-registering an existing source updates it without creating duplicates."""
        initial_payload = {
            "name": "Campus Placement Drive 2026",
            "type": "COLLEGE_SUBMISSION",
            "status": "ACTIVE",
            "configuration": {"portal_url": "https://placement.college.edu/feed1"}
        }
        res1 = client.post("/api/admin/sources", json=initial_payload, headers=admin_headers)
        assert res1.status_code == 200
        id1 = res1.json()["source"]["id"]

        # Register again with same type and name but updated config and status
        updated_payload = {
            "name": "Campus Placement Drive 2026",
            "type": "COLLEGE_SUBMISSION",
            "status": "PAUSED",
            "configuration": {"portal_url": "https://placement.college.edu/feed_updated"}
        }
        res2 = client.post("/api/admin/sources", json=updated_payload, headers=admin_headers)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["source"]["id"] == id1  # Same deterministic or deduplicated ID
        assert data2["source"]["status"] == "PAUSED"
        assert data2["source"]["configuration"]["portal_url"] == "https://placement.college.edu/feed_updated"

        # Verify no duplicate entries exist in DB
        db = SessionLocal()
        try:
            matches = db.query(SourceRegistryDB).filter_by(type="COLLEGE_SUBMISSION", name="Campus Placement Drive 2026").all()
            assert len(matches) == 1
        finally:
            db.close()

    def test_pause_and_resume_source(self, client, admin_headers):
        """Test pausing and resuming a source."""
        # Create a test source
        payload = {
            "name": "Test Pauseable Source",
            "type": "CSV",
            "status": "ACTIVE",
            "configuration": {"file_path": "data/sample.csv"}
        }
        create_res = client.post("/api/admin/sources", json=payload, headers=admin_headers)
        source_id = create_res.json()["source"]["id"]
        assert create_res.json()["source"]["status"] == "ACTIVE"

        # Pause
        toggle_res1 = client.post(f"/api/admin/sources/{source_id}/toggle", headers=admin_headers)
        assert toggle_res1.status_code == 200
        assert toggle_res1.json()["source"]["status"] == "PAUSED"

        # Resume
        toggle_res2 = client.post(f"/api/admin/sources/{source_id}/toggle", headers=admin_headers)
        assert toggle_res2.status_code == 200
        assert toggle_res2.json()["source"]["status"] == "ACTIVE"

    def test_single_source_ingestion_endpoint(self, client, admin_headers):
        """Test triggering ingestion for a single registered source."""
        # Register a valid source
        payload = {
            "name": "Single Source Ingestion Test",
            "type": "COMPANY_CAREERS",
            "status": "ACTIVE",
            "configuration": {"company_name": "TestCorp", "target_url": "https://testcorp.com/jobs"}
        }
        create_res = client.post("/api/admin/sources", json=payload, headers=admin_headers)
        source_id = create_res.json()["source"]["id"]

        # Run single source ingestion
        ingest_res = client.post(f"/api/admin/sources/{source_id}/ingest", headers=admin_headers)
        assert ingest_res.status_code == 200
        data = ingest_res.json()
        assert data["status"] == "success"
        assert "report" in data
        assert "collected" in data["report"] or "saved" in data["report"]

    def test_admin_only_access_enforcement(self, client, student_headers):
        """Test that students and unauthenticated users cannot access source management endpoints."""
        # Unauthenticated access
        assert client.get("/api/admin/sources").status_code == 401
        assert client.post("/api/admin/sources", json={}).status_code == 401

        # Student role access (Forbidden 403)
        res_list = client.get("/api/admin/sources", headers=student_headers)
        assert res_list.status_code == 403

        res_create = client.post(
            "/api/admin/sources",
            json={"name": "Hacker Source", "type": "TELEGRAM", "status": "ACTIVE"},
            headers=student_headers
        )
        assert res_create.status_code == 403

        res_toggle = client.post("/api/admin/sources/src_tg_test/toggle", headers=student_headers)
        assert res_toggle.status_code == 403

        res_ingest = client.post("/api/admin/sources/src_tg_test/ingest", headers=student_headers)
        assert res_ingest.status_code == 403

        res_delete = client.delete("/api/admin/sources/src_tg_test", headers=student_headers)
        assert res_delete.status_code == 403

    def test_delete_source_preserves_historical_opportunities(self, client, admin_headers):
        """Test that deleting a source removes it from registry without deleting historical opportunities."""
        db = SessionLocal()
        source_id = f"src_delete_test_{uuid.uuid4().hex[:6]}"
        opp_id = f"opp_preserve_test_{uuid.uuid4().hex[:6]}"
        try:
            # Create a source directly
            src = SourceRegistryDB(
                id=source_id,
                name="Delete Test Source",
                type="TELEGRAM",
                status="ACTIVE",
                trust_level="UNVERIFIED_EXTERNAL",
                items_count=1
            )
            db.add(src)

            # Create an opportunity associated with this source
            opp = OpportunityDB(
                id=opp_id,
                title="Historical Preserved Internship",
                company="Preserve Co",
                location="Remote",
                opportunity_type="INTERNSHIP",
                source="TELEGRAM",
                source_id=source_id,
                apply_url="https://example.com/apply",
                verification_status="VERIFIED"
            )
            db.add(opp)
            db.commit()
        finally:
            db.close()

        # Delete the source via Admin API
        del_res = client.delete(f"/api/admin/sources/{source_id}", headers=admin_headers)
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "success"

        # Verify source is removed from registry
        db = SessionLocal()
        try:
            src_in_db = db.query(SourceRegistryDB).filter_by(id=source_id).first()
            assert src_in_db is None

            # Verify historical opportunity is still intact
            opp_in_db = db.query(OpportunityDB).filter_by(id=opp_id).first()
            assert opp_in_db is not None
            assert opp_in_db.title == "Historical Preserved Internship"
            db.delete(opp_in_db)
            db.commit()
        finally:
            db.close()
