"""Service for saving, unsaving, and querying student bookmarked opportunities."""

import json
from typing import List, Optional
from datetime import datetime, timezone
from backend.models.opportunity import Opportunity
from backend.models.saved_opportunity import SavedOpportunity
from backend.database.db import SessionLocal, SavedOpportunityDB, OpportunityDB
from backend.utils.logger import get_logger

logger = get_logger("saved_service")


def save_opportunity_for_student(
    opportunity_id: str,
    student_id: str = "default_student"
) -> SavedOpportunity:
    """Save/bookmark an opportunity for a student. Idempotent: prevents duplicate saves."""
    session = SessionLocal()
    try:
        # Verify opportunity exists
        opp = session.query(OpportunityDB).filter_by(id=opportunity_id).first()
        if not opp:
            raise ValueError(f"Opportunity '{opportunity_id}' does not exist")

        # Check existing save
        existing = session.query(SavedOpportunityDB).filter_by(
            student_id=student_id,
            opportunity_id=opportunity_id
        ).first()

        if existing:
            return SavedOpportunity(
                id=existing.id,
                student_id=existing.student_id,
                opportunity_id=existing.opportunity_id,
                created_at=existing.created_at.isoformat() if existing.created_at else datetime.now(timezone.utc).isoformat()
            )

        save_id = f"save_{student_id}_{opportunity_id}"
        now = datetime.now(timezone.utc)
        record = SavedOpportunityDB(
            id=save_id,
            student_id=student_id,
            opportunity_id=opportunity_id,
            created_at=now
        )
        session.add(record)
        session.commit()

        return SavedOpportunity(
            id=save_id,
            student_id=student_id,
            opportunity_id=opportunity_id,
            created_at=now.isoformat()
        )
    finally:
        session.close()


def unsave_opportunity_for_student(
    opportunity_id: str,
    student_id: str = "default_student"
) -> bool:
    """Remove a saved opportunity bookmark for a student."""
    session = SessionLocal()
    try:
        record = session.query(SavedOpportunityDB).filter_by(
            student_id=student_id,
            opportunity_id=opportunity_id
        ).first()

        if not record:
            return False

        session.delete(record)
        session.commit()
        return True
    finally:
        session.close()


def is_opportunity_saved(
    opportunity_id: str,
    student_id: str = "default_student"
) -> bool:
    """Check if an opportunity is currently bookmarked by the student."""
    session = SessionLocal()
    try:
        count = session.query(SavedOpportunityDB).filter_by(
            student_id=student_id,
            opportunity_id=opportunity_id
        ).count()
        return count > 0
    finally:
        session.close()


def get_saved_opportunity_ids(student_id: str = "default_student") -> List[str]:
    """Retrieve all opportunity IDs bookmarked by the student."""
    session = SessionLocal()
    try:
        records = session.query(SavedOpportunityDB.opportunity_id).filter_by(student_id=student_id).all()
        return [r[0] for r in records]
    finally:
        session.close()


def get_saved_opportunities_for_student(
    student_id: str = "default_student"
) -> List[Opportunity]:
    """Retrieve all full Opportunity objects saved by the student, ordered newest first."""
    session = SessionLocal()
    try:
        rows = (
            session.query(OpportunityDB)
            .join(SavedOpportunityDB, OpportunityDB.id == SavedOpportunityDB.opportunity_id)
            .filter(SavedOpportunityDB.student_id == student_id)
            .order_by(SavedOpportunityDB.created_at.desc())
            .all()
        )

        results: List[Opportunity] = []
        for row in rows:
            skills = json.loads(row.skills or "[]")
            results.append(Opportunity(
                id=row.id,
                title=row.title,
                company=row.company,
                description=row.description,
                opportunity_type=row.opportunity_type,
                skills=skills,
                location=row.location,
                remote=row.remote,
                stipend=row.stipend,
                salary=row.salary,
                experience=row.experience,
                eligibility=row.eligibility,
                deadline=row.deadline,
                source=row.source,
                source_url=row.source_url,
                apply_url=row.apply_url,
                posted_date=row.posted_date,
                collected_date=row.collected_date,
                status=row.status
            ))
        return results
    finally:
        session.close()
