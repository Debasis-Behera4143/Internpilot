"""AI and Machine Learning package initialization."""

from backend.ai.embedder import get_embedding, get_model
from backend.ai.scorer import score_job
from backend.ai.outreach import generate_outreach
from backend.ai.recruiter_finder import generate_recruiter_search
from backend.ai.skill_gap import find_skill_gaps, analyze_skill_gap

__all__ = [
    "get_embedding",
    "get_model",
    "score_job",
    "generate_outreach",
    "generate_recruiter_search",
    "find_skill_gaps",
    "analyze_skill_gap"
]
