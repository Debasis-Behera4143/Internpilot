"""Authentication and authorization dependency middleware."""

from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.database.db import get_db, UserDB
from backend.utils.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_token_from_request(request: Request, bearer_token: Optional[str] = None) -> Optional[str]:
    """Extract token from Authorization header or cookie."""
    if bearer_token and isinstance(bearer_token, str):
        return bearer_token.strip()
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        if isinstance(cookie_token, str) and cookie_token.startswith("Bearer "):
            return cookie_token[7:].strip()
        return cookie_token
    return None


def get_current_user_optional(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[UserDB]:
    """Safely return current authenticated user or None if unauthenticated."""
    extracted_token = get_token_from_request(request, token)
    if not extracted_token:
        return None
    
    payload = decode_access_token(extracted_token)
    if not payload:
        return None
    
    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        return None
    
    user = db.query(UserDB).filter(UserDB.id == user_id, UserDB.is_active == True).first()
    return user


def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> UserDB:
    """Validate token and return active UserDB entity, raising 401 on failure."""
    user = get_current_user_optional(request, token, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_student(
    current_user: UserDB = Depends(get_current_user),
) -> UserDB:
    """Ensure current user is authenticated as a student (or admin with student context)."""
    if current_user.role not in ["STUDENT", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student account required",
        )
    return current_user


def require_admin(
    current_user: UserDB = Depends(get_current_user),
) -> UserDB:
    """Ensure current user has administrative privileges."""
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
