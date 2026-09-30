"""Service for managing student notification preferences."""

from datetime import datetime, timezone
from backend.models.preferences import NotificationPreference
from backend.database.db import SessionLocal, NotificationPreferenceDB
from backend.utils.logger import get_logger

logger = get_logger("preference_service")


def get_notification_preferences(student_id: str = "default_student") -> NotificationPreference:
    """Retrieve notification preferences for a student."""
    session = SessionLocal()
    try:
        record = session.query(NotificationPreferenceDB).filter_by(student_id=student_id).first()
        if not record:
            # Create default preferences
            record = NotificationPreferenceDB(
                student_id=student_id,
                new_matching_opportunity=True,
                deadline_approaching=True,
                application_reminder=True,
                email_digest=False
            )
            session.add(record)
            session.commit()

        return NotificationPreference(
            new_matching_opportunity=record.new_matching_opportunity,
            deadline_approaching=record.deadline_approaching,
            application_reminder=record.application_reminder,
            email_digest=record.email_digest
        )
    finally:
        session.close()


def update_notification_preferences(
    prefs: NotificationPreference,
    student_id: str = "default_student"
) -> NotificationPreference:
    """Update notification preferences for a student."""
    session = SessionLocal()
    try:
        record = session.query(NotificationPreferenceDB).filter_by(student_id=student_id).first()
        if not record:
            record = NotificationPreferenceDB(student_id=student_id)
            session.add(record)

        record.new_matching_opportunity = prefs.new_matching_opportunity
        record.deadline_approaching = prefs.deadline_approaching
        record.application_reminder = prefs.application_reminder
        record.email_digest = prefs.email_digest
        record.updated_at = datetime.now(timezone.utc)

        session.commit()

        return NotificationPreference(
            new_matching_opportunity=record.new_matching_opportunity,
            deadline_approaching=record.deadline_approaching,
            application_reminder=record.application_reminder,
            email_digest=record.email_digest
        )
    finally:
        session.close()
