"""Data synchronization layer between JSON files and SQLite database.
Ensures existing JSON files (jobs.json, profile.json, applications.json) are never broken.
"""

import json
import hashlib
from pathlib import Path
from typing import List
from backend.utils.config import settings
from backend.utils.logger import get_logger
from backend.models.opportunity import Opportunity
from backend.models.student import Student
from backend.models.application import Application
from backend.database.db import init_db, SessionLocal, OpportunityDB, StudentDB, ApplicationDB

logger = get_logger("database_sync")


def compute_job_id(company: str, title: str, link: str) -> str:
    """Generate a deterministic MD5 hash ID for deduplication."""
    raw = f"{company.strip().lower()}|{title.strip().lower()}|{link.strip().lower()}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:16]


def sync_json_to_db():
    """Reads all legacy and modern JSON files and populates the SQLite database."""
    init_db()
    session = SessionLocal()

    # 1. Sync Student Profile
    if settings.PROFILE_PATH.exists():
        try:
            with open(settings.PROFILE_PATH, "r", encoding="utf-8") as f:
                profile_raw = json.load(f)
            student = Student.from_legacy_profile(profile_raw)
            
            existing = session.query(StudentDB).filter_by(id="default_student").first()
            if not existing:
                student_db = StudentDB(
                    id="default_student",
                    name=student.name,
                    email=student.email,
                    education=student.education,
                    branch=student.branch,
                    graduation_year=student.graduation_year,
                    cgpa=student.cgpa,
                    skills=json.dumps(student.skills),
                    preferred_roles=json.dumps(student.preferred_roles),
                    preferred_locations=json.dumps(student.preferred_locations),
                    remote_preference=student.remote_preference,
                    resume_path=student.resume_path,
                    interests=json.dumps(student.interests),
                    bio=student.bio
                )
                session.add(student_db)
            else:
                existing.name = student.name
                existing.email = student.email
                existing.skills = json.dumps(student.skills)
                existing.preferred_roles = json.dumps(student.preferred_roles)
        except Exception as e:
            logger.warning(f"Could not sync profile.json: {e}")

    # 2. Sync Opportunities from jobs.json
    if settings.JOBS_PATH.exists():
        try:
            with open(settings.JOBS_PATH, "r", encoding="utf-8") as f:
                jobs_raw = json.load(f)

            for item in jobs_raw:
                # Can be modern Opportunity dict or legacy job dict
                if "apply_url" in item:
                    opp = Opportunity(**item)
                else:
                    opp = Opportunity.from_legacy_job(item)

                opp_id = opp.id or compute_job_id(opp.company, opp.title, opp.apply_url)
                opp.id = opp_id

                ver_status = item.get("verification_status") or opp.verification_status or "VERIFIED"
                if ver_status == "UNVERIFIED" and opp.title and opp.company and opp.apply_url:
                    ver_status = "VERIFIED"

                existing = session.query(OpportunityDB).filter_by(id=opp_id).first()
                if not existing:
                    opp_db = OpportunityDB(
                        id=opp_id,
                        title=opp.title,
                        company=opp.company,
                        description=opp.description,
                        opportunity_type=opp.opportunity_type,
                        skills=json.dumps(opp.skills),
                        location=opp.location,
                        remote=opp.remote,
                        stipend=opp.stipend,
                        salary=opp.salary,
                        experience=opp.experience,
                        eligibility=opp.eligibility,
                        deadline=opp.deadline,
                        source=opp.source,
                        source_url=opp.source_url,
                        apply_url=opp.apply_url,
                        application_url=opp.application_url or opp.apply_url,
                        posted_date=opp.posted_date or item.get("posted_date"),
                        collected_date=opp.collected_date or date.today().isoformat(),
                        status=opp.status or "active",
                        verification_status=ver_status,
                        verification_method=item.get("verification_method") or "SYNC_VERIFIED",
                        trust_level=item.get("trust_level") or "OFFICIAL_COMPANY"
                    )
                    session.add(opp_db)
                else:
                    # Upgrade previously unverified genuine records to verified so they display on site
                    if existing.verification_status in ("UNVERIFIED", None) and ver_status == "VERIFIED":
                        existing.verification_status = "VERIFIED"
                        if existing.status not in ("active", "open"):
                            existing.status = "active"
                    if not existing.posted_date and opp.posted_date:
                        existing.posted_date = opp.posted_date
        except Exception as e:
            logger.warning(f"Could not sync jobs.json: {e}")

    # 3. Sync Applications
    if settings.APPLICATIONS_PATH.exists():
        try:
            with open(settings.APPLICATIONS_PATH, "r", encoding="utf-8") as f:
                apps_raw = json.load(f)

            for i, app_item in enumerate(apps_raw):
                app_id = app_item.get("id", f"app_{i+1}")
                existing = session.query(ApplicationDB).filter_by(id=app_id).first()
                if not existing:
                    app_db = ApplicationDB(
                        id=app_id,
                        company=app_item.get("company", "Unknown"),
                        role=app_item.get("role", "Unknown"),
                        status=app_item.get("status", "Applied"),
                        applied_date=app_item.get("date", app_item.get("applied_date", "")),
                        notes=app_item.get("notes", ""),
                        source=app_item.get("source", "InternPilot"),
                        apply_url=app_item.get("apply_url", "")
                    )
                    session.add(app_db)
        except Exception as e:
            logger.warning(f"Could not sync applications.json: {e}")

    session.commit()
    session.close()
    logger.info("Database synchronized with JSON files successfully.")


def sync_db_to_json():
    """Dumps DB state back to JSON files to preserve complete file-level compatibility."""
    session = SessionLocal()
    try:
        # Dump jobs
        db_jobs = session.query(OpportunityDB).all()
        jobs_list = []
        for j in db_jobs:
            jobs_list.append({
                "id": j.id,
                "title": j.title,
                "company": j.company,
                "description": j.description,
                "type": j.opportunity_type,
                "opportunity_type": j.opportunity_type,
                "skills": json.loads(j.skills or "[]"),
                "location": j.location,
                "remote": j.remote,
                "stipend": j.stipend,
                "salary": j.salary,
                "experience": j.experience,
                "eligibility": j.eligibility,
                "deadline": j.deadline,
                "source": j.source,
                "source_url": j.source_url,
                "link": j.apply_url,
                "apply_url": j.apply_url,
                "application_url": j.application_url or j.apply_url,
                "posted_date": j.posted_date,
                "collected_date": j.collected_date,
                "status": j.status,
                "verification_status": j.verification_status or "VERIFIED",
                "verification_method": j.verification_method,
                "trust_level": j.trust_level or "OFFICIAL_COMPANY"
            })
        with open(settings.JOBS_PATH, "w", encoding="utf-8") as f:
            json.dump(jobs_list, f, indent=4)

        # Dump applications
        db_apps = session.query(ApplicationDB).all()
        apps_list = []
        for a in db_apps:
            apps_list.append({
                "id": a.id,
                "company": a.company,
                "role": a.role,
                "status": a.status,
                "date": a.applied_date,
                "applied_date": a.applied_date,
                "notes": a.notes
            })
        with open(settings.APPLICATIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(apps_list, f, indent=4)
    finally:
        session.close()
