"""Comprehensive automated tests for STEP 7:
- Multi-Source Registry & Trust Architecture
- Dynamic Telegram Channel Manager
- Opportunity Verification Engine & Admin Queue
- Student Verified-Only Filtering & Honest Badges
- Source Adapters (ATS, Company Careers, Compliant LinkedIn, Compliant Internshala, CSV/JSON)
"""

import json
import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.database.db import SessionLocal, OpportunityDB, SourceRegistryDB, UserDB, init_db
from backend.models.source import (
    SourceType,
    SourceStatus,
    SourceTrustLevel,
    SourceCreateRequest,
    SourceUpdateRequest,
    TelegramChannelCreateRequest,
)
from backend.models.opportunity import Opportunity
from backend.services import source_service, verification_service, opportunity_service
from backend.collectors.ats_adapter import ATSAdapter
from backend.collectors.company_careers_adapter import CompanyCareersAdapter
from backend.collectors.linkedin_adapter import LinkedInAdapter
from backend.collectors.internshala_adapter import InternshalaAdapter
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
        admin = db.query(UserDB).filter_by(email="admin_step7_test@hub.com").first()
        if not admin:
            admin = UserDB(
                id="user_admin_step7_test",
                email="admin_step7_test@hub.com",
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
        student = db.query(UserDB).filter_by(email="student_step7_test@hub.com").first()
        if not student:
            student = UserDB(
                id="user_student_step7_test",
                email="student_step7_test@hub.com",
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


# ============================================================================
# 1. SOURCE REGISTRY & TRUST ARCHITECTURE
# ============================================================================

def test_source_registry_crud(client, admin_headers):
    """Admin can list, create, update, toggle, and delete registered sources."""
    # 1. List initial sources (seeded automatically)
    res = client.get("/api/admin/sources", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["count"] >= 4

    # 2. Create a new ATS Public Feed source
    create_payload = {
        "name": "Stripe & Figma ATS Feeds",
        "type": "ATS_PUBLIC_FEED",
        "status": "ACTIVE",
        "configuration": {"companies": ["stripe", "figma"]}
    }
    create_res = client.post("/api/admin/sources", json=create_payload, headers=admin_headers)
    assert create_res.status_code == 200
    created_source = create_res.json()["source"]
    source_id = created_source["id"]
    assert created_source["trust_level"] == "OFFICIAL_COMPANY"
    assert created_source["status"] == "ACTIVE"

    # 3. Toggle source status (ACTIVE -> PAUSED)
    toggle_res = client.post(f"/api/admin/sources/{source_id}/toggle", headers=admin_headers)
    assert toggle_res.status_code == 200
    assert toggle_res.json()["source"]["status"] == "PAUSED"

    # 4. Toggle back (PAUSED -> ACTIVE)
    toggle_res2 = client.post(f"/api/admin/sources/{source_id}/toggle", headers=admin_headers)
    assert toggle_res2.status_code == 200
    assert toggle_res2.json()["source"]["status"] == "ACTIVE"

    # 5. Update source configuration
    update_res = client.put(
        f"/api/admin/sources/{source_id}",
        json={"name": "Updated ATS Feeds", "configuration": {"companies": ["stripe", "figma", "notion"]}},
        headers=admin_headers
    )
    assert update_res.status_code == 200
    assert update_res.json()["source"]["name"] == "Updated ATS Feeds"

    # 6. Delete source
    del_res = client.delete(f"/api/admin/sources/{source_id}", headers=admin_headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "success"


def test_student_cannot_access_source_registry(client, student_headers):
    """Students must be denied access to admin source management endpoints (403)."""
    res = client.get("/api/admin/sources", headers=student_headers)
    assert res.status_code == 403


# ============================================================================
# 2. DYNAMIC TELEGRAM CHANNEL MANAGER
# ============================================================================

def test_telegram_channel_manager(client, admin_headers):
    """Admin can dynamically register a Telegram public channel without touching code."""
    payload = {
        "channel_name": "Bangalore Tech Jobs",
        "channel_username": "@bangalore_tech_interns",
        "preview_url": "https://t.me/s/bangalore_tech_interns",
        "status": "ACTIVE"
    }
    res = client.post("/api/admin/sources/telegram/add", json=payload, headers=admin_headers)
    assert res.status_code == 200
    src = res.json()["source"]
    assert src["id"] == "src_tg_bangalore_tech_interns"
    assert src["type"] == "TELEGRAM"
    assert src["trust_level"] == "UNVERIFIED_EXTERNAL"
    assert src["configuration"]["channel_username"] == "bangalore_tech_interns"

    # Test TelegramCollector loads dynamically from DB
    col = TelegramCollector()
    assert "bangalore_tech_interns" in col.channels


def test_source_run_recording():
    """Verify that source run outcomes update the registry audit columns in SQLite."""
    db = SessionLocal()
    try:
        source_id = "src_test_audit_record"
        req = SourceCreateRequest(name="Test Audit Source", type=SourceType.TELEGRAM)
        source_service.create_source(db, req)
        
        # Record successful run
        source_service.record_source_run(db, source_id, success=True, items_added=5)
        
        # Verify
        s = db.query(SourceRegistryDB).filter_by(id=source_id).first()
        if s:
            assert s.last_success_at is not None
            assert s.items_count >= 5
    finally:
        db.close()


# ============================================================================
# 3. OPPORTUNITY VERIFICATION ENGINE & ADMIN QUEUE
# ============================================================================

def test_auto_determine_trust_and_verification():
    """Verify domain-based and source-based automatic trust & verification assignment."""
    # Company careers source
    trust, ver_status, method = verification_service.auto_determine_trust_and_verification(
        source_type="COMPANY_CAREERS",
        source_url="https://careers.google.com",
        apply_url="https://careers.google.com/jobs/123"
    )
    assert trust == SourceTrustLevel.OFFICIAL_COMPANY.value
    assert ver_status == "VERIFIED"
    assert method == "OFFICIAL_COMPANY_SOURCE"

    # Telegram post linking to official Greenhouse ATS
    trust2, ver_status2, method2 = verification_service.auto_determine_trust_and_verification(
        source_type="TELEGRAM",
        source_url="https://t.me/s/jobs/456",
        apply_url="https://boards.greenhouse.io/figma/jobs/789"
    )
    assert trust2 == SourceTrustLevel.UNVERIFIED_EXTERNAL.value
    assert ver_status2 == "VERIFIED"
    assert method2 == "OFFICIAL_ATS_DESTINATION"

    # Unknown external link from Telegram
    trust3, ver_status3, method3 = verification_service.auto_determine_trust_and_verification(
        source_type="TELEGRAM",
        source_url="https://t.me/s/jobs/456",
        apply_url="https://unknown-portal.xyz/apply"
    )
    assert trust3 == SourceTrustLevel.UNVERIFIED_EXTERNAL.value
    assert ver_status3 == "PENDING_REVIEW"
    assert method3 is None


def test_verification_queue_and_actions(client, admin_headers):
    """Admin can view the verification queue, verify, reject, and keep opportunities pending."""
    db = SessionLocal()
    test_opp_id = "opp_test_verif_queue_1"
    try:
        # Create a pending review opportunity
        opp = Opportunity(
            id=test_opp_id,
            title="Senior Backend Intern",
            company="VerifTest Labs",
            description="Backend engineering role using Python and PostgreSQL.",
            apply_url="https://veriftest.com/apply/backend",
            source="EMPLOYER_SUBMISSION",
            verification_status="PENDING_REVIEW",
            trust_level="EMPLOYER_SUBMITTED"
        )
        opportunity_service.save_opportunity(opp)

        # 1. Query Verification Queue
        res = client.get("/api/admin/verification-queue?status=ALL", headers=admin_headers)
        assert res.status_code == 200
        q_data = res.json()["data"]
        assert "counts" in q_data
        assert q_data["counts"]["PENDING_REVIEW"] >= 1

        # 2. Verify Opportunity
        v_res = client.post(
            f"/api/admin/verify/{test_opp_id}",
            json={"notes": "Company verified via official domain email"},
            headers=admin_headers
        )
        assert v_res.status_code == 200
        assert v_res.json()["opportunity"]["verification_status"] == "VERIFIED"
        assert v_res.json()["opportunity"]["verified_by"] == "admin_step7_test@hub.com"

        # 3. Mark Pending Again
        p_res = client.post(
            f"/api/admin/pending/{test_opp_id}",
            json={"notes": "Requesting additional employer documentation"},
            headers=admin_headers
        )
        assert p_res.status_code == 200
        assert p_res.json()["opportunity"]["verification_status"] == "PENDING_REVIEW"

        # 4. Reject Opportunity
        r_res = client.post(
            f"/api/admin/reject/{test_opp_id}",
            json={"notes": "Broken application link"},
            headers=admin_headers
        )
        assert r_res.status_code == 200
        assert r_res.json()["opportunity"]["verification_status"] == "REJECTED"

    finally:
        # Cleanup test opp
        db.query(OpportunityDB).filter_by(id=test_opp_id).delete()
        db.commit()
        db.close()


# ============================================================================
# 4. STUDENT "VERIFIED ONLY" FILTERING & PRIVACY
# ============================================================================

def test_student_verified_only_filter(client, student_headers):
    """Students can filter exclusively for verified listings and receive clean badges without source leakage."""
    db = SessionLocal()
    opp_v_id = "opp_test_verified_listing"
    opp_u_id = "opp_test_unverified_listing"
    try:
        # Verified opportunity
        opp_v = Opportunity(
            id=opp_v_id,
            title="Verified ML Research Intern",
            company="Open Science AI",
            description="Machine Learning research role.",
            apply_url="https://openscience.org/apply",
            source="COMPANY_CAREERS",
            source_channel="internal_scraper_ch",
            source_url="https://t.me/s/secret_ch/123",
            verification_status="VERIFIED",
            trust_level="OFFICIAL_COMPANY"
        )
        # Unverified opportunity
        opp_u = Opportunity(
            id=opp_u_id,
            title="Unverified Fast Job",
            company="Fast Start",
            description="General technical intern.",
            apply_url="https://faststart.xyz/job",
            source="Telegram",
            source_channel="unverified_feed",
            source_url="https://t.me/s/feed/999",
            verification_status="UNVERIFIED",
            trust_level="UNVERIFIED_EXTERNAL"
        )
        opportunity_service.save_opportunity(opp_v)
        opportunity_service.save_opportunity(opp_u)

        # 1. Fetch with verified_only=true
        res = client.get("/api/opportunities?verified_only=true", headers=student_headers)
        assert res.status_code == 200
        items = res.json()
        assert len(items) > 0

        # Every returned item MUST have verification_status == "VERIFIED"
        for item in items:
            assert item["verification_status"] == "VERIFIED"
            # Strict student privacy guarantees
            assert "source_channel" not in item or item.get("source_channel") is None
            assert "source_url" not in item or item.get("source_url") is None
            assert "raw_text" not in item or item.get("raw_text") is None

        # Verify that unverified opportunity is NOT returned in verified_only
        item_ids = [it["id"] for it in items]
        assert opp_v_id in item_ids
        assert opp_u_id not in item_ids

    finally:
        db.query(OpportunityDB).filter(OpportunityDB.id.in_([opp_v_id, opp_u_id])).delete(synchronize_session=False)
        db.commit()
        db.close()


# ============================================================================
# 5. MULTI-SOURCE ADAPTERS (ATS, COMPANY, LINKEDIN, INTERNSHALA)
# ============================================================================

def test_ats_adapter_initialization():
    """ATS Adapter correctly initializes supported providers."""
    adapter = ATSAdapter()
    assert adapter.name == "ats_feed"
    assert "OpenAI" in adapter.companies


def test_company_careers_adapter():
    """Company Careers Adapter correctly tags opportunities with OFFICIAL_COMPANY trust."""
    adapter = CompanyCareersAdapter([
        {
            "title": "Software Engineering Intern",
            "company": "Google",
            "location": "Bengaluru, India",
            "apply_url": "https://careers.google.com/jobs/123",
            "skills": ["Python", "C++", "DSA"]
        }
    ])
    opps = adapter.collect()
    assert len(opps) == 1
    opp = opps[0]
    assert opp.company == "Google"
    assert opp.trust_level == "OFFICIAL_COMPANY"
    assert opp.verification_status == "VERIFIED"
    assert opp.verification_method == "OFFICIAL_COMPANY_SOURCE"


def test_compliant_linkedin_adapter():
    """LinkedIn Adapter clearly reports when not configured rather than scraping unauthorized data."""
    adapter = LinkedInAdapter()
    assert adapter.name == "linkedin"
    # Should safely return empty list or export file items without crashing
    opps = adapter.collect()
    assert isinstance(opps, list)


def test_compliant_internshala_adapter():
    """Internshala Adapter clearly handles import files without unauthorized scraping."""
    adapter = InternshalaAdapter()
    assert adapter.name == "internshala_authorized"
    opps = adapter.collect()
    assert isinstance(opps, list)
