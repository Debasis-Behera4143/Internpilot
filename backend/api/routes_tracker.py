"""Application Tracker REST API routes."""

from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends
from backend.models.application import Application
from backend.services.tracker_service import (
    get_all_applications,
    add_application,
    update_application_status,
)
from backend.database.db import UserDB
from backend.api.deps import require_student

router = APIRouter(prefix="/api/applications", tags=["Application Tracker"])


class CreateApplicationRequest(BaseModel):
    company: str
    role: str
    status: str = "Applied"
    notes: Optional[str] = ""
    opportunity_id: Optional[str] = None
    apply_url: Optional[str] = ""


class UpdateStatusRequest(BaseModel):
    status: str
    notes: Optional[str] = None


@router.get("", response_model=List[Application])
def list_applications(current_user: UserDB = Depends(require_student)):
    """Retrieve applications for the authenticated student."""
    return get_all_applications(student_id=current_user.id)


@router.post("", response_model=Application)
def track_application(
    req: CreateApplicationRequest,
    current_user: UserDB = Depends(require_student),
):
    """Log a new job or internship application for the authenticated student."""
    return add_application(
        company=req.company,
        role=req.role,
        status=req.status,
        notes=req.notes or "",
        opportunity_id=req.opportunity_id,
        apply_url=req.apply_url or "",
        student_id=current_user.id,
    )


@router.patch("/{app_id}", response_model=Application)
@router.put("/{app_id}", response_model=Application)
def update_status(
    app_id: str,
    req: UpdateStatusRequest,
    current_user: UserDB = Depends(require_student),
):
    """Update application status (e.g. Applied -> Interviewing -> Offer)."""
    updated = update_application_status(
        app_id,
        req.status,
        notes=req.notes,
        student_id=current_user.id,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Application not found or unauthorized")
    return updated
