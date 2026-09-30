"""Service for managing the unified source registry and Telegram channels."""

import re
import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database.db import SourceRegistryDB
from backend.models.source import (
    SourceType,
    SourceStatus,
    SourceTrustLevel,
    SourceModel,
    SourceCreateRequest,
    SourceUpdateRequest,
    TelegramChannelCreateRequest,
)
from backend.utils.logger import get_logger

logger = get_logger("source_service")


def normalize_telegram_handle(channel_or_url: str) -> str:
    """Extract clean Telegram username handle from handle string or preview URL."""
    if not channel_or_url:
        return ""
    c = str(channel_or_url).strip()
    c = re.sub(r"^https?://(?:www\.)?t(?:elegram)?\.me/(?:s/)?", "", c, flags=re.IGNORECASE)
    c = c.lstrip("@").strip("/").strip()
    return c


def categorize_admin_error(raw_err: Optional[str]) -> str:
    """Map raw exception details into standardized, admin-safe error categories."""
    if not raw_err:
        return "Connection failed"
    err_low = str(raw_err).lower()
    if any(k in err_low for k in ["timeout", "connection", "connect", "dns", "refused", "name resolution", "max retries", "http/network"]):
        return "Connection failed"
    if any(k in err_low for k in ["invalid channel", "not found", "404", "channel username", "invite link"]):
        return "Invalid channel"
    if any(k in err_low for k in ["url validation", "ssrf", "disallowed", "unsupported scheme"]):
        return "URL validation failed"
    if any(k in err_low for k in ["auth", "token", "unauthorized", "forbidden", "401", "403"]):
        return "Authentication error"
    if any(k in err_low for k in ["database", "sqlite", "operationalerror", "integrityerror"]):
        return "Database error"
    if any(k in err_low for k in ["parse", "parser", "html", "json", "syntax", "extract"]):
        return "Parser error"
    clean = re.sub(r"[a-zA-Z0-9_\-\.]{25,}", "[redacted]", str(raw_err))
    return clean[:80]


# Default trust mapping for source types
DEFAULT_TRUST_MAPPING = {
    SourceType.COMPANY_CAREERS: SourceTrustLevel.OFFICIAL_COMPANY,
    SourceType.ATS_PUBLIC_FEED: SourceTrustLevel.OFFICIAL_COMPANY,
    SourceType.LINKEDIN_AUTHORIZED: SourceTrustLevel.AUTHORIZED_API,
    SourceType.INTERNSHALA_AUTHORIZED_OR_IMPORT: SourceTrustLevel.AUTHORIZED_API,
    SourceType.EMPLOYER_SUBMISSION: SourceTrustLevel.EMPLOYER_SUBMITTED,
    SourceType.COLLEGE_SUBMISSION: SourceTrustLevel.COLLEGE_SUBMITTED,
    SourceType.TELEGRAM: SourceTrustLevel.UNVERIFIED_EXTERNAL,
    SourceType.CSV: SourceTrustLevel.UNVERIFIED_EXTERNAL,
    SourceType.JSON: SourceTrustLevel.UNVERIFIED_EXTERNAL,
}


def _db_to_model(row: SourceRegistryDB) -> SourceModel:
    config = {}
    if row.configuration:
        try:
            config = json.loads(row.configuration)
        except Exception:
            config = {}

    status_str = str(row.status).upper() if row.status else "ACTIVE"
    if status_str == "ERROR":
        status_val = SourceStatus.FAILED
    elif status_str in SourceStatus.__members__:
        status_val = SourceStatus[status_str]
    else:
        status_val = SourceStatus.ACTIVE

    return SourceModel(
        id=row.id,
        name=row.name,
        type=SourceType(row.type) if row.type in SourceType.__members__ else row.type,
        status=status_val,
        trust_level=SourceTrustLevel(row.trust_level) if row.trust_level in SourceTrustLevel.__members__ else row.trust_level,
        configuration=config,
        last_ingested_at=row.last_ingested_at,
        last_success_at=row.last_success_at,
        last_error=row.last_error,
        items_count=row.items_count or 0,
        items_accepted=row.items_accepted or 0,
        items_rejected=row.items_rejected or 0,
        created_at=row.created_at.isoformat() if row.created_at else None,
        updated_at=row.updated_at.isoformat() if row.updated_at else None,
    )


def list_sources(
    db: Session,
    source_type: Optional[str] = None,
    status: Optional[str] = None
) -> List[SourceModel]:
    """List all registered sources with optional type and status filtering."""
    query = db.query(SourceRegistryDB)
    if source_type:
        query = query.filter(SourceRegistryDB.type == source_type.upper())
    if status:
        query = query.filter(SourceRegistryDB.status == status.upper())
    
    rows = query.order_by(SourceRegistryDB.type, SourceRegistryDB.name).all()
    return [_db_to_model(r) for r in rows]


def get_source(db: Session, source_id: str) -> Optional[SourceModel]:
    """Retrieve a single source by ID."""
    row = db.query(SourceRegistryDB).filter_by(id=source_id).first()
    return _db_to_model(row) if row else None


def create_source(db: Session, data: SourceCreateRequest) -> SourceModel:
    """Create a new source registry entry with duplicate prevention."""
    cfg = data.configuration or {}

    # Handle Telegram specifically to have clean deterministic ID and handle detection
    if data.type == SourceType.TELEGRAM:
        from backend.utils.url_validator import validate_telegram_channel_spec
        raw_handle = str(cfg.get("channel_username") or "")
        if not raw_handle:
            raw_handle = re.sub(r"[^A-Za-z0-9_]", "_", data.name).strip("_")
        handle = normalize_telegram_handle(raw_handle)
        is_val, msg, details = validate_telegram_channel_spec(handle, cfg.get("preview_url"))
        if not is_val:
            fallback_slug = re.sub(r"[^A-Za-z0-9_]", "_", handle).strip("_")
            is_val, msg, details = validate_telegram_channel_spec(fallback_slug, cfg.get("preview_url"))
            if not is_val:
                raise ValueError(msg)
            handle = fallback_slug
        cfg["channel_username"] = handle
        cfg["preview_url"] = details.get("preview_url") or f"https://t.me/s/{handle}"
        data.configuration = cfg
        source_id = f"src_tg_{handle.lower()}"
    else:
        # Check if source with same type and name exists
        existing = db.query(SourceRegistryDB).filter_by(type=data.type.value, name=data.name).first()
        if existing:
            # Update configuration and status of existing source rather than duplicating
            existing.status = data.status.value
            if data.trust_level:
                existing.trust_level = data.trust_level.value
            current_cfg = {}
            if existing.configuration:
                try:
                    current_cfg = json.loads(existing.configuration)
                except Exception:
                    pass
            current_cfg.update(cfg)
            existing.configuration = json.dumps(current_cfg)
            existing.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing)
            logger.info(f"Updated existing registered source: {existing.name} ({existing.id})")
            return _db_to_model(existing)

        source_id = f"src_{data.type.value.lower()}_{uuid.uuid4().hex[:8]}"

    # Check if deterministic source_id already exists
    existing = db.query(SourceRegistryDB).filter_by(id=source_id).first()
    if existing:
        existing.name = data.name
        existing.status = data.status.value
        if data.trust_level:
            existing.trust_level = data.trust_level.value
        existing.configuration = json.dumps(cfg)
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        logger.info(f"Updated existing source by ID: {existing.name} ({existing.id})")
        return _db_to_model(existing)

    trust = data.trust_level or DEFAULT_TRUST_MAPPING.get(data.type, SourceTrustLevel.UNVERIFIED_EXTERNAL)

    db_source = SourceRegistryDB(
        id=source_id,
        name=data.name,
        type=data.type.value,
        status=data.status.value,
        trust_level=trust.value,
        configuration=json.dumps(cfg),
        items_count=0
    )
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    logger.info(f"Registered source: {db_source.name} [{db_source.type}] ({db_source.id})")
    return _db_to_model(db_source)


def ingest_source(db: Session, source_id: str) -> Dict[str, Any]:
    """Execute ingestion for a single registered source and update audit metrics."""
    from backend.services.ingestion_service import run_ingestion_pipeline
    from backend.collectors.telegram_collector import TelegramCollector
    from backend.collectors.ats_adapter import ATSAdapter
    from backend.collectors.company_careers_adapter import CompanyCareersAdapter
    from backend.collectors.linkedin_adapter import LinkedInAdapter
    from backend.collectors.internshala_adapter import InternshalaAdapter
    from backend.collectors.csv_collector import CSVCollector
    from backend.collectors.json_collector import JSONCollector

    row = db.query(SourceRegistryDB).filter_by(id=source_id).first()
    if not row:
        raise ValueError(f"Source with id '{source_id}' not found.")

    # Mark source as RUNNING
    row.status = "RUNNING"
    db.commit()
    db.refresh(row)

    cfg = {}
    if row.configuration:
        try:
            cfg = json.loads(row.configuration)
        except Exception:
            pass

    collector = None
    st = row.type.upper()

    if st == "TELEGRAM":
        handle = cfg.get("channel_username") or row.name
        clean_handle = normalize_telegram_handle(handle)
        collector = TelegramCollector(channels=[clean_handle])
    elif st == "ATS_PUBLIC_FEED":
        companies = cfg.get("companies")
        if isinstance(companies, list):
            comp_map = {c.capitalize(): f"greenhouse:{c.lower()}" for c in companies}
        elif isinstance(companies, dict):
            comp_map = companies
        else:
            comp_map = None
        collector = ATSAdapter(companies=comp_map)
    elif st == "COMPANY_CAREERS":
        comp_configs = cfg.get("companies") or [
            {
                "title": f"{cfg.get('company_name', row.name)} Intern",
                "company": cfg.get("company_name", row.name),
                "apply_url": cfg.get("url", "https://careers.example.com"),
                "location": "Bengaluru / Remote"
            }
        ]
        collector = CompanyCareersAdapter(company_configs=comp_configs)
    elif st == "LINKEDIN_AUTHORIZED":
        collector = LinkedInAdapter()
    elif st == "INTERNSHALA_AUTHORIZED_OR_IMPORT":
        collector = InternshalaAdapter()
    elif st == "CSV":
        collector = CSVCollector(csv_path=cfg.get("file_path"))
    elif st == "JSON":
        collector = JSONCollector(json_path=cfg.get("file_path"))
    else:
        # Fallback to Telegram collector
        handle = cfg.get("channel_username") or row.name
        clean_handle = normalize_telegram_handle(handle)
        collector = TelegramCollector(channels=[clean_handle])

    try:
        report = run_ingestion_pipeline(collectors=[collector])
        errors = report.get("errors", {})
        has_error = len(errors) > 0
        err_msg = list(errors.values())[0] if has_error else None
        safe_err = categorize_admin_error(err_msg) if has_error else None

        new_added = report.get("new_added", 0)
        rejected = report.get("rejected", 0)
        found = report.get("found", 0)

        record_source_run(
            db=db,
            source_id=source_id,
            success=not has_error,
            error=safe_err,
            items_added=new_added,
            items_rejected=rejected,
            items_found=found
        )
        return report
    except Exception as e:
        logger.error(f"Ingestion failed for source {source_id}: {e}", exc_info=True)
        safe_err = categorize_admin_error(str(e))
        record_source_run(
            db=db,
            source_id=source_id,
            success=False,
            error=safe_err,
            items_added=0,
            items_rejected=0,
            items_found=0
        )
        return {
            "found": 0,
            "parsed": 0,
            "rejected": 0,
            "duplicates": 0,
            "expired": 0,
            "pending": 0,
            "pending_review": 0,
            "verified": 0,
            "new_added": 0,
            "saved": 0,
            "errors": {source_id: safe_err},
            "error": safe_err,
            "status": "failed"
        }


def update_source(db: Session, source_id: str, data: SourceUpdateRequest) -> Optional[SourceModel]:
    """Update source properties or configuration."""
    row = db.query(SourceRegistryDB).filter_by(id=source_id).first()
    if not row:
        return None

    if data.name is not None:
        row.name = data.name
    if data.status is not None:
        row.status = data.status.value
    if data.trust_level is not None:
        row.trust_level = data.trust_level.value
    if data.configuration is not None:
        current_config = {}
        if row.configuration:
            try:
                current_config = json.loads(row.configuration)
            except Exception:
                pass
        current_config.update(data.configuration)
        row.configuration = json.dumps(current_config)

    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _db_to_model(row)


def delete_source(db: Session, source_id: str) -> bool:
    """Delete a registered source."""
    row = db.query(SourceRegistryDB).filter_by(id=source_id).first()
    if not row:
        return False
    db.delete(row)
    db.commit()
    logger.info(f"Deleted source: {source_id}")
    return True


def add_telegram_channel(db: Session, req: TelegramChannelCreateRequest) -> SourceModel:
    """Add a new Telegram public channel source dynamically."""
    from backend.utils.url_validator import validate_telegram_channel_spec

    handle = normalize_telegram_handle(req.channel_username)
    is_val, msg, details = validate_telegram_channel_spec(handle, req.preview_url)
    if not is_val:
        raise ValueError(msg)

    source_id = f"src_tg_{handle.lower()}"
    preview_url = details.get("preview_url") or req.preview_url or f"https://t.me/s/{handle}"

    # Check if channel handle already exists
    existing = db.query(SourceRegistryDB).filter_by(id=source_id).first()
    if existing:
        existing.name = req.channel_name
        existing.status = req.status.value
        existing.configuration = json.dumps({
            "channel_username": handle,
            "preview_url": preview_url
        })
        existing.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return _db_to_model(existing)

    db_source = SourceRegistryDB(
        id=source_id,
        name=req.channel_name,
        type=SourceType.TELEGRAM.value,
        status=req.status.value,
        trust_level=SourceTrustLevel.UNVERIFIED_EXTERNAL.value,
        configuration=json.dumps({
            "channel_username": handle,
            "preview_url": preview_url
        }),
        items_count=0
    )
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    logger.info(f"Added Telegram channel: @{handle} ({req.channel_name})")
    return _db_to_model(db_source)


def toggle_source_status(db: Session, source_id: str, new_status: Optional[str] = None) -> Optional[SourceModel]:
    """Toggle source status between ACTIVE and PAUSED, or set to specific status."""
    row = db.query(SourceRegistryDB).filter_by(id=source_id).first()
    if not row:
        return None

    if new_status:
        row.status = new_status.upper()
    else:
        row.status = "ACTIVE" if row.status == "PAUSED" else "PAUSED"

    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return _db_to_model(row)


def record_source_run(
    db: Session,
    source_id: str,
    success: bool,
    error: Optional[str] = None,
    items_added: int = 0,
    items_rejected: int = 0,
    items_found: Optional[int] = None
) -> None:
    """Record the execution outcome of an ingestion run for a source."""
    now_iso = datetime.now(timezone.utc).isoformat()
    row = db.query(SourceRegistryDB).filter_by(id=source_id).first()
    if not row:
        return

    row.last_ingested_at = now_iso
    total_found = items_found if items_found is not None else (items_added + items_rejected)
    if success:
        row.status = "SUCCESS"
        row.last_success_at = now_iso
        row.last_error = None
        if total_found > 0:
            row.items_count = (row.items_count or 0) + total_found
        if items_added > 0:
            row.items_accepted = (row.items_accepted or 0) + items_added
        if items_rejected > 0:
            row.items_rejected = (row.items_rejected or 0) + items_rejected
    else:
        row.status = "FAILED"
        row.last_error = error[:500] if error else "Connection failed"
        if items_rejected > 0:
            row.items_rejected = (row.items_rejected or 0) + items_rejected

    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)


def validate_source_specification(
    db: Session,
    source_type: str,
    name: str,
    configuration: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Validate a candidate source specification before saving, returning structured diagnostics.
    
    Used for the interactive Validate -> Preview -> Confirm workflow.
    """
    from backend.utils.url_validator import validate_telegram_channel_spec, validate_application_url

    st = (source_type or "").upper()
    cfg = configuration or {}
    clean_name = (name or "").strip()

    if not clean_name:
        return {
            "valid": False,
            "status_code": "INVALID_NAME",
            "message": "✕ Source name cannot be empty.",
            "preview": None
        }

    # 1. Telegram Validation
    if st == "TELEGRAM":
        handle = cfg.get("channel_username") or clean_name
        preview_url = cfg.get("preview_url")
        is_valid, msg, details = validate_telegram_channel_spec(handle, preview_url)
        if not is_valid:
            return {
                "valid": False,
                "status_code": "INVALID_TELEGRAM_SPEC",
                "message": msg,
                "preview": None
            }

        # Check for duplicate source in DB
        source_id = f"src_tg_{details['handle'].lower()}"
        existing = db.query(SourceRegistryDB).filter_by(id=source_id).first()
        is_dup = existing is not None

        return {
            "valid": True,
            "is_duplicate": is_dup,
            "status_code": "DUPLICATE_SOURCE" if is_dup else "VALID_TELEGRAM",
            "message": "⚠ Duplicate source (existing channel will be updated)" if is_dup else msg,
            "preview": {
                "id": source_id,
                "name": clean_name,
                "type": "TELEGRAM",
                "handle": details["channel_username"],
                "preview_url": details["preview_url"],
                "trust_level": "UNVERIFIED_EXTERNAL",
                "is_existing": is_dup
            }
        }

    # 2. Company Careers Validation
    elif st == "COMPANY_CAREERS":
        target_url = cfg.get("target_url") or cfg.get("url")
        if not target_url:
            return {
                "valid": False,
                "status_code": "MISSING_URL",
                "message": "✕ Careers page URL is required.",
                "preview": None
            }
        is_valid_url, reason, canon_url = validate_application_url(target_url)
        if not is_valid_url:
            return {
                "valid": False,
                "status_code": "INVALID_URL",
                "message": f"✕ Invalid careers URL: {reason}",
                "preview": None
            }
        return {
            "valid": True,
            "is_duplicate": False,
            "status_code": "VALID_COMPANY_CAREERS",
            "message": "✓ Valid Company Careers source specification",
            "preview": {
                "name": clean_name,
                "type": "COMPANY_CAREERS",
                "target_url": canon_url,
                "trust_level": "OFFICIAL_COMPANY"
            }
        }

    # 3. ATS Public Feed Validation
    elif st == "ATS_PUBLIC_FEED":
        board_url = cfg.get("board_url") or cfg.get("target_url")
        if not board_url:
            return {
                "valid": False,
                "status_code": "MISSING_BOARD",
                "message": "✕ ATS feed URL or company token is required.",
                "preview": None
            }
        return {
            "valid": True,
            "is_duplicate": False,
            "status_code": "VALID_ATS",
            "message": "✓ Valid ATS feed specification",
            "preview": {
                "name": clean_name,
                "type": "ATS_PUBLIC_FEED",
                "provider": cfg.get("provider", "greenhouse"),
                "board_url": board_url,
                "trust_level": "OFFICIAL_COMPANY"
            }
        }

    # 4. Authorized Feeds (LinkedIn / Internshala)
    elif st in ("LINKEDIN_AUTHORIZED", "INTERNSHALA_AUTHORIZED_OR_IMPORT"):
        return {
            "valid": True,
            "is_duplicate": False,
            "status_code": "VALID_AUTHORIZED_FEED",
            "message": f"✓ Valid {st.replace('_', ' ').title()} integration specification",
            "preview": {
                "name": clean_name,
                "type": st,
                "trust_level": "AUTHORIZED_API"
            }
        }

    # 5. File Feeds (CSV / JSON)
    elif st in ("CSV", "JSON"):
        file_path = cfg.get("file_path")
        if not file_path:
            return {
                "valid": False,
                "status_code": "MISSING_FILE_PATH",
                "message": "✕ File path is required for dataset import.",
                "preview": None
            }
        return {
            "valid": True,
            "is_duplicate": False,
            "status_code": "VALID_FILE_SPEC",
            "message": f"✓ Valid {st} dataset file specification",
            "preview": {
                "name": clean_name,
                "type": st,
                "file_path": file_path,
                "trust_level": "UNVERIFIED_EXTERNAL"
            }
        }

    # Fallback
    return {
        "valid": True,
        "is_duplicate": False,
        "status_code": "VALID_SOURCE",
        "message": f"✓ Valid source configuration ({st})",
        "preview": {
            "name": clean_name,
            "type": st,
            "trust_level": "UNVERIFIED_EXTERNAL"
        }
    }


def preview_import_records(
    db: Session,
    records: List[Dict[str, Any]],
    source_type: str = "CSV"
) -> ImportPreviewResponse:
    """Validate, preview, detect duplicates, validate URLs, and classify jobs before importing."""
    from backend.models.source import ImportPreviewItem, ImportPreviewResponse
    from backend.services.job_classifier import classify_opportunity_content, is_company_identifiable
    from backend.utils.url_validator import validate_application_url
    from backend.database.db import OpportunityDB
    from datetime import date

    total_records = len(records)
    valid_count = 0
    rejected_count = 0
    duplicate_count = 0
    sample_preview: List[ImportPreviewItem] = []
    rejection_summary_set = set()

    # Pre-index existing URLs and (company, title) from database for fast duplicate check
    existing_urls = {
        row[0].strip().lower()
        for row in db.query(OpportunityDB.apply_url).filter(OpportunityDB.apply_url.isnot(None)).all()
        if row[0]
    }
    existing_fingerprints = {
        (row[0].strip().lower(), row[1].strip().lower())
        for row in db.query(OpportunityDB.company, OpportunityDB.title).all()
        if row[0] and row[1]
    }

    seen_batch_urls = set()
    seen_batch_fps = set()
    today_iso = date.today().isoformat()

    def _extract_field(d: Dict[str, Any], *keys: str) -> str:
        for k in keys:
            if k in d and d[k] is not None:
                val = str(d[k]).strip()
                if val:
                    return val
        lower_map = {str(k).strip().lower(): v for k, v in d.items()}
        for k in keys:
            lk = k.strip().lower()
            if lk in lower_map and lower_map[lk] is not None:
                val = str(lower_map[lk]).strip()
                if val:
                    return val
        return ""

    for idx, raw in enumerate(records, start=1):
        title = _extract_field(raw, "title", "job title", "position", "role")
        company = _extract_field(raw, "company", "company name", "organization", "employer")
        apply_url = _extract_field(raw, "apply_url", "apply url", "application url", "job_url", "job url", "link", "url")
        location = _extract_field(raw, "location", "job location", "city") or "Remote"
        opp_type_raw = _extract_field(raw, "opportunity_type", "employment type", "type") or "internship"
        opp_type = "internship" if "intern" in opp_type_raw.lower() else "full-time"
        desc = _extract_field(raw, "description", "job description", "summary") or title
        deadline = _extract_field(raw, "deadline", "application deadline", "expiry") or None

        is_valid = True
        is_dup = False
        rejection_reason = None

        # 1. Company check
        co_valid, co_msg = is_company_identifiable(company)
        if not co_valid:
            is_valid = False
            rejection_reason = co_msg

        # 2. Title check
        elif len(title) < 3 or title.lower() in ("untitled", "job", "intern", "hiring"):
            is_valid = False
            rejection_reason = "Job title is too short or generic placeholder"

        # 3. URL check
        elif not apply_url or not apply_url.startswith(("http://", "https://")):
            is_valid = False
            rejection_reason = f"Invalid or missing apply_url: '{apply_url}'"
        else:
            url_valid, url_msg, canon_url = validate_application_url(apply_url)
            if not url_valid:
                is_valid = False
                rejection_reason = f"Invalid URL: {url_msg}"
            else:
                apply_url = canon_url

        # 4. Job Classification (genuine job checks)
        if is_valid:
            is_genuine, reject_cat, class_reasons = classify_opportunity_content(title, company, desc, apply_url)
            if not is_genuine:
                is_valid = False
                rejection_reason = f"Classified as non-job ({reject_cat}): {'; '.join(class_reasons)}"

        # 5. Expiry Check
        if is_valid and deadline and deadline < today_iso:
            is_valid = False
            rejection_reason = f"Opportunity expired: deadline {deadline} has passed"

        # 6. Duplicate check (in-batch & database)
        if is_valid:
            norm_url = apply_url.lower()
            fp = (company.lower(), title.lower())

            if norm_url in seen_batch_urls or fp in seen_batch_fps:
                is_dup = True
                is_valid = False
                rejection_reason = "Duplicate listing in import batch"
            elif norm_url in existing_urls or fp in existing_fingerprints:
                is_dup = True
                is_valid = False
                rejection_reason = "Already exists in platform database"
            else:
                seen_batch_urls.add(norm_url)
                seen_batch_fps.add(fp)

        # Count tally
        if is_valid and not is_dup:
            valid_count += 1
            val_status = "VALID"
        elif is_dup:
            duplicate_count += 1
            val_status = "DUPLICATE"
            if rejection_reason:
                rejection_summary_set.add(rejection_reason)
        else:
            rejected_count += 1
            val_status = "REJECTED"
            if rejection_reason:
                rejection_summary_set.add(rejection_reason)

        if len(sample_preview) < 50:
            sample_preview.append(ImportPreviewItem(
                index=idx,
                title=title or "Untitled",
                company=company or "Unknown",
                location=location or "Remote",
                opportunity_type=opp_type,
                apply_url=apply_url,
                is_valid=is_valid and not is_dup,
                is_duplicate=is_dup,
                validation_status=val_status,
                rejection_reason=rejection_reason
            ))

    return ImportPreviewResponse(
        total_records=total_records,
        valid_count=valid_count,
        rejected_count=rejected_count,
        duplicate_count=duplicate_count,
        sample_preview=sample_preview,
        rejection_summary=sorted(list(rejection_summary_set))
    )


def confirm_and_ingest_import(
    db: Session,
    records: List[Dict[str, Any]],
    source_name: str,
    source_type: str,
    admin_user: str
) -> Dict[str, Any]:
    """Execute confirmed import, persisting validated records through the 7-stage publishing pipeline."""
    from backend.models.opportunity import Opportunity
    from backend.models.source import SourceTrustLevel
    from backend.services.verification_service import evaluate_opportunity_verification
    from backend.services.opportunity_service import save_opportunity
    from backend.services.audit_service import log_audit_event
    from backend.database.sync import sync_db_to_json
    from datetime import date

    # Preview and validate records first
    preview = preview_import_records(db=db, records=records, source_type=source_type)
    
    accepted_count = 0
    rejected_count = preview.rejected_count
    duplicate_count = preview.duplicate_count

    # Determine source registry entity
    st_upper = source_type.upper()
    source_row = db.query(SourceRegistryDB).filter(
        (SourceRegistryDB.type == st_upper) | (SourceRegistryDB.name == source_name)
    ).first()

    source_id = source_row.id if source_row else f"src_import_{st_upper.lower()}"
    if "EMPLOYER" in st_upper:
        trust_level = SourceTrustLevel.EMPLOYER_SUBMITTED.value
    elif "COLLEGE" in st_upper:
        trust_level = SourceTrustLevel.COLLEGE_SUBMITTED.value
    elif "ATS" in st_upper:
        trust_level = SourceTrustLevel.ATS_PUBLIC.value
    elif "COMPANY" in st_upper:
        trust_level = SourceTrustLevel.OFFICIAL_COMPANY.value
    elif "LINKEDIN" in st_upper or "IMPORT" in st_upper or st_upper in ("CSV", "JSON"):
        trust_level = SourceTrustLevel.IMPORTED_DATA.value
    elif source_row and source_row.trust_level:
        trust_level = source_row.trust_level
    else:
        trust_level = SourceTrustLevel.UNVERIFIED_EXTERNAL.value

    for item in preview.sample_preview:
        if not item.is_valid or item.is_duplicate:
            continue

        raw = records[item.index - 1] if (0 <= item.index - 1 < len(records)) else {}

        desc = str(raw.get("description") or raw.get("Job Description") or raw.get("summary") or item.title).strip()
        if len(desc) < 15:
            desc = f"{item.title} opportunity at {item.company}."

        raw_skills = raw.get("skills") or raw.get("Skills") or []
        if isinstance(raw_skills, str):
            skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
        elif isinstance(raw_skills, list):
            skills = [str(s).strip() for s in raw_skills if str(s).strip()]
        else:
            skills = []

        opp = Opportunity(
            title=item.title,
            company=item.company,
            description=desc,
            opportunity_type=item.opportunity_type,
            skills=skills,
            location=item.location,
            remote="remote" in item.location.lower(),
            work_mode="remote" if "remote" in item.location.lower() else ("hybrid" if "hybrid" in item.location.lower() else "on-site"),
            stipend=raw.get("stipend") or raw.get("Stipend") or None,
            salary=raw.get("salary") or raw.get("Salary") or None,
            experience=raw.get("experience") or raw.get("Experience") or "Fresher / Student",
            eligibility=raw.get("eligibility") or raw.get("Eligibility") or "All students",
            deadline=raw.get("deadline") or raw.get("Deadline") or None,
            source=source_name,
            source_url=raw.get("source_url") or raw.get("job_url") or item.apply_url,
            apply_url=item.apply_url,
            posted_date=str(raw.get("posted_date") or date.today().isoformat())[:10],
            status="active",
            trust_level=trust_level,
            source_id=source_id,
            verification_status="PENDING_REVIEW"
        )

        # Run 7-stage verification gate
        final_status, verif_level, checks, failure_reasons = evaluate_opportunity_verification(opp, db=db)
        opp.verification_status = final_status
        opp.verification_checks = json.dumps(checks)
        if failure_reasons:
            opp.verification_notes = f"Validation notices: {'; '.join(failure_reasons[:3])}"

        saved = save_opportunity(opp)
        accepted_count += 1

    # Update source metrics in database
    if source_row:
        record_source_run(
            db=db,
            source_id=source_row.id,
            success=True,
            items_added=accepted_count,
            items_rejected=rejected_count + duplicate_count,
            items_found=preview.total_records
        )

    log_audit_event(
        db=db,
        event_type="IMPORT_CONFIRMED",
        actor=admin_user,
        target=source_name,
        details={
            "source_type": source_type,
            "total_records": preview.total_records,
            "accepted": accepted_count,
            "rejected": rejected_count,
            "duplicates": duplicate_count
        }
    )

    try:
        sync_db_to_json()
    except Exception:
        pass

    return {
        "status": "success",
        "message": f"Successfully ingested {accepted_count} opportunities from {source_name}.",
        "total_records": preview.total_records,
        "accepted": accepted_count,
        "rejected": rejected_count,
        "duplicates": duplicate_count,
        "rejection_summary": preview.rejection_summary
    }


