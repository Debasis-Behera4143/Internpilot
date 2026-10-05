"""User data models and authentication request/response schemas."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class UserRole(str, Enum):
    """Supported system user roles."""
    STUDENT = "STUDENT"
    ADMIN = "ADMIN"


class UserRegisterRequest(BaseModel):
    """Schema for student self-registration."""
    name: str = Field(..., min_length=2, max_length=128, description="Student's full name")
    email: str = Field(..., min_length=3, max_length=255, description="Valid student email address")
    password: str = Field(..., min_length=6, max_length=128, description="Account password (min 6 characters)")
    confirm_password: str = Field(..., min_length=6, max_length=128, description="Password confirmation")


class UserLoginRequest(BaseModel):
    """Schema for user credentials login."""
    email: str = Field(..., min_length=3, max_length=255, description="Registered email address")
    password: str = Field(..., min_length=1, description="Account password")


class GoogleLoginRequest(BaseModel):
    """Schema for Google OAuth / Sign-in verification."""
    credential: Optional[str] = Field(default=None, description="Google ID Token / OIDC credential JWT from Google One Tap or Sign-In button")
    email: Optional[str] = Field(default=None, min_length=3, max_length=255, description="Google email address")
    name: Optional[str] = Field(default=None, description="User's display name from Google")


class ForgotPasswordRequest(BaseModel):
    """Schema for password recovery request."""
    email: str = Field(..., min_length=3, max_length=255, description="Registered account email address")


class UserResponse(BaseModel):
    """Public user profile response (password hash strictly omitted)."""
    id: str
    email: str
    role: str
    name: Optional[str] = None
    is_active: bool = True
    auth_provider: str = "local"
    is_onboarded: bool = False
    created_at: Optional[str] = None


class TokenResponse(BaseModel):
    """JWT Token response returned upon successful authentication."""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    is_new_user: bool = False
    redirect_url: str = "/"
