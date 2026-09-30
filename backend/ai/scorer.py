"""Hybrid AI Career Match Scorer with multi-factor explainable ranking.

Calculates match compatibility between student profiles and opportunities across:
1. Semantic vector similarity (SentenceTransformers cosine similarity) [35%]
2. Technical skill compatibility (matched vs required skills) [30%]
3. Role preference alignment [15%]
4. Academic and branch eligibility [10%]
5. Location and remote work preference [5%]
6. Experience level alignment [5%]

100% local, free, and deterministic without paid API dependencies.
"""

import re
import json
from difflib import SequenceMatcher
from typing import Optional, Union, Dict, Any, Tuple, List

from backend.ai.embedder import (
    embed_student,
    embed_opportunity,
    calculate_similarity
)
from backend.ai.skill_dictionary import canonicalize_skill
from backend.ai.skill_gap import analyze_skill_gap
from backend.ai.explanation import generate_recommendation_explanation
from backend.models.opportunity import Opportunity
from backend.models.student import Student
from backend.utils.config import settings
from backend.utils.logger import get_logger

logger = get_logger("ai_scorer")

_default_student_profile: Optional[Student] = None


def load_default_profile() -> Student:
    """Lazily load default student profile from data/profile.json."""
    global _default_student_profile
    if _default_student_profile is None:
        if settings.PROFILE_PATH.exists():
            try:
                with open(settings.PROFILE_PATH, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                _default_student_profile = Student.from_legacy_profile(raw)
            except Exception as e:
                logger.warning(f"Failed to parse profile.json: {e}")
                _default_student_profile = Student(name="Student Candidate")
        else:
            _default_student_profile = Student(name="Student Candidate")
    return _default_student_profile


def calculate_semantic_score(
    student: Union[Student, Dict[str, Any]],
    job: Union[Opportunity, Dict[str, Any]]
) -> float:
    """Compute dense cosine similarity between student and opportunity representations (0.0 to 1.0)."""
    s_emb = embed_student(student)
    j_emb = embed_opportunity(job)
    return calculate_similarity(s_emb, j_emb)


def calculate_skill_score(
    student_skills: List[str],
    job_skills: List[str]
) -> Tuple[float, List[str], List[str]]:
    """Calculate skill compatibility score, matched skills list, and missing skills list."""
    if not job_skills:
        # If job lists no explicit skills, assign a neutral-positive 0.75 score
        return (0.75, [canonicalize_skill(s) for s in student_skills], [])

    gap = analyze_skill_gap(student_skills, job_skills)
    matched = gap["matching_skills"]
    missing = gap["missing_skills"]
    score = gap["match_percentage"] / 100.0

    return (score, matched, missing)


def calculate_role_score(
    preferred_roles: List[str],
    job_title: str
) -> float:
    """Calculate alignment between student target roles and opportunity title (0.0 to 1.0)."""
    if not preferred_roles or not job_title:
        return 0.5

    clean_title = job_title.lower()
    best_ratio = 0.0

    for role in preferred_roles:
        clean_role = role.lower()
        # Direct substring containment
        if clean_role in clean_title or clean_title in clean_role:
            return 1.0

        # Token overlap
        role_tokens = set(re.findall(r"\w+", clean_role))
        title_tokens = set(re.findall(r"\w+", clean_title))
        overlap = role_tokens.intersection(title_tokens)
        if overlap:
            token_score = len(overlap) / max(len(role_tokens), 1)
            best_ratio = max(best_ratio, token_score)

        # Sequence matcher ratio
        seq_ratio = SequenceMatcher(None, clean_role, clean_title).ratio()
        best_ratio = max(best_ratio, seq_ratio)

    return min(1.0, max(0.2, best_ratio))


def evaluate_eligibility(
    student: Union[Student, Dict[str, Any]],
    job: Union[Opportunity, Dict[str, Any]]
) -> Tuple[float, str]:
    """Evaluate eligibility criteria returning (score, status).
    Status values: 'eligible', 'possibly_eligible', 'not_eligible'.
    """
    eligibility_text = ""
    if isinstance(job, Opportunity):
        eligibility_text = (job.eligibility or "").lower()
        desc = (job.description or "").lower()
    else:
        eligibility_text = str(job.get("eligibility", "")).lower()
        desc = str(job.get("description", "")).lower()

    if isinstance(student, Student):
        cgpa = student.cgpa or 8.0
        grad_year = student.graduation_year or 2026
        branch = (student.branch or "").lower()
    else:
        cgpa = float(student.get("cgpa", 8.0) or 8.0)
        grad_year = int(student.get("graduation_year", 2026) or 2026)
        branch = str(student.get("branch", "")).lower()

    combined = f"{eligibility_text} {desc}"

    # 1. CGPA check
    cgpa_req = re.search(r"(?:minimum|min|at least)?\s*([6789]\.[0-9])\s*(?:cgpa|gpa)", combined)
    if cgpa_req:
        min_cgpa = float(cgpa_req.group(1))
        if cgpa < min_cgpa:
            return (0.3, "not_eligible")

    # 2. Graduation year check
    batch_matches = re.findall(r"\b(202[0-9])\s*(?:batch|passout|graduates|passing)?\b", combined)
    if batch_matches:
        batches = [int(b) for b in batch_matches]
        if grad_year not in batches and not any(abs(grad_year - b) <= 1 for b in batches):
            return (0.5, "possibly_eligible")

    # 3. Branch criteria
    if "computer science only" in combined or "cse only" in combined:
        if not any(k in branch for k in ["computer", "cse", "software", "ai", "data"]):
            return (0.4, "not_eligible")

    # Default to eligible if criteria met or open to all
    if not eligibility_text or "all" in eligibility_text or "any" in eligibility_text or "open" in eligibility_text:
        return (1.0, "eligible")

    return (0.9, "eligible")


def calculate_location_score(
    student: Union[Student, Dict[str, Any]],
    job: Union[Opportunity, Dict[str, Any]]
) -> float:
    """Calculate location & remote work compatibility score (0.0 to 1.0)."""
    if isinstance(job, Opportunity):
        job_remote = job.remote
        job_location = (job.location or "").lower()
    else:
        job_remote = bool(job.get("remote", True))
        job_location = str(job.get("location", "")).lower()

    if isinstance(student, Student):
        student_remote_pref = student.remote_preference
        pref_locs = [l.lower() for l in student.preferred_locations]
    else:
        student_remote_pref = bool(student.get("remote_preference", True))
        pref_locs = [str(l).lower() for l in student.get("preferred_locations", [])]

    # Perfect match: Remote job for student who likes remote
    if job_remote and student_remote_pref:
        return 1.0

    # City match
    for loc in pref_locs:
        if loc and (loc in job_location or job_location in loc):
            return 1.0

    # Remote job for student without strong remote preference
    if job_remote:
        return 0.85

    # On-site in unlisted city
    return 0.4


def calculate_experience_score(
    student: Union[Student, Dict[str, Any]],
    job: Union[Opportunity, Dict[str, Any]]
) -> float:
    """Calculate experience level match score (0.0 to 1.0)."""
    if isinstance(job, Opportunity):
        exp = (job.experience or "").lower()
        opp_type = (job.opportunity_type or "").lower()
    else:
        exp = str(job.get("experience", "")).lower()
        opp_type = str(job.get("opportunity_type", job.get("type", ""))).lower()

    # Students / freshers match internships, entry-level, and fresher roles
    if "fresher" in exp or "student" in exp or "intern" in opp_type or "entry" in exp or "0-1" in exp:
        return 1.0
    if "senior" in exp or "lead" in exp or "5+" in exp or "4+" in exp:
        return 0.3
    return 0.85


def calculate_match_details(
    job: Union[Opportunity, Dict[str, Any]],
    student: Optional[Union[Student, Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Execute complete hybrid multi-signal matching between a student and opportunity.
    Returns structured scoring breakdown, subscores, eligibility, and explainability text.
    """
    if student is None:
        student = load_default_profile()

    # Resolve properties
    if isinstance(job, Opportunity):
        job_skills = job.skills
        job_title = job.title
        company = job.company
        is_remote = job.remote
        location = job.location
    else:
        job_skills = job.get("skills", [])
        job_title = job.get("title", "Opportunity")
        company = job.get("company", "Company")
        is_remote = bool(job.get("remote", True))
        location = job.get("location", "Remote")

    if isinstance(student, Student):
        student_skills = student.skills
        student_roles = student.preferred_roles
        student_remote_pref = student.remote_preference
    else:
        student_skills = student.get("skills", [])
        student_roles = student.get("preferred_roles", [])
        student_remote_pref = bool(student.get("remote_preference", True))

    # Calculate individual subscores (each in [0.0, 1.0])
    semantic_score = calculate_semantic_score(student, job)
    skill_score, matched_skills, missing_skills = calculate_skill_score(student_skills, job_skills)
    role_score = calculate_role_score(student_roles, job_title)
    eligibility_score, eligibility_status = evaluate_eligibility(student, job)
    location_score = calculate_location_score(student, job)
    experience_score = calculate_experience_score(student, job)

    # Weighted Hybrid Combination (Total weights sum to 1.0)
    weighted_sum = (
        settings.WEIGHT_SEMANTIC * semantic_score +
        settings.WEIGHT_SKILL * skill_score +
        settings.WEIGHT_ROLE * role_score +
        settings.WEIGHT_ELIGIBILITY * eligibility_score +
        settings.WEIGHT_LOCATION * location_score +
        settings.WEIGHT_EXPERIENCE * experience_score
    )

    final_percentage = round(max(0.0, min(100.0, weighted_sum * 100.0)), 2)

    # Generate transparent explanation
    explanation = generate_recommendation_explanation(
        match_score=final_percentage,
        matched_skills=matched_skills,
        missing_skills=missing_skills,
        role_score=role_score,
        eligibility_status=eligibility_status,
        location_score=location_score,
        is_remote=is_remote,
        student_remote_pref=student_remote_pref,
        job_location=location,
        job_title=job_title,
        company=company
    )

    return {
        "match_score": final_percentage,
        "semantic_score": round(semantic_score, 3),
        "skill_score": round(skill_score, 3),
        "role_score": round(role_score, 3),
        "eligibility_score": round(eligibility_score, 3),
        "location_score": round(location_score, 3),
        "experience_score": round(experience_score, 3),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "eligibility": eligibility_status,
        "explanation": explanation["summary"],
        "explanation_details": explanation
    }


def score_job(
    job: Union[Dict[str, Any], Opportunity],
    student: Optional[Student] = None
) -> float:
    """Calculate overall hybrid match score (0-100%).
    Fully backwards-compatible with legacy InternPilot score_job(job) signature.
    """
    details = calculate_match_details(job, student=student)
    return details["match_score"]
