"""Admin routes for platform management, live database KPIs, and source oversight."""

from typing import List, Optional, Dict, Any, Union
from pathlib import Path
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database.db import get_db, OpportunityDB, UserDB, StudentDB, SourceRegistryDB
from backend.models.opportunity import Opportunity
from backend.api.deps import require_admin

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/dashboard")
def get_admin_dashboard(admin_user: UserDB = Depends(require_admin), db: Session = Depends(get_db)):
    """Retrieve simplified admin dashboard metrics and recent opportunity activity."""
    active_sources = db.query(SourceRegistryDB).filter_by(status="ACTIVE").count()
    total_jobs = db.query(OpportunityDB).count()
    verified_jobs = db.query(OpportunityDB).filter_by(verification_status="VERIFIED").count()
    pending_review = db.query(OpportunityDB).filter_by(verification_status="PENDING_REVIEW").count()
    rejected = db.query(OpportunityDB).filter_by(verification_status="REJECTED").count()
    expired = db.query(OpportunityDB).filter(
        (OpportunityDB.status.in_(["expired", "closed"])) |
        ((OpportunityDB.deadline.isnot(None)) & (OpportunityDB.deadline != "") & (OpportunityDB.deadline < date.today().isoformat()))
    ).count()

    # Fetch recent 20 opportunities with full source and verification status
    recent_db_opps = (
        db.query(OpportunityDB)
        .order_by(OpportunityDB.created_at.desc())
        .limit(20)
        .all()
    )

    recent_opportunities = []
    for opp in recent_db_opps:
        recent_opportunities.append({
            "id": opp.id,
            "title": opp.title,
            "company": opp.company,
            "opportunity_type": opp.opportunity_type,
            "source": opp.source,
            "source_channel": opp.source_channel,
            "source_url": opp.source_url,
            "apply_url": opp.apply_url,
            "application_url": opp.application_url or opp.apply_url,
            "status": opp.status,
            "verification_status": opp.verification_status,
            "collected_date": opp.collected_date,
            "created_at": opp.created_at.isoformat() if opp.created_at else None,
        })

    metrics = {
        "active_sources": active_sources,
        "total_jobs": total_jobs,
        "verified_jobs": verified_jobs,
        "pending_review": pending_review,
        "rejected": rejected,
        "expired": expired,
    }

    return {
        "status": "success",
        "metrics": metrics,
        "kpis": {
            **metrics,
            "total_opportunities": total_jobs,
            "active_opportunities": verified_jobs,
            "expired_opportunities": expired,
        },
        "recent_opportunities": recent_opportunities,
    }


@router.get("/opportunities", response_model=List[Opportunity])
def get_admin_opportunities(
    limit: int = 100,
    offset: int = 0,
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db),
):
    opps = (
        db.query(OpportunityDB)
        .order_by(func.coalesce(OpportunityDB.created_at, func.datetime("now")).desc(), OpportunityDB.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    result = []
    for opp in opps:
        import json
        skills = []
        if opp.skills:
            try:
                skills = json.loads(opp.skills) if isinstance(opp.skills, str) else opp.skills
            except Exception:
                skills = [opp.skills]
        
        result.append(Opportunity(
            id=opp.id,
            title=opp.title,
            company=opp.company,
            description=opp.description or "",
            opportunity_type=opp.opportunity_type or "internship",
            skills=skills,
            location=opp.location or "Remote",
            remote=opp.remote if opp.remote is not None else True,
            stipend=opp.stipend,
            salary=opp.salary,
            experience=opp.experience or "Fresher / Student",
            eligibility=opp.eligibility or "All students",
            deadline=opp.deadline,
            source=opp.source or "direct",
            source_channel=opp.source_channel,
            source_url=opp.source_url or "",
            apply_url=opp.apply_url,
            posted_date=opp.posted_date,
            collected_date=opp.collected_date or "",
            status=opp.status or "open",
            raw_text=opp.raw_text,
            verification_status=opp.verification_status or "UNVERIFIED",
            verification_method=opp.verification_method,
            verified_at=opp.verified_at,
            verified_by=opp.verified_by,
            verification_notes=opp.verification_notes,
            trust_level=opp.trust_level or "UNVERIFIED_EXTERNAL",
            source_id=opp.source_id,
        ))
    return result


# ==========================================
# SOURCE REGISTRY & TELEGRAM CHANNEL MANAGER
# ==========================================

from backend.models.source import (
    SourceModel,
    SourceCreateRequest,
    SourceUpdateRequest,
    TelegramChannelCreateRequest,
    ImportConfirmRequest,
    ImportPreviewResponse,
    ImportPreviewItem,
    LinkedInStatusResponse,
)
from backend.services import source_service, verification_service
from backend.services.ingestion_service import run_ingestion_pipeline
from backend.collectors.telegram_collector import TelegramCollector
from backend.collectors.ats_adapter import ATSAdapter
from backend.collectors.company_careers_adapter import CompanyCareersAdapter
from pydantic import BaseModel, Field


class VerifyActionRequest(BaseModel):
    notes: Optional[str] = Field(default=None, description="Admin verification audit notes")
    method: Optional[str] = Field(default="ADMIN_MANUAL_REVIEW", description="Verification method code")


class ValidateSourceReq(BaseModel):
    name: str
    type: str
    configuration: Optional[dict] = None


@router.post("/sources/validate")
def validate_admin_source(
    req: ValidateSourceReq,
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Validate source specification before adding (Validate -> Preview -> Confirm Add)."""
    return source_service.validate_source_specification(
        db=db,
        source_type=req.type,
        name=req.name,
        configuration=req.configuration
    )


@router.get("/quality-dashboard")
def get_system_quality_dashboard(
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Retrieve full system quality metrics, validation tallies, and source health breakdown."""
    total_opps = db.query(OpportunityDB).count()
    active_opps = db.query(OpportunityDB).filter(OpportunityDB.status.in_(["open", "active"])).count()
    expired_opps = db.query(OpportunityDB).filter(OpportunityDB.status.in_(["expired", "closed"])).count()
    verified_opps = db.query(OpportunityDB).filter(OpportunityDB.verification_status == "VERIFIED").count()
    pending_opps = db.query(OpportunityDB).filter(OpportunityDB.verification_status == "PENDING_REVIEW").count()
    unverified_opps = db.query(OpportunityDB).filter(OpportunityDB.verification_status == "UNVERIFIED").count()
    rejected_opps = db.query(OpportunityDB).filter(OpportunityDB.verification_status == "REJECTED").count()

    sources = source_service.list_sources(db=db)
    source_health_rows = []
    failed_sources_count = 0
    last_successful_ingestion = None

    for s in sources:
        if s.last_error:
            failed_sources_count += 1
        if s.last_success_at:
            if not last_successful_ingestion or s.last_success_at > last_successful_ingestion:
                last_successful_ingestion = s.last_success_at

        source_health_rows.append({
            "id": s.id,
            "name": s.name,
            "type": s.type.value if hasattr(s.type, "value") else str(s.type),
            "status": s.status.value if hasattr(s.status, "value") else str(s.status),
            "last_run": s.last_ingested_at,
            "items_count": s.items_count or 0,
            "trust_level": s.trust_level.value if hasattr(s.trust_level, "value") else str(s.trust_level),
            "error": s.last_error
        })

    return {
        "status": "success",
        "quality_metrics": {
            "total_opportunities": total_opps,
            "published": active_opps,
            "pending_review": pending_opps,
            "rejected": rejected_opps,
            "expired": expired_opps,
            "verified": verified_opps,
            "unverified": unverified_opps,
            "failed_sources": failed_sources_count,
            "last_successful_ingestion": last_successful_ingestion
        },
        "sources_health": source_health_rows
    }


@router.get("/sources")
def list_admin_sources(
    source_type: Optional[str] = None,
    status: Optional[str] = None,
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all registered data sources and Telegram channels with their health metrics."""
    sources = source_service.list_sources(db=db, source_type=source_type, status=status)
    return {"status": "success", "count": len(sources), "sources": [s.to_dict() for s in sources]}


@router.post("/sources")
def create_admin_source(
    req: SourceCreateRequest,
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Register a new opportunity source with duplicate prevention (idempotent upsert)."""
    try:
        created = source_service.create_source(db=db, data=req)
        return {"status": "success", "message": f"Source '{created.name}' registered successfully.", "source": created.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sources/telegram/add")
def add_telegram_channel_source(
    req: TelegramChannelCreateRequest,
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Add or update a public Telegram channel source for dynamic ingestion."""
    try:
        created = source_service.add_telegram_channel(db=db, req=req)
        return {
            "status": "success",
            "message": f"Telegram channel @{created.configuration.get('channel_username', req.channel_username)} added successfully.",
            "source": created.to_dict()
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))



@router.put("/sources/{source_id}")
def update_admin_source(
    source_id: str,
    req: SourceUpdateRequest,
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update source properties, status, or configuration."""
    updated = source_service.update_source(db=db, source_id=source_id, data=req)
    if not updated:
        return {"status": "error", "message": f"Source {source_id} not found."}
    return {"status": "success", "message": "Source updated.", "source": updated.to_dict()}


@router.post("/sources/{source_id}/toggle")
def toggle_admin_source(
    source_id: str,
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Toggle source status between ACTIVE and PAUSED."""
    updated = source_service.toggle_source_status(db=db, source_id=source_id)
    if not updated:
        return {"status": "error", "message": f"Source {source_id} not found."}
    return {
        "status": "success",
        "message": f"Source status changed to {updated.status.value}.",
        "source": updated.to_dict()
    }


@router.delete("/sources/{source_id}")
def delete_admin_source(
    source_id: str,
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Delete a registered source."""
    success = source_service.delete_source(db=db, source_id=source_id)
    if not success:
        return {"status": "error", "message": f"Source {source_id} not found."}
    return {"status": "success", "message": f"Source {source_id} deleted successfully."}


@router.post("/sources/{source_id}/ingest")
def trigger_single_source_ingestion(
    source_id: str,
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Trigger ingestion specifically for a single registered source."""
    try:
        report = source_service.ingest_source(db=db, source_id=source_id)
        return {
            "status": "success",
            "message": f"Ingestion completed for source {source_id}. Added {report.get('new_added', 0)} new opportunities.",
            "report": report
        }
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": f"Ingestion failed: {str(e)}"}


@router.post("/sources/telegram/ingest")
def trigger_telegram_ingestion(
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Trigger ingestion specifically across all ACTIVE dynamic Telegram channels."""
    col = TelegramCollector()
    report = run_ingestion_pipeline(collectors=[col])
    return {
        "status": "success",
        "message": f"Telegram ingestion completed across {len(col.channels)} dynamic channels.",
        "report": report
    }


@router.post("/sources/ingest-all")
@router.post("/ingest")
def trigger_all_sources_ingestion(
    admin_user: UserDB = Depends(require_admin)
):
    """Trigger unified multi-source ingestion pipeline across all configured collectors."""
    report = run_ingestion_pipeline()
    return {
        "status": "success",
        "message": f"Multi-source ingestion completed. Added {report.get('new_added', 0)} new opportunities.",
        "report": report
    }


# ==========================================
# LINKEDIN AUTHORIZED INTEGRATION & IMPORT
# ==========================================

class LinkedInImportPayload(BaseModel):
    csv_content: Optional[str] = None
    json_content: Optional[Union[str, List[Dict[str, Any]]]] = None
    file_path: Optional[str] = None


@router.get("/linkedin/status")
def get_linkedin_status(
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Retrieve LinkedIn source connection status, credentials check, and import statistics."""
    from backend.collectors.linkedin_collector import LinkedInCollector
    col = LinkedInCollector()
    conn_info = col.get_connection_status()

    # Query LinkedIn source in registry if present
    src = db.query(SourceRegistryDB).filter_by(id="src_linkedin_authorized_default").first()
    if not src:
        src = db.query(SourceRegistryDB).filter(SourceRegistryDB.type == "LINKEDIN_AUTHORIZED").first()

    return {
        "status": "success",
        "connection_status": conn_info["connection_status"],
        "api_available": conn_info["api_available"],
        "message": conn_info["message"],
        "notice": conn_info.get("notice", "LinkedIn authorization/import required"),
        "export_file_present": conn_info["export_file_present"],
        "last_import": src.last_ingested_at if src else None,
        "imported_jobs": src.items_count if src else 0,
        "accepted": src.items_accepted if src else 0,
        "rejected": src.items_rejected if src else 0,
        "duplicates": 0,
        "source": src.id if src else None
    }


@router.post("/linkedin/import")
def import_linkedin_opportunities(
    payload: LinkedInImportPayload,
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Import opportunities from authorized LinkedIn CSV or JSON export."""
    from backend.collectors.linkedin_collector import LinkedInCollector
    col = LinkedInCollector()

    opps: List[Opportunity] = []
    rejections: List[str] = []

    if payload.csv_content:
        opps, rejections = col.parse_csv_content(payload.csv_content, source_label="LinkedIn Admin CSV Import")
    elif payload.json_content:
        opps, rejections = col.parse_json_content(payload.json_content, source_label="LinkedIn Admin JSON Import")
    elif payload.file_path:
        p = Path(payload.file_path)
        if not p.exists():
            raise HTTPException(status_code=400, detail=f"File not found: {payload.file_path}")
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if p.suffix.lower() == ".csv":
            opps, rejections = col.parse_csv_content(content, source_label=f"LinkedIn Export ({p.name})")
        else:
            opps, rejections = col.parse_json_content(content, source_label=f"LinkedIn Export ({p.name})")
    else:
        # Default scan from settings.DATA_DIR
        opps = col.collect()
        rejections = col.last_run_stats.get("reasons", [])

    # Now run ingestion pipeline / confirm import through verification engine
    raw_dicts = [o.to_dict() for o in opps]
    result = source_service.confirm_and_ingest_import(
        db=db,
        records=raw_dicts,
        source_name="LinkedIn Authorized Integration",
        source_type="LINKEDIN_AUTHORIZED",
        admin_user=admin_user.email
    )
    result["total_processed"] = (result.get("total_records") or len(raw_dicts)) + len(rejections)
    result["rejected"] = result.get("rejected", 0) + len(rejections)
    existing_samples = result.get("sample_rejected") or []
    result["sample_rejected"] = existing_samples + [{"title": r.split(":")[0], "reason": r} for r in rejections]
    result["initial_validation_rejections"] = rejections[:20]
    return result


# ==========================================
# IMPORT OPPORTUNITIES WORKFLOW (PREVIEW & CONFIRM)
# ==========================================

class ImportPreviewPayload(BaseModel):
    source_name: Optional[str] = "Authorized Import"
    source_type: Optional[str] = "CSV"
    csv_content: Optional[str] = None
    json_content: Optional[Union[str, List[Dict[str, Any]]]] = None
    content: Optional[Union[str, List[Dict[str, Any]], Dict[str, Any]]] = None
    file_path: Optional[str] = None


@router.post("/import/preview")
def preview_opportunities_import(
    payload: ImportPreviewPayload,
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Validate, preview, detect duplicates, and classify jobs before importing."""
    import json
    records: List[Dict[str, Any]] = []

    target_content = payload.content if payload.content is not None else (payload.json_content or payload.csv_content)

    if isinstance(target_content, list):
        records = target_content
    elif isinstance(target_content, dict):
        records = target_content.get("jobs") or target_content.get("elements") or [target_content]
    elif isinstance(target_content, str):
        trimmed = target_content.strip()
        if trimmed.startswith("[") or trimmed.startswith("{"):
            try:
                parsed = json.loads(trimmed)
                records = parsed if isinstance(parsed, list) else parsed.get("jobs", [parsed])
            except Exception:
                import csv
                import io
                records = list(csv.DictReader(io.StringIO(trimmed)))
        else:
            import csv
            import io
            records = list(csv.DictReader(io.StringIO(trimmed)))
    elif payload.file_path:
        p = Path(payload.file_path)
        if not p.exists():
            raise HTTPException(status_code=400, detail=f"File not found: {payload.file_path}")
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            if p.suffix.lower() == ".csv":
                import csv
                reader = csv.DictReader(f)
                records = list(reader)
            else:
                data = json.load(f)
                records = data if isinstance(data, list) else data.get("jobs", [data])
    else:
        raise HTTPException(status_code=400, detail="Must provide csv_content, json_content, or file_path")

    preview_res = source_service.preview_import_records(
        db=db,
        records=records,
        source_type=payload.source_type or "CSV"
    )
    p_dict = preview_res.model_dump()
    reasons_dict = {}
    for r in preview_res.rejection_summary:
        reasons_dict[r] = reasons_dict.get(r, 0) + 1

    return {
        "status": "success",
        "preview": p_dict,
        "total": preview_res.total_records,
        "valid_count": preview_res.valid_count,
        "rejected_count": preview_res.rejected_count,
        "duplicates_count": preview_res.duplicate_count,
        "items": p_dict.get("sample_preview", []),
        "rejection_reasons": reasons_dict,
        "records_count": len(records)
    }


@router.post("/import/confirm")
def confirm_opportunities_import(
    req: ImportConfirmRequest,
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Confirm and ingest previewed opportunities through the 7-stage verification gate."""
    res = source_service.confirm_and_ingest_import(
        db=db,
        records=req.records,
        source_name=req.source_name,
        source_type=req.source_type.value if hasattr(req.source_type, "value") else str(req.source_type),
        admin_user=admin_user.email
    )
    return res


# ==========================================
# ADMIN VERIFICATION QUEUE
# ==========================================

@router.get("/verification-queue")
def get_admin_verification_queue(
    status: str = "ALL",
    page: int = 1,
    page_size: int = 50,
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Retrieve opportunities for the Admin Verification Queue with status breakdown."""
    queue_data = verification_service.get_verification_queue(
        db=db, status=status, page=page, page_size=page_size
    )
    return {"status": "success", "data": queue_data}


@router.post("/verify/{opp_id}")
def verify_opportunity_endpoint(
    opp_id: str,
    req: VerifyActionRequest = VerifyActionRequest(),
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Approve and verify an opportunity listing."""
    result = verification_service.verify_opportunity(
        db=db,
        opp_id=opp_id,
        admin_user=admin_user.email,
        method=req.method or "ADMIN_MANUAL_REVIEW",
        notes=req.notes
    )
    if not result:
        return {"status": "error", "message": f"Opportunity {opp_id} not found."}
    return {"status": "success", "message": "Opportunity marked as VERIFIED.", "opportunity": result.to_dict()}


@router.post("/reject/{opp_id}")
def reject_opportunity_endpoint(
    opp_id: str,
    req: VerifyActionRequest = VerifyActionRequest(),
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Reject an opportunity listing."""
    result = verification_service.reject_opportunity(
        db=db,
        opp_id=opp_id,
        admin_user=admin_user.email,
        notes=req.notes
    )
    if not result:
        return {"status": "error", "message": f"Opportunity {opp_id} not found."}
    return {"status": "success", "message": "Opportunity marked as REJECTED.", "opportunity": result.to_dict()}


@router.post("/pending/{opp_id}")
def set_pending_opportunity_endpoint(
    opp_id: str,
    req: VerifyActionRequest = VerifyActionRequest(),
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Keep opportunity in PENDING_REVIEW status."""
    result = verification_service.set_pending_opportunity(
        db=db,
        opp_id=opp_id,
        admin_user=admin_user.email,
        notes=req.notes
    )
    if not result:
        return {"status": "error", "message": f"Opportunity {opp_id} not found."}
    return {"status": "success", "message": "Opportunity kept in PENDING_REVIEW.", "opportunity": result.to_dict()}


# ==========================================
# USER MANAGEMENT & ROLES
# ==========================================

class UserRoleUpdateRequest(BaseModel):
    role: str = Field(..., description="ADMIN or STUDENT")


@router.get("/users")
def list_admin_users(
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all registered platform users with roles and status."""
    users = db.query(UserDB).order_by(UserDB.created_at.desc()).all()
    user_list = []
    for u in users:
        student_prof = db.query(StudentDB).filter_by(user_id=u.id).first()
        user_list.append({
            "id": u.id,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "name": student_prof.name if student_prof else u.email.split("@")[0],
            "created_at": u.created_at.isoformat() if u.created_at else None
        })
    return {"status": "success", "count": len(user_list), "users": user_list}


@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: str,
    req: UserRoleUpdateRequest,
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update role for a user (ADMIN or STUDENT) with security audit logging."""
    target_user = db.query(UserDB).filter_by(id=user_id).first()
    if not target_user:
        return {"status": "error", "message": f"User {user_id} not found."}

    new_role = req.role.strip().upper()
    if new_role not in ["ADMIN", "STUDENT"]:
        return {"status": "error", "message": "Invalid role. Must be ADMIN or STUDENT."}

    old_role = target_user.role
    target_user.role = new_role
    db.commit()

    from backend.services.audit_service import log_audit_event
    log_audit_event(
        db=db,
        event_type="USER_ROLE_CHANGED",
        actor=admin_user.email,
        target=user_id,
        details={"old_role": old_role, "new_role": new_role}
    )

    return {"status": "success", "message": f"User role updated to {new_role}."}


# ==========================================
# AUDIT LOGS, SECURITY & HEALTH
# ==========================================

@router.get("/audit-logs")
def get_admin_audit_logs(
    limit: int = 100,
    event_type: Optional[str] = None,
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Retrieve security and administrative audit event log entries."""
    from backend.services.audit_service import get_audit_logs
    logs = get_audit_logs(db=db, limit=limit, event_type=event_type)
    return {"status": "success", "count": len(logs), "logs": logs}


@router.get("/security-status")
def get_admin_security_status(
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Retrieve platform security posture, active defenses, and lockout status."""
    return {
        "status": "SECURE",
        "security_controls": {
            "password_hashing": "Bcrypt (12 rounds)",
            "authentication": "Stateless JWT (HS256) with Server Token Revocation Blacklist",
            "access_control": "Server-side Role-Based (RBAC) + Object-Level Student Data Isolation",
            "ssrf_protection": "Active (Localhost, Private IPs, Link-Local, Cloud Metadata Blocked)",
            "rate_limiting": "In-Memory Sliding Token Bucket on Auth, Sources, and File Uploads",
            "file_upload_validation": "Strict PDF Header Verification (%PDF-), 5MB size ceiling, MIME validation",
            "sql_injection_defense": "SQLAlchemy Parameterized ORM / Zero Raw Concatenation",
            "xss_defense": "XSS-safe text rendering + Content Security Policy & Security Headers",
            "error_handling": "Sanitized JSON responses without production stack traces"
        },
        "audit_policy": "Strict zero-credential logging (Passkeys, Tokens, Resumes Redacted)"
    }


@router.get("/system-health")
def get_admin_system_health(
    admin_user: UserDB = Depends(require_admin)
):
    """Execute live system health checks."""
    from backend.services.health_service import check_system_health
    return check_system_health()

