"""Pytest configuration and test authentication setup."""

import pytest
from fastapi.testclient import TestClient
from backend.api.app import app
from backend.database.db import SessionLocal, UserDB, StudentDB
from backend.utils.security import hash_password, create_access_token


@pytest.fixture(scope="session", autouse=True)
def setup_test_users():
    """Ensure default test student and test admin users exist in the SQLite database."""
    session = SessionLocal()
    try:
        # Default Student
        default_student_user = session.query(UserDB).filter(UserDB.id == "default_student").first()
        if not default_student_user:
            default_student_user = UserDB(
                id="default_student",
                email="default_student@example.com",
                password_hash=hash_password("DefaultStudentPass123!"),
                role="STUDENT",
                is_active=True,
            )
            session.add(default_student_user)

        # Ensure default student profile exists
        default_student_prof = session.query(StudentDB).filter(StudentDB.id == "default_student").first()
        if not default_student_prof:
            default_student_prof = StudentDB(
                id="default_student",
                user_id="default_student",
                name="Debasis Behera",
                email="default_student@example.com",
                skills='["Python", "PyTorch", "Machine Learning"]',
                preferred_roles='["AI Engineer Intern", "Machine Learning Intern"]',
                preferred_locations='["Remote", "Bengaluru"]',
                remote_preference=True,
            )
            session.add(default_student_prof)

        # Default Admin
        default_admin_user = session.query(UserDB).filter(UserDB.id == "default_admin").first()
        if not default_admin_user:
            default_admin_user = UserDB(
                id="default_admin",
                email="admin@careerhub.local",
                password_hash=hash_password("AdminSecurePassword123!"),
                role="ADMIN",
                is_active=True,
            )
            session.add(default_admin_user)

        session.commit()
    finally:
        session.close()


@pytest.fixture
def auth_student_token():
    """Generate a valid JWT token for default student."""
    return create_access_token({
        "sub": "default_student",
        "email": "default_student@example.com",
        "role": "STUDENT",
    })


@pytest.fixture
def auth_admin_token():
    """Generate a valid JWT token for default admin."""
    return create_access_token({
        "sub": "default_admin",
        "email": "admin@careerhub.local",
        "role": "ADMIN",
    })


@pytest.fixture
def auth_student_headers(auth_student_token):
    """Authorization header dictionary for default student."""
    return {"Authorization": f"Bearer {auth_student_token}"}


@pytest.fixture
def auth_admin_headers(auth_admin_token):
    """Authorization header dictionary for default admin."""
    return {"Authorization": f"Bearer {auth_admin_token}"}


@pytest.fixture
def authed_client(auth_student_headers):
    """FastAPI TestClient pre-configured with student authorization headers."""
    c = TestClient(app)
    c.headers.update(auth_student_headers)
    return c


@pytest.fixture
def admin_client(auth_admin_headers):
    """FastAPI TestClient pre-configured with admin authorization headers."""
    c = TestClient(app)
    c.headers.update(auth_admin_headers)
    return c
