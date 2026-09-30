"""Opportunity text representation synthesizer for semantic embedding.

Transforms structured Opportunity attributes into a concise, information-rich
textual format optimized for dense vector representation models.
"""

from typing import Union, Dict, Any
from backend.models.opportunity import Opportunity


def get_job_representation(opportunity: Union[Opportunity, Dict[str, Any]]) -> str:
    """Generate clean textual representation of an opportunity for embedding.
    
    Combines role title, company, required skills, location, remote availability,
    experience level, eligibility criteria, and concise role summary without
    irrelevant metadata or URLs.
    """
    if isinstance(opportunity, Opportunity):
        title = opportunity.title
        company = opportunity.company
        opp_type = opportunity.opportunity_type
        skills = opportunity.skills
        location = opportunity.location
        remote_str = "Yes" if opportunity.remote else "No"
        experience = opportunity.experience
        eligibility = opportunity.eligibility
        desc = opportunity.description
    else:
        title = opportunity.get("title", "Untitled Role")
        company = opportunity.get("company", "Company")
        opp_type = opportunity.get("opportunity_type", opportunity.get("type", "internship"))
        skills = opportunity.get("skills", [])
        location = opportunity.get("location", "Remote")
        remote_val = opportunity.get("remote", True)
        remote_str = "Yes" if remote_val else "No"
        experience = opportunity.get("experience", "Fresher / Student")
        eligibility = opportunity.get("eligibility", "All students")
        desc = opportunity.get("description", "")

    skills_formatted = ", ".join(skills) if skills else "General technical skills"

    # Truncate overly verbose descriptions to keep focus on key competencies
    clean_desc = (desc[:300] + "...") if len(desc) > 300 else desc

    parts = [
        f"{title} at {company} ({opp_type}).",
        f"Required skills: {skills_formatted}.",
        f"Location: {location}.",
        f"Remote: {remote_str}.",
        f"Experience: {experience}.",
        f"Eligibility: {eligibility}."
    ]

    if clean_desc and clean_desc != title:
        parts.append(f"Summary: {clean_desc}")

    return " ".join(parts)
