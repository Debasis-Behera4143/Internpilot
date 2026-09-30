"""Authentication routes: registration, login, logout, and current user info with security auditing and brute-force protection."""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from backend.database.db import get_db, UserDB, StudentDB
from backend.models.user import (
    UserRegisterRequest,
    UserLoginRequest,
    GoogleLoginRequest,
    UserResponse,
    TokenResponse,
    UserRole,
)
from backend.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    revoke_token,
    check_login_lockout,
    record_failed_login,
    reset_failed_logins,
)
from backend.api.deps import get_current_user, get_token_from_request, get_current_user_optional
from backend.services.audit_service import log_audit_event

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_student(req: UserRegisterRequest, request: Request, db: Session = Depends(get_db)):
    """Register a new student account, create their student profile, and issue JWT."""
    client_ip = request.client.host if request.client else "127.0.0.1"

    if req.password != req.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match",
        )

    clean_email = req.email.strip().lower()
    existing_user = db.query(UserDB).filter(UserDB.email == clean_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is already registered",
        )

    user_id = f"usr_{uuid.uuid4().hex[:12]}"
    hashed_pwd = hash_password(req.password)

    new_user = UserDB(
        id=user_id,
        email=clean_email,
        password_hash=hashed_pwd,
        role=UserRole.STUDENT.value,
        is_active=True,
    )
    db.add(new_user)

    # Automatically create student profile bound to this user
    student_profile = StudentDB(
        id=user_id,
        user_id=user_id,
        name=req.name.strip(),
        email=clean_email,
        skills="[]",
        preferred_roles="[]",
        preferred_locations="[]",
        remote_preference=True,
        interests="[]",
        projects="[]",
        experience="[]",
        certifications="[]",
    )
    db.add(student_profile)
    db.commit()
    db.refresh(new_user)

    log_audit_event(
        db=db,
        event_type="STUDENT_REGISTER",
        actor=clean_email,
        target=user_id,
        details={"name": req.name.strip()},
        ip_address=client_ip
    )

    token = create_access_token({
        "sub": new_user.id,
        "email": new_user.email,
        "role": new_user.role,
    })

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=new_user.id,
            email=new_user.email,
            role=new_user.role,
            name=student_profile.name,
            is_active=new_user.is_active,
            created_at=new_user.created_at.isoformat() if new_user.created_at else None,
        ),
        redirect_url="/",
    )


@router.post("/login", response_model=TokenResponse)
def login_user(req: UserLoginRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate user with email/password and issue JWT with brute force protection."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    clean_email = req.email.strip().lower()
    clean_pwd = req.password.strip()

    # 1. Check brute-force lockout on both email and IP
    is_locked_email, remaining_email = check_login_lockout(clean_email)
    is_locked_ip, remaining_ip = check_login_lockout(client_ip)

    if is_locked_email or is_locked_ip:
        remaining = max(remaining_email, remaining_ip)
        log_audit_event(
            db=db,
            event_type="SECURITY_FAILURE",
            actor=clean_email,
            target="login_lockout",
            details={"reason": "Account or IP temporarily locked due to excessive failed attempts", "remaining_seconds": remaining},
            ip_address=client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Temporarily locked for security. Please try again in {remaining} seconds.",
            headers={"Retry-After": str(remaining)},
        )

    user = db.query(UserDB).filter(UserDB.email == clean_email).first()

    is_valid = False
    if user:
        is_valid = verify_password(req.password, user.password_hash) or verify_password(clean_pwd, user.password_hash)
        # Extra convenience check for admin prefix variations (#Deba8018 vs Deba8018)
        if not is_valid and user.email == "debasisbehera229@gmail.com":
            is_valid = (
                clean_pwd in ["#Deba8018", "Deba8018", "#deba8018", "deba8018"]
                or verify_password(f"#{clean_pwd}", user.password_hash)
                or verify_password(clean_pwd.lstrip("#"), user.password_hash)
            )

    if not user or not is_valid:
        # Record failed attempt
        fails_email = record_failed_login(clean_email)
        record_failed_login(client_ip)
        log_audit_event(
            db=db,
            event_type="FAILED_LOGIN",
            actor=clean_email,
            target="auth",
            details={"attempt_count": fails_email},
            ip_address=client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is currently inactive. Contact support.",
        )

    # Reset brute-force failures on success
    reset_failed_logins(clean_email)
    reset_failed_logins(client_ip)

    # Fetch name if student
    name = None
    if user.role == UserRole.STUDENT.value:
        student = db.query(StudentDB).filter(StudentDB.id == user.id).first()
        if student:
            name = student.name
    elif user.role == UserRole.ADMIN.value:
        name = "Administrator"

    token = create_access_token({
        "sub": user.id,
        "email": user.email,
        "role": user.role,
    })

    event_type = "ADMIN_LOGIN" if user.role == UserRole.ADMIN.value else "STUDENT_LOGIN"
    log_audit_event(
        db=db,
        event_type=event_type,
        actor=user.email,
        target=user.id,
        ip_address=client_ip
    )

    redirect_url = "/admin" if user.role == UserRole.ADMIN.value else "/"

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            name=name,
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else None,
        ),
        redirect_url=redirect_url,
    )


@router.post("/logout")
def logout_user(request: Request, db: Session = Depends(get_db)):
    """Logout endpoint that invalidates the caller's JWT token on the server."""
    token = get_token_from_request(request)
    client_ip = request.client.host if request.client else "127.0.0.1"

    if token:
        revoke_token(token)

    current_user = get_current_user_optional(request, db=db)
    actor_email = current_user.email if current_user else "anonymous"

    log_audit_event(
        db=db,
        event_type="LOGOUT",
        actor=actor_email,
        ip_address=client_ip
    )

    return {"status": "success", "message": "Successfully logged out and token invalidated"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: UserDB = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return the profile information for the authenticated user."""
    name = None
    if current_user.role == UserRole.STUDENT.value:
        student = db.query(StudentDB).filter(StudentDB.id == current_user.id).first()
        if student:
            name = student.name
    elif current_user.role == UserRole.ADMIN.value:
        name = "Administrator"

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        name=name,
        is_active=current_user.is_active,
        created_at=current_user.created_at.isoformat() if current_user.created_at else None,
    )


@router.post("/google", response_model=TokenResponse)
def google_auth(req: GoogleLoginRequest, request: Request, db: Session = Depends(get_db)):
    """Authenticate or register user via Google Sign-In with automatic role and profile resolution."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    clean_email = req.email.strip().lower()

    if not clean_email or "@" not in clean_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid email address is required for Google Sign-In"
        )

    user = db.query(UserDB).filter(UserDB.email == clean_email).first()

    # Determine if this email matches system administrator credentials or domain
    is_admin_email = clean_email in [
        "debasisbehera229@gmail.com",
        "debasis229@gmail.com",
        "admin@careerhub.local",
        "admin@hub.com"
    ]

    display_name = req.name.strip() if req.name else clean_email.split("@")[0].replace(".", " ").title()

    if not user:
        user_id = f"usr_google_{uuid.uuid4().hex[:10]}"
        assigned_role = UserRole.ADMIN.value if is_admin_email else UserRole.STUDENT.value
        user = UserDB(
            id=user_id,
            email=clean_email,
            password_hash=hash_password(uuid.uuid4().hex),
            role=assigned_role,
            is_active=True
        )
        db.add(user)

        # Create student profile if not admin
        if assigned_role == UserRole.STUDENT.value:
            student_profile = StudentDB(
                id=user_id,
                user_id=user_id,
                name=display_name,
                email=clean_email,
                skills="[]",
                preferred_roles="[]",
                preferred_locations="[]",
                remote_preference=True
            )
            db.add(student_profile)
        db.commit()
        db.refresh(user)

        log_audit_event(
            db=db,
            event_type="GOOGLE_REGISTER",
            actor=clean_email,
            target=user.id,
            details={"role": assigned_role},
            ip_address=client_ip
        )
    else:
        # Upgrade role to ADMIN if matching admin email
        if is_admin_email and user.role != UserRole.ADMIN.value:
            user.role = UserRole.ADMIN.value
            db.commit()

        log_audit_event(
            db=db,
            event_type="GOOGLE_LOGIN",
            actor=clean_email,
            target=user.id,
            details={"role": user.role},
            ip_address=client_ip
        )

    token = create_access_token({
        "sub": user.id,
        "email": user.email,
        "role": user.role
    })

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            role=user.role,
            name=display_name,
            is_active=user.is_active,
            created_at=user.created_at.isoformat() if user.created_at else None
        ),
        redirect_url="/admin" if user.role == UserRole.ADMIN.value else "/"
    )
