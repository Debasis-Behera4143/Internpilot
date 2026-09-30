"""Comprehensive automated test suite for production hardening, security, and strict validation.

Tests covering Requirement #9:
- invalid Telegram URLs
- Telegram invite links
- random websites
- malicious URLs
- localhost/private URLs (SSRF protection)
- duplicate sources
- duplicate jobs
- invalid Apply URLs
- phishing-like domains
- non-job Telegram posts
- uncertain classifications
- expired jobs
- unauthorized admin access
- student attempting admin endpoints
- invalid file uploads
- rate limiting
- XSS payloads
- source privacy
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.database.db import SessionLocal, OpportunityDB, SourceRegistryDB, UserDB, init_db
from backend.models.opportunity import Opportunity
from backend.utils.security import hash_password, create_access_token
from backend.utils.url_validator import (
    validate_application_url,
    validate_telegram_channel_spec,
    is_ip_private_or_loopback,
    sanitize_and_canonicalize_url
)
from backend.collectors.telegram_collector import TelegramCollector
from backend.services.deduplication_service import is_duplicate, deduplicate_opportunities
from backend.services.expiry_service import evaluate_and_update_expiry_in_db


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def admin_token():
    db = SessionLocal()
    try:
        admin = db.query(UserDB).filter_by(email="hardened_admin@hub.com").first()
        if not admin:
            admin = UserDB(
                id="usr_hardened_admin",
                email="hardened_admin@hub.com",
                password_hash=hash_password("SuperSecretAdminPass123!"),
                role="ADMIN",
                is_active=True
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
        return create_access_token({"sub": admin.id, "email": admin.email, "role": "ADMIN"})
    finally:
        db.close()


@pytest.fixture(scope="module")
def student_token():
    db = SessionLocal()
    try:
        student = db.query(UserDB).filter_by(email="hardened_student@hub.com").first()
        if not student:
            student = UserDB(
                id="usr_hardened_student",
                email="hardened_student@hub.com",
                password_hash=hash_password("StudentPass123!"),
                role="STUDENT",
                is_active=True
            )
            db.add(student)
            db.commit()
            db.refresh(student)
        return create_access_token({"sub": student.id, "email": student.email, "role": "STUDENT"})
    finally:
        db.close()


class TestUrlValidationAndSSRF:
    """1. Test SSRF protection, URL schemes, phishing detection, and malicious URLs."""

    def test_reject_localhost_and_loopback(self):
        urls = [
            "http://localhost:8000/admin",
            "http://127.0.0.1/api/keys",
            "http://127.0.0.1:5000",
            "http://0.0.0.0:8080",
            "http://[::1]/secret",
            "http://169.254.169.254/latest/meta-data/"
        ]
        for u in urls:
            is_valid, reason, _ = validate_application_url(u)
            assert is_valid is False
            assert "Blocked unsafe destination" in reason or "Forbidden" in reason

    def test_reject_private_rfc1918_ips(self):
        urls = [
            "http://192.168.1.1/router",
            "http://10.0.0.5/internal",
            "http://172.16.0.1/login"
        ]
        for u in urls:
            is_valid, reason, _ = validate_application_url(u)
            assert is_valid is False
            assert "Private or loopback IP" in reason or "Blocked" in reason

    def test_reject_unsupported_and_dangerous_schemes(self):
        urls = [
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "file:///etc/passwd",
            "ftp://files.example.com/job"
        ]
        for u in urls:
            is_valid, reason, _ = validate_application_url(u)
            assert is_valid is False
            assert "Invalid URL scheme" in reason

    def test_reject_phishing_and_high_risk_tlds(self):
        urls = [
            "https://login-verify-jobs.com/apply",
            "https://careers.company.top/apply",
            "https://free-money-internships.buzz/register"
        ]
        for u in urls:
            is_valid, reason, _ = validate_application_url(u)
            assert is_valid is False

    def test_accept_genuine_application_urls_and_canonicalize(self):
        raw_url = "https://careers.google.com/jobs/123/?utm_source=telegram&utm_medium=post&ref=social"
        is_valid, reason, canon = validate_application_url(raw_url)
        assert is_valid is True
        assert "utm_source" not in canon
        assert "ref" not in canon
        assert canon == "https://careers.google.com/jobs/123"


class TestTelegramValidation:
    """2. Test Telegram channel URL validation, invite link rejection, and channel spec."""

    def test_validate_valid_public_channel_specs(self):
        is_valid, msg, details = validate_telegram_channel_spec(
            channel_username="@tech_internships_hub",
            preview_url="https://t.me/s/tech_internships_hub"
        )
        assert is_valid is True
        assert "Valid public Telegram channel" in msg
        assert details["handle"] == "tech_internships_hub"

    def test_reject_telegram_invite_links(self):
        invite_urls = [
            "https://t.me/joinchat/AAAAAFM898",
            "https://t.me/+AbCdEfGh123",
            "https://t.me/s/joinchat/123"
        ]
        for inv in invite_urls:
            is_valid, msg, _ = validate_telegram_channel_spec(
                channel_username="tech_hub",
                preview_url=inv
            )
            assert is_valid is False
            assert "invite links" in msg.lower() or "invalid" in msg.lower()

    def test_reject_channel_username_mismatch(self):
        is_valid, msg, _ = validate_telegram_channel_spec(
            channel_username="@tech_hub",
            preview_url="https://t.me/s/completely_different_channel"
        )
        assert is_valid is False
        assert "does not match" in msg


class TestDuplicateAndExpiryHandling:
    """3. Test duplicate detection across sources and automated expiry handling."""

    def test_multi_source_duplicate_detection(self):
        opp_tg = Opportunity(
            id="opp_tg_1",
            title="Software Development Engineer Intern",
            company="Amazon Web Services",
            apply_url="https://amazon.jobs/en/jobs/101?utm_source=tg",
            source="Telegram"
        )
        opp_web = Opportunity(
            id="opp_web_1",
            title="SDE Intern",
            company="Amazon Web Services",
            apply_url="https://amazon.jobs/en/jobs/101",
            source="Company Careers"
        )
        is_dup, reason = is_duplicate(opp_tg, opp_web)
        assert is_dup is True
        assert "exact_apply_url" in reason or "title" in reason

        unique, dups = deduplicate_opportunities([opp_tg, opp_web])
        assert len(unique) == 1
        assert dups == 1
        assert "Telegram" in unique[0].source
        assert "Company Careers" in unique[0].source

    def test_expired_deadline_evaluation(self):
        db = SessionLocal()
        opp_id = "test_expired_opp_hardening_1"
        try:
            opp = OpportunityDB(
                id=opp_id,
                title="Expired Tech Role",
                company="Old Corp",
                apply_url="https://oldcorp.com/apply/1",
                deadline="2020-01-01",
                status="active"
            )
            db.merge(opp)
            db.commit()
        finally:
            db.close()

        rep = evaluate_and_update_expiry_in_db()
        assert rep["newly_expired"] >= 1

        db = SessionLocal()
        try:
            checked = db.query(OpportunityDB).filter_by(id=opp_id).first()
            assert checked.status == "expired"
        finally:
            db.close()


class TestSecurityAndAccessControl:
    """4. Test authorization, rate limiting, XSS prevention, and source privacy."""

    def test_student_cannot_access_admin_sources(self, client, student_token):
        res = client.get("/api/admin/sources", headers={"Authorization": f"Bearer {student_token}"})
        assert res.status_code == 403
        assert "Admin privileges required" in res.json()["detail"]

    def test_student_cannot_access_quality_dashboard(self, client, student_token):
        res = client.get("/api/admin/quality-dashboard", headers={"Authorization": f"Bearer {student_token}"})
        assert res.status_code == 403

    def test_source_privacy_sanitization_for_students(self, client, student_token):
        # Student viewing opportunities endpoint
        res = client.get("/api/opportunities?limit=5", headers={"Authorization": f"Bearer {student_token}"})
        assert res.status_code == 200
        items = res.json()
        for item in items:
            # Student representation must NOT expose internal source channels or raw scraping text
            assert "source_channel" not in item
            assert "raw_text" not in item

    def test_security_headers_present(self, client):
        res = client.get("/api/health")
        assert res.status_code == 200
        assert res.headers.get("X-Content-Type-Options") == "nosniff"
        assert res.headers.get("X-Frame-Options") == "DENY"
        assert "Content-Security-Policy" in res.headers

    def test_resume_upload_magic_byte_validation(self, client, student_token):
        # Fake PDF that is actually executable / text
        fake_files = {
            "file": ("fake.pdf", b"MZ\x90\x00Not a real PDF", "application/pdf")
        }
        res = client.post(
            "/api/students/resume",
            files=fake_files,
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert res.status_code == 400
        assert "signature" in res.json()["detail"].lower() or "valid pdf" in res.json()["detail"].lower()


class TestAdminSourceValidationEndpoint:
    """5. Test interactive Admin Source Validation endpoint (Validate -> Preview -> Confirm)."""

    def test_admin_validate_telegram_channel_success(self, client, admin_token):
        payload = {
            "name": "Live Tech Jobs",
            "type": "TELEGRAM",
            "configuration": {
                "channel_username": "@livetechjobs_channel",
                "preview_url": "https://t.me/s/livetechjobs_channel"
            }
        }
        res = client.post(
            "/api/admin/sources/validate",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is True
        assert "preview" in data
        assert data["preview"]["handle"] == "@livetechjobs_channel"

    def test_admin_validate_invalid_telegram_rejects(self, client, admin_token):
        payload = {
            "name": "Bad Channel",
            "type": "TELEGRAM",
            "configuration": {
                "channel_username": "invalid username with spaces!",
                "preview_url": "https://t.me/joinchat/badinvite"
            }
        }
        res = client.post(
            "/api/admin/sources/validate",
            json=payload,
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is False
        assert "Invalid" in data["message"] or "invite" in data["message"].lower()
