"""Comprehensive test suite for strict verification gate, security, SSRF defense, filtering, and authorization."""

import io
from datetime import date
import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from backend.api.app import app
from backend.database.db import SessionLocal, OpportunityDB, UserDB, StudentDB
from backend.models.user import UserRole
from backend.models.source import SourceType, SourceTrustLevel
from backend.utils.security import create_access_token, hash_password
from backend.utils.url_validator import validate_application_url, is_hostname_safe, is_ip_private_or_loopback
from backend.services import verification_service, opportunity_service

client = TestClient(app)

STUDENT_TOKEN = create_access_token({"sub": "usr_test_stud_1", "email": "student1@example.edu", "role": "STUDENT"})
ADMIN_TOKEN = create_access_token({"sub": "usr_test_adm_1", "email": "admin1@example.edu", "role": "ADMIN"})

STUDENT_HEADERS = {"Authorization": f"Bearer {STUDENT_TOKEN}"}
ADMIN_HEADERS = {"Authorization": f"Bearer {ADMIN_TOKEN}"}


@pytest.fixture(autouse=True)
def setup_test_data():
    db = SessionLocal()
    try:
        # Create student user if not present
        if not db.query(UserDB).filter_by(id="usr_test_stud_1").first():
            db.add(UserDB(
                id="usr_test_stud_1",
                email="student1@example.edu",
                password_hash=hash_password("Pass123!"),
                role="STUDENT",
                is_active=True
            ))
            db.add(StudentDB(
                id="usr_test_stud_1",
                user_id="usr_test_stud_1",
                name="Test Student",
                email="student1@example.edu",
                skills='["Python", "React", "PostgreSQL"]'
            ))

        # Create admin user if not present
        if not db.query(UserDB).filter_by(id="usr_test_adm_1").first():
            db.add(UserDB(
                id="usr_test_adm_1",
                email="admin1@example.edu",
                password_hash=hash_password("AdminPass123!"),
                role="ADMIN",
                is_active=True
            ))

        # Seed sample opportunities with various verification statuses
        opp_verified = OpportunityDB(
            id="opp_test_verified_101",
            title="Backend Software Intern",
            company="Stripe Global",
            description="Build scalable backend services using Python and PostgreSQL.",
            opportunity_type="internship",
            skills='["Python", "PostgreSQL", "API"]',
            location="Bengaluru / Remote",
            remote=True,
            experience="Fresher / Student",
            stipend="₹60,000/month",
            apply_url="https://boards.greenhouse.io/stripe/jobs/101",
            source="ATS_PUBLIC_FEED",
            verification_status="VERIFIED",
            trust_level="OFFICIAL_COMPANY",
            status="active"
        )

        opp_pending = OpportunityDB(
            id="opp_test_pending_202",
            title="Unreviewed Machine Learning Intern",
            company="Pending AI Corp",
            description="Machine learning data processing role.",
            opportunity_type="internship",
            skills='["Python", "PyTorch"]',
            location="Remote",
            remote=True,
            experience="Fresher",
            apply_url="https://unknown-portal-99.xyz/apply",
            source="TELEGRAM",
            verification_status="PENDING_REVIEW",
            trust_level="UNVERIFIED_EXTERNAL",
            status="active"
        )

        opp_rejected = OpportunityDB(
            id="opp_test_rejected_303",
            title="Spam Course Promotion",
            company="Fake Academy",
            description="Buy course now to get guaranteed 100% money back airdrop bounty.",
            opportunity_type="job",
            skills='["Crypto"]',
            apply_url="https://scam-site.top/join",
            source="TELEGRAM",
            verification_status="REJECTED",
            trust_level="UNVERIFIED_EXTERNAL",
            status="active"
        )

        today_iso = date.today().isoformat()
        opp_verified.posted_date = today_iso
        opp_pending.posted_date = today_iso
        opp_rejected.posted_date = today_iso

        for item in [opp_verified, opp_pending, opp_rejected]:
            db.merge(item)

        db.commit()
    finally:
        db.close()


def test_student_feed_only_shows_verified():
    """Requirement 5: Students should ONLY see opportunities whose publication status is VERIFIED."""
    res = client.get("/api/opportunities?limit=200", headers=STUDENT_HEADERS)
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)

    item_ids = [o["id"] for o in items]
    assert "opp_test_verified_101" in item_ids
    assert "opp_test_pending_202" not in item_ids
    assert "opp_test_rejected_303" not in item_ids

    # Every item returned to a student must have VERIFIED status
    for o in items:
        assert o.get("verification_status") == "VERIFIED"
        # Source channel or private scraping details should not be leaked to student
        assert "source_channel" not in o or o["source_channel"] is None or o["source_channel"] == ""


def test_admin_can_see_pending_and_rejected():
    """Admins can view pending and unverified listings for review."""
    res = client.get("/api/opportunities?verified_only=false&limit=200", headers=ADMIN_HEADERS)
    assert res.status_code == 200
    items = res.json()
    item_ids = [o["id"] for o in items]
    assert "opp_test_verified_101" in item_ids
    assert "opp_test_pending_202" in item_ids


def test_student_cannot_access_unverified_by_id():
    """Direct ID lookup of an unverified or pending job returns 404 for students."""
    # Verified job -> 200
    res_v = client.get("/api/opportunities/opp_test_verified_101", headers=STUDENT_HEADERS)
    assert res_v.status_code == 200

    # Pending job -> 404 for student
    res_p = client.get("/api/opportunities/opp_test_pending_202", headers=STUDENT_HEADERS)
    assert res_p.status_code == 404

    # Admin can access pending job -> 200
    res_admin = client.get("/api/opportunities/opp_test_pending_202", headers=ADMIN_HEADERS)
    assert res_admin.status_code == 200


def test_student_cannot_access_admin_endpoints():
    """Requirement 10: Server-side RBAC enforces 403 on admin-only endpoints."""
    res1 = client.get("/api/admin/dashboard", headers=STUDENT_HEADERS)
    assert res1.status_code in [401, 403]

    res2 = client.post("/api/admin/verify/opp_test_pending_202", headers=STUDENT_HEADERS, json={})
    assert res2.status_code in [401, 403]

    res3 = client.get("/api/admin/users", headers=STUDENT_HEADERS)
    assert res3.status_code in [401, 403]


def test_multi_filter_combinations():
    """Requirement 13: Multi-filters work together with accurate boolean AND logic."""
    res = client.get("/api/opportunities?type=internship&remote=true&skill=Python&experience=Fresher", headers=STUDENT_HEADERS)
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 1
    for o in items:
        assert o["remote"] is True
        assert "python" in [s.lower() for s in o["skills"]]


def test_pagination_headers():
    """Requirement 13: Pagination headers return accurate totals and page info."""
    res = client.get("/api/opportunities?limit=5&page=1", headers=STUDENT_HEADERS)
    assert res.status_code == 200
    assert "X-Total-Count" in res.headers
    assert "X-Page" in res.headers
    assert "X-Total-Pages" in res.headers
    assert int(res.headers["X-Page"]) == 1


def test_ssrf_and_private_ip_rejection():
    """Requirement 11: Reject localhost, loopback, private IPs, and internal hostnames."""
    # Localhost
    valid, reason, _ = validate_application_url("http://localhost:8000/apply")
    assert not valid
    assert "Forbidden" in reason or "internal" in reason or "loopback" in reason

    # 127.0.0.1
    valid2, _, _ = validate_application_url("http://127.0.0.1/jobs/1")
    assert not valid2

    # AWS/GCP Cloud Metadata IP
    valid3, _, _ = validate_application_url("http://169.254.169.254/latest/meta-data")
    assert not valid3

    # Private RFC1918 (10.x and 192.168.x)
    assert is_ip_private_or_loopback("10.0.1.5")
    assert is_ip_private_or_loopback("192.168.1.1")
    assert is_ip_private_or_loopback("172.16.0.1")

    # Non-HTTP Schemes
    valid_file, _, _ = validate_application_url("file:///etc/passwd")
    assert not valid_file

    valid_js, _, _ = validate_application_url("javascript:alert(1)")
    assert not valid_js

    valid_data, _, _ = validate_application_url("data:text/html,<h1>Hello</h1>")
    assert not valid_data


def test_telegram_channel_validation():
    """Requirement 9: Public @channel validation and rejection of private invite links."""
    # Private invite link -> Rejected
    valid, reason, _ = validate_application_url("https://t.me/+AbCdEfGhIjKl")
    assert not valid

    # Malformed URL -> Rejected
    valid2, _, _ = validate_application_url("not_a_valid_url")
    assert not valid2

    # Valid ATS link -> Accepted
    valid_ats, _, canon = validate_application_url("https://boards.greenhouse.io/figma/jobs/12345?utm_source=tg")
    assert valid_ats
    assert "utm_source" not in canon  # Tracking parameter stripped


def test_resume_upload_validation_non_pdf():
    """Requirement 10: Resume upload rejects non-PDF files."""
    files = {"file": ("script.py", b"print('malicious')", "text/x-python")}
    res = client.post("/api/students/resume", headers=STUDENT_HEADERS, files=files)
    assert res.status_code == 400
    assert "PDF" in res.json()["detail"]


def test_resume_upload_valid_pdf():
    """Requirement 10: Valid PDF resume parsing."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(100, 750, "Debasis Behera")
    c.drawString(100, 720, "SKILLS: Python, FastApi, React, PostgreSQL")
    c.save()
    buf.seek(0)

    files = {"file": ("debasis_resume.pdf", buf.read(), "application/pdf")}
    res = client.post("/api/students/resume?apply_to_profile=true", headers=STUDENT_HEADERS, files=files)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "Python" in data["extracted_data"]["skills"]


def test_token_logout_invalidation():
    """Requirement 10: Logged out tokens are revoked in blacklist and rejected."""
    db = SessionLocal()
    try:
        if not db.query(UserDB).filter_by(id="usr_logout_test").first():
            db.add(UserDB(
                id="usr_logout_test",
                email="logout@example.edu",
                password_hash=hash_password("Pass123!"),
                role="STUDENT",
                is_active=True
            ))
            db.add(StudentDB(
                id="usr_logout_test",
                user_id="usr_logout_test",
                name="Logout Test User",
                email="logout@example.edu"
            ))
            db.commit()
    finally:
        db.close()

    logout_token = create_access_token({"sub": "usr_logout_test", "email": "logout@example.edu", "role": "STUDENT"})
    headers = {"Authorization": f"Bearer {logout_token}"}

    # First request works
    res1 = client.get("/api/student", headers=headers)
    assert res1.status_code == 200

    # Logout
    res_logout = client.post("/api/auth/logout", headers=headers)
    assert res_logout.status_code == 200

    # Subsequent request fails with 401
    res2 = client.get("/api/student", headers=headers)
    assert res2.status_code == 401
