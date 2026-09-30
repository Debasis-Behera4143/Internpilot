"""Comprehensive automated tests for CareerHub Genuine Sources, Verification Gate,
Compliant LinkedIn Imports, Legitimate Adapters, and Admin Source Dashboard.
"""

import io
import json
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.database.db import SessionLocal, OpportunityDB, SourceRegistryDB, UserDB, init_db
from backend.models.source import SourceType, SourceStatus, SourceTrustLevel
from backend.models.opportunity import Opportunity
from backend.services import source_service, verification_service, opportunity_service
from backend.services.job_classifier import (
    classify_opportunity_content,
    is_company_identifiable,
)
from backend.collectors.ats_adapter import ATSAdapter
from backend.collectors.linkedin_collector import LinkedInCollector
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
        admin = db.query(UserDB).filter_by(email="admin_genuine_test@hub.com").first()
        if not admin:
            admin = UserDB(
                id="user_admin_genuine_test",
                email="admin_genuine_test@hub.com",
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
        student = db.query(UserDB).filter_by(email="student_genuine_test@hub.com").first()
        if not student:
            student = UserDB(
                id="user_student_genuine_test",
                email="student_genuine_test@hub.com",
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


# ==============================================================================
# 1. LINKEDIN CSV IMPORT WITH STANDARD HEADERS
# ==============================================================================

def test_linkedin_csv_import_standard_headers(client, admin_headers):
    """Test importing valid LinkedIn CSV records with standard headers."""
    import uuid
    uid = uuid.uuid4().hex[:6]
    co_stripe = f"Stripe{uid}"
    co_datadog = f"Datadog{uid}"
    url_stripe = f"https://stripe.com/jobs/{uid}"
    url_datadog = f"https://datadog.com/careers/{uid}"

    csv_data = (
        "Job Title,Company,Location,Description,Apply URL\n"
        f"Backend Python Intern,{co_stripe},Bengaluru,\"Build scalable payment APIs using Python and FastAPI.\",{url_stripe}\n"
        f"Cloud Infrastructure Engineer,{co_datadog},Remote,\"Work with Kubernetes, Go, and distributed telemetry systems.\",{url_datadog}\n"
    )

    res = client.post(
        "/api/admin/linkedin/import",
        headers=admin_headers,
        json={"csv_content": csv_data}
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "success"
    assert body["accepted"] == 2
    assert body["rejected"] == 0

    # Verify listings are stored with PENDING_REVIEW status and IMPORTED_DATA trust level
    db = SessionLocal()
    try:
        opp = db.query(OpportunityDB).filter_by(company=co_stripe, title="Backend Python Intern").first()
        assert opp is not None
        assert opp.verification_status == "PENDING_REVIEW"
        assert "linkedin" in opp.source.lower()
        assert opp.apply_url == url_stripe
        assert opp.work_mode in ["hybrid", "remote", "on-site"]
    finally:
        db.close()


# ==============================================================================
# 2. LINKEDIN JSON IMPORT
# ==============================================================================

def test_linkedin_json_import(client, admin_headers):
    """Test importing valid LinkedIn JSON format records."""
    import uuid
    uid = uuid.uuid4().hex[:6]
    co_anthropic = f"Anthropic{uid}"
    url_anthropic = f"https://anthropic.com/careers/{uid}"
    co_spotify = f"Spotify{uid}"
    url_spotify = f"https://spotify.com/jobs/{uid}"

    json_records = [
        {
            "title": "Machine Learning Engineer Intern",
            "company": co_anthropic,
            "location": "San Francisco, CA",
            "opportunity_type": "internship",
            "apply_url": url_anthropic,
            "description": "Research and evaluate alignment techniques for large language models.",
            "work_mode": "hybrid"
        },
        {
            "title": "Data Analyst Trainee",
            "company": co_spotify,
            "location": "Remote",
            "opportunity_type": "job",
            "apply_url": url_spotify,
            "description": "Analyze user listening behavior using SQL, Python, and BigQuery.",
            "work_mode": "remote"
        }
    ]

    res = client.post(
        "/api/admin/linkedin/import",
        headers=admin_headers,
        json={"json_content": json_records}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert body["accepted"] == 2

    db = SessionLocal()
    try:
        opp = db.query(OpportunityDB).filter_by(company=co_anthropic).first()
        assert opp is not None
        assert opp.verification_status == "PENDING_REVIEW"
        assert opp.apply_url == url_anthropic
    finally:
        db.close()


# ==============================================================================
# 3. MALFORMED LINKEDIN DATA REJECTED
# ==============================================================================

def test_linkedin_malformed_records_rejected(client, admin_headers):
    """Ensure records missing required fields (title, company, URL) are rejected."""
    csv_malformed = (
        "Job Title,Company,Location,Apply URL\n"
        ",MissingTitleCorp,Remote,https://example.com/apply\n"
        "Valid Title,,Remote,https://example.com/apply\n"
        "Software Engineer,Acme Corp,Remote,\n"
    )

    res = client.post(
        "/api/admin/linkedin/import",
        headers=admin_headers,
        json={"csv_content": csv_malformed}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["accepted"] == 0
    assert body["rejected"] == 3
    assert len(body["sample_rejected"]) == 3


# ==============================================================================
# 4. DUPLICATE LINKEDIN JOBS (IN-BATCH AND CROSS-DB)
# ==============================================================================

def test_linkedin_duplicates_handling(client, admin_headers):
    """Ensure in-batch duplicates and database duplicates are accurately detected."""
    import uuid
    uid = uuid.uuid4().hex[:6]
    co_cloudflare = f"Cloudflare{uid}"
    url_cloudflare = f"https://cloudflare.com/careers/{uid}"

    # 1. In-batch duplicate test
    batch_with_duplicates = [
        {
            "title": "Security Analyst",
            "company": co_cloudflare,
            "apply_url": url_cloudflare,
            "description": "Analyze threat traffic across the global CDN."
        },
        {
            "title": "Security Analyst",
            "company": co_cloudflare,
            "apply_url": url_cloudflare,
            "description": "Duplicate copy of the above posting."
        }
    ]

    res = client.post(
        "/api/admin/linkedin/import",
        headers=admin_headers,
        json={"json_content": batch_with_duplicates}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["accepted"] == 1
    assert body["duplicates"] == 1

    # 2. Cross-DB duplicate test (submitting the same item again in a new call)
    res2 = client.post(
        "/api/admin/linkedin/import",
        headers=admin_headers,
        json={"json_content": [batch_with_duplicates[0]]}
    )
    assert res2.status_code == 200
    body2 = res2.json()
    assert body2["accepted"] == 0
    assert body2["duplicates"] == 1


# ==============================================================================
# 5. INVALID URLS AND SSRF ATTEMPTS REJECTED
# ==============================================================================

def test_invalid_urls_and_ssrf_rejected(client, admin_headers):
    """Verify that private IPs, metadata endpoints, and non-http URLs are rejected."""
    dangerous_records = [
        {"title": "DevOps", "company": "Target1", "apply_url": "http://127.0.0.1:8000/admin"},
        {"title": "DevOps", "company": "Target2", "apply_url": "http://localhost/secret"},
        {"title": "DevOps", "company": "Target3", "apply_url": "http://169.254.169.254/latest/meta-data"},
        {"title": "DevOps", "company": "Target4", "apply_url": "javascript:alert(1)"},
        {"title": "DevOps", "company": "Target5", "apply_url": "file:///etc/passwd"}
    ]

    res = client.post(
        "/api/admin/import/preview",
        headers=admin_headers,
        json={
            "content": dangerous_records,
            "source_name": "SSRF Security Test",
            "source_type": "JSON"
        }
    )
    assert res.status_code == 200
    body = res.json()
    assert body["valid_count"] == 0
    assert body["rejected_count"] == 5


# ==============================================================================
# 6. EXPIRED JOBS REJECTED FROM PUBLICATION
# ==============================================================================

def test_expired_jobs_handling(client, admin_headers):
    """Verify that jobs with past deadlines are flagged as expired and not published."""
    past_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    expired_record = [
        {
            "title": "Summer Intern 2023",
            "company": "RetroTech",
            "apply_url": "https://retrotech.com/jobs/summer-2023",
            "deadline": past_date,
            "description": "Historical internship with expired deadline."
        }
    ]

    res = client.post(
        "/api/admin/import/preview",
        headers=admin_headers,
        json={
            "content": expired_record,
            "source_name": "Expiry Test",
            "source_type": "JSON"
        }
    )
    assert res.status_code == 200
    body = res.json()
    assert body["valid_count"] == 0
    assert body["rejected_count"] == 1
    assert "has passed" in body["items"][0]["rejection_reason"].lower()


# ==============================================================================
# 7. NON-JOB CONTENT CLASSIFICATION & REJECTIONS
# ==============================================================================

def test_job_classifier_promotional_courses():
    """Courses, bootcamps, and coaching institutes must be classified as non-job and rejected."""
    text = "Learn Full Stack Web Development! Enroll in our 12-week certification course with 50% discount!"
    is_gen, cat, reasons = classify_opportunity_content(title="Full Stack Bootcamp Course", company="Coding School", description=text)
    assert not is_gen
    assert cat in ["PROMOTIONAL_CONTENT", "PROMOTIONAL_COURSE_OR_BOOTCAMP"]


def test_job_classifier_paid_training_scams():
    """Paid training, deposit schemes, and registration fee demands must be rejected."""
    text = "Guaranteed placement upon joining. A small refundable security deposit of Rs 2500 is required for training material."
    is_gen, cat, reasons = classify_opportunity_content(title="Java Trainee (Training Included)", company="Tech Institute", description=text)
    assert not is_gen
    assert cat == "PAID_TRAINING_SCAM"


def test_job_classifier_referral_only():
    """Referral-only posts without genuine application details must be rejected."""
    text = "I am a Software Engineer at Microsoft. Giving referrals for SDE-1 roles. DM me your resume on LinkedIn."
    is_gen, cat, reasons = classify_opportunity_content(title="Referral Available for Microsoft", company="Senior Dev", description=text)
    assert not is_gen
    assert cat == "REFERRAL_ONLY"


def test_job_classifier_dm_to_apply():
    """Posts demanding WhatsApp or direct messages without a company application portal must be rejected."""
    text = "Immediate hiring for freshers! Send your CV on WhatsApp +91 9876543210. No website application."
    is_gen, cat, reasons = classify_opportunity_content(title="HR Intern", company="Local Agency", description=text)
    assert not is_gen
    assert cat == "DM_TO_APPLY"


def test_job_classifier_unidentified_company():
    """Vague or anonymous companies like 'Top MNC' or 'Confidential Startup' must be rejected."""
    valid, msg = is_company_identifiable("Top MNC")
    assert not valid
    valid, msg = is_company_identifiable("Confidential Client")
    assert not valid
    valid, msg = is_company_identifiable("Urgent Hiring")
    assert not valid
    valid, msg = is_company_identifiable("Razorpay")
    assert valid
    valid, msg = is_company_identifiable("Infosys Limited")
    assert valid


# ==============================================================================
# 8. TELEGRAM: UNRELATED CONTENT REJECTED, GENUINE ATS LINKS ACCEPTED
# ==============================================================================

def test_telegram_unrelated_vs_genuine_content():
    """Telegram crypto/promo messages rejected, while genuine job broadcasts are recognized."""
    # Spam / crypto / promotion
    crypto_msg = "Join our Binance pump and dump VIP signal group for 10x guaranteed returns!"
    is_gen_crypto, cat_crypto, _ = classify_opportunity_content(title="Crypto Signals VIP", company="Telegram Channel", description=crypto_msg)
    assert not is_gen_crypto

    # Genuine job broadcast with ATS link
    job_msg = (
        "Uber is hiring Software Engineer Interns (2026 Batch)!\n"
        "Location: Hyderabad / Bengaluru\n"
        "Stipend: ₹1,00,000/month\n"
        "Apply here: https://boards.greenhouse.io/uber/jobs/456789"
    )
    is_gen_job, cat_job, _ = classify_opportunity_content(
        title="Software Engineer Intern",
        company="Uber",
        description=job_msg,
        apply_url="https://boards.greenhouse.io/uber/jobs/456789"
    )
    assert is_gen_job
    assert cat_job is None


# ==============================================================================
# 9. LEGITIMATE ATS ADAPTERS (GREENHOUSE, LEVER, WORKDAY)
# ==============================================================================

def test_ats_adapter_providers_and_workday():
    """Verify ATS adapter supports Greenhouse, Lever, and Workday public feeds."""
    adapter = ATSAdapter()
    assert "greenhouse" in adapter.SUPPORTED_PROVIDERS
    assert "lever" in adapter.SUPPORTED_PROVIDERS
    assert "workday" in adapter.SUPPORTED_PROVIDERS

    # Greenhouse item parse test
    gh_raw = {
        "id": 12345,
        "title": "Software Engineer, Core Systems",
        "absolute_url": "https://boards.greenhouse.io/stripe/jobs/12345",
        "location": {"name": "Bengaluru, India"},
        "content": "<p>Build high-throughput transaction infrastructure.</p>"
    }
    opp = adapter._parse_greenhouse_job("Stripe", gh_raw)
    assert opp is not None
    assert opp.title == "Software Engineer, Core Systems"
    assert opp.company == "Stripe"
    assert opp.apply_url == "https://boards.greenhouse.io/stripe/jobs/12345"
    assert opp.trust_level == "ATS_PUBLIC"


# ==============================================================================
# 10. EMPLOYER AND COLLEGE SUBMISSION WORKFLOWS
# ==============================================================================

def test_employer_and_college_submission_import(client, admin_headers):
    """Test importing employer submissions and verifying they are held in PENDING_REVIEW with proper trust."""
    import uuid
    uid = uuid.uuid4().hex[:6]
    co_name = f"InnovateCorp{uid}"
    apply_url = f"https://innovatecorp.io/careers/{uid}"

    employer_jobs = [
        {
            "title": "Junior Frontend Developer",
            "company": co_name,
            "location": "Remote",
            "apply_url": apply_url,
            "description": "Vue.js and Tailwind CSS developer for our SaaS analytics product.",
            "work_mode": "remote"
        }
    ]

    res = client.post(
        "/api/admin/import/confirm",
        headers=admin_headers,
        json={
            "source_name": "Employer Direct Portal",
            "source_type": "EMPLOYER_SUBMISSION",
            "records": employer_jobs
        }
    )
    assert res.status_code == 200
    body = res.json()
    assert body["accepted"] == 1

    db = SessionLocal()
    try:
        opp = db.query(OpportunityDB).filter_by(company=co_name).first()
        assert opp is not None
        assert opp.trust_level == "EMPLOYER_SUBMITTED"
        assert opp.verification_status == "PENDING_REVIEW"
    finally:
        db.close()


# ==============================================================================
# 11. SOURCE DUPLICATION PREVENTION
# ==============================================================================

def test_source_duplication_prevention(client, admin_headers):
    """Attempting to register the same source name or Telegram handle returns existing or 400 error."""
    import uuid
    src_name = f"Acme Global Careers ATS {uuid.uuid4().hex[:6]}"

    # Register source first time
    res1 = client.post(
        "/api/admin/sources",
        headers=admin_headers,
        json={
            "name": src_name,
            "type": "ATS_PUBLIC_FEED",
            "configuration": {"url": "https://boards.greenhouse.io/acme"}
        }
    )
    assert res1.status_code == 200
    src1_id = res1.json()["source"]["id"]

    # Register same source again with duplicate name and updated config
    res2 = client.post(
        "/api/admin/sources",
        headers=admin_headers,
        json={
            "name": src_name,
            "type": "ATS_PUBLIC_FEED",
            "configuration": {"url": "https://boards.greenhouse.io/acme_v2"}
        }
    )
    assert res2.status_code == 200
    assert res2.json()["source"]["id"] == src1_id

    # Verify no duplicate entries exist in DB
    db = SessionLocal()
    try:
        matches = db.query(SourceRegistryDB).filter_by(name=src_name).all()
        assert len(matches) == 1
    finally:
        db.close()


# ==============================================================================
# 12. UNAUTHORIZED SOURCE ACCESS & STUDENT ACCESS CONTROL
# ==============================================================================

def test_student_forbidden_from_admin_sources(client, student_headers):
    """Ensure non-admin student users receive 403 Forbidden on all administrative source APIs."""
    endpoints = [
        ("GET", "/api/admin/sources"),
        ("GET", "/api/admin/linkedin/status"),
        ("POST", "/api/admin/linkedin/import"),
        ("POST", "/api/admin/import/preview"),
        ("POST", "/api/admin/import/confirm"),
    ]

    for method, path in endpoints:
        if method == "GET":
            res = client.get(path, headers=student_headers)
        else:
            res = client.post(path, headers=student_headers, json={})
        assert res.status_code in [403, 401], f"Expected 403/401 for {path}, got {res.status_code}"


# ==============================================================================
# 13. STUDENT FEED CONTAINS ONLY VERIFIED JOBS WITH HONEST TRANSPARENCY
# ==============================================================================

def test_student_feed_verified_only_and_metadata_transparency(client, student_headers, admin_headers):
    """Verify that student opportunity search only returns VERIFIED listings and masks internal source secrets."""
    db = SessionLocal()
    try:
        # Create one verified opportunity and one unverified/pending opportunity
        verified_opp = OpportunityDB(
            id="opp_verified_student_test",
            title="Senior Platform Engineer",
            company="GitHub",
            opportunity_type="job",
            location="Remote",
            work_mode="remote",
            apply_url="https://github.com/careers/platform-eng",
            source="ats_public_feed",
            source_channel="internal_admin_channel_123",
            source_url="https://secret-admin-feed.internal/jobs",
            status="active",
            verification_status="VERIFIED",
            trust_level="ATS_PUBLIC",
            salary="₹30,00,000 - ₹45,00,000",
            skills='["Go", "Kubernetes", "Linux"]'
        )
        db.merge(verified_opp)

        pending_opp = OpportunityDB(
            id="opp_pending_student_test",
            title="Secret Pending Role",
            company="Stealth Startup",
            opportunity_type="internship",
            location="Bengaluru",
            apply_url="https://stealth.io/careers/secret",
            source="linkedin",
            status="active",
            verification_status="PENDING_REVIEW",
            trust_level="IMPORTED_DATA"
        )
        db.merge(pending_opp)
        db.commit()

        # Query student opportunities endpoint
        res = client.get("/api/opportunities?verified_only=true", headers=student_headers)
        assert res.status_code == 200
        items = res.json()
        item_ids = [i["id"] for i in items]

        # Verified opp MUST be present, Pending opp MUST NOT be present
        assert "opp_verified_student_test" in item_ids
        assert "opp_pending_student_test" not in item_ids

        # Inspect student record transparency
        retrieved = next(i for i in items if i["id"] == "opp_verified_student_test")
        assert retrieved["company"] == "GitHub"
        assert retrieved["work_mode"].lower() == "remote"
        assert retrieved["is_verified"] is True
        assert retrieved["verification_status"] == "VERIFIED"
        # Ensure internal scrapers/channels are not leaked
        assert "source_channel" not in retrieved
        assert "source_url" not in retrieved
    finally:
        db.close()


# ==============================================================================
# 14. ADMIN LINKEDIN STATUS HONEST REPORTING
# ==============================================================================

def test_admin_linkedin_status_reporting(client, admin_headers):
    """Admin LinkedIn status endpoint must clearly report connection status and never claim fake live access."""
    res = client.get("/api/admin/linkedin/status", headers=admin_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert "connection_status" in body
    assert "api_available" in body
    # When credentials are not configured, it must state "Authorized import required" or "DISCONNECTED"
    if not body["api_available"]:
        assert body["connection_status"] in ["NOT CONNECTED", "Authorized import required", "DISCONNECTED"]
        assert "authorized" in body.get("notice", "").lower() or "authorized" in body.get("connection_status", "").lower() or body["connection_status"] == "NOT CONNECTED"
