"""Student profile REST API routes and Resume Upload handling."""

import shutil
import json
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Depends
from fastapi.responses import FileResponse
from backend.models.student import Student
from backend.models.opportunity import Opportunity, StudentOpportunity
from backend.models.preferences import NotificationPreference
from backend.models.user import UserRole
from backend.services.student_service import get_current_student, update_current_student
from backend.services.saved_service import get_saved_opportunities_for_student
from backend.services.preference_service import (
    get_notification_preferences,
    update_notification_preferences,
)
from backend.ai.resume_parser import parse_resume
from backend.utils.config import settings
from backend.utils.logger import get_logger
from backend.database.db import UserDB
from backend.api.deps import require_student

logger = get_logger("routes_students")

router = APIRouter(prefix="/api/student", tags=["Student Profile"])
plural_router = APIRouter(prefix="/api/students", tags=["Student Profile"])


@router.get("", response_model=Student)
@plural_router.get("", response_model=Student, include_in_schema=False)
def get_student_profile(current_user: UserDB = Depends(require_student)):
    """Retrieve the current active student profile."""
    return get_current_student(student_id=current_user.id)


@router.put("", response_model=Student)
@plural_router.put("", response_model=Student, include_in_schema=False)
def save_student_profile(student: Student, current_user: UserDB = Depends(require_student)):
    """Update student profile details, academic records, and career preferences."""
    return update_current_student(student, student_id=current_user.id)


@router.post("/resume")
@plural_router.post("/resume", include_in_schema=False)
async def upload_student_resume(
    file: UploadFile = File(..., description="PDF Resume document"),
    apply_to_profile: bool = Query(False, description="Automatically update active student profile with extracted skills"),
    current_user: UserDB = Depends(require_student),
):
    """Upload PDF resume, validate format & size, extract structured fields, and optionally sync to profile."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file format. Only PDF documents (.pdf) are supported.",
        )

    # Read and check file size (limit to 10MB)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File size exceeds maximum allowed limit (10MB).",
        )
    if len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty.",
        )

    # Magic byte validation for genuine PDF file
    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=400,
            detail="Invalid file signature. Uploaded file is not a valid PDF document.",
        )

    # Sanitize filename and save locally in data/resumes/
    clean_filename = "".join(c for c in Path(file.filename).name if c.isalnum() or c in (".", "_", "-"))
    safe_name = f"{current_user.id}_{clean_filename}"
    target_path = settings.RESUMES_DIR / safe_name
    try:
        with open(target_path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.error(f"Failed to save resume: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to persist uploaded resume: {e}")

    # Parse resume
    try:
        extracted = parse_resume(target_path)
    except ValueError as ve:
        logger.warning(f"Resume text extraction warning: {ve}")
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        logger.error(f"Resume parsing error: {e}", exc_info=True)
        raise HTTPException(
            status_code=422,
            detail=f"Could not parse resume contents: {e}. Please ensure the PDF is not password-protected and contains selectable text.",
        )

    student = get_current_student(student_id=current_user.id)
    student.resume_path = str(target_path.relative_to(settings.ROOT_DIR).as_posix())

    if apply_to_profile:
        # Merge extracted skills into student profile without duplicating
        existing_lower = {s.lower() for s in student.skills}
        for s in extracted.get("skills", []):
            if s.lower() not in existing_lower:
                student.skills.append(s)
                existing_lower.add(s.lower())

        if extracted.get("name") and student.name in ["Student Candidate", "Default Student"]:
            student.name = extracted["name"]
        if extracted.get("email") and student.email in ["student@example.com", ""]:
            student.email = extracted["email"]
        if extracted.get("phone") and not student.phone:
            student.phone = extracted["phone"]

        # If education was extracted, optionally update
        if extracted.get("education"):
            edu_entry = extracted["education"][0]
            if edu_entry.get("degree"):
                student.education = edu_entry["degree"]
            if edu_entry.get("branch"):
                student.branch = edu_entry["branch"]
            if edu_entry.get("graduation_year"):
                student.graduation_year = edu_entry["graduation_year"]
            if edu_entry.get("cgpa"):
                student.cgpa = edu_entry["cgpa"]

        if extracted.get("projects") and not student.projects:
            student.projects = extracted["projects"]
        if extracted.get("experience") and not student.experience:
            student.experience = extracted["experience"]
        if extracted.get("certifications") and not student.certifications:
            student.certifications = extracted["certifications"]

        update_current_student(student, student_id=current_user.id)

    return {
        "status": "success",
        "message": "Resume uploaded and parsed successfully",
        "resume_path": student.resume_path,
        "extracted_data": extracted,
        "completeness_score": student.completeness_score(),
        "applied_to_profile": apply_to_profile,
    }


@router.get("/resume/download")
@plural_router.get("/resume/download", include_in_schema=False)
def download_student_resume(
    student_id: Optional[str] = Query(None, description="Student ID (admin only)"),
    current_user: UserDB = Depends(require_student),
):
    """Securely stream uploaded resume PDF only to authenticated owner or admin."""
    target_id = current_user.id
    if student_id and student_id != current_user.id:
        if current_user.role != UserRole.ADMIN.value:
            raise HTTPException(status_code=403, detail="Cannot access another student's resume")
        target_id = student_id

    student = get_current_student(student_id=target_id)
    if not student.resume_path:
        raise HTTPException(status_code=404, detail="No resume uploaded for this profile")

    # Resolve safely against ROOT_DIR and prevent path traversal
    full_path = (settings.ROOT_DIR / student.resume_path).resolve()
    resumes_dir = settings.RESUMES_DIR.resolve()

    try:
        full_path.relative_to(resumes_dir)
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied to requested file path")

    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="Resume file not found on disk")

    sanitized_filename = "".join(c for c in full_path.name if c.isalnum() or c in (".", "_", "-"))
    return FileResponse(
        path=str(full_path),
        media_type="application/pdf",
        filename=sanitized_filename,
    )


@router.get("/saved", response_model=List[StudentOpportunity])
@plural_router.get("/saved", response_model=List[StudentOpportunity], include_in_schema=False)
def get_student_saved_opportunities(current_user: UserDB = Depends(require_student)):
    """Retrieve all opportunities bookmarked by the active student (source metadata sanitized)."""
    full_opps = get_saved_opportunities_for_student(student_id=current_user.id)
    return [opp.to_student_dict() for opp in full_opps]


@router.get("/completeness")
@plural_router.get("/completeness", include_in_schema=False)
def get_student_profile_completeness(current_user: UserDB = Depends(require_student)):
    """Retrieve profile completeness percentage and missing section breakdown."""
    student = get_current_student(student_id=current_user.id)
    return student.completeness_breakdown()


@router.get("/preferences", response_model=NotificationPreference)
@plural_router.get("/preferences", response_model=NotificationPreference, include_in_schema=False)
def get_student_alert_preferences(current_user: UserDB = Depends(require_student)):
    """Retrieve active student alert and notification preferences."""
    return get_notification_preferences()


@router.put("/preferences", response_model=NotificationPreference)
@plural_router.put("/preferences", response_model=NotificationPreference, include_in_schema=False)
def save_student_alert_preferences(
    prefs: NotificationPreference,
    current_user: UserDB = Depends(require_student),
):
    """Update active student notification preferences."""
    return update_notification_preferences(prefs)


@router.post("/demo/{profile_key}")
@plural_router.post("/demo/{profile_key}", include_in_schema=False)
def switch_demo_profile(profile_key: str, current_user: UserDB = Depends(require_student)):
    """Switch active profile to a curated demonstration persona (Student A: AI/ML or Student B: Web/Backend)."""
    demo_file = settings.DATA_DIR / "demo_students.json"
    if not demo_file.exists():
        raise HTTPException(status_code=404, detail="demo_students.json not found")

    with open(demo_file, "r", encoding="utf-8") as f:
        demos = json.load(f)

    # Normalize key (support 'a', 'b', 'student_a', 'student_b')
    key = profile_key.lower().strip()
    if key in ("a", "aiml", "ai"):
        key = "student_a"
    elif key in ("b", "web", "backend", "fullstack"):
        key = "student_b"

    if key not in demos:
        raise HTTPException(status_code=404, detail=f"Demo profile '{profile_key}' not found. Valid options: student_a, student_b")

    target_data = demos[key]
    student = Student(**target_data)
    updated = update_current_student(student, student_id=current_user.id)

    return {
        "status": "success",
        "message": f"Active profile switched to {student.name} ({key})",
        "student": updated.to_dict(),
        "completeness": updated.completeness_breakdown(),
    }
