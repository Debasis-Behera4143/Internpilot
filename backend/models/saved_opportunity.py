"""Domain model for student saved/bookmarked opportunities."""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field


class SavedOpportunity(BaseModel):
    """Represents an opportunity bookmarked by a student for later reference."""

    id: Optional[str] = Field(default=None, description="Unique bookmark ID")
    student_id: str = Field(default="default_student", description="Student ID who saved the opportunity")
    opportunity_id: str = Field(..., description="Foreign key reference to Opportunity ID")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Timestamp when saved"
    )

    def to_dict(self) -> dict:
        return self.model_dump()
