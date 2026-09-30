"""Security utility module: password hashing with bcrypt, JWT token handling, token revocation blacklist, and login brute-force protection."""

import os
import time
import hashlib
import datetime
from datetime import timezone, timedelta
from typing import Optional, Dict, Any, Tuple, List, Set
import bcrypt
import jwt

from backend.utils.logger import get_logger

logger = get_logger("security")

# Configuration with safe fallback for local development
JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "internpilot-local-secure-jwt-secret-key-32bytes-min!")
JWT_ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours

# In-memory token blacklist cache for sub-millisecond check
_token_blacklist_cache: Set[str] = set()

# Brute force login tracking: key (ip or email) -> list of failure timestamps
_failed_login_attempts: Dict[str, List[float]] = {}
MAX_FAILED_LOGINS: int = 5
LOCKOUT_WINDOW_SECONDS: int = 300  # 5 minutes


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt with automatic salt generation."""
    if not password:
        raise ValueError("Password cannot be empty")
    # Truncate password to 72 bytes as per bcrypt specification
    pw_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pw_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        pw_bytes = plain_password.encode("utf-8")[:72]
        hash_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pw_bytes, hash_bytes)
    except Exception:
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generate a signed JWT access token containing arbitrary payload claims."""
    to_encode = data.copy()
    now = datetime.datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT access token. Returns decoded payload or None if invalid/expired/revoked."""
    if not token or is_token_revoked(token):
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception:
        return None


def _compute_token_hash(token: str) -> str:
    """Compute sha256 hash of token to prevent storing raw tokens in database."""
    if not token or not isinstance(token, str):
        return ""
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def revoke_token(token: str) -> bool:
    """Revoke a JWT token by adding its SHA-256 hash to the blacklist."""
    if not token:
        return False
    t_hash = _compute_token_hash(token)
    _token_blacklist_cache.add(t_hash)

    # Persist in DB
    try:
        from backend.database.db import SessionLocal, TokenBlacklistDB
        session = SessionLocal()
        try:
            existing = session.query(TokenBlacklistDB).filter_by(token_hash=t_hash).first()
            if not existing:
                rev_entry = TokenBlacklistDB(
                    id=f"rev_{t_hash[:16]}",
                    token_hash=t_hash,
                    revoked_at=datetime.datetime.now(timezone.utc)
                )
                session.add(rev_entry)
                session.commit()
            return True
        except Exception as e:
            logger.warning(f"Error persisting revoked token hash: {e}")
            try:
                session.rollback()
            except Exception:
                pass
            return True
        finally:
            session.close()
    except Exception as e:
        logger.warning(f"Error importing DB in revoke_token: {e}")
        return True


def is_token_revoked(token: str) -> bool:
    """Check whether a token has been revoked / logged out."""
    if not token:
        return True
    t_hash = _compute_token_hash(token)
    if t_hash in _token_blacklist_cache:
        return True

    # Check database
    try:
        from backend.database.db import SessionLocal, TokenBlacklistDB
        session = SessionLocal()
        try:
            rev = session.query(TokenBlacklistDB).filter_by(token_hash=t_hash).first()
            if rev:
                _token_blacklist_cache.add(t_hash)
                return True
            return False
        except Exception:
            return False
        finally:
            session.close()
    except Exception:
        return False


# =========================================================================
# LOGIN BRUTE FORCE PROTECTION
# =========================================================================

def check_login_lockout(key: str) -> Tuple[bool, int]:
    """Check if account or IP is temporarily locked due to repeated failed logins.
    
    Returns: (is_locked: bool, remaining_lockout_seconds: int)
    """
    clean_key = (key or "").strip().lower()
    now = time.time()
    attempts = _failed_login_attempts.get(clean_key, [])

    # Keep only attempts within the sliding lockout window
    recent_attempts = [t for t in attempts if (now - t) < LOCKOUT_WINDOW_SECONDS]
    _failed_login_attempts[clean_key] = recent_attempts

    if len(recent_attempts) >= MAX_FAILED_LOGINS:
        oldest_in_window = min(recent_attempts)
        remaining = int(LOCKOUT_WINDOW_SECONDS - (now - oldest_in_window))
        return True, max(1, remaining)

    return False, 0


def record_failed_login(key: str) -> int:
    """Record a failed login attempt and return count within the window."""
    clean_key = (key or "").strip().lower()
    now = time.time()
    attempts = _failed_login_attempts.get(clean_key, [])
    attempts.append(now)
    # Prune old
    recent_attempts = [t for t in attempts if (now - t) < LOCKOUT_WINDOW_SECONDS]
    _failed_login_attempts[clean_key] = recent_attempts
    return len(recent_attempts)


def reset_failed_logins(key: str) -> None:
    """Reset failed login attempts upon successful login."""
    clean_key = (key or "").strip().lower()
    _failed_login_attempts.pop(clean_key, None)
