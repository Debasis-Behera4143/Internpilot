"""Skill gap analysis engine for comparing student capabilities with opportunity requirements.

Identifies matched vs missing skills, handles canonical skill aliases, and classifies
missing skills into actionable priority tiers (high, medium, optional).
"""

import re
from typing import List, Dict, Any, Union
from backend.ai.skill_dictionary import canonicalize_skill


def find_skill_gaps(profile_skills: List[str], job_skills: List[str]) -> List[str]:
    """Identify required job skills that are missing from candidate profile skills.
    Performs case-insensitive and canonical alias matching.
    """
    if not job_skills:
        return []

    profile_canonical = {
        canonicalize_skill(s).lower()
        for s in profile_skills if s and s.strip()
    }
    missing = []

    for skill in job_skills:
        clean = skill.strip()
        if not clean:
            continue
        canon = canonicalize_skill(clean)
        if canon.lower() not in profile_canonical and clean.lower() not in profile_canonical:
            missing.append(canon)

    # Deduplicate while preserving order
    seen = set()
    result = []
    for s in missing:
        if s.lower() not in seen:
            seen.add(s.lower())
            result.append(s)
    return result


def analyze_skill_gap(profile_skills: List[str], job_skills: List[str]) -> Dict[str, Any]:
    """Comprehensive skill analysis providing match percentage, matching skills, and missing skills."""
    if not job_skills:
        return {
            "match_percentage": 100.0,
            "matching_skills": [canonicalize_skill(s) for s in profile_skills],
            "missing_skills": [],
            "total_required": 0
        }

    profile_canonical = {
        canonicalize_skill(s).lower()
        for s in profile_skills if s and s.strip()
    }
    matching = []
    missing = []

    for skill in job_skills:
        clean = skill.strip()
        if not clean:
            continue
        canon = canonicalize_skill(clean)
        if canon.lower() in profile_canonical or clean.lower() in profile_canonical:
            matching.append(canon)
        else:
            missing.append(canon)

    # Deduplicate
    matching = list(dict.fromkeys(matching))
    missing = list(dict.fromkeys(missing))

    total = len(matching) + len(missing)
    match_pct = round((len(matching) / total) * 100.0, 1) if total > 0 else 100.0

    return {
        "match_percentage": match_pct,
        "matching_skills": matching,
        "missing_skills": missing,
        "total_required": total
    }


def classify_missing_skills(
    missing_skills: List[str],
    job_title: str = "",
    job_description: str = ""
) -> Dict[str, List[str]]:
    """Classify missing skills into actionable learning tiers:
    - High Priority: Appears in job title or explicitly stated as mandatory/required.
    - Medium Priority: Standard required skill from listing.
    - Optional: Described as preferred, nice-to-have, bonus, or secondary.
    """
    categorized: Dict[str, List[str]] = {
        "high_priority": [],
        "medium_priority": [],
        "optional": []
    }

    if not missing_skills:
        return categorized

    desc_lower = job_description.lower()
    title_lower = job_title.lower()

    # Regex patterns for mandatory vs optional contexts
    optional_patterns = [
        re.compile(r"(?:preferred|nice to have|good to have|plus|bonus|optional|advantageous)[\s\w,.:-]{0,50}\b" + re.escape(s.lower()) + r"\b", re.IGNORECASE)
        for s in missing_skills
    ]
    mandatory_patterns = [
        re.compile(r"(?:must have|required|mandatory|essential|strong proficiency in)[\s\w,.:-]{0,50}\b" + re.escape(s.lower()) + r"\b", re.IGNORECASE)
        for s in missing_skills
    ]

    for idx, skill in enumerate(missing_skills):
        s_lower = skill.lower()
        # High priority if present in job title
        if s_lower in title_lower or mandatory_patterns[idx].search(desc_lower):
            categorized["high_priority"].append(skill)
        elif optional_patterns[idx].search(desc_lower):
            categorized["optional"].append(skill)
        else:
            categorized["medium_priority"].append(skill)

    return categorized


def compute_detailed_skill_gap(
    profile_skills: List[str],
    job_skills: List[str],
    job_title: str = "",
    job_description: str = ""
) -> Dict[str, Any]:
    """Compute complete skill gap breakdown with prioritized missing skill roadmap."""
    gap_data = analyze_skill_gap(profile_skills, job_skills)
    missing = gap_data["missing_skills"]
    categorized = classify_missing_skills(missing, job_title, job_description)

    return {
        "required_skills": [canonicalize_skill(s) for s in job_skills],
        "student_skills": [canonicalize_skill(s) for s in profile_skills],
        "matched_skills": gap_data["matching_skills"],
        "missing_skills": missing,
        "categorized_missing": categorized,
        "match_percentage": gap_data["match_percentage"],
        "total_required": gap_data["total_required"]
    }
