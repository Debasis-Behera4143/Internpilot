"""Matching service connecting student profiles with opportunities using hybrid AI scoring."""

from typing import List, Optional, Dict, Any
from backend.models.opportunity import Opportunity
from backend.models.student import Student
from backend.services.opportunity_service import get_all_opportunities
from backend.services.student_service import get_current_student
from backend.ai.scorer import score_job, calculate_match_details
from backend.ai.skill_gap import find_skill_gaps, compute_detailed_skill_gap
from backend.ai.outreach import generate_outreach
from backend.ai.recruiter_finder import generate_recruiter_search
from backend.utils.config import settings
from backend.utils.logger import get_logger

logger = get_logger("matching_service")


def get_recommendations(
    student: Optional[Student] = None,
    min_score: Optional[float] = None,
    limit: Optional[int] = 50,
    remote: Optional[bool] = None,
    location: Optional[str] = None,
    role: Optional[str] = None,
    skill: Optional[str] = None,
    verified_only: Optional[bool] = None
) -> List[Dict[str, Any]]:
    """Retrieve personalized, explainable recommendations for a student ranked by hybrid match score."""
    if student is None:
        student = get_current_student()

    threshold = min_score if min_score is not None else settings.MIN_MATCH_SCORE_THRESHOLD
    # Strict fail-closed: student recommendations MUST ONLY include VERIFIED, active opportunities
    opportunities = get_all_opportunities(status="active", verified_only=True)

    recommendations: List[Dict[str, Any]] = []

    for opp in opportunities:
        if (opp.verification_status or "").upper() != "VERIFIED" or opp.status not in ("active", "open"):
            continue
        # Filter checks
        if remote is not None and opp.remote != remote:
            continue
        if location and location.lower() not in opp.location.lower():
            continue
        if role and role.lower() not in opp.title.lower():
            continue
        if skill and not any(skill.lower() in s.lower() for s in opp.skills):
            continue

        details = calculate_match_details(opp, student=student)
        score = details["match_score"]

        if score >= threshold:
            rec = {
                "opportunity_id": opp.id,
                "title": opp.title,
                "company": opp.company,
                "opportunity_type": opp.opportunity_type,
                "location": opp.location,
                "remote": opp.remote,
                "work_mode": "Remote" if opp.remote else ("Hybrid" if ("hybrid" in (opp.location or "").lower() or "hybrid" in (opp.description or "").lower()) else "On-site"),
                "stipend": opp.stipend,
                "salary": opp.salary,
                "experience": opp.experience,
                "deadline": opp.deadline,
                "apply_url": opp.apply_url,
                "verification_status": opp.verification_status or "UNVERIFIED",
                "verification_method": opp.verification_method,
                "trust_level": opp.trust_level or "UNVERIFIED_EXTERNAL",
                "match_score": score,
                "semantic_score": details["semantic_score"],
                "skill_score": details["skill_score"],
                "role_score": details["role_score"],
                "eligibility_score": details["eligibility_score"],
                "location_score": details["location_score"],
                "experience_score": details["experience_score"],
                "matched_skills": details["matched_skills"],
                "missing_skills": details["missing_skills"],
                "eligibility": details["eligibility"],
                "explanation": details["explanation"],
                "explanation_details": details["explanation_details"]
            }
            recommendations.append(rec)

    # Sort descending by match score
    recommendations.sort(key=lambda x: x["match_score"], reverse=True)

    # Graceful Fallback: If no recommendations meet the threshold or profile is minimal,
    # supply top recent verified opportunities rather than showing an empty screen,
    # but only if caller did not explicitly enforce a custom min_score threshold.
    if not recommendations and opportunities and min_score is None:
        for opp in opportunities[:limit or 20]:
            if (opp.verification_status or "").upper() != "VERIFIED" or opp.status not in ("active", "open"):
                continue
            details = calculate_match_details(opp, student=student)
            score = max(50.0, details["match_score"])
            rec = {
                "opportunity_id": opp.id,
                "title": opp.title,
                "company": opp.company,
                "opportunity_type": opp.opportunity_type,
                "location": opp.location,
                "remote": opp.remote,
                "work_mode": "Remote" if opp.remote else ("Hybrid" if ("hybrid" in (opp.location or "").lower() or "hybrid" in (opp.description or "").lower()) else "On-site"),
                "stipend": opp.stipend,
                "salary": opp.salary,
                "experience": opp.experience,
                "deadline": opp.deadline,
                "apply_url": opp.apply_url,
                "verification_status": opp.verification_status or "VERIFIED",
                "verification_method": opp.verification_method,
                "trust_level": opp.trust_level or "UNVERIFIED_EXTERNAL",
                "match_score": score,
                "semantic_score": details["semantic_score"],
                "skill_score": details["skill_score"],
                "role_score": details["role_score"],
                "eligibility_score": details["eligibility_score"],
                "location_score": details["location_score"],
                "experience_score": details["experience_score"],
                "matched_skills": details["matched_skills"],
                "missing_skills": details["missing_skills"],
                "eligibility": details["eligibility"],
                "explanation": "Curated recently verified opportunity for your career discovery.",
                "explanation_details": details["explanation_details"],
                "is_fallback": True
            }
            recommendations.append(rec)

    if limit:
        recommendations = recommendations[:limit]

    return recommendations


def run_batch_matching(student: Optional[Student] = None) -> Dict[str, Any]:
    """Execute batch matching for a student across all active opportunities.
    Updates match scores in memory/cache and produces execution statistics.
    """
    if student is None:
        student = get_current_student()

    opportunities = get_all_opportunities(status="active")
    processed_count = len(opportunities)
    recommended_count = 0
    scores: List[float] = []

    for opp in opportunities:
        details = calculate_match_details(opp, student=student)
        score = details["match_score"]
        opp.match_score = score
        opp.missing_skills = details["missing_skills"]
        scores.append(score)
        if score >= settings.MIN_MATCH_SCORE_THRESHOLD:
            recommended_count += 1

    avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0

    logger.info(
        f"Batch matching completed for '{student.name}': {processed_count} processed, "
        f"{recommended_count} recommendations above threshold, avg score: {avg_score}%"
    )

    return {
        "student": student.name,
        "opportunities_processed": processed_count,
        "recommendations_generated": recommended_count,
        "average_score": avg_score
    }


def get_ranked_opportunities(
    student: Optional[Student] = None,
    min_score: Optional[float] = None
) -> List[Opportunity]:
    """Rank opportunities for a student by AI match score (backward compatible)."""
    if student is None:
        student = get_current_student()

    threshold = min_score if min_score is not None else settings.MIN_MATCH_SCORE_THRESHOLD
    opportunities = get_all_opportunities()

    ranked: List[Opportunity] = []

    for opp in opportunities:
        details = calculate_match_details(opp, student=student)
        score = details["match_score"]
        opp.match_score = score
        opp.missing_skills = details["missing_skills"]

        if score >= threshold:
            ranked.append(opp)

    ranked.sort(key=lambda x: (x.match_score or 0.0), reverse=True)
    return ranked


def get_opportunity_insights(opp_id: str, student: Optional[Student] = None) -> dict:
    """Generate comprehensive match breakdown, explanation, outreach, and recruiter queries."""
    if student is None:
        student = get_current_student()

    opportunities = get_all_opportunities()
    target_opp = next((o for o in opportunities if o.id == opp_id), None)

    if not target_opp:
        return {"error": f"Opportunity {opp_id} not found"}

    match_details = calculate_match_details(target_opp, student=student)
    detailed_gap = compute_detailed_skill_gap(
        profile_skills=student.skills,
        job_skills=target_opp.skills,
        job_title=target_opp.title,
        job_description=target_opp.description
    )

    outreach = generate_outreach(
        target_opp,
        candidate_summary=f"{student.education} student specializing in {student.branch}"
    )
    recruiter_links = generate_recruiter_search(target_opp)

    return {
        "opportunity": target_opp.to_dict(),
        "match_score": match_details["match_score"],
        "match_details": match_details,
        "skill_gap": detailed_gap,
        "matched_skills": match_details["matched_skills"],
        "missing_skills": match_details["missing_skills"],
        "explanation": match_details["explanation"],
        "explanation_details": match_details["explanation_details"],
        "outreach_message": outreach,
        "recruiter_search": recruiter_links
    }


def get_aggregated_skill_gaps(
    student: Optional[Student] = None,
    min_score: Optional[float] = None,
    limit: int = 25
) -> Dict[str, Any]:
    """Analyze missing skills across the student's top recommended opportunities.
    Computes real frequencies and prioritizes skills into High, Medium, and Optional categories.
    """
    if student is None:
        student = get_current_student()

    recs = get_recommendations(student=student, min_score=min_score or 30.0, limit=limit)
    if not recs:
        recs = get_recommendations(student=student, min_score=0.0, limit=limit)

    total_recs = len(recs)
    missing_counts: Dict[str, int] = {}
    title_mentions: Dict[str, int] = {}
    matched_counts: Dict[str, int] = {}

    for r in recs:
        title_lower = r["title"].lower()
        for s in r.get("missing_skills", []):
            missing_counts[s] = missing_counts.get(s, 0) + 1
            if s.lower() in title_lower:
                title_mentions[s] = title_mentions.get(s, 0) + 1

        for s in r.get("matched_skills", []):
            matched_counts[s] = matched_counts.get(s, 0) + 1

    high_priority: List[str] = []
    medium_priority: List[str] = []
    optional_priority: List[str] = []
    freq_list: List[Dict[str, Any]] = []

    sorted_missing = sorted(missing_counts.items(), key=lambda x: x[1], reverse=True)

    for skill, count in sorted_missing:
        pct = round((count / total_recs) * 100, 1) if total_recs > 0 else 0.0
        if title_mentions.get(skill, 0) > 0 or pct >= 30.0:
            priority = "high"
            high_priority.append(skill)
        elif pct >= 15.0:
            priority = "medium"
            medium_priority.append(skill)
        else:
            priority = "optional"
            optional_priority.append(skill)

        freq_list.append({
            "skill": skill,
            "count": count,
            "percentage": pct,
            "priority": priority,
            "title_relevant": title_mentions.get(skill, 0) > 0
        })

    sorted_matched = sorted(matched_counts.items(), key=lambda x: x[1], reverse=True)
    matched_freq = [
        {
            "skill": skill,
            "count": count,
            "percentage": round((count / total_recs) * 100, 1) if total_recs > 0 else 0.0
        }
        for skill, count in sorted_matched
    ]

    return {
        "student": student.name,
        "recommendations_analyzed": total_recs,
        "missing_skills_frequency": freq_list,
        "high_priority": high_priority,
        "medium_priority": medium_priority,
        "optional": optional_priority,
        "matched_skills_frequency": matched_freq
    }
