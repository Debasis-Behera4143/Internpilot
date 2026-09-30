"""Services package initialization."""

from backend.services.opportunity_service import (
    get_all_opportunities,
    save_opportunity,
    collect_all_opportunities,
    get_opportunity_stats
)
from backend.services.student_service import (
    get_current_student,
    update_current_student
)
from backend.services.matching_service import (
    get_ranked_opportunities,
    get_opportunity_insights
)
from backend.services.tracker_service import (
    get_all_applications,
    add_application,
    update_application_status
)
from backend.services.ingestion_service import run_ingestion_pipeline
from backend.services.deduplication_service import deduplicate_opportunities, is_duplicate
from backend.services.expiry_service import is_opportunity_expired, evaluate_and_update_expiry_in_db

__all__ = [
    "get_all_opportunities",
    "save_opportunity",
    "collect_all_opportunities",
    "get_opportunity_stats",
    "get_current_student",
    "update_current_student",
    "get_ranked_opportunities",
    "get_opportunity_insights",
    "get_all_applications",
    "add_application",
    "update_application_status",
    "run_ingestion_pipeline",
    "deduplicate_opportunities",
    "is_duplicate",
    "is_opportunity_expired",
    "evaluate_and_update_expiry_in_db"
]
