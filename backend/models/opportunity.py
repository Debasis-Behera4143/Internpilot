"""Opportunity data model for student opportunities (internships, full-time, research, etc.)."""

from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class Opportunity(BaseModel):
    """Opportunity entity representing an internship, job, fellowship, or research role."""

    id: Optional[str] = Field(default=None, description="Unique identifier (e.g. hash or UUID)")
    title: str = Field(..., description="Job or internship title")
    company: str = Field(default="Unknown", description="Hiring organization / company")
    description: str = Field(default="", description="Detailed opportunity description or summary")
    opportunity_type: str = Field(default="internship", description="Type: internship, full-time, fellowship, research")
    skills: List[str] = Field(default_factory=list, description="Required or preferred skills")
    location: str = Field(default="Remote", description="Job location (city, state, country)")
    remote: bool = Field(default=True, description="Whether remote work is supported")
    stipend: Optional[str] = Field(default=None, description="Monthly or total stipend for interns")
    salary: Optional[str] = Field(default=None, description="Annual salary range or compensation")
    experience: str = Field(default="Fresher / Student", description="Experience level required")
    eligibility: str = Field(default="All students / freshers", description="Degree or eligibility criteria")
    deadline: Optional[str] = Field(default=None, description="Application deadline date (YYYY-MM-DD)")
    source: str = Field(default="direct", description="Data source name (yc, wellfound, internshala, etc.)")
    source_channel: Optional[str] = Field(default=None, description="Specific channel name if from multi-channel source (e.g. Telegram)")
    source_url: str = Field(default="", description="URL of the source platform listing")
    apply_url: str = Field(..., description="Direct application or company link")
    application_url: Optional[str] = Field(default=None, description="Verified direct application or career portal link")
    normalized_url: Optional[str] = Field(default=None, description="Normalized de-tracked URL")
    posted_date: Optional[str] = Field(default=None, description="Date originally posted (YYYY-MM-DD)")
    collected_date: str = Field(
        default_factory=lambda: date.today().isoformat(),
        description="Date collected by the system (YYYY-MM-DD)"
    )
    status: str = Field(default="open", description="Status: open, closed, applied, expired")
    raw_text: Optional[str] = Field(default=None, description="Original raw post or message text for traceability")

    # Source-aware Verification and Trust fields
    verification_status: str = Field(default="UNVERIFIED", description="Status: VERIFIED, PENDING_REVIEW, REJECTED, UNVERIFIED")
    verification_method: Optional[str] = Field(default=None, description="Method: OFFICIAL_COMPANY_SOURCE, ADMIN_VERIFIED, AUTHORIZED_FEED, etc.")
    verified_at: Optional[str] = Field(default=None, description="ISO timestamp when verified")
    verified_by: Optional[str] = Field(default=None, description="Admin email or identifier")
    verification_notes: Optional[str] = Field(default=None, description="Audit notes / justification")
    trust_level: str = Field(default="UNVERIFIED_EXTERNAL", description="Source trust: OFFICIAL_COMPANY, AUTHORIZED_API, EMPLOYER_SUBMITTED, COLLEGE_SUBMITTED, UNVERIFIED_EXTERNAL")
    verification_checks: Optional[str] = Field(default="{}", description="JSON string of verification checks")
    work_mode: Optional[str] = Field(default=None, description="Work mode: remote, hybrid, on-site")
    source_id: Optional[str] = Field(default=None, description="Registered Source ID")

    def model_post_init(self, __context) -> None:
        if not self.application_url and self.apply_url:
            self.application_url = self.apply_url
        elif not self.apply_url and self.application_url:
            self.apply_url = self.application_url
        if not self.normalized_url and self.apply_url:
            self.normalized_url = self.apply_url

    # Additional analytical fields
    match_score: Optional[float] = Field(default=None, description="Calculated AI match score (0-100)")
    missing_skills: List[str] = Field(default_factory=list, description="Identified skill gaps for student")

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dictionary."""
        return self.model_dump()

    def to_student_dict(self) -> dict:
        """Convert to a sanitized dictionary strictly excluding Telegram channels, post URLs, and raw text."""
        mode = "Remote" if self.remote else ("Hybrid" if ("hybrid" in (self.location or "").lower() or "hybrid" in (self.description or "").lower()) else "On-site")
        return StudentOpportunity(
            id=self.id,
            title=self.title,
            company=self.company,
            description=self.description,
            opportunity_type=self.opportunity_type,
            skills=self.skills,
            location=self.location,
            remote=self.remote,
            work_mode=mode,
            stipend=self.stipend,
            salary=self.salary,
            experience=self.experience,
            eligibility=self.eligibility,
            deadline=self.deadline,
            apply_url=self.apply_url,
            application_url=self.application_url or self.apply_url,
            posted_date=self.posted_date or self.collected_date or date.today().isoformat(),
            status=self.status,
            verification_status=self.verification_status,
            is_verified=(self.verification_status == "VERIFIED"),
            verification_method=self.verification_method,
            trust_level=self.trust_level,
            match_score=self.match_score,
            missing_skills=self.missing_skills,
        ).model_dump()


    @classmethod
    def from_legacy_job(cls, legacy_dict: dict) -> "Opportunity":
        """Convert legacy InternPilot job dict {title, link, type, description, source} into Opportunity."""
        title = legacy_dict.get("title", "Untitled Opportunity")
        link = legacy_dict.get("link", "")
        source = legacy_dict.get("source", "legacy")
        opp_type = legacy_dict.get("type", "internship")
        desc = legacy_dict.get("description", title)

        # Infer company from title if structured like "Company • Description" or "Role, Company"
        company = "Unknown"
        if "•" in title:
            parts = title.split("•", 1)
            company = parts[0].strip()
        elif ", " in title:
            parts = title.rsplit(", ", 1)
            company = parts[1].strip()

        # Extract common tech keywords as skills from description and title
        keywords = [
            "Python", "PyTorch", "TensorFlow", "Machine Learning", "Deep Learning",
            "Data Science", "SQL", "Docker", "FastAPI", "React", "Node.js", "Java",
            "C++", "Computer Vision", "NLP", "Analytics", "AWS", "Git"
        ]
        combined_text = f"{title} {desc}".lower()
        extracted_skills = [kw for kw in keywords if kw.lower() in combined_text]

        # Determine if remote
        remote = "remote" in combined_text or "anywhere" in combined_text

        return cls(
            title=title,
            company=company,
            description=desc,
            opportunity_type=opp_type,
            skills=extracted_skills,
            location="Remote" if remote else "India / Global",
            remote=remote,
            stipend=None,
            salary=None,
            experience="Fresher / Student",
            eligibility="Undergraduate / Postgraduate",
            deadline=None,
            source=source,
            source_url=link,
            apply_url=link,
            posted_date=date.today().isoformat(),
            collected_date=date.today().isoformat(),
            status="open"
        )


class StudentOpportunity(BaseModel):
    """Sanitized student-facing opportunity schema strictly omitting internal sources and raw text."""
    id: Optional[str] = None
    title: str
    company: str = "Unknown"
    description: str = ""
    opportunity_type: str = "internship"
    skills: List[str] = Field(default_factory=list)
    location: str = "Remote"
    remote: bool = True
    work_mode: Optional[str] = "Remote"
    stipend: Optional[str] = None
    salary: Optional[str] = None
    experience: str = "Fresher / Student"
    eligibility: str = "All students / freshers"
    deadline: Optional[str] = None
    apply_url: str
    application_url: Optional[str] = None
    posted_date: Optional[str] = None
    status: str = "open"
    verification_status: str = "UNVERIFIED"
    is_verified: bool = False
    verification_method: Optional[str] = None
    trust_level: str = "UNVERIFIED_EXTERNAL"
    match_score: Optional[float] = None
    missing_skills: List[str] = Field(default_factory=list)

