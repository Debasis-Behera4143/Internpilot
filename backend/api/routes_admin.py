from typing import List, Optional, Dict, Any, Union
from pathlib import Path
from datetime import date
import json
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc, asc
from pydantic import BaseModel, Field

from backend.database.db import (
    get_db, OpportunityDB, UserDB, StudentDB, SourceRegistryDB,
    ApplicationDB, SavedOpportunityDB, AuditLogDB
)
from backend.models.opportunity import Opportunity
from backend.api.deps import require_admin

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.get("/dashboard")
def get_admin_dashboard(admin_user: UserDB = Depends(require_admin), db: Session = Depends(get_db)):
    """Retrieve comprehensive admin dashboard metrics with summary cards."""
    active_sources = db.query(SourceRegistryDB).filter_by(status="ACTIVE").count()
    failed_sources = db.query(SourceRegistryDB).filter(
        (SourceRegistryDB.status == "FAILED") | (SourceRegistryDB.last_error.isnot(None))
    ).count()

    total_jobs = db.query(OpportunityDB).count()
    pending_approval = db.query(OpportunityDB).filter(OpportunityDB.approval_status == "pending").count()
    approved = db.query(OpportunityDB).filter(OpportunityDB.approval_status == "approved").count()
    verified_jobs = db.query(OpportunityDB).filter_by(verification_status="VERIFIED").count()
    pending_review = db.query(OpportunityDB).filter_by(verification_status="PENDING_REVIEW").count()
    rejected = db.query(OpportunityDB).filter(
        (OpportunityDB.verification_status == "REJECTED") | (OpportunityDB.approval_status == "rejected")
    ).count()

    unknown_comps = ["Unknown", "Unknown Company", "N/A", "NA", "Not specified", "Company", "none", "null"]
    unknown_company_count = db.query(OpportunityDB).filter(
        (OpportunityDB.company.in_(unknown_comps)) | (OpportunityDB.normalized_company == "Unknown")
    ).count()

    duplicate_candidates_count = db.query(OpportunityDB).filter(
        OpportunityDB.duplicate_group.isnot(None)
    ).count()

    expired = db.query(OpportunityDB).filter(
        (OpportunityDB.status.in_(["expired", "closed"])) |
        ((OpportunityDB.deadline.isnot(None)) & (OpportunityDB.deadline != "") & (OpportunityDB.deadline < date.today().isoformat()))
    ).count()

    # Real user and application metrics: only real registered students are counted
    student_users = db.query(UserDB).filter_by(role="STUDENT").count()
    admin_users = db.query(UserDB).filter_by(role="ADMIN").count()
    total_users = student_users  # Starts at 0 for demo/clean baseline until a student registers

    total_applications = db.query(ApplicationDB).count()
    pending_applications = db.query(ApplicationDB).filter(
        ApplicationDB.status.in_(["Applied", "Under Review", "Interviewing"])
    ).count()
    offer_applications = db.query(ApplicationDB).filter_by(status="Offer").count()
    rejected_applications = db.query(ApplicationDB).filter_by(status="Rejected").count()

    # Fetch recent 10 registered users
    recent_registered_users = (
        db.query(UserDB)
        .order_by(UserDB.created_at.desc())
        .limit(10)
        .all()
    )
    recent_users_data = []
    for u in recent_registered_users:
        prof = db.query(StudentDB).filter_by(user_id=u.id).first()
        app_count = db.query(ApplicationDB).filter(
            or_(ApplicationDB.student_id == u.id, ApplicationDB.student_id == (prof.id if prof else ""))
        ).count()
        recent_users_data.append({
            "id": u.id,
            "email": u.email,
            "name": prof.name if prof else u.email.split("@")[0],
            "role": u.role,
            "college": prof.education if prof else "N/A",
            "branch": prof.branch if prof else "N/A",
            "graduation_year": prof.graduation_year if prof else None,
            "applications_count": app_count,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })

    # Fetch recent 15 opportunities
    recent_db_opps = (
        db.query(OpportunityDB)
        .order_by(OpportunityDB.created_at.desc())
        .limit(15)
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
            "approval_status": getattr(opp, "approval_status", None) or ("approved" if opp.verification_status == "VERIFIED" else "pending"),
            "verification_status": opp.verification_status,
            "company_confidence": getattr(opp, "company_confidence", 1.0) or 1.0,
            "collected_date": opp.collected_date,
            "created_at": opp.created_at.isoformat() if opp.created_at else None,
        })

    metrics = {
        "total_users": total_users,
        "active_users": total_users,
        "student_users": student_users,
        "admin_users": admin_users,
        "total_applications": total_applications,
        "pending_applications": pending_applications,
        "offer_applications": offer_applications,
        "rejected_applications": rejected_applications,
        "active_sources": active_sources,
        "failed_sources": failed_sources,
        "sources_active": active_sources,
        "sources_failed": failed_sources,
        "total_jobs": total_jobs,
        "total_opportunities": total_jobs,
        "pending_approval": pending_approval,
        "approved": approved,
        "verified_jobs": verified_jobs,
        "verified": verified_jobs,
        "pending_review": pending_review,
        "needs_review": pending_review,
        "rejected": rejected,
        "unknown_company": unknown_company_count,
        "duplicate_candidates": duplicate_candidates_count,
        "expired": expired,
        "active_opportunities": verified_jobs,
        "expired_opportunities": expired,
    }

    return {
        "status": "success",
        "metrics": metrics,
        "kpis": metrics,
        "recent_users": recent_users_data,
        "recent_opportunities": recent_opportunities,
    }


@router.get("/opportunities")
def get_admin_opportunities(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(50, ge=1, le=500, description="Items per page"),
    offset: Optional[int] = Query(None, ge=0, description="Offset override"),
    q: Optional[str] = Query(None, description="Search query"),
    approval_status: Optional[str] = Query(None, description="Approval filter"),
    verification_status: Optional[str] = Query(None, description="Verification filter"),
    source: Optional[str] = Query(None, description="Source filter"),
    newly_collected: Optional[bool] = Query(None, description="Recent 48h ingestion filter"),
    unknown_company: Optional[bool] = Query(None, description="Unknown company filter"),
    low_confidence: Optional[bool] = Query(None, description="Low confidence filter"),
    duplicate_candidates: Optional[bool] = Query(None, description="Duplicate candidates filter"),
    sort_by: Optional[str] = Query("newest", description="Sort order"),
    format: Optional[str] = Query(None, description="Response format: 'paged' or default list"),
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db),
    response: Response = None,
):
    """Retrieve paginated and filtered opportunities for admin management."""
    from backend.services.opportunity_service import get_all_opportunities

    calc_offset = offset if offset is not None else ((page - 1) * limit)

    items, total_count = get_all_opportunities(
        query=q,
        source=source,
        approval_status=approval_status,
        verification_status=verification_status,
        newly_collected=newly_collected,
        unknown_company=unknown_company,
        low_confidence=low_confidence,
        duplicate_candidates=duplicate_candidates,
        sort_by=sort_by,
        limit=limit,
        offset=calc_offset,
        return_total=True
    )

    total_pages = max(1, (total_count + limit - 1) // limit) if limit > 0 else 1
    current_page = (calc_offset // limit) + 1 if limit > 0 else 1

    item_dicts = [opp.to_dict() for opp in items]

    if response is not None and isinstance(response, Response):
        response.headers["X-Total-Count"] = str(total_count)
        response.headers["X-Total-Pages"] = str(total_pages)
        response.headers["X-Page"] = str(current_page)
        response.headers["X-Limit"] = str(limit)

    if format == "paged":
        return {
            "status": "success",
            "items": item_dicts,
            "total": total_count,
            "total_pages": total_pages,
            "page": current_page,
            "limit": limit
        }

    return item_dicts


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
# OPPORTUNITY MANAGEMENT & BULK ACTIONS
# ==========================================

class BulkActionRequest(BaseModel):
    opp_ids: Optional[List[str]] = None
    reason: Optional[str] = "Bulk administrative action"


class OpportunityEditRequest(BaseModel):
    title: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    opportunity_type: Optional[str] = None
    deadline: Optional[str] = None
    apply_url: Optional[str] = None
    stipend: Optional[str] = None


@router.get("/opportunities")
def list_admin_opportunities(
    q: Optional[str] = Query(None, description="Search by title, company, or skills"),
    approval_status: Optional[str] = Query(None, description="pending, approved, rejected"),
    verification_status: Optional[str] = Query(None, description="unverified, verified, needs_review, rejected"),
    unknown_company: Optional[bool] = Query(None, description="Filter for unknown/missing company names"),
    low_confidence: Optional[bool] = Query(None, description="Filter for company confidence < 0.70"),
    duplicate_candidates: Optional[bool] = Query(None, description="Filter for duplicate candidate groups"),
    source: Optional[str] = Query(None, description="Filter by source type or name"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    sort_by: str = Query("newest"),
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Retrieve full opportunity list for Admin with granular filters and company extraction telemetry."""
    # Map verification_status aliases
    v_stat = None
    if verification_status:
        v_clean = verification_status.strip().lower()
        if v_clean in ("verified", "verify"):
            v_stat = "VERIFIED"
        elif v_clean in ("needs_review", "pending_review", "needs review"):
            v_stat = "PENDING_REVIEW"
        elif v_clean in ("unverified", "unverify"):
            v_stat = "UNVERIFIED"
        elif v_clean in ("rejected", "reject"):
            v_stat = "REJECTED"

    appr_stat = approval_status.strip().lower() if approval_status and approval_status.lower() != "all" else None

    calc_offset = (page - 1) * limit

    items, total_count = opportunity_service.get_all_opportunities(
        query=q,
        source=source,
        approval_status=appr_stat,
        verification_status=v_stat,
        unknown_company=unknown_company,
        low_confidence=low_confidence,
        duplicate_candidates=duplicate_candidates,
        limit=limit,
        offset=calc_offset,
        sort_by=sort_by,
        return_total=True
    )

    total_pages = max(1, (total_count + limit - 1) // limit) if limit > 0 else 1

    return {
        "status": "success",
        "items": [opp.to_dict() for opp in items],
        "total": total_count,
        "page": page,
        "limit": limit,
        "total_pages": total_pages
    }


@router.get("/opportunities/eligibility")
def get_admin_verification_eligibility(
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Retrieve counts of pending opportunities, eligible for verification, and requiring review."""
    counts = verification_service.get_bulk_verification_eligibility(db=db)
    return {"status": "success", "data": counts}


@router.post("/opportunities/bulk-approve")
def bulk_approve_admin_endpoint(
    req: BulkActionRequest = BulkActionRequest(),
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Approve all pending opportunities or specified IDs."""
    result = verification_service.bulk_approve_opportunities(
        db=db,
        opp_ids=req.opp_ids,
        admin_user=admin_user.email
    )
    return result


@router.post("/opportunities/bulk-verify")
def bulk_verify_admin_endpoint(
    req: BulkActionRequest = BulkActionRequest(),
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Verify all eligible opportunities passing the conservative verification gate."""
    result = verification_service.bulk_verify_opportunities(
        db=db,
        opp_ids=req.opp_ids,
        admin_user=admin_user.email
    )
    return result


@router.post("/opportunities/bulk-reject")
def bulk_reject_admin_endpoint(
    req: BulkActionRequest = BulkActionRequest(),
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Reject pending or specified opportunities."""
    result = verification_service.bulk_reject_opportunities(
        db=db,
        opp_ids=req.opp_ids,
        admin_user=admin_user.email,
        reason=req.reason or "Bulk rejected by administrator"
    )
    return result


@router.post("/opportunities/{opp_id}/approve")
def approve_single_opportunity_endpoint(
    opp_id: str,
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Approve single opportunity into public feed."""
    opp = verification_service.approve_opportunity(db=db, opp_id=opp_id, admin_user=admin_user.email)
    if not opp:
        return {"status": "error", "message": f"Opportunity {opp_id} not found."}
    return {"status": "success", "message": "Opportunity approved successfully.", "opportunity": opp.to_dict()}


@router.post("/opportunities/{opp_id}/reject")
def reject_single_opportunity_endpoint(
    opp_id: str,
    req: VerifyActionRequest = VerifyActionRequest(),
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Reject single opportunity."""
    opp = verification_service.reject_opportunity(db=db, opp_id=opp_id, admin_user=admin_user.email, notes=req.notes)
    if not opp:
        return {"status": "error", "message": f"Opportunity {opp_id} not found."}
    return {"status": "success", "message": "Opportunity rejected.", "opportunity": opp.to_dict()}


@router.post("/opportunities/{opp_id}/verify")
def verify_single_opportunity_endpoint(
    opp_id: str,
    req: VerifyActionRequest = VerifyActionRequest(),
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Mark single opportunity as verified."""
    opp = verification_service.verify_opportunity(db=db, opp_id=opp_id, admin_user=admin_user.email, method=req.method or "ADMIN_MANUAL_REVIEW", notes=req.notes)
    if not opp:
        return {"status": "error", "message": f"Opportunity {opp_id} not found."}
    return {"status": "success", "message": "Opportunity marked as VERIFIED.", "opportunity": opp.to_dict()}


@router.post("/opportunities/{opp_id}/needs-review")
def needs_review_single_opportunity_endpoint(
    opp_id: str,
    req: VerifyActionRequest = VerifyActionRequest(),
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Flag single opportunity as requiring review."""
    opp = verification_service.set_pending_opportunity(db=db, opp_id=opp_id, admin_user=admin_user.email, notes=req.notes)
    if not opp:
        return {"status": "error", "message": f"Opportunity {opp_id} not found."}
    return {"status": "success", "message": "Opportunity flagged for review.", "opportunity": opp.to_dict()}


@router.put("/opportunities/{opp_id}")
def edit_opportunity_endpoint(
    opp_id: str,
    req: OpportunityEditRequest,
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Edit core fields of an opportunity."""
    opp = db.query(OpportunityDB).filter_by(id=opp_id).first()
    if not opp:
        return {"status": "error", "message": f"Opportunity {opp_id} not found."}

    if req.title:
        opp.title = req.title.strip()
    if req.company:
        opp.company = req.company.strip()
        opp.normalized_company = req.company.strip()
    if req.location:
        opp.location = req.location.strip()
    if req.opportunity_type:
        opp.opportunity_type = req.opportunity_type.strip()
    if req.deadline:
        opp.deadline = req.deadline.strip()
    if req.apply_url:
        opp.apply_url = req.apply_url.strip()
        opp.application_url = req.apply_url.strip()
    if req.stipend:
        opp.stipend = req.stipend.strip()

    db.commit()
    db.refresh(opp)
    return {"status": "success", "message": "Opportunity updated successfully."}


# ==========================================
# USER MANAGEMENT & ROLES
# ==========================================

class UserRoleUpdateRequest(BaseModel):
    role: str = Field(..., description="ADMIN or STUDENT")


@router.get("/users")
def list_admin_users(
    q: Optional[str] = Query(None, description="Search by name, email, college, or branch"),
    role: Optional[str] = Query(None, description="Filter by role (ADMIN, STUDENT)"),
    status: Optional[str] = Query(None, description="Filter by active status (active, inactive)"),
    sort_by: str = Query("created_at", description="Sort field (created_at, email, name)"),
    sort_dir: str = Query("desc", description="Sort direction (asc, desc)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List registered users with search, role/status filtering, sorting, and pagination. Never exposes hashes/secrets."""
    query = db.query(UserDB)

    if role:
        query = query.filter(UserDB.role == role.strip().upper())
    if status:
        if status.lower() == "active":
            query = query.filter(UserDB.is_active == True)
        elif status.lower() == "inactive":
            query = query.filter(UserDB.is_active == False)

    # If search query provided, search UserDB email or StudentDB name/education/branch
    if q and q.strip():
        search_term = f"%{q.strip()}%"
        # Find matching student user_ids
        matched_student_user_ids = [
            s.user_id for s in db.query(StudentDB.user_id).filter(
                or_(
                    StudentDB.name.ilike(search_term),
                    StudentDB.education.ilike(search_term),
                    StudentDB.branch.ilike(search_term),
                    StudentDB.email.ilike(search_term)
                )
            ).all() if s.user_id
        ]
        query = query.filter(
            or_(
                UserDB.email.ilike(search_term),
                UserDB.id.in_(matched_student_user_ids)
            )
        )

    # Sorting
    if sort_by == "email":
        order_col = UserDB.email
    else:
        order_col = UserDB.created_at

    if sort_dir.lower() == "asc":
        query = query.order_by(asc(order_col))
    else:
        query = query.order_by(desc(order_col))

    total_count = query.count()
    offset = (page - 1) * page_size
    users = query.offset(offset).limit(page_size).all()

    user_list = []
    for u in users:
        student_prof = db.query(StudentDB).filter_by(user_id=u.id).first()
        app_count = db.query(ApplicationDB).filter(
            or_(ApplicationDB.student_id == u.id, ApplicationDB.student_id == (student_prof.id if student_prof else ""))
        ).count()
        user_list.append({
            "id": u.id,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "name": student_prof.name if student_prof else u.email.split("@")[0],
            "college": student_prof.education if student_prof else "N/A",
            "branch": student_prof.branch if student_prof else "N/A",
            "graduation_year": student_prof.graduation_year if student_prof else None,
            "applications_count": app_count,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "updated_at": u.updated_at.isoformat() if u.updated_at else None,
        })

    return {
        "status": "success",
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": (total_count + page_size - 1) // page_size if page_size > 0 else 1,
        "users": user_list
    }


@router.get("/users/{user_id}")
def get_admin_user_details(
    user_id: str,
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Retrieve full user profile, skills, real applications, saved opportunities, and audit logs. Zero secrets."""
    u = db.query(UserDB).filter_by(id=user_id).first()
    if not u:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    student_prof = db.query(StudentDB).filter_by(user_id=u.id).first()
    student_id = student_prof.id if student_prof else u.id

    # Parse stored skills & interests safely
    skills = []
    if student_prof and student_prof.skills:
        try:
            skills = json.loads(student_prof.skills) if isinstance(student_prof.skills, str) else student_prof.skills
        except Exception:
            skills = [student_prof.skills]

    interests = []
    if student_prof and student_prof.interests:
        try:
            interests = json.loads(student_prof.interests) if isinstance(student_prof.interests, str) else student_prof.interests
        except Exception:
            interests = [student_prof.interests]

    # Applications from database
    apps_db = db.query(ApplicationDB).filter(
        or_(ApplicationDB.student_id == u.id, ApplicationDB.student_id == student_id)
    ).order_by(ApplicationDB.created_at.desc()).all()

    applications = []
    for a in apps_db:
        applications.append({
            "id": a.id,
            "company": a.company,
            "role": a.role,
            "status": a.status,
            "applied_date": a.applied_date,
            "opportunity_id": a.opportunity_id,
            "notes": a.notes,
            "source": a.source,
            "created_at": a.created_at.isoformat() if a.created_at else None
        })

    # Saved opportunities from database
    saved_db = db.query(SavedOpportunityDB).filter(
        or_(SavedOpportunityDB.student_id == u.id, SavedOpportunityDB.student_id == student_id)
    ).order_by(SavedOpportunityDB.created_at.desc()).all()

    saved_opportunities = []
    for s in saved_db:
        opp = db.query(OpportunityDB).filter_by(id=s.opportunity_id).first()
        saved_opportunities.append({
            "saved_id": s.id,
            "opportunity_id": s.opportunity_id,
            "title": opp.title if opp else "Opportunity",
            "company": opp.company if opp else "Unknown",
            "location": opp.location if opp else "Remote",
            "status": opp.status if opp else "active",
            "saved_at": s.created_at.isoformat() if s.created_at else None
        })

    # Audit / Activity logs
    recent_logs = db.query(AuditLogDB).filter(
        or_(AuditLogDB.actor == u.email, AuditLogDB.target == u.id, AuditLogDB.target == u.email)
    ).order_by(AuditLogDB.created_at.desc()).limit(20).all()

    activity = []
    for log in recent_logs:
        activity.append({
            "id": log.id,
            "event_type": log.event_type,
            "actor": log.actor,
            "details": log.details,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat() if log.created_at else None
        })

    return {
        "status": "success",
        "user": {
            "id": u.id,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "updated_at": u.updated_at.isoformat() if u.updated_at else None,
        },
        "profile": {
            "name": student_prof.name if student_prof else u.email.split("@")[0],
            "email": student_prof.email if student_prof else u.email,
            "phone": student_prof.phone if student_prof else None,
            "education": student_prof.education if student_prof else "N/A",
            "branch": student_prof.branch if student_prof else "N/A",
            "graduation_year": student_prof.graduation_year if student_prof else None,
            "cgpa": student_prof.cgpa if student_prof else None,
            "bio": student_prof.bio if student_prof else "",
            "skills": skills,
            "interests": interests,
            "remote_preference": student_prof.remote_preference if student_prof else True,
        },
        "applications": applications,
        "saved_opportunities": saved_opportunities,
        "activity": activity
    }


@router.get("/applications")
def list_admin_applications(
    q: Optional[str] = Query(None, description="Search company or role"),
    status: Optional[str] = Query(None, description="Filter by application status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all student applications across the entire platform with full relational detail."""
    query = db.query(ApplicationDB)
    if status and status.strip():
        query = query.filter(ApplicationDB.status == status.strip())
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                ApplicationDB.company.ilike(term),
                ApplicationDB.role.ilike(term)
            )
        )

    total = query.count()
    offset = (page - 1) * page_size
    apps = query.order_by(ApplicationDB.created_at.desc()).offset(offset).limit(page_size).all()

    app_list = []
    for a in apps:
        # Find student and user info
        student = db.query(StudentDB).filter(
            or_(StudentDB.id == a.student_id, StudentDB.user_id == a.student_id)
        ).first()
        opp = db.query(OpportunityDB).filter_by(id=a.opportunity_id).first() if a.opportunity_id else None

        app_list.append({
            "id": a.id,
            "student_id": a.student_id,
            "applicant_name": student.name if student else "Student",
            "applicant_email": student.email if student else "N/A",
            "company": a.company,
            "role": a.role,
            "status": a.status,
            "applied_date": a.applied_date,
            "opportunity_id": a.opportunity_id,
            "opportunity_title": opp.title if opp else None,
            "opportunity_type": opp.opportunity_type if opp else None,
            "apply_url": a.apply_url or (opp.apply_url if opp else None),
            "source": a.source,
            "created_at": a.created_at.isoformat() if a.created_at else None
        })

    return {
        "status": "success",
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size > 0 else 1,
        "applications": app_list
    }


@router.get("/analytics")
def get_admin_analytics(
    admin_user: UserDB = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Calculate platform-wide statistical analytics from real database records."""
    total_users = db.query(UserDB).count()
    active_users = db.query(UserDB).filter_by(is_active=True).count()
    student_users = db.query(UserDB).filter_by(role="STUDENT").count()
    admin_users = db.query(UserDB).filter_by(role="ADMIN").count()

    total_apps = db.query(ApplicationDB).count()
    app_status_counts = {}
    for st, count in db.query(ApplicationDB.status, func.count(ApplicationDB.id)).group_by(ApplicationDB.status).all():
        app_status_counts[st] = count

    total_opps = db.query(OpportunityDB).count()
    verified_opps = db.query(OpportunityDB).filter_by(verification_status="VERIFIED").count()
    pending_opps = db.query(OpportunityDB).filter_by(verification_status="PENDING_REVIEW").count()
    rejected_opps = db.query(OpportunityDB).filter_by(verification_status="REJECTED").count()

    total_sources = db.query(SourceRegistryDB).count()
    active_sources = db.query(SourceRegistryDB).filter_by(status="ACTIVE").count()

    # Opportunity type breakdown
    opp_type_counts = {}
    for o_type, count in db.query(OpportunityDB.opportunity_type, func.count(OpportunityDB.id)).group_by(OpportunityDB.opportunity_type).all():
        opp_type_counts[o_type or "unspecified"] = count

    return {
        "status": "success",
        "analytics": {
            "users": {
                "total": total_users,
                "active": active_users,
                "students": student_users,
                "admins": admin_users
            },
            "applications": {
                "total": total_apps,
                "breakdown": app_status_counts
            },
            "opportunities": {
                "total": total_opps,
                "verified": verified_opps,
                "pending_review": pending_opps,
                "rejected": rejected_opps,
                "by_type": opp_type_counts
            },
            "sources": {
                "total": total_sources,
                "active": active_sources
            }
        }
    }


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

