"""Student profile data model representing the job/internship seeker."""

from typing import List, Optional
from pydantic import BaseModel, Field, EmailStr


class Student(BaseModel):
    """Student data model with academic, skill, and career preference information."""

    name: str = Field(..., description="Student's full name")
    email: str = Field(default="student@example.com", description="Contact email address")
    education: str = Field(default="B.Tech", description="Current or completed degree (e.g. B.Tech, B.S., M.Tech)")
    branch: str = Field(default="Computer Science & Engineering", description="Specialization or branch of study")
    graduation_year: int = Field(default=2026, description="Expected or completed year of graduation")
    cgpa: Optional[float] = Field(default=8.5, description="Cumulative Grade Point Average (scale of 10 or 4)")
    skills: List[str] = Field(default_factory=list, description="List of technical and soft skills")
    preferred_roles: List[str] = Field(
        default_factory=lambda: ["ML Intern", "Software Engineer Intern", "Data Science Intern"],
        description="Target job or internship titles"
    )
    preferred_locations: List[str] = Field(
        default_factory=lambda: ["Remote", "Bangalore", "Hyderabad", "Delhi NCR"],
        description="Preferred job locations"
    )
    remote_preference: bool = Field(default=True, description="Preference for remote work opportunities")
    phone: Optional[str] = Field(default=None, description="Contact telephone or mobile number")
    resume_path: Optional[str] = Field(default=None, description="Local or storage path to uploaded resume PDF/DOCX")

    # Optional additional fields for matching enrichment
    interests: List[str] = Field(default_factory=list, description="Academic and industry areas of interest")
    projects: List[str] = Field(default_factory=list, description="Notable academic or portfolio projects")
    experience: List[str] = Field(default_factory=list, description="Past internships, roles, or practical experience")
    certifications: List[str] = Field(default_factory=list, description="Professional or course certifications")
    bio: Optional[str] = Field(default="", description="Short student summary / pitch")

    def to_dict(self) -> dict:
        """Convert student model to dictionary."""
        return self.model_dump()

    def completeness_score(self) -> float:
        """Compute profile completeness percentage (0-100%)."""
        checks = [
            bool(self.name and self.name != "Student Candidate"),
            bool(self.email and "@" in self.email),
            bool(self.education),
            bool(self.branch),
            bool(self.graduation_year),
            bool(self.cgpa and self.cgpa > 0),
            bool(self.skills and len(self.skills) >= 3),
            bool(self.preferred_roles),
            bool(self.preferred_locations),
            bool(self.projects or self.experience),
            bool(self.bio and len(self.bio) > 15),
            bool(self.resume_path)
        ]
        return round((sum(1 for c in checks if c) / len(checks)) * 100.0, 1)

    def completeness_breakdown(self) -> dict:
        """Return percentage and detailed list of completed and missing profile sections."""
        items = [
            ("Personal Details", bool(self.name and self.name != "Student Candidate" and self.email and "@" in self.email)),
            ("Academic Details", bool(self.education and self.branch and self.graduation_year and self.cgpa and self.cgpa > 0)),
            ("Skills (at least 3)", bool(self.skills and len(self.skills) >= 3)),
            ("Career Preferences", bool(self.preferred_roles and self.preferred_locations)),
            ("Projects & Experience", bool(self.projects or self.experience)),
            ("Bio / Professional Pitch", bool(self.bio and len(self.bio) > 15)),
            ("Resume Document", bool(self.resume_path))
        ]
        completed = [name for name, ok in items if ok]
        missing = [name for name, ok in items if not ok]
        return {
            "score": self.completeness_score(),
            "completed": completed,
            "missing": missing
        }

    def get_search_text(self) -> str:
        """Return combined string representation for vector embedding and semantic matching."""
        from backend.ai.student_representation import get_student_representation
        return get_student_representation(self)

    @classmethod
    def from_legacy_profile(cls, legacy_dict: dict) -> "Student":
        """Convert legacy InternPilot profile dictionary into comprehensive Student model."""
        return cls(
            name=legacy_dict.get("name", "Student Candidate"),
            email=legacy_dict.get("email", "candidate@example.com"),
            education=legacy_dict.get("education", "B.Tech Computer Science"),
            branch=legacy_dict.get("branch", "Artificial Intelligence & Data Science"),
            graduation_year=legacy_dict.get("graduation_year", 2026),
            cgpa=legacy_dict.get("cgpa", 8.8),
            skills=legacy_dict.get("skills", ["Python", "Machine Learning", "Data Analysis"]),
            preferred_roles=legacy_dict.get("preferred_roles", ["ML Intern", "AI Intern"]),
            preferred_locations=legacy_dict.get("preferred_locations", ["Remote", "Bangalore"]),
            remote_preference=legacy_dict.get("remote_preference", True),
            resume_path=legacy_dict.get("resume_path", None),
            interests=legacy_dict.get("interests", ["AI", "FinTech", "Research"]),
            bio=legacy_dict.get("bio", f"Aspiring AI/ML engineer focused on applied machine learning.")
        )
