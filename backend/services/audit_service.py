"""Audit Logging Service for recording security events, authentication, source lifecycle, and verification actions."""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database.db import SessionLocal, AuditLogDB
from backend.utils.logger import get_logger

logger = get_logger("audit_service")

# Keys that MUST be redacted from audit logs to ensure strict privacy and credential safety
REDACTED_KEYS = {
    "password", "password_hash", "confirm_password", "token", "access_token",
    "secret", "api_key", "authorization", "resume_content", "raw_text", "cookie"
}


def _sanitize_details(details: Any) -> str:
    """Sanitize detail dictionary, redacting sensitive keys and ensuring valid string output."""
    if not details:
        return ""
    if isinstance(details, str):
        # Prevent logging obvious token or password strings
        lower_str = details.lower()
        if any(f"{rk}=" in lower_str or f'"{rk}"' in lower_str for rk in REDACTED_KEYS):
            return "[REDACTED_SENSITIVE_DATA]"
        return details

    if isinstance(details, dict):
        sanitized = {}
        for k, v in details.items():
            if str(k).lower() in REDACTED_KEYS:
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, dict):
                sanitized[k] = json.loads(_sanitize_details(v))
            else:
                sanitized[k] = v
        try:
            return json.dumps(sanitized)
        except Exception:
            return str(sanitized)

    return str(details)


def log_audit_event(
    db: Optional[Session],
    event_type: str,
    actor: str,
    target: Optional[str] = None,
    details: Optional[Any] = None,
    ip_address: Optional[str] = None
) -> Optional[AuditLogDB]:
    """Record an auditable action into AuditLogDB and application log.
    
    Safe against DB session failure; never raises exceptions to the caller.
    """
    clean_details = _sanitize_details(details)
    log_id = f"aud_{uuid.uuid4().hex[:12]}"

    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        entry = AuditLogDB(
            id=log_id,
            event_type=event_type,
            actor=actor or "SYSTEM",
            target=target,
            details=clean_details,
            ip_address=ip_address,
            created_at=datetime.now(timezone.utc)
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        logger.info(f"[AUDIT] {event_type} | Actor: {actor} | Target: {target} | IP: {ip_address}")
        return entry
    except Exception as e:
        logger.warning(f"Failed to record audit event ({event_type}): {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return None
    finally:
        if close_session:
            db.close()


def get_audit_logs(
    db: Session,
    limit: int = 50,
    offset: int = 0,
    event_type: Optional[str] = None
) -> Dict[str, Any]:
    """Retrieve paginated audit logs for the admin security and audit viewer."""
    query = db.query(AuditLogDB)
    if event_type:
        query = query.filter(AuditLogDB.event_type == event_type.upper())

    total = query.count()
    items = query.order_by(desc(AuditLogDB.created_at)).offset(offset).limit(limit).all()

    rows = []
    for item in items:
        rows.append({
            "id": item.id,
            "event_type": item.event_type,
            "actor": item.actor,
            "target": item.target,
            "details": item.details,
            "ip_address": item.ip_address,
            "created_at": item.created_at.isoformat() if item.created_at else None
        })

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "logs": rows
    }
