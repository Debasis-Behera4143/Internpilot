"""AI Matching and Recommendation REST API routes."""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Query, Depends
from backend.models.opportunity import Opportunity, StudentOpportunity
from backend.services.matching_service import (
    get_recommendations,
    run_batch_matching,
    get_ranked_opportunities,
    get_opportunity_insights,
    get_aggregated_skill_gaps,
)
from backend.services.student_service import get_current_student
from backend.database.db import UserDB
from backend.api.deps import require_student

router = APIRouter(prefix="/api/matching", tags=["AI Matching"])


def _sanitize_rec(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Strip internal Telegram source metadata from a recommendation object."""
    sanitized = dict(rec)
    sanitized.pop("source", None)
    sanitized.pop("source_url", None)
    sanitized.pop("source_channel", None)
    sanitized.pop("raw_text", None)
    return sanitized


@router.get("/skill-gaps")
def get_skill_gaps_analysis(
    min_score: Optional[float] = Query(None, description="Minimum match percentage score"),
    limit: int = Query(25, ge=1, le=100, description="Max opportunities to analyze"),
    current_user: UserDB = Depends(require_student),
):
    """Retrieve aggregated skill gap frequency and priority roadmap across student recommendations."""
    student = get_current_student(student_id=current_user.id)
    return get_aggregated_skill_gaps(student=student, min_score=min_score, limit=limit)


@router.get("/recommendations")
def get_personalized_recommendations(
    limit: Optional[int] = Query(50, description="Max opportunities to return"),
    min_score: Optional[float] = Query(None, description="Minimum match percentage score (0-100)"),
    minimum_score: Optional[float] = Query(None, description="Alias for min_score", include_in_schema=False),
    remote: Optional[bool] = Query(None, description="Filter by remote work support"),
    location: Optional[str] = Query(None, description="Filter by location/city name"),
    role: Optional[str] = Query(None, description="Filter by role or designation keywords"),
    skill: Optional[str] = Query(None, description="Filter by required technical skill"),
    verified_only: Optional[bool] = Query(None, description="Filter for verified opportunities only"),
    current_user: UserDB = Depends(require_student),
):
    """Retrieve personalized, explainable recommendations ranked by hybrid AI match score."""
    effective_min_score = min_score if min_score is not None else minimum_score
    student = get_current_student(student_id=current_user.id)
    recs = get_recommendations(
        student=student,
        min_score=effective_min_score,
        limit=limit,
        remote=remote,
        location=location,
        role=role,
        skill=skill,
        verified_only=verified_only,
    )
    return [_sanitize_rec(r) for r in recs]


@router.post("/run")
def run_batch_matching_pipeline(current_user: UserDB = Depends(require_student)):
    """Execute batch matching for the current active student profile across all active opportunities."""
    student = get_current_student(student_id=current_user.id)
    return run_batch_matching(student=student)


@router.get("/ranked", response_model=List[StudentOpportunity])
def get_ranked(
    min_score: Optional[float] = Query(None, description="Minimum match percentage threshold (0-100)"),
    current_user: UserDB = Depends(require_student),
):
    """Retrieve all opportunities ranked by AI match score (sanitized for students)."""
    student = get_current_student(student_id=current_user.id)
    ranked = get_ranked_opportunities(student=student, min_score=min_score)
    return [opp.to_student_dict() for opp in ranked]


@router.get("/insights/{opp_id}")
def get_insights(opp_id: str, current_user: UserDB = Depends(require_student)):
    """Retrieve AI match score, detailed skill gap, outreach draft, and recruiter links for an opportunity."""
    student = get_current_student(student_id=current_user.id)
    insights = get_opportunity_insights(opp_id, student=student)
    if "opportunity" in insights and isinstance(insights["opportunity"], dict):
        opp_dict = insights["opportunity"]
        opp_dict.pop("source", None)
        opp_dict.pop("source_url", None)
        opp_dict.pop("source_channel", None)
        opp_dict.pop("raw_text", None)
    return insights
