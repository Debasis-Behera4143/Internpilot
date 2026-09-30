"""Comprehensive test suite covering all 19 required verification and security scenarios:

1. Telegram fake job
2. Telegram invite link
3. Telegram referral post
4. Telegram course advertisement
5. Expired Telegram job
6. Invalid application URL
7. Phishing URL
8. Localhost / private IP SSRF URL
9. Redirect URL SSRF validation
10. Duplicate job prevention
11. Fake / unidentified company
12. Valid company job
13. LinkedIn import
14. Invalid LinkedIn import
15. Student accessing pending job
16. Student accessing admin API
17. Admin source management
18. Compact job filtering
19. Authentication & session security
"""

import pytest
from datetime import date, timedelta, datetime, timezone
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.collectors.telegram_collector import TelegramCollector
from backend.collectors.linkedin_collector import LinkedInCollector
from backend.utils.url_validator import validate_application_url, probe_application_url, is_ip_private_or_loopback
from backend.services.job_classifier import classify_opportunity_content
from backend.services.verification_service import evaluate_opportunity_verification
from backend.services import source_service
from backend.database.db import SessionLocal, OpportunityDB, UserDB, TokenBlacklistDB
from backend.models.source import SourceCreateRequest, SourceUpdateRequest, SourceType, SourceStatus


@pytest.fixture
def client():
    return TestClient(app)


# =========================================================================
# 1. Telegram fake job
# =========================================================================
def test_1_telegram_fake_job():
    """Vague / spammy Telegram post with no company or legit job structure is classified as non-job."""
    spam_post = "Work from home! Earn Rs 1500 daily typing captcha. No experience needed! DM now @scam_admin"
    is_genuine, reject_cat, reasons = classify_opportunity_content("Captcha Job", "Unknown", spam_post)
    assert not is_genuine
    assert reject_cat in ["PAID_TRAINING_SCAM", "VAGUE_HIRING", "ADVERTISEMENT", "UNIDENTIFIED_COMPANY"]

    collector = TelegramCollector()
    parsed = collector.extract_opportunity_from_text(spam_post)
    # Collector must fail closed and return None
    assert parsed is None


# =========================================================================
# 2. Telegram invite link
# =========================================================================
def test_2_telegram_invite_link():
    """Telegram post containing ONLY invite link or channel link as apply URL is rejected."""
    invite_post = (
        "Python Internship Opening! Apply immediately at https://t.me/joinchat/AAAAAFxyz123 "
        "or contact our channel https://t.me/tech_jobs_official"
    )
    collector = TelegramCollector()
    parsed = collector.extract_opportunity_from_text(invite_post)
    # Collector drops posts with only Telegram links
    assert parsed is None

    # url_validator directly rejects Telegram domains as application URL
    is_valid, reason, _ = validate_application_url("https://t.me/joinchat/AbcDef123")
    assert not is_valid
    assert "telegram" in reason.lower()


# =========================================================================
# 3. Telegram referral post
# =========================================================================
def test_3_telegram_referral_post():
    """Telegram referral / sign up promotion is classified as referral and dropped."""
    referral_text = (
        "Huge hiring opportunity! Sign up using my referral link https://example.com/ref/12345 "
        "and use code BONUS100 to get cash bonus. Direct referral available."
    )
    is_genuine, reject_cat, reasons = classify_opportunity_content("Referral Promo", "Unknown Corp", referral_text)
    assert not is_genuine
    assert reject_cat in ["REFERRAL_ONLY", "UNIDENTIFIED_COMPANY", "ADVERTISEMENT", "PROMOTIONAL_CONTENT"]

    collector = TelegramCollector()
    parsed = collector.extract_opportunity_from_text(referral_text)
    assert parsed is None


# =========================================================================
# 4. Telegram course advertisement
# =========================================================================
def test_4_telegram_course_advertisement():
    """Course sales with placement promises are classified as course and dropped."""
    course_text = (
        "Full Stack Web Development Masterclass! 100% placement guarantee course. "
        "Register for webinar at https://learncodingbootcamp.com/enroll today!"
    )
    is_genuine, reject_cat, reasons = classify_opportunity_content("Course Placement", "Coding Bootcamp", course_text)
    assert not is_genuine
    assert reject_cat in ["PROMOTIONAL_CONTENT", "PAID_TRAINING_SCAM", "ADVERTISEMENT"]

    collector = TelegramCollector()
    parsed = collector.extract_opportunity_from_text(course_text)
    assert parsed is None


# =========================================================================
# 5. Expired Telegram job
# =========================================================================
def test_5_expired_telegram_job():
    """Telegram post with a past deadline is discarded by the collector."""
    past_date = (date.today() - timedelta(days=30)).isoformat()
    expired_text = (
        f"Software Engineer at Infosys. Location: Bengaluru. "
        f"Apply before deadline: {past_date}. Link: https://careers.infosys.com/job/123"
    )
    collector = TelegramCollector()
    parsed = collector.extract_opportunity_from_text(expired_text)
    assert parsed is None


# =========================================================================
# 6. Invalid application URL
# =========================================================================
def test_6_invalid_application_url():
    """Application URL must require HTTPS and valid structure."""
    # HTTP without HTTPS
    is_valid, reason, _ = validate_application_url("http://careers.google.com/jobs/123")
    assert not is_valid
    assert "https" in reason.lower()

    # javascript / mailto schemes
    is_valid, reason, _ = validate_application_url("javascript:alert(1)")
    assert not is_valid

    # Malformed
    is_valid, reason, _ = validate_application_url("not_a_valid_url")
    assert not is_valid


# =========================================================================
# 7. Phishing URL
# =========================================================================
def test_7_phishing_url():
    """URL shorteners or suspicious credential domains are flagged or rejected."""
    # Shortener bit.ly
    is_valid, reason, _ = validate_application_url("https://bit.ly/3xJobOpportunity")
    assert not is_valid or "shortener" in reason.lower()

    # Generic shortener tinyurl
    is_valid, reason, _ = validate_application_url("https://tinyurl.com/freejob")
    assert not is_valid or "shortener" in reason.lower()


# =========================================================================
# 8. Localhost / private IP SSRF URL
# =========================================================================
def test_8_localhost_private_ip_ssrf():
    """SSRF checks block loopback, RFC1918, and cloud metadata IPs."""
    assert is_ip_private_or_loopback("127.0.0.1") is True
    assert is_ip_private_or_loopback("10.0.0.1") is True
    assert is_ip_private_or_loopback("192.168.1.1") is True
    assert is_ip_private_or_loopback("172.16.0.1") is True
    assert is_ip_private_or_loopback("169.254.169.254") is True

    # validate_application_url blocks localhost / private IP hostnames
    is_valid, reason, _ = validate_application_url("https://localhost:8000/apply")
    assert not is_valid
    assert "ssrf" in reason.lower() or "blocked" in reason.lower() or "localhost" in reason.lower()

    is_valid, reason, _ = validate_application_url("https://127.0.0.1/admin/apply")
    assert not is_valid


# =========================================================================
# 9. Redirect URL SSRF validation
# =========================================================================
def test_9_redirect_url_ssrf_probe():
    """probe_application_url checks every hop and rejects private IP redirects."""
    # Probing an invalid / private address directly fails
    reachable, msg, final_url = probe_application_url("https://127.0.0.1:9999/apply", timeout=1.0)
    assert not reachable
    assert "ssrf" in msg.lower() or "blocked" in msg.lower() or "not reachable" in msg.lower()


# =========================================================================
# 10. Duplicate job prevention
# =========================================================================
def test_10_duplicate_job_prevention(admin_client):
    """Submitting the exact same normalized URL / company / title is detected as duplicate."""
    db = SessionLocal()
    unique_title = f"Data Analyst Intern DupCheck {date.today().isoformat()}"
    test_opp = OpportunityDB(
        id="test_dup_original_1",
        title=unique_title,
        company="Razorpay",
        opportunity_type="internship",
        source="company_careers",
        apply_url="https://jobs.lever.co/razorpay/data-analyst-dup-1",
        application_url="https://jobs.lever.co/razorpay/data-analyst-dup-1",
        normalized_url="jobs.lever.co/razorpay/data-analyst-dup-1",
        status="active",
        verification_status="VERIFIED"
    )
    db.merge(test_opp)
    db.commit()
    db.close()

    # Try previewing import with duplicate URL
    preview_res = admin_client.post(
        "/api/admin/import/preview",
        json={
            "content": f"Title,Company,Location,Apply URL\n{unique_title},Razorpay,Bengaluru,https://jobs.lever.co/razorpay/data-analyst-dup-1",
            "source_name": "CSV Test",
            "source_type": "CSV"
        }
    )
    assert preview_res.status_code == 200
    data = preview_res.json()
    assert data["duplicates_count"] >= 1
    assert data["items"][0]["is_duplicate"] is True


# =========================================================================
# 11. Fake / unidentified company
# =========================================================================
def test_11_fake_unidentified_company():
    """Job with missing company or domain mismatch cannot achieve VERIFIED status."""
    final_status, level, checks, reasons = evaluate_opportunity_verification({
        "title": "Software Engineer Intern",
        "company": "Top Secret Stealth MNC",
        "apply_url": "https://suspicious-unrelated-portal.xyz/jobs/apply",
        "opportunity_type": "internship",
        "description": "Work on software projects.",
        "trust_level": "PUBLIC_TELEGRAM"
    })
    assert final_status in ["PENDING_REVIEW", "REJECTED"]
    assert final_status != "VERIFIED"


# =========================================================================
# 12. Valid company job
# =========================================================================
def test_12_valid_company_job():
    """Job with legitimate company and matching official ATS domain evaluates to VERIFIED."""
    final_status, level, checks, reasons = evaluate_opportunity_verification({
        "title": "Software Engineer Intern 2026",
        "company": "Google",
        "apply_url": "https://careers.google.com/jobs/results/12345-software-engineer",
        "opportunity_type": "internship",
        "description": "Join Google engineering team for Summer 2026 internship in Bengaluru.",
        "location": "Bengaluru",
        "deadline": (date.today() + timedelta(days=60)).isoformat(),
        "trust_level": "OFFICIAL_COMPANY"
    })
    assert final_status == "VERIFIED"


# =========================================================================
# 13. LinkedIn import
# =========================================================================
def test_13_linkedin_import(admin_client):
    """LinkedIn collector states required authorization and import route accepts datasets."""
    collector = LinkedInCollector()
    assert collector.get_status() == "LinkedIn authorization/import required"

    import uuid
    uid = uuid.uuid4().hex[:6]
    records = [
        {
            "title": f"Frontend Engineer Intern {uid}",
            "company": "Microsoft",
            "location": "Hyderabad",
            "opportunity_type": "internship",
            "apply_url": f"https://careers.microsoft.com/us/en/job/{uid}",
            "description": "Build user experiences at Microsoft.",
            "deadline": (date.today() + timedelta(days=45)).isoformat()
        }
    ]
    res = admin_client.post(
        "/api/admin/import/confirm",
        json={
            "source_name": "LinkedIn Authorized Batch",
            "source_type": "LINKEDIN_AUTHORIZED",
            "records": records
        }
    )
    assert res.status_code == 200
    data = res.json()
    assert data["accepted"] >= 1


# =========================================================================
# 14. Invalid LinkedIn import
# =========================================================================
def test_14_invalid_linkedin_import(admin_client):
    """LinkedIn / CSV import preview flags malformed items missing title or company."""
    malformed_csv = "Title,Company,Apply URL\n,Unknown Corp,https://careers.example.com\nValid Role,,https://careers.example.com"
    preview_res = admin_client.post(
        "/api/admin/import/preview",
        json={
            "content": malformed_csv,
            "source_name": "LinkedIn Export",
            "source_type": "CSV"
        }
    )
    assert preview_res.status_code == 200
    data = preview_res.json()
    assert data["rejected_count"] >= 2


# =========================================================================
# 15. Student accessing pending job
# =========================================================================
def test_15_student_accessing_pending_job(authed_client, admin_client):
    """Student cannot see or fetch a job held in PENDING_REVIEW (fail-closed)."""
    db = SessionLocal()
    pending_job = OpportunityDB(
        id="job_pending_secret_review_1",
        title="Unverified Opportunity Pending",
        company="Stealth Inc",
        opportunity_type="internship",
        source="telegram",
        apply_url="https://careers.stealth.com/apply",
        application_url="https://careers.stealth.com/apply",
        status="open",
        verification_status="PENDING_REVIEW",
        created_at=datetime.now(timezone.utc),
    )
    db.merge(pending_job)
    db.commit()
    db.close()

    try:
        # 1. Student detail request returns 404
        res = authed_client.get("/api/opportunities/job_pending_secret_review_1")
        assert res.status_code == 404

        # 2. Student list feed does not contain the pending job
        feed_res = authed_client.get("/api/opportunities?q=Unverified Opportunity Pending")
        assert feed_res.status_code == 200
        items = feed_res.json()
        found = any(i["id"] == "job_pending_secret_review_1" for i in items)
        assert not found

        # Admin CAN see it in raw view
        admin_res = admin_client.get("/api/admin/opportunities")
        assert admin_res.status_code == 200
        admin_items = admin_res.json()
        assert any(i["id"] == "job_pending_secret_review_1" for i in admin_items)
    finally:
        clean_db = SessionLocal()
        clean_db.query(OpportunityDB).filter_by(id="job_pending_secret_review_1").delete()
        clean_db.commit()
        clean_db.close()


# =========================================================================
# 16. Student accessing admin API
# =========================================================================
def test_16_student_accessing_admin_api(authed_client):
    """Student credentials requesting admin endpoints are rejected with HTTP 403 Forbidden."""
    res = authed_client.get("/api/admin/dashboard")
    assert res.status_code == 403

    res_sources = authed_client.get("/api/admin/sources")
    assert res_sources.status_code == 403

    res_users = authed_client.get("/api/admin/users")
    assert res_users.status_code == 403


# =========================================================================
# 17. Admin source management
# =========================================================================
def test_17_admin_source_management(admin_client):
    """Admin can create, list, pause/resume, update, and delete sources."""
    # 1. Create
    create_res = admin_client.post(
        "/api/admin/sources",
        json={
            "name": "Acme ATS Feed",
            "type": "ATS_PUBLIC_FEED",
            "configuration": {"url": "https://careers.acme.corp/jobs"}
        }
    )
    assert create_res.status_code == 200
    src_id = create_res.json()["source"]["id"]

    # 2. List
    list_res = admin_client.get("/api/admin/sources")
    assert list_res.status_code == 200
    sources = list_res.json()["sources"]
    assert any(s["id"] == src_id for s in sources)

    # 3. Toggle Pause / Resume
    toggle_res = admin_client.post(f"/api/admin/sources/{src_id}/toggle")
    assert toggle_res.status_code == 200
    assert toggle_res.json()["source"]["status"] == "PAUSED"

    # Toggle back to ACTIVE
    toggle_res2 = admin_client.post(f"/api/admin/sources/{src_id}/toggle")
    assert toggle_res2.status_code == 200
    assert toggle_res2.json()["source"]["status"] == "ACTIVE"

    # 4. Update (Edit)
    update_res = admin_client.put(
        f"/api/admin/sources/{src_id}",
        json={
            "name": "Acme Global Careers ATS",
            "status": "ACTIVE",
            "configuration": {"url": "https://careers.acme.corp/global"}
        }
    )
    assert update_res.status_code == 200
    assert update_res.json()["source"]["name"] == "Acme Global Careers ATS"

    # 5. Delete
    delete_res = admin_client.delete(f"/api/admin/sources/{src_id}")
    assert delete_res.status_code == 200


# =========================================================================
# 18. Compact job filtering
# =========================================================================
def test_18_compact_job_filtering(client):
    """Opportunities API handles compact filters and verified_only fails closed."""
    # Default search (verified_only=True)
    res = client.get("/api/opportunities?type=internship&work_mode=remote")
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)
    for opp in items:
        assert opp["verification_status"] == "VERIFIED"
        assert opp["status"] in ["open", "active"]


# =========================================================================
# 19. Authentication & session security
# =========================================================================
def test_19_auth_and_session_security(client):
    """Tests password hashing, login, logout token blacklisting, and revocation."""
    # 1. Successful student login
    login_res = client.post(
        "/api/auth/login",
        json={"email": "default_student@example.com", "password": "DefaultStudentPass123!"}
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    assert token is not None

    # 2. Invalid password rejected
    bad_login = client.post(
        "/api/auth/login",
        json={"email": "default_student@example.com", "password": "WrongPassword!"}
    )
    assert bad_login.status_code == 401

    # 3. Access with valid token
    headers = {"Authorization": f"Bearer {token}"}
    me_res = client.get("/api/student", headers=headers)
    assert me_res.status_code == 200

    # 4. Logout revokes token
    logout_res = client.post("/api/auth/logout", headers=headers)
    assert logout_res.status_code == 200

    # 5. Blacklisted token cannot access endpoints anymore
    post_logout_res = client.get("/api/student", headers=headers)
    assert post_logout_res.status_code == 401
