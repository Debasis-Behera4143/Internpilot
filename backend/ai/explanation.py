"""Explainable Recommendation Engine.

Generates deterministic, transparent natural language explanations for student-opportunity matches
based on calculated multi-factor subscores without relying on costly or non-deterministic LLMs.
"""

from typing import List, Dict, Any, Optional


def generate_recommendation_explanation(
    match_score: float,
    matched_skills: List[str],
    missing_skills: List[str],
    role_score: float,
    eligibility_status: str,
    location_score: float,
    is_remote: bool,
    student_remote_pref: bool,
    job_location: str = "Remote",
    job_title: str = "",
    company: str = ""
) -> Dict[str, Any]:
    """Generate structured and natural-language rationale for a recommendation."""
    reasons: List[str] = []
    improvements: List[str] = []

    # 1. Headline Assessment
    if match_score >= 80:
        headline = "Strong match"
    elif match_score >= 60:
        headline = "Good match"
    elif match_score >= 40:
        headline = "Moderate match"
    else:
        headline = "Potential stretch match"

    # 2. Skill Rationale
    if matched_skills:
        top_skills = matched_skills[:4]
        skills_phrase = ", ".join(top_skills)
        reasons.append(f"Your {skills_phrase} {'skills match' if len(top_skills) > 1 else 'skill matches'} role requirements")
    else:
        reasons.append("Your academic background provides transferable foundations for this role")

    # 3. Role Alignment
    if role_score >= 0.7:
        reasons.append(f"Target role aligns directly with {job_title}")
    elif role_score >= 0.4:
        reasons.append("Role offers adjacent experience in your field")

    # 4. Location & Remote Compatibility
    if is_remote and student_remote_pref:
        reasons.append("Remote flexibility matches your preference")
    elif location_score >= 0.8:
        reasons.append(f"Office location ({job_location}) matches your preferred cities")
    elif not is_remote:
        improvements.append(f"On-site position located in {job_location}")

    # 5. Missing Skills Roadmap
    if missing_skills:
        top_missing = missing_skills[:3]
        for s in top_missing:
            improvements.append(f"Familiarity with {s} is advantageous")

    # 6. Eligibility Check
    eligibility_badge = "Eligible"
    if eligibility_status == "possibly_eligible":
        eligibility_badge = "Possibly Eligible"
        improvements.append("Check employer degree/batch requirements")
    elif eligibility_status == "not_eligible":
        eligibility_badge = "Review Eligibility"
        improvements.append("Eligibility criteria (e.g. batch or branch) may differ")

    # Assemble cohesive multi-sentence explanation text
    sentences = [f"{headline} for your profile."]
    if matched_skills:
        skills_str = ", ".join(matched_skills[:3])
        sentences.append(f"Your {skills_str} {'skills match' if len(matched_skills[:3]) > 1 else 'skill matches'} the position at {company}.")
    
    if is_remote and student_remote_pref:
        sentences.append("The job is remote, which aligns with your preferences.")
    elif location_score >= 0.8:
        sentences.append(f"The role is located in {job_location}, matching your preferences.")
    elif not is_remote:
        sentences.append(f"Note that this position is on-site in {job_location}.")

    if missing_skills:
        missing_str = ", ".join(missing_skills[:2])
        sentences.append(f"Adding {missing_str} to your portfolio could strengthen your candidacy.")

    summary_text = " ".join(sentences)

    return {
        "summary": summary_text,
        "headline": headline,
        "reasons": reasons,
        "improvements": improvements,
        "eligibility_badge": eligibility_badge
    }
