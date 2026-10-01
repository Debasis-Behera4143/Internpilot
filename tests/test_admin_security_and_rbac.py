"""Comprehensive automated test suite verifying strict Backend RBAC, Route Protection, Admin APIs, and Security Invariants.

Tests requirements:
1. Unauthenticated user: GET /admin -> 401 Unauthorized or 302 Redirect to login
2. Normal user (STUDENT): GET /admin -> 403 Forbidden
3. Normal user manually calls: GET /api/admin/users -> 403 Forbidden
4. Unauthenticated API request: GET /api/admin/users -> 401 Unauthorized
5. Admin: GET /admin -> Admin Dashboard (200 OK)
6. Admin: GET /api/admin/users -> 200 OK with real DB user data (no secrets/hashes/tokens)
7. Admin: GET /api/admin/users/{user_id} -> 200 OK with detailed profile, applications, saved opps, activity
8. Admin: GET /api/admin/applications -> 200 OK with full platform student applications
9. Admin: GET /api/admin/analytics -> 200 OK with real database statistics
10. Attempt to manipulate role through payload or client-side claims -> Backend strictly rejects unauthorized access.
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from backend.api.app import app
from backend.database.db import SessionLocal, UserDB, StudentDB, ApplicationDB, OpportunityDB
from backend.utils.security import hash_password, create_access_token

client = TestClient(app)


@pytest.fixture
def test_db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def student_user(test_db):
    """Create a verified STUDENT user."""
    email = f"student_{uuid.uuid4().hex[:8]}@example.edu"
    pwd = "StudentPassword123!"
    user = UserDB(
        id=f"usr_std_{uuid.uuid4().hex[:8]}",
        email=email,
        password_hash=hash_password(pwd),
        role="STUDENT",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()

    student = StudentDB(
        id=user.id,
        user_id=user.id,
        name="Test Student",
        email=email,
        education="B.Tech Computer Science",
        branch="Computer Science",
        graduation_year=2026,
        skills='["Python", "FastAPI"]'
    )
    test_db.add(student)
    test_db.commit()

    token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
    return {"user": user, "student": student, "token": token, "email": email, "password": pwd}


@pytest.fixture
def admin_user(test_db):
    """Create a verified ADMIN user."""
    email = f"admin_{uuid.uuid4().hex[:8]}@platform.local"
    pwd = "AdminSecurePassword123!"
    user = UserDB(
        id=f"usr_adm_{uuid.uuid4().hex[:8]}",
        email=email,
        password_hash=hash_password(pwd),
        role="ADMIN",
        is_active=True
    )
    test_db.add(user)
    test_db.commit()

    token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
    return {"user": user, "token": token, "email": email, "password": pwd}


def test_1_unauthenticated_get_admin_page():
    """Test 1: Unauthenticated request to GET /admin rejects or redirects away."""
    # API/JSON client request without auth -> 401
    res_api = client.get("/admin", headers={"Accept": "application/json"})
    assert res_api.status_code == 401
    assert "authentication required" in res_api.json()["detail"].lower()

    # Browser request without auth -> 302 redirect to login
    res_browser = client.get("/admin", headers={"Accept": "text/html"}, follow_redirects=False)
    assert res_browser.status_code == 302
    assert "/?auth=login" in res_browser.headers["location"]


def test_2_normal_user_get_admin_page(student_user):
    """Test 2: Normal user (STUDENT) requesting /admin gets 403 Forbidden."""
    headers = {
        "Authorization": f"Bearer {student_user['token']}",
        "Accept": "application/json"
    }
    res = client.get("/admin", headers=headers)
    assert res.status_code == 403
    assert "forbidden" in res.json()["detail"].lower()


def test_3_normal_user_calls_api_admin_users(student_user):
    """Test 3: Normal user manually calling GET /api/admin/users receives 403 Forbidden."""
    headers = {"Authorization": f"Bearer {student_user['token']}"}
    res = client.get("/api/admin/users", headers=headers)
    assert res.status_code == 403
    assert "admin privileges required" in res.json()["detail"].lower()


def test_4_unauthenticated_api_request_to_admin_users():
    """Test 4: Unauthenticated API request to GET /api/admin/users receives 401 Unauthorized."""
    res = client.get("/api/admin/users")
    assert res.status_code == 401
    assert "authentication required" in res.json()["detail"].lower()


def test_5_admin_accesses_admin_page(admin_user):
    """Test 5: Authenticated ADMIN user GET /admin receives 200 OK (serves portal)."""
    headers = {
        "Authorization": f"Bearer {admin_user['token']}",
        "Accept": "text/html"
    }
    res = client.get("/admin", headers=headers)
    assert res.status_code == 200


def test_6_admin_calls_api_admin_users(admin_user):
    """Test 6: Authenticated ADMIN user GET /api/admin/users returns real data with zero sensitive secrets."""
    headers = {"Authorization": f"Bearer {admin_user['token']}"}
    res = client.get("/api/admin/users", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "users" in data
    assert len(data["users"]) > 0

    # Verify sensitive data is NOT leaked
    for u in data["users"]:
        assert "password" not in u
        assert "password_hash" not in u
        assert "token" not in u
        assert "jwt" not in u


def test_7_admin_user_details_endpoint(admin_user, student_user, test_db):
    """Test 7: Authenticated ADMIN gets comprehensive user details from real database relations."""
    headers = {"Authorization": f"Bearer {admin_user['token']}"}
    student_id = student_user["user"].id

    # Create a real application for student
    app_record = ApplicationDB(
        id=f"app_{uuid.uuid4().hex[:8]}",
        student_id=student_id,
        company="Stripe",
        role="Software Engineer Intern",
        status="Applied"
    )
    test_db.add(app_record)
    test_db.commit()

    res = client.get(f"/api/admin/users/{student_id}", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["user"]["email"] == student_user["email"]
    assert data["profile"]["name"] == "Test Student"
    assert len(data["applications"]) >= 1
    assert data["applications"][0]["company"] == "Stripe"


def test_8_admin_applications_and_analytics(admin_user):
    """Test 8: Authenticated ADMIN accesses platform applications and analytics."""
    headers = {"Authorization": f"Bearer {admin_user['token']}"}

    # Applications list
    res_apps = client.get("/api/admin/applications", headers=headers)
    assert res_apps.status_code == 200
    data_apps = res_apps.json()
    assert data_apps["status"] == "success"
    assert "applications" in data_apps

    # Analytics calculation
    res_analytics = client.get("/api/admin/analytics", headers=headers)
    assert res_analytics.status_code == 200
    data_analytics = res_analytics.json()
    assert data_analytics["status"] == "success"
    assert "users" in data_analytics["analytics"]
    assert "applications" in data_analytics["analytics"]
    assert "opportunities" in data_analytics["analytics"]


def test_9_tampering_role_cannot_bypass_backend(student_user):
    """Test 9: Manipulating role in request headers/body or client state cannot bypass backend RBAC."""
    # Attempt to spoof role header or claim admin privileges
    headers = {
        "Authorization": f"Bearer {student_user['token']}",
        "X-User-Role": "ADMIN",
        "Role": "ADMIN"
    }

    # Attempt to access admin routes with spoofed headers
    res1 = client.get("/api/admin/users", headers=headers)
    assert res1.status_code == 403

    res2 = client.get("/api/admin/applications", headers=headers)
    assert res2.status_code == 403

    res3 = client.get("/api/admin/dashboard", headers=headers)
    assert res3.status_code == 403
