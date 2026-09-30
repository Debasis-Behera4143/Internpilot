"""Application model for tracking student internship and job application status."""

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class Application(BaseModel):
    """Represents an application lifecycle entry."""

    id: Optional[str] = Field(default=None, description="Unique application ID")
    company: str = Field(..., description="Target company")
    role: str = Field(..., description="Target role or job title")
    opportunity_id: Optional[str] = Field(default=None, description="Optional foreign key to Opportunity")
    status: str = Field(
        default="Applied",
        description="Status: Saved, Applied, Under Review, Interviewing, Offered, Rejected, Withdrawn"
    )
    applied_date: str = Field(
        default_factory=lambda: date.today().isoformat(),
        description="Date applied (YYYY-MM-DD)"
    )
    notes: Optional[str] = Field(default="", description="Student interview notes, recruiter contacts, or feedback")
    source: Optional[str] = Field(default="InternPilot Hub", description="Source where opportunity was found")
    apply_url: Optional[str] = Field(default="", description="Link to application page or portal")

    def to_dict(self) -> dict:
        return self.model_dump()
