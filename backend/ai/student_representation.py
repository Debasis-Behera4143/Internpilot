"""Student text representation synthesizer for semantic embedding.

Transforms candidate academic credentials, competencies, technical projects,
and career aspirations into a dense textual profile suitable for semantic search.
"""

from typing import Union, Dict, Any
from backend.models.student import Student


def get_student_representation(student: Union[Student, Dict[str, Any]]) -> str:
    """Generate rich textual representation of a student for semantic embedding.
    
    Combines degree, branch of study, technical competencies, target job roles,
    portfolio projects, professional experience, certifications, and location/remote preferences.
    """
    if isinstance(student, Student):
        education = student.education
        branch = student.branch
        skills = student.skills
        interests = student.interests
        preferred_roles = student.preferred_roles
        preferred_locations = student.preferred_locations
        remote_pref = student.remote_preference
        projects = getattr(student, "projects", [])
        experience = getattr(student, "experience", [])
        certifications = getattr(student, "certifications", [])
        bio = student.bio
    else:
        education = student.get("education", "B.Tech")
        branch = student.get("branch", "Computer Science")
        skills = student.get("skills", [])
        interests = student.get("interests", [])
        preferred_roles = student.get("preferred_roles", [])
        preferred_locations = student.get("preferred_locations", [])
        remote_pref = student.get("remote_preference", True)
        projects = student.get("projects", [])
        experience = student.get("experience", [])
        certifications = student.get("certifications", [])
        bio = student.get("bio", "")

    skills_str = ", ".join(skills) if skills else "General problem solving"
    roles_str = ", ".join(preferred_roles) if preferred_roles else "Software Engineering"
    loc_str = ", ".join(preferred_locations) if preferred_locations else "Remote"
    remote_text = "Remote friendly" if remote_pref else "Prefers on-site"

    parts = [
        f"{branch} student pursuing {education}.",
        f"Skills: {skills_str}.",
        f"Target roles: {roles_str}.",
        f"Preferred locations: {loc_str} ({remote_text})."
    ]

    if interests:
        parts.append(f"Interests: {', '.join(interests)}.")

    if projects:
        # Take top 3 projects
        parts.append(f"Projects: {'; '.join(projects[:3])}.")

    if experience:
        parts.append(f"Experience: {'; '.join(experience[:2])}.")

    if certifications:
        parts.append(f"Certifications: {', '.join(certifications[:3])}.")

    if bio:
        parts.append(f"Bio: {bio}")

    return " ".join(parts)
