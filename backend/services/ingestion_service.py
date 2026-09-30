"""Unified Ingestion Engine Service.

Coordinates all collectors, applies normalization, validation, deduplication,
expiry evaluation, and database persistence with complete failure isolation.
"""

from typing import List, Dict, Any, Optional
from datetime import date
from backend.collectors.base_collector import BaseCollector
from backend.collectors.yc_collector import YCCollector
from backend.collectors.wellfound_collector import WellfoundCollector
from backend.collectors.internshala_collector import InternshalaCollector
from backend.collectors.telegram_collector import TelegramCollector
from backend.collectors.linkedin_collector import LinkedInCollector
from backend.collectors.import_collector import ImportCollector
from backend.collectors.sample_collector import SampleCollector
from backend.collectors.normalizer import normalize_opportunity
from backend.services.deduplication_service import deduplicate_opportunities, is_duplicate, merge_opportunity_records
from backend.services.expiry_service import evaluate_and_update_expiry_in_db
from backend.services.opportunity_service import save_opportunity, get_all_opportunities
from backend.database.sync import sync_db_to_json
from backend.models.opportunity import Opportunity
from backend.utils.logger import get_logger

logger = get_logger("ingestion_service")


def get_default_collectors() -> List[BaseCollector]:
    """Instantiate all configured opportunity collectors."""
    return [
        YCCollector(),
        WellfoundCollector(),
        InternshalaCollector(),
        TelegramCollector(),
        LinkedInCollector(),
        ImportCollector()
    ]


def run_ingestion_pipeline(
    collectors: Optional[List[BaseCollector]] = None,
    sources: Optional[List[str]] = None,
    allow_sample_fallback: bool = True
) -> Dict[str, Any]:
    """Execute the complete opportunity ingestion pipeline across all sources.
    Guarantees that a failure in one source never stops the remaining sources.
    
    Args:
        collectors: Optional explicit list of collector instances.
        sources: Optional list of source name strings to filter active collectors.
        allow_sample_fallback: Fall back to existing database/dataset if 0 collected.
    """
    if collectors is None:
        all_cols = get_default_collectors()
        if sources:
            source_filters = [s.strip().lower() for s in sources if s.strip()]
            collectors = [
                c for c in all_cols
                if any(sf in c.name.lower() or c.name.lower() in sf or sf.rstrip('s') in c.name.lower() for sf in source_filters)
            ]
        else:
            collectors = all_cols

    sources_attempted: List[str] = []
    sources_successful: List[str] = []
    errors: Dict[str, str] = {}
    channel_stats: Dict[str, Any] = {}
    raw_collected: List[Opportunity] = []

    logger.info(f"Starting unified opportunity ingestion across {len(collectors)} collectors...")

    # 1. Collection Phase with Fault Isolation
    for col in collectors:
        sources_attempted.append(col.name)
        try:
            logger.info(f"Collecting from source '{col.name}'...")
            items = col.collect()
            raw_collected.extend(items)
            sources_successful.append(col.name)
            logger.info(f"Source '{col.name}' successfully yielded {len(items)} records.")
            if hasattr(col, "get_channel_stats"):
                stats = col.get_channel_stats()
                if stats:
                    channel_stats.update(stats)
        except Exception as e:
            err_msg = str(e)
            errors[col.name] = err_msg
            logger.warning(f"Error during collection from '{col.name}': {err_msg}. Continuing with remaining collectors.")

    # Fallback to sample collector if zero opportunities collected and database is empty
    existing_opps = get_all_opportunities()
    if not raw_collected and not existing_opps and allow_sample_fallback:
        logger.info("Zero opportunities collected from live sources and database is empty. Using sample collector fallback...")
        sample_col = SampleCollector()
        sources_attempted.append(sample_col.name)
        try:
            items = sample_col.collect()
            raw_collected.extend(items)
            sources_successful.append(sample_col.name)
        except Exception as e:
            errors[sample_col.name] = str(e)

    total_collected_count = len(raw_collected)
    invalid_urls_rejected = 0

    # 2. Normalization & URL/Content Validation Phase
    normalized_opps: List[Opportunity] = []
    from backend.utils.url_validator import validate_application_url

    for raw in raw_collected:
        try:
            norm = normalize_opportunity(raw)
            # Basic validation
            if not norm.title or not norm.company or not norm.apply_url:
                logger.debug(f"Dropped incomplete opportunity: title='{norm.title}', company='{norm.company}'")
                continue

            # Strict URL validation & SSRF protection
            is_valid_url, reason, canon_url = validate_application_url(norm.apply_url)
            if not is_valid_url:
                logger.warning(f"Rejected opportunity '{norm.title}' due to invalid apply URL ({reason})")
                invalid_urls_rejected += 1
                continue

            norm.apply_url = canon_url
            normalized_opps.append(norm)
        except Exception as e:
            logger.debug(f"Normalization error for item: {e}")

    # 3. In-Batch Deduplication Phase
    batch_unique, in_batch_duplicates = deduplicate_opportunities(normalized_opps)

    # 4. Cross-Database Deduplication & Persistence Phase with Verification Tracking
    saved_count = 0
    cross_db_duplicates = 0
    pending_review_count = 0
    verified_count = 0
    published_count = 0

    # Index existing opportunities for fast URL matching
    existing_url_map = {o.apply_url: o for o in existing_opps if o.apply_url}
    existing_list = list(existing_opps)

    for opp in batch_unique:
        matched_existing: Optional[Opportunity] = None

        # Check exact apply URL match first
        if opp.apply_url in existing_url_map:
            matched_existing = existing_url_map[opp.apply_url]
        else:
            # Check multi-signal duplicate
            for ex in existing_list:
                is_dup, _ = is_duplicate(opp, ex)
                if is_dup:
                    matched_existing = ex
                    break

        if matched_existing:
            cross_db_duplicates += 1
            # Merge candidate into existing record
            merged = merge_opportunity_records(matched_existing, opp)
            save_opportunity(merged)
        else:
            if not opp.verification_status or opp.verification_status in ("UNVERIFIED", "PENDING_REVIEW"):
                if opp.title and opp.company and opp.apply_url:
                    opp.verification_status = "VERIFIED"
                    opp.status = "active"
            saved = save_opportunity(opp)
            existing_list.append(opp)
            if opp.apply_url:
                existing_url_map[opp.apply_url] = opp
            saved_count += 1
            if (opp.verification_status or "").upper() == "VERIFIED":
                verified_count += 1
                if opp.status in ("active", "open"):
                    published_count += 1
            else:
                pending_review_count += 1

    total_duplicates_removed = in_batch_duplicates + cross_db_duplicates

    # 5. Expiry Check Phase
    expiry_report = evaluate_and_update_expiry_in_db()
    expired_count = expiry_report.get("newly_expired", 0)

    # 6. Synchronize Database to data/jobs.json
    try:
        sync_db_to_json()
    except Exception as e:
        logger.warning(f"Error synchronizing database to jobs.json: {e}")

    # Record errors to SourceRegistryDB and Audit Logs
    try:
        from backend.database.db import SessionLocal, SourceRegistryDB, AuditLogDB
        db_session = SessionLocal()
        try:
            for src_name, err in errors.items():
                src_row = db_session.query(SourceRegistryDB).filter(
                    (SourceRegistryDB.name.ilike(f"%{src_name}%")) |
                    (SourceRegistryDB.id.ilike(f"%{src_name}%"))
                ).first()
                if src_row:
                    src_row.last_error = err
                # Log audit entry
                db_session.add(AuditLogDB(
                    id=f"audit_err_{date.today().isoformat()}_{src_name[:16]}",
                    event_type="INGESTION_ERROR",
                    actor="system_ingestion",
                    target=src_name,
                    details=err
                ))
            db_session.commit()
        finally:
            db_session.close()
    except Exception as db_err:
        logger.debug(f"Notice updating source error logs: {db_err}")

    # Standardized 9-metric report required by system specifications
    total_found = total_collected_count
    total_parsed = len(normalized_opps)
    total_rejected = invalid_urls_rejected + (total_found - total_parsed)

    report = {
        "found": total_found,
        "parsed": total_parsed,
        "rejected": total_rejected,
        "duplicates": total_duplicates_removed,
        "expired": expired_count,
        "pending": pending_review_count,
        "pending_review": pending_review_count,
        "verified": verified_count,
        "published": published_count,
        "errors": errors,
        # Additional metadata for backward compatibility
        "sources_attempted": sources_attempted,
        "sources_successful": sources_successful,
        "collected": total_collected_count,
        "duplicates_removed": total_duplicates_removed,
        "saved": saved_count,
        "new_added": saved_count,
        "channel_stats": channel_stats
    }

    logger.info(f"Ingestion completed: {report}")
    return report

