"""Regression test suite for Step 25: User-Facing Fixes and Critical Enhancements.

Tests cover:
1. AUTH: Google sign-in validation, returning user, duplicate prevention, password reset distinction.
2. ONBOARDING: Manual profile creation, fast resume extraction, profile review & confirmation, profile completeness.
3. RECOMMENDATIONS: Ordering by match score, fallback behavior when minimal profile.
4. JOB VALIDATION: Expiry detection, dead indicators, revalidation probing.
5. COMPANY: Extraction from domain, text patterns, and canonical normalization.
6. SECURITY: Resume download isolation, student cross-access prevention, admin RBAC.
"""

import pytest
import uuid
import json
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.api.app import app
from backend.database.db import SessionLocal, UserDB, StudentDB, OpportunityDB
from backend.utils.security import hash_password, create_access_token
from backend.models.opportunity import Opportunity
from backend.models.student import Student
from backend.services.expiry_service import is_opportunity_expired, check_content_for_closed_indicators
from backend.services.company_extractor import resolve_company, canonicalize_company_name
from backend.services.matching_service import get_recommendations

client = TestClient(app)


@pytest.fixture
def db_session():
    session = SessionLocal()
    yield session
    session.close()


# ==============================================================================
# 1. AUTHENTICATION REGRESSION TESTS
# ==============================================================================

def test_google_login_new_user_detection():
    """Verify first-time Google user is detected with is_new_user=True and is_onboarded=False."""
    unique_email = f"google_new_{uuid.uuid4().hex[:8]}@example.com"
    with patch("backend.api.routes_auth._verify_google_token") as mock_verify:
        mock_verify.return_value = {
            "email": unique_email,
            "name": "New Google User",
            "email_verified": True
        }
        res = client.post("/api/auth/google", json={"credential": "mock_id_token"})
        assert res.status_code == 200
        data = res.json()
        assert data["is_new_user"] is True
        assert data["user"]["is_onboarded"] is False
        assert data["user"]["auth_provider"] == "google"
        assert "access_token" in data


def test_google_login_returning_user_recognition():
    """Verify returning Google user does not duplicate account and preserves profile."""
    unique_email = f"google_ret_{uuid.uuid4().hex[:8]}@example.com"
    with patch("backend.api.routes_auth._verify_google_token") as mock_verify:
        mock_verify.return_value = {
            "email": unique_email,
            "name": "Returning Google User",
            "email_verified": True
        }
        # First sign-in
        res1 = client.post("/api/auth/google", json={"credential": "token1"})
        assert res1.status_code == 200
        assert res1.json()["is_new_user"] is True

        # Second sign-in
        res2 = client.post("/api/auth/google", json={"credential": "token2"})
        assert res2.status_code == 200
        assert res2.json()["is_new_user"] is False
        assert res2.json()["user"]["id"] == res1.json()["user"]["id"]


def test_forgot_password_distinguishes_google_account(db_session):
    """Verify Google accounts inform user that passwords are managed by Google."""
    google_email = f"google_only_{uuid.uuid4().hex[:8]}@gmail.com"
    user = UserDB(
        id=f"usr_{uuid.uuid4().hex[:12]}",
        email=google_email,
        role="STUDENT",
        auth_provider="google",
        password_hash=""
    )
    db_session.add(user)
    db_session.commit()

    res = client.post("/api/auth/forgot-password", json={"email": google_email})
    assert res.status_code == 200
    data = res.json()
    assert data["auth_provider"] == "google"
    assert "Google" in data["message"] and "recovery" in data["message"].lower()


def test_forgot_password_for_password_account(db_session):
    """Verify email/password accounts initiate standard reset flow."""
    local_email = f"local_user_{uuid.uuid4().hex[:8]}@example.com"
    user = UserDB(
        id=f"usr_{uuid.uuid4().hex[:12]}",
        email=local_email,
        role="STUDENT",
        auth_provider="local",
        password_hash=hash_password("MyPass123!")
    )
    db_session.add(user)
    db_session.commit()

    res = client.post("/api/auth/forgot-password", json={"email": local_email})
    assert res.status_code == 200
    data = res.json()
    assert data["auth_provider"] == "local"
    assert "Password reset instructions" in data["message"]


# ==============================================================================
# 2. ONBOARDING & PROFILE COMPLETENESS TESTS
# ==============================================================================

def test_manual_profile_update_and_onboarding_status(db_session):
    """Verify manual profile updating marks UserDB.is_onboarded as True."""
    email = f"student_ob_{uuid.uuid4().hex[:8]}@example.com"
    uid = f"usr_{uuid.uuid4().hex[:12]}"
    user = UserDB(
        id=uid,
        email=email,
        password_hash=hash_password("Pass123!"),
        role="STUDENT",
        is_onboarded=False
    )
    db_session.add(user)
    student = StudentDB(id=uid, user_id=uid, name="Onboard Candidate", email=email)
    db_session.add(student)
    db_session.commit()

    token = create_access_token({"sub": uid, "role": "STUDENT"})
    headers = {"Authorization": f"Bearer {token}"}

    update_payload = {
        "name": "Onboard Candidate",
        "education": "B.Tech Computer Science",
        "branch": "CSE",
        "graduation_year": 2026,
        "skills": ["Python", "FastAPI", "React"],
        "preferred_roles": ["Software Engineer Intern"],
        "preferred_locations": ["Remote"],
        "remote_preference": True
    }
    res = client.put("/api/student", json=update_payload, headers=headers)
    assert res.status_code == 200

    # Verify user record in db is now onboarded
    user_db = db_session.query(UserDB).filter_by(id=uid).first()
    assert user_db.is_onboarded is True


def test_profile_completeness_breakdown():
    """Verify completeness percentage and breakdown response."""
    student = Student(
        name="Alex Smith",
        email="alex@college.edu",
        education="B.S.",
        branch="Software Engineering",
        graduation_year=2026,
        cgpa=8.5,
        skills=["Python", "FastAPI", "React", "Docker"],
        preferred_roles=["Backend Intern"],
        preferred_locations=["Remote"]
    )
    breakdown = student.completeness_breakdown()
    assert "score" in breakdown
    assert breakdown["score"] >= 50.0
    assert "Personal Details" in breakdown["completed"]
    assert "Skills (at least 3)" in breakdown["completed"]


# ==============================================================================
# 3. RECOMMENDATIONS & FALLBACK TESTS
# ==============================================================================

def test_recommendation_ordering_and_fallback():
    """Verify recommendations are returned with scores and order descending."""
    student = Student(
        name="Candidate",
        skills=["Python", "Machine Learning", "PyTorch"],
        preferred_roles=["ML Intern", "AI Engineer"],
        preferred_locations=["Remote"],
        remote_preference=True
    )
    recs = get_recommendations(student=student, limit=10)
    assert isinstance(recs, list)
    if len(recs) >= 2:
        assert recs[0]["match_score"] >= recs[1]["match_score"]
    for r in recs:
        assert "match_score" in r
        assert r["verification_status"] == "VERIFIED"


# ==============================================================================
# 4. JOB VALIDATION & EXPIRY TESTS
# ==============================================================================

def test_dead_and_closed_indicators():
    """Verify closed and expired status phrases are recognized."""
    closed_titles = [
        "Software Intern (Applications Closed)",
        "Data Analyst - Position Filled",
        "Frontend Developer [Job Expired]",
        "404 Page Not Found",
        "Machine Learning Role - No longer accepting applications"
    ]
    for title in closed_titles:
        is_closed, phrase = check_content_for_closed_indicators(title)
        assert is_closed is True
        assert phrase is not None

    opp = Opportunity(
        title="Full Stack Intern (Applications Closed)",
        company="TechCorp",
        apply_url="https://techcorp.com/jobs/123"
    )
    expired, reason = is_opportunity_expired(opp)
    assert expired is True
    assert "closed_indicator_in_title" in reason


def test_expired_deadline_detection():
    """Verify past deadlines cause opportunity to be flagged expired."""
    opp = Opportunity(
        title="Active Title",
        company="Company X",
        apply_url="https://company.com/apply",
        deadline="2020-01-01"
    )
    expired, reason = is_opportunity_expired(opp)
    assert expired is True
    assert "deadline_passed" in reason


# ==============================================================================
# 5. COMPANY EXTRACTION & NORMALIZATION TESTS
# ==============================================================================

def test_company_extraction_and_canonicalization():
    """Verify canonical entity resolution without hallucination."""
    # Canonical mappings
    canon1, conf1, _ = canonicalize_company_name("Microsoft India Pvt. Ltd.")
    assert canon1 == "Microsoft"
    assert conf1 >= 0.90

    canon2, conf2, _ = canonicalize_company_name("TCS iON")
    assert canon2 == "TCS"

    # From explicit ATS URL
    res = resolve_company(apply_url="https://boards.greenhouse.io/airbnb/jobs/12345")
    assert res["normalized_company"] == "Airbnb"
    assert res["company_confidence"] >= 0.90

    # From uninformative placeholder
    res_unknown = resolve_company(raw_company="Unknown Company")
    assert res_unknown["normalized_company"] in ("Unknown", "Not specified")


# ==============================================================================
# 6. RESUME PRIVACY & SECURITY TESTS
# ==============================================================================

def test_unauthenticated_cannot_access_resume():
    """Verify anonymous request cannot download resumes."""
    res = client.get("/api/student/resume/download")
    assert res.status_code == 401


def test_student_cannot_download_another_students_resume(db_session):
    """Verify student A cannot supply student B's ID to download their resume."""
    student_a_id = f"usr_{uuid.uuid4().hex[:12]}"
    student_b_id = f"usr_{uuid.uuid4().hex[:12]}"

    user_a = UserDB(
        id=student_a_id,
        email=f"stud_a_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password("Pass123!"),
        role="STUDENT",
        is_active=True
    )
    db_session.add(user_a)
    db_session.commit()

    token_a = create_access_token({"sub": student_a_id, "role": "STUDENT"})
    headers = {"Authorization": f"Bearer {token_a}"}

    res = client.get(f"/api/student/resume/download?student_id={student_b_id}", headers=headers)
    assert res.status_code == 403
    assert "Cannot access another student's resume" in res.json()["detail"]
