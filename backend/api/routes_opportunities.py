"""Opportunities REST API routes supporting filtering, ingestion, stats, submissions, and source privacy."""

import re
from typing import List, Optional, Dict, Any, Union
from datetime import date
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Query, Response, Depends

from backend.models.opportunity import Opportunity, StudentOpportunity
from backend.models.user import UserRole
from backend.services.opportunity_service import (
    get_all_opportunities,
    save_opportunity,
    get_opportunity_stats,
)
from backend.services.ingestion_service import run_ingestion_pipeline
from backend.collectors.normalizer import normalize_opportunity
from backend.database.db import UserDB
from backend.api.deps import get_current_user_optional, require_admin, require_student
from backend.services.saved_service import (
    save_opportunity_for_student,
    unsave_opportunity_for_student,
    get_saved_opportunities_for_student,
    get_saved_opportunity_ids,
)

router = APIRouter(prefix="/api/opportunities", tags=["Opportunities"])


class SubmitOpportunityRequest(BaseModel):
    """Schema for employer or college submitted opportunities."""
    title: str = Field(..., min_length=2, description="Job / internship title")
    company: str = Field(..., min_length=2, description="Hiring organization name")
    description: str = Field(..., min_length=10, description="Role description and requirements")
    apply_url: str = Field(..., min_length=5, description="Valid application URL")
    submission_type: str = Field(default="employer", description="'employer' or 'college'")
    opportunity_type: Optional[str] = Field(default="internship", description="internship, full-time, research, etc.")
    skills: Optional[List[str]] = Field(default_factory=list, description="Target technical skills")
    location: Optional[str] = Field(default="Remote", description="City / state or Remote")
    remote: Optional[bool] = Field(default=True, description="Remote work availability")
    stipend: Optional[str] = Field(default=None, description="Stipend or compensation")
    salary: Optional[str] = Field(default=None, description="Annual compensation")
    deadline: Optional[str] = Field(default=None, description="Application deadline (YYYY-MM-DD)")
    eligibility: Optional[str] = Field(default="All eligible students", description="Academic eligibility criteria")
    experience: Optional[str] = Field(default="Fresher / Student", description="Experience level")


@router.get("")
def list_opportunities(
    response: Response,
    q: Optional[str] = Query(None, description="Search by title, company, skill, location or description text"),
    query: Optional[str] = Query(None, description="Alternative alias for search query"),
    source: Optional[str] = Query(None, description="Filter by source platform"),
    type: Optional[str] = Query(None, description="Filter by opportunity type (internship, job, etc.)"),
    opportunity_type: Optional[str] = Query(None, description="Filter by opportunity type"),
    location: Optional[str] = Query(None, description="Filter by location"),
    remote: Optional[bool] = Query(None, description="Filter for remote opportunities"),
    work_mode: Optional[str] = Query(None, description="Work mode: remote, hybrid, on-site"),
    experience: Optional[str] = Query(None, description="Experience level: Fresher, Experienced, etc."),
    company: Optional[str] = Query(None, description="Filter by company name"),
    posted_within_days: Optional[int] = Query(None, description="Posted within last N days"),
    has_salary: Optional[bool] = Query(None, description="Filter for listings with salary or stipend"),
    verified_only: Optional[bool] = Query(None, description="Filter for verified opportunities only"),
    verification_status: Optional[str] = Query(None, description="Filter by verification status (Admin only)"),
    skill: Optional[str] = Query(None, description="Filter by required skill"),
    status: Optional[str] = Query(None, description="Filter by lifecycle status"),
    sort_by: Optional[str] = Query("newest", description="Sort order: newest, relevance, deadline, stipend, title, company"),
    limit: int = Query(50, ge=1, le=500, description="Number of results per page"),
    offset: Optional[int] = Query(None, ge=0, description="Offset for pagination"),
    page: Optional[int] = Query(None, ge=1, description="Page number (1-indexed)"),
    current_user: Optional[UserDB] = Depends(get_current_user_optional),
):
    """Retrieve filtered list of opportunities. Students ONLY receive published VERIFIED opportunities."""
    is_admin = current_user and current_user.role == UserRole.ADMIN.value
    
    # Calculate offset from page if specified
    calc_offset = 0
    if page is not None and page > 0:
        calc_offset = (page - 1) * limit
    elif offset is not None:
        calc_offset = offset

    # Strict Publishing Gate: Non-admin students only ever see VERIFIED opportunities
    effective_verified_only = True if not is_admin else verified_only
    effective_status = "active" if not is_admin else status
    effective_query = q if q is not None else query
    effective_type = type if type is not None else opportunity_type

    items, total_count = get_all_opportunities(
        query=effective_query,
        opportunity_type=effective_type,
        source=source,
        location=location,
        remote_only=remote,
        work_mode=work_mode,
        experience=experience,
        company=company,
        posted_within_days=posted_within_days,
        has_salary=has_salary,
        verified_only=effective_verified_only,
        verification_status=verification_status if is_admin else None,
        skill=skill,
        status=effective_status,
        limit=limit,
        offset=calc_offset,
        sort_by=sort_by,
        return_total=True
    )

    current_page = (calc_offset // limit) + 1 if limit > 0 else 1
    total_pages = max(1, (total_count + limit - 1) // limit) if limit > 0 else 1

    # Set detailed pagination headers
    response.headers["X-Total-Count"] = str(total_count)
    response.headers["X-Total-Returned"] = str(len(items))
    response.headers["X-Page"] = str(current_page)
    response.headers["X-Total-Pages"] = str(total_pages)
    response.headers["X-Offset"] = str(calc_offset)
    response.headers["X-Limit"] = str(limit)

    if is_admin:
        return [opp.to_dict() for opp in items]
    
    # Strict fail-closed defense-in-depth: students ONLY receive VERIFIED and non-expired opportunities
    today_iso = date.today().isoformat()
    verified_student_items = [
        opp for opp in items
        if (opp.verification_status or "").upper() == "VERIFIED"
        and opp.status in ("active", "open")
        and (not opp.deadline or opp.deadline >= today_iso)
    ]
    return [opp.to_student_dict() for opp in verified_student_items]


@router.get("/stats")
def get_stats() -> Dict[str, Any]:
    """Retrieve statistical summary of opportunities by status, source, and type."""
    return get_opportunity_stats()


@router.post("/ingest")
def trigger_ingestion(admin_user: UserDB = Depends(require_admin)):
    """Trigger the unified opportunity ingestion engine (Admin only)."""
    report = run_ingestion_pipeline()
    return {
        "status": "success",
        "message": f"Ingestion completed. {report.get('new_added', 0)} new opportunities added.",
        "report": report
    }


@router.post("/refresh")
async def refresh_opportunities():
    """Trigger an on-demand refresh of all opportunity sources so newly posted jobs appear immediately."""
    from backend.services.scheduler_service import trigger_immediate_ingestion
    report = await trigger_immediate_ingestion()
    if not report:
        report = {}
    return {
        "status": "success",
        "message": f"Feed refreshed. Found {report.get('found', 0)} postings, added {report.get('saved', 0)} new opportunities ({report.get('verified', 0)} published).",
        "report": report
    }


@router.post("/submit")
def submit_opportunity(
    req: SubmitOpportunityRequest,
    current_user: Optional[UserDB] = Depends(get_current_user_optional),
):
    """Submit a verified employer or college opportunity listing."""
    # Basic URL validation
    if not re.match(r"^https?://", req.apply_url.strip()):
        raise HTTPException(status_code=400, detail="Invalid application URL. Must start with http:// or https://")

    is_employer = (req.submission_type.lower() == "employer")
    src_type = "Employer Submission" if is_employer else "College Submission"
    trust = "EMPLOYER_SUBMITTED" if is_employer else "COLLEGE_SUBMITTED"
    ver_method = "EMPLOYER_SUBMISSION" if is_employer else "COLLEGE_PORTAL"

    opp = Opportunity(
        title=req.title.strip(),
        company=req.company.strip(),
        description=req.description.strip(),
        opportunity_type=req.opportunity_type or "internship",
        skills=req.skills or [],
        location=req.location or "Remote",
        remote=req.remote if req.remote is not None else True,
        stipend=req.stipend,
        salary=req.salary,
        deadline=req.deadline,
        eligibility=req.eligibility or "All eligible students",
        experience=req.experience or "Fresher / Student",
        source=src_type,
        source_url=req.apply_url.strip(),
        apply_url=req.apply_url.strip(),
        posted_date=date.today().isoformat(),
        status="active",
        trust_level=trust,
        verification_status="PENDING_REVIEW",
        verification_method=ver_method,
        verification_notes=f"Submitted via {req.submission_type} submission portal"
    )

    normalized = normalize_opportunity(opp)
    saved = save_opportunity(normalized)
    
    is_admin = current_user and current_user.role == UserRole.ADMIN.value
    if is_admin:
        return saved.to_dict()
    return saved.to_student_dict()


@router.get("/saved")
def list_saved_opportunities(current_user: Optional[UserDB] = Depends(get_current_user_optional)):
    """Retrieve all opportunities saved/bookmarked by the student."""
    student_id = current_user.id if current_user else "default_student"
    items = get_saved_opportunities_for_student(student_id=student_id)
    is_admin = current_user and current_user.role == UserRole.ADMIN.value
    if is_admin:
        return [opp.to_dict() for opp in items]
    return [opp.to_student_dict() for opp in items]


@router.get("/saved/ids")
def list_saved_opportunity_ids(current_user: Optional[UserDB] = Depends(get_current_user_optional)):
    """Retrieve list of opportunity IDs bookmarked by the student."""
    student_id = current_user.id if current_user else "default_student"
    return {"saved_ids": get_saved_opportunity_ids(student_id=student_id)}


@router.post("/{opp_id}/save")
def save_single_opportunity(
    opp_id: str,
    current_user: Optional[UserDB] = Depends(get_current_user_optional),
):
    """Bookmark an opportunity for later reference."""
    student_id = current_user.id if current_user else "default_student"
    try:
        bookmark = save_opportunity_for_student(opp_id, student_id=student_id)
        return {"status": "success", "message": f"Opportunity {opp_id} saved", "bookmark": bookmark.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{opp_id}/save")
def unsave_single_opportunity(
    opp_id: str,
    current_user: Optional[UserDB] = Depends(get_current_user_optional),
):
    """Remove an opportunity bookmark."""
    student_id = current_user.id if current_user else "default_student"
    removed = unsave_opportunity_for_student(opp_id, student_id=student_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Bookmark for opportunity {opp_id} not found")
    return {"status": "success", "message": f"Opportunity {opp_id} unsaved"}


@router.get("/{opp_id}")
def get_opportunity(
    opp_id: str,
    current_user: Optional[UserDB] = Depends(get_current_user_optional),
):
    """Retrieve single opportunity by ID with role-based source privacy and verification enforcement."""
    is_admin = current_user and current_user.role == UserRole.ADMIN.value
    opportunities = get_all_opportunities(verified_only=None if is_admin else True)
    for opp in opportunities:
        if opp.id == opp_id:
            if not is_admin:
                today_iso = date.today().isoformat()
                if (
                    opp.verification_status != "VERIFIED"
                    or opp.status not in ("active", "open")
                    or (opp.deadline and opp.deadline < today_iso)
                ):
                    raise HTTPException(status_code=404, detail="Opportunity not found")
                return opp.to_student_dict()
            return opp.to_dict()
    raise HTTPException(status_code=404, detail="Opportunity not found")
