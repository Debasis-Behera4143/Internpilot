"""Comprehensive automated test suite for Step 6A: Authentication, Role-Based Access Control, Data Isolation, and Source Privacy."""

import pytest
import uuid
from fastapi.testclient import TestClient
from backend.api.app import app
from backend.database.db import SessionLocal, UserDB, StudentDB, OpportunityDB
from backend.utils.security import hash_password, verify_password, create_access_token

client = TestClient(app)


@pytest.fixture
def test_db():
    """Provide a clean database session for test teardown."""
    session = SessionLocal()
    yield session
    session.close()


def test_password_hashing_and_verification():
    """Verify bcrypt direct hashing and verification behavior."""
    raw_pwd = "MySecretPassword123!"
    hashed = hash_password(raw_pwd)
    assert hashed != raw_pwd
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert verify_password(raw_pwd, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password("", hashed) is False


def test_student_registration_and_db_persistence(test_db):
    """Test student self-registration, validation, duplicate rejection, and bcrypt persistence."""
    unique_email = f"student_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "name": "Devin Candidate",
        "email": unique_email,
        "password": "SecureStudentPass123!",
        "confirm_password": "SecureStudentPass123!",
    }

    # 1. Successful Registration
    res = client.post("/api/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == unique_email
    assert data["user"]["role"] == "STUDENT"
    assert data["user"]["name"] == "Devin Candidate"

    # 2. Check SQLite persistence (Ensure password is NEVER plaintext)
    user_in_db = test_db.query(UserDB).filter(UserDB.email == unique_email).first()
    assert user_in_db is not None
    assert user_in_db.password_hash != "SecureStudentPass123!"
    assert verify_password("SecureStudentPass123!", user_in_db.password_hash) is True

    # 3. Check corresponding Student profile was created
    student_in_db = test_db.query(StudentDB).filter(StudentDB.id == user_in_db.id).first()
    assert student_in_db is not None
    assert student_in_db.name == "Devin Candidate"

    # 4. Duplicate Email Rejection
    dup_res = client.post("/api/auth/register", json=payload)
    assert dup_res.status_code == 400
    assert "already registered" in dup_res.json()["detail"].lower()

    # 5. Password Mismatch Rejection
    mismatch_payload = dict(payload)
    mismatch_payload["email"] = f"mismatch_{uuid.uuid4().hex[:8]}@example.com"
    mismatch_payload["confirm_password"] = "DifferentPassword123!"
    mismatch_res = client.post("/api/auth/register", json=mismatch_payload)
    assert mismatch_res.status_code == 400
    assert "passwords do not match" in mismatch_res.json()["detail"].lower()


def test_user_login_and_token_generation(test_db):
    """Test user login with valid/invalid credentials."""
    email = f"login_user_{uuid.uuid4().hex[:8]}@example.com"
    pwd = "ValidLoginPass123!"
    
    # Create user
    user = UserDB(
        id=f"usr_{uuid.uuid4().hex[:12]}",
        email=email,
        password_hash=hash_password(pwd),
        role="STUDENT",
        is_active=True,
    )
    test_db.add(user)
    test_db.commit()

    # 1. Valid Login
    login_res = client.post("/api/auth/login", json={"email": email, "password": pwd})
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "access_token" in login_data
    assert login_data["user"]["email"] == email

    # 2. Invalid Password
    bad_pwd_res = client.post("/api/auth/login", json={"email": email, "password": "WrongPassword"})
    assert bad_pwd_res.status_code == 401

    # 3. Non-existent User
    unknown_res = client.post("/api/auth/login", json={"email": "nobody@nowhere.com", "password": "AnyPassword123!"})
    assert unknown_res.status_code == 401


def test_unauthenticated_protected_endpoints():
    """Verify that student-protected APIs strictly return 401 when no token is provided."""
    # Profile
    res_prof = client.get("/api/student")
    assert res_prof.status_code == 401

    # Applications
    res_apps = client.get("/api/applications")
    assert res_apps.status_code == 401

    # Recommendations
    res_recs = client.get("/api/matching/recommendations")
    assert res_recs.status_code == 401


def test_role_based_admin_access_control(test_db):
    """Verify that students receive 403 Forbidden on admin routes and Admins receive 200 OK."""
    # 1. Create Student
    student_email = f"student_{uuid.uuid4().hex[:8]}@example.com"
    student_pwd = "StudentPassword123!"
    student_user = UserDB(
        id=f"usr_{uuid.uuid4().hex[:12]}",
        email=student_email,
        password_hash=hash_password(student_pwd),
        role="STUDENT",
        is_active=True,
    )
    test_db.add(student_user)

    # 2. Create Admin
    admin_email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
    admin_pwd = "AdminPassword123!"
    admin_user = UserDB(
        id=f"usr_{uuid.uuid4().hex[:12]}",
        email=admin_email,
        password_hash=hash_password(admin_pwd),
        role="ADMIN",
        is_active=True,
    )
    test_db.add(admin_user)
    test_db.commit()

    student_token = create_access_token({"sub": student_user.id, "email": student_email, "role": "STUDENT"})
    admin_token = create_access_token({"sub": admin_user.id, "email": admin_email, "role": "ADMIN"})

    student_headers = {"Authorization": f"Bearer {student_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Student accessing /api/admin/dashboard -> 403 Forbidden
    res_student_admin = client.get("/api/admin/dashboard", headers=student_headers)
    assert res_student_admin.status_code == 403

    # Admin accessing /api/admin/dashboard -> 200 OK with KPIs
    res_admin = client.get("/api/admin/dashboard", headers=admin_headers)
    assert res_admin.status_code == 200
    admin_data = res_admin.json()
    assert "kpis" in admin_data
    assert "total_opportunities" in admin_data["kpis"]
    assert "recent_opportunities" in admin_data


def test_student_data_isolation(test_db):
    """Verify Student 1 and Student 2 have complete data isolation for applications."""
    # Register Student 1
    s1_email = f"s1_{uuid.uuid4().hex[:8]}@example.com"
    r1 = client.post("/api/auth/register", json={
        "name": "Student One",
        "email": s1_email,
        "password": "Password123!",
        "confirm_password": "Password123!",
    })
    token1 = r1.json()["access_token"]
    h1 = {"Authorization": f"Bearer {token1}"}

    # Register Student 2
    s2_email = f"s2_{uuid.uuid4().hex[:8]}@example.com"
    r2 = client.post("/api/auth/register", json={
        "name": "Student Two",
        "email": s2_email,
        "password": "Password123!",
        "confirm_password": "Password123!",
    })
    token2 = r2.json()["access_token"]
    h2 = {"Authorization": f"Bearer {token2}"}

    # Student 1 logs an application
    create_res = client.post("/api/applications", headers=h1, json={
        "company": "Exclusive Company A",
        "role": "AI Research Scientist",
        "status": "Applied",
        "notes": "Student 1 private notes",
    })
    assert create_res.status_code == 200
    app_id = create_res.json()["id"]

    # Student 1 can see their application
    s1_apps = client.get("/api/applications", headers=h1).json()
    assert any(a["id"] == app_id for a in s1_apps)

    # Student 2 cannot see Student 1's application
    s2_apps = client.get("/api/applications", headers=h2).json()
    assert not any(a["id"] == app_id for a in s2_apps)

    # Student 2 cannot update Student 1's application
    update_res = client.patch(f"/api/applications/{app_id}", headers=h2, json={"status": "Offered"})
    assert update_res.status_code == 404


def test_source_privacy_student_vs_admin(test_db):
    """Verify students cannot see Telegram channels/post URLs while Admins have full transparency."""
    # Seed a test opportunity with sensitive Telegram scraping metadata
    opp_id = f"opp_tg_{uuid.uuid4().hex[:8]}"
    tg_opp = OpportunityDB(
        id=opp_id,
        title="Senior Machine Learning Intern",
        company="Neural Labs Inc",
        description="Build state-of-the-art NLP transformers.",
        opportunity_type="internship",
        skills='["Python", "PyTorch"]',
        location="Remote",
        remote=True,
        apply_url="https://neurallabs.ai/careers/apply/123",
        source="telegram",
        source_channel="TOP_SECRET_JOBS_CHANNEL",
        source_url="https://t.me/TOP_SECRET_JOBS_CHANNEL/9999",
        raw_text="CONFIDENTIAL TELEGRAM MESSAGE CONTENT SCRAPED HERE",
        status="active",
        verification_status="VERIFIED",
    )
    test_db.add(tg_opp)
    test_db.commit()

    # 1. Unauthenticated or Student Call
    student_email = f"student_privacy_{uuid.uuid4().hex[:8]}@example.com"
    r_stud = client.post("/api/auth/register", json={
        "name": "Privacy Student",
        "email": student_email,
        "password": "Password123!",
        "confirm_password": "Password123!",
    })
    s_token = r_stud.json()["access_token"]
    s_headers = {"Authorization": f"Bearer {s_token}"}

    res_student_opps = client.get("/api/opportunities", headers=s_headers)
    assert res_student_opps.status_code == 200
    student_opps_list = res_student_opps.json()

    target_for_student = next((o for o in student_opps_list if o.get("id") == opp_id), None)
    if target_for_student:
        # Crucial assertions: NO Telegram channel, NO Telegram post URL, NO raw text in student response
        assert "source_channel" not in target_for_student
        assert "source_url" not in target_for_student
        assert "raw_text" not in target_for_student
        assert target_for_student.get("apply_url") == "https://neurallabs.ai/careers/apply/123"

    # Check single opportunity retrieval for student
    res_single = client.get(f"/api/opportunities/{opp_id}", headers=s_headers)
    assert res_single.status_code == 200
    single_data = res_single.json()
    assert "source_channel" not in single_data
    assert "source_url" not in single_data
    assert "raw_text" not in single_data
    assert single_data["apply_url"] == "https://neurallabs.ai/careers/apply/123"

    # 2. Admin Call
    admin_email = f"admin_privacy_{uuid.uuid4().hex[:8]}@example.com"
    admin_user = UserDB(
        id=f"usr_{uuid.uuid4().hex[:12]}",
        email=admin_email,
        password_hash=hash_password("AdminPass123!"),
        role="ADMIN",
        is_active=True,
    )
    test_db.add(admin_user)
    test_db.commit()

    a_token = create_access_token({"sub": admin_user.id, "email": admin_email, "role": "ADMIN"})
    a_headers = {"Authorization": f"Bearer {a_token}"}

    # Admin call to /api/admin/opportunities
    res_admin_opps = client.get("/api/admin/opportunities", headers=a_headers)
    assert res_admin_opps.status_code == 200
    admin_opps_list = res_admin_opps.json()
    target_for_admin = next((o for o in admin_opps_list if o.get("id") == opp_id), None)
    assert target_for_admin is not None
    assert target_for_admin.get("source_channel") == "TOP_SECRET_JOBS_CHANNEL"
    assert target_for_admin.get("source_url") == "https://t.me/TOP_SECRET_JOBS_CHANNEL/9999"
    assert target_for_admin.get("raw_text") == "CONFIDENTIAL TELEGRAM MESSAGE CONTENT SCRAPED HERE"
