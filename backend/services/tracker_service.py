"""Tracker service managing the student application lifecycle."""

import json
from datetime import date
from typing import List, Optional
from backend.models.application import Application
from backend.database.db import SessionLocal, ApplicationDB
from backend.database.sync import sync_db_to_json
from backend.utils.config import settings


def get_all_applications(student_id: Optional[str] = None) -> List[Application]:
    """Retrieve applications, optionally filtered by student_id."""
    session = SessionLocal()
    try:
        query = session.query(ApplicationDB)
        if student_id:
            query = query.filter((ApplicationDB.student_id == student_id) | (ApplicationDB.student_id == "default_student"))
        db_apps = query.all()
        return [
            Application(
                id=a.id,
                company=a.company,
                role=a.role,
                opportunity_id=a.opportunity_id,
                status=a.status,
                applied_date=a.applied_date,
                notes=a.notes,
                source=a.source,
                apply_url=a.apply_url,
            )
            for a in db_apps
        ]
    finally:
        session.close()


def add_application(
    company: str,
    role: str,
    status: str = "Applied",
    notes: str = "",
    opportunity_id: Optional[str] = None,
    apply_url: str = "",
    student_id: str = "default_student",
) -> Application:
    """Create a new tracked application record or update existing if opportunity_id already tracked."""
    session = SessionLocal()
    try:
        # Check if already tracked for this opportunity
        if opportunity_id:
            existing = session.query(ApplicationDB).filter_by(
                opportunity_id=opportunity_id,
                student_id=student_id,
            ).first()
            if existing:
                existing.status = status
                if notes:
                    existing.notes = notes
                if apply_url:
                    existing.apply_url = apply_url
                session.commit()
                app_obj = Application(
                    id=existing.id,
                    company=existing.company,
                    role=existing.role,
                    opportunity_id=existing.opportunity_id,
                    status=existing.status,
                    applied_date=existing.applied_date,
                    notes=existing.notes,
                    source=existing.source,
                    apply_url=existing.apply_url,
                )
                return app_obj

        app_id = f"app_{session.query(ApplicationDB).count() + 1}"
        db_app = ApplicationDB(
            id=app_id,
            student_id=student_id,
            company=company,
            role=role,
            opportunity_id=opportunity_id,
            status=status,
            applied_date=date.today().isoformat(),
            notes=notes,
            source="Student Career Hub",
            apply_url=apply_url,
        )
        session.add(db_app)
        session.commit()

        app_obj = Application(
            id=app_id,
            company=company,
            role=role,
            opportunity_id=opportunity_id,
            status=status,
            applied_date=date.today().isoformat(),
            notes=notes,
            source="Student Career Hub",
            apply_url=apply_url,
        )
    finally:
        session.close()

    sync_db_to_json()
    return app_obj


def update_application_status(
    app_id: str,
    new_status: str,
    notes: Optional[str] = None,
    student_id: Optional[str] = None,
) -> Optional[Application]:
    """Update status (e.g. Applied -> Interviewing -> Offer), guarding by student_id if provided."""
    session = SessionLocal()
    try:
        query = session.query(ApplicationDB).filter_by(id=app_id)
        if student_id:
            query = query.filter((ApplicationDB.student_id == student_id) | (ApplicationDB.student_id == "default_student"))
        db_app = query.first()
        if not db_app:
            return None

        db_app.status = new_status
        if notes is not None:
            db_app.notes = notes
        session.commit()

        app_obj = Application(
            id=db_app.id,
            company=db_app.company,
            role=db_app.role,
            opportunity_id=db_app.opportunity_id,
            status=db_app.status,
            applied_date=db_app.applied_date,
            notes=db_app.notes,
            source=db_app.source,
            apply_url=db_app.apply_url,
        )
    finally:
        session.close()

    sync_db_to_json()
    return app_obj
