"""Domain model for student notification and alert preferences."""

from datetime import datetime, timezone
from pydantic import BaseModel, Field


class NotificationPreference(BaseModel):
    """Notification and alert settings for the student."""

    new_matching_opportunity: bool = Field(
        default=True,
        description="Notify when a new opportunity exceeds match threshold"
    )
    deadline_approaching: bool = Field(
        default=True,
        description="Alert 48 hours before tracked opportunity deadlines"
    )
    application_reminder: bool = Field(
        default=True,
        description="Remind to log status or follow up on submitted applications"
    )
    email_digest: bool = Field(
        default=False,
        description="Optional weekly digest summary"
    )

    def to_dict(self) -> dict:
        return self.model_dump()
