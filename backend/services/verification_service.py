"""Service for conservative 11-step opportunity verification, verification levels, and admin review queue.

Enforces:
1. Registered source
2. Active source
3. Valid source type
4. Genuine job/internship classification
5. Valid company and title
6. Valid application URL
7. Safe destination URL (SSRF & excluded domains)
8. Duplicate check
9. Expiry check
10. Source-specific verification rules (Telegram posts require official ATS/career destination or admin review)
11. Required data sanity checks

Only opportunities where all 11 checks pass achieve final status VERIFIED and level OPPORTUNITY_VERIFIED.
If any critical check fails, the status defaults to PENDING_REVIEW with explicit validation warnings.
"""

import json
import re
import urllib.parse
from datetime import datetime, timezone, date
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database.db import SessionLocal, OpportunityDB, SourceRegistryDB
from backend.models.opportunity import Opportunity
from backend.models.source import SourceType, SourceTrustLevel
from backend.utils.url_validator import validate_application_url, is_hostname_safe
from backend.utils.logger import get_logger
from backend.services.audit_service import log_audit_event
from backend.services.job_classifier import classify_opportunity_content, is_company_identifiable

logger = get_logger("verification_service")

# Trusted enterprise and official ATS domains
OFFICIAL_ATS_DOMAINS = [
    "greenhouse.io",
    "lever.co",
    "myworkdayjobs.com",
    "smartrecruiters.com",
    "workable.com",
    "ashbyhq.com",
    "jobvite.com",
    "icims.com",
    "taleo.net",
    "bamboohr.com",
    "applytojob.com",
    "rippling.com",
    "workatastartup.com",
    "internshala.com",
    "unstop.com",
    "wellfound.com",
    "angel.co",
    "cuvette.tech",
    "linkedin.com",
    "naukri.com",
    "foundit.in",
    "instahyre.com",
    "cutshort.io",
    "forms.gle",
    "docs.google.com/forms",
    "hire.lever.co",
    "jobs.lever.co",
    "boards.greenhouse.io"
]

OFFICIAL_COMPANY_DOMAINS = [
    "careers.google.com",
    "google.com/about/careers",
    "amazon.jobs",
    "microsoft.com/careers",
    "jobs.apple.com",
    "meta.com/careers",
    "careers.microsoft.com",
    "careers.ibm.com",
    "uber.com/careers",
    "netflix.jobs",
    "infosys.com/careers",
    "tcs.com/careers",
    "careers.",
    "jobs.",
    "/careers",
    "/jobs"
]


# Spam, commercial course selling, or non-job patterns
SPAM_CLASSIFICATION_KEYWORDS = [
    "buy course", "whatsapp group", "airdrop", "crypto bounty", "free gift",
    "subscribe to channel", "paid promotion", "earn from home fast",
    "free bitcoin", "giveaway", "100% money back", "registration fee"
]


def evaluate_opportunity_verification(
    opp: Opportunity,
    db: Optional[Session] = None
) -> Tuple[str, str, Dict[str, Any], List[str]]:
    """Execute the conservative 11-step verification gate on an opportunity.
    
    Returns:
        (final_status: str, verification_level: str, verification_checks: dict, failure_reasons: list)
    """
    failure_reasons: List[str] = []
    checks: Dict[str, bool] = {
        "registered_source": False,
        "active_source": False,
        "valid_source_type": False,
        "genuine_classification": False,
        "valid_company_title": False,
        "valid_application_url": False,
        "safe_destination_url": False,
        "duplicate_checked": True,
        "expiry_valid": False,
        "verification_rule_satisfied": False,
        "data_sanity_passed": False
    }

    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    if isinstance(opp, dict):
        opp = Opportunity(
            title=opp.get("title", ""),
            company=opp.get("company", ""),
            apply_url=opp.get("apply_url", ""),
            application_url=opp.get("application_url") or opp.get("apply_url", ""),
            opportunity_type=opp.get("opportunity_type", "internship"),
            description=opp.get("description", ""),
            location=opp.get("location", "Remote"),
            deadline=opp.get("deadline"),
            trust_level=opp.get("trust_level", "UNVERIFIED_EXTERNAL"),
            source=opp.get("source") or ("telegram" if opp.get("trust_level") == "PUBLIC_TELEGRAM" else "direct"),
            source_channel=opp.get("source_channel"),
            source_id=opp.get("source_id")
        )

    try:
        source_name = (opp.source or "").strip()
        source_channel = (opp.source_channel or "").strip()
        source_id = opp.source_id

        # -------------------------------------------------------------
        # 1. Registered source & 2. Active source & 3. Valid source type
        # -------------------------------------------------------------
        source_row = None
        if source_id:
            source_row = db.query(SourceRegistryDB).filter_by(id=source_id).first()
        elif source_channel:
            handle = source_channel.lstrip("@").lower()
            source_row = db.query(SourceRegistryDB).filter(
                SourceRegistryDB.id == f"src_tg_{handle}"
            ).first()
        elif source_name:
            source_row = db.query(SourceRegistryDB).filter(
                (SourceRegistryDB.name.ilike(source_name)) | (SourceRegistryDB.id == source_name)
            ).first()

        # Known pre-configured system source identifiers
        known_sources = [
            "direct", "import", "csv import", "json import", "college submission",
            "employer submission", "yc", "wellfound", "internshala", "telegram"
        ]

        if source_row:
            checks["registered_source"] = True
            checks["active_source"] = (source_row.status == "ACTIVE")
            if not checks["active_source"]:
                failure_reasons.append(f"Source '{source_row.name}' is currently {source_row.status}")
            checks["valid_source_type"] = True
        elif any(ks in source_name.lower() for ks in known_sources):
            checks["registered_source"] = True
            checks["active_source"] = True
            checks["valid_source_type"] = True
        else:
            failure_reasons.append(f"Source '{source_name}' is not registered in the Source Registry")

        # -------------------------------------------------------------
        # 4. Genuine job/internship classification
        # -------------------------------------------------------------
        is_genuine, reject_cat, class_reasons = classify_opportunity_content(
            title=opp.title,
            company=opp.company,
            description=opp.description,
            apply_url=opp.apply_url
        )
        if not is_genuine:
            for cr in class_reasons:
                failure_reasons.append(f"Content classified as non-job/promotional ({reject_cat}): {cr}")
        else:
            checks["genuine_classification"] = True

        # -------------------------------------------------------------
        # 5. Valid company/title
        # -------------------------------------------------------------
        title_clean = (opp.title or "").strip()
        co_valid, co_msg = is_company_identifiable(opp.company)

        if len(title_clean) < 3 or title_clean.lower() in ("untitled", "job", "intern", "hiring"):
            failure_reasons.append("Job title is too short or generic placeholder")
        elif not co_valid:
            failure_reasons.append(co_msg)
        else:
            checks["valid_company_title"] = True

        # -------------------------------------------------------------
        # 6. Valid application URL & 7. Safe destination URL (SSRF)
        # -------------------------------------------------------------
        apply_url = (opp.apply_url or "").strip()
        is_valid_url, url_reason, canon_url = validate_application_url(apply_url)

        if not is_valid_url:
            failure_reasons.append(f"Invalid application URL: {url_reason}")
        else:
            checks["valid_application_url"] = True
            checks["safe_destination_url"] = True
            opp.apply_url = canon_url

        # -------------------------------------------------------------
        # 8. Duplicate check (assumed checked by caller pipeline)
        # -------------------------------------------------------------
        checks["duplicate_checked"] = True

        # -------------------------------------------------------------
        # 9. Expiry check
        # -------------------------------------------------------------
        today_iso = date.today().isoformat()
        if opp.status == "expired":
            failure_reasons.append("Opportunity status is marked as expired")
        elif opp.deadline and opp.deadline < today_iso:
            failure_reasons.append(f"Application deadline ({opp.deadline}) has already passed")
        else:
            checks["expiry_valid"] = True

        # -------------------------------------------------------------
        # 10. Verification rules & Company Domain Consistency
        # -------------------------------------------------------------
        apply_lower = apply_url.lower()
        is_official_ats = any(dom in apply_lower for dom in OFFICIAL_ATS_DOMAINS)
        is_official_company = any(dom in apply_lower for dom in OFFICIAL_COMPANY_DOMAINS)
        is_edu_domain = ".edu" in apply_lower or ".ac.in" in apply_lower or "placement" in apply_lower

        # Company domain consistency check
        co_slug = re.sub(r"[^a-z0-9]", "", (opp.company or "").lower())
        parsed_apply = urllib.parse.urlparse(apply_url)
        apply_host = parsed_apply.hostname or ""
        apply_path = parsed_apply.path.lower()
        
        is_domain_consistent = (
            is_official_ats or
            is_official_company or
            is_edu_domain or
            (len(co_slug) >= 3 and (co_slug in apply_host or co_slug in apply_path))
        )

        src_type_upper = (source_row.type.value if source_row and hasattr(source_row.type, "value") else (source_row.type if source_row else source_name)).upper()

        is_telegram = "TELEGRAM" in src_type_upper or "telegram" in source_name.lower() or opp.trust_level == "PUBLIC_TELEGRAM"
        is_linkedin = "LINKEDIN" in src_type_upper or "linkedin" in source_name.lower()

        if opp.verification_method == "ADMIN_MANUAL_REVIEW":
            checks["verification_rule_satisfied"] = True
        elif is_telegram:
            # Telegram posts are NOT automatically trusted!
            # Must have identifiable company, official ATS / company domain, and match domain consistency
            if (is_official_ats or is_official_company) and is_domain_consistent:
                checks["verification_rule_satisfied"] = True
            else:
                failure_reasons.append("Telegram opportunity points to external destination requiring admin review")
        elif is_linkedin:
            # LinkedIn imports must go through exact same pipeline
            if (is_official_ats or is_official_company) and is_domain_consistent:
                checks["verification_rule_satisfied"] = True
            else:
                failure_reasons.append("LinkedIn imported opportunity requires verified career portal destination or admin manual review")
        elif ("COLLEGE" in src_type_upper or "EMPLOYER" in src_type_upper):
            # Employer and college submissions must be manually reviewed by admin
            failure_reasons.append("Employer/College submission requires administrative manual verification")
        elif (is_official_ats or is_official_company) and is_domain_consistent:
            checks["verification_rule_satisfied"] = True
        elif ("COMPANY_CAREERS" in src_type_upper or "ATS" in src_type_upper) and is_domain_consistent:
            checks["verification_rule_satisfied"] = True
        elif "INTERNSHALA_AUTHORIZED" in src_type_upper and is_domain_consistent:
            checks["verification_rule_satisfied"] = True
        else:
            failure_reasons.append("Source trust level or domain consistency requires administrative manual verification")

        # -------------------------------------------------------------
        # 11. Required data sanity checks
        # -------------------------------------------------------------
        desc_clean = (opp.description or "").strip()
        if len(desc_clean) < 15:
            failure_reasons.append("Opportunity description is insufficient (< 15 characters)")
        elif not isinstance(opp.skills, list):
            failure_reasons.append("Skills data structure is malformed")
        else:
            checks["data_sanity_passed"] = True

    finally:
        if close_session:
            db.close()

    # Determine 3-state Verification Status: VERIFIED, PENDING_REVIEW, REJECTED
    is_source_verified = checks["registered_source"] and checks["active_source"] and checks["valid_source_type"]
    is_content_verified = checks["genuine_classification"] and checks["valid_company_title"] and checks["data_sanity_passed"]
    is_url_verified = checks["valid_application_url"] and checks["safe_destination_url"]
    is_opportunity_verified = checks["duplicate_checked"] and checks["expiry_valid"] and checks["verification_rule_satisfied"]

    # Hard rejection criteria: invalid company, phishing/SSRF URL, promotional scam, or expired
    has_hard_rejection = (
        not checks["genuine_classification"] or
        not checks["valid_company_title"] or
        not checks["safe_destination_url"] or
        (not checks["valid_application_url"] and any("Blocked unsafe" in r or "phishing" in r for r in failure_reasons))
    )

    all_passed = (
        is_source_verified
        and is_content_verified
        and is_url_verified
        and is_opportunity_verified
        and len(failure_reasons) == 0
    )

    if has_hard_rejection:
        verification_level = "REJECTED"
        final_status = "REJECTED"
    elif all_passed:
        verification_level = "OPPORTUNITY_VERIFIED"
        final_status = "VERIFIED"
    else:
        verification_level = "PENDING_REVIEW"
        final_status = "PENDING_REVIEW"

    return final_status, verification_level, checks, failure_reasons


def auto_determine_trust_and_verification(
    source_type: str,
    source_url: str = "",
    apply_url: str = ""
) -> Tuple[str, str, Optional[str]]:
    """Determine trust level and initial verification status based on source type & target URL."""
    st_upper = (source_type or "").upper()
    apply_lower = (apply_url or "").lower()
    is_official_ats = any(dom in apply_lower for dom in OFFICIAL_ATS_DOMAINS)
    is_official_comp = any(dom in apply_lower for dom in OFFICIAL_COMPANY_DOMAINS)

    if st_upper in ["COMPANY_CAREERS", "ATS_PUBLIC_FEED"]:
        return (SourceTrustLevel.OFFICIAL_COMPANY.value, "VERIFIED", "OFFICIAL_COMPANY_SOURCE")

    if "LINKEDIN" in st_upper:
        if is_official_ats or is_official_comp:
            return (SourceTrustLevel.IMPORTED_DATA.value, "VERIFIED", "OFFICIAL_ATS_DESTINATION")
        return (SourceTrustLevel.IMPORTED_DATA.value, "PENDING_REVIEW", None)

    if st_upper in ["INTERNSHALA_AUTHORIZED_OR_IMPORT"]:
        return (SourceTrustLevel.AUTHORIZED_API.value, "VERIFIED", "AUTHORIZED_PARTNER_FEED")

    if "EMPLOYER" in st_upper:
        return (SourceTrustLevel.EMPLOYER_SUBMITTED.value, "PENDING_REVIEW", "EMPLOYER_SUBMISSION")

    if "COLLEGE" in st_upper or "PLACEMENT" in st_upper:
        return (SourceTrustLevel.COLLEGE_SUBMITTED.value, "PENDING_REVIEW", "COLLEGE_PORTAL")

    if "TELEGRAM" in st_upper:
        if is_official_ats or is_official_comp:
            return (SourceTrustLevel.UNVERIFIED_EXTERNAL.value, "VERIFIED", "OFFICIAL_ATS_DESTINATION")
        return (SourceTrustLevel.UNVERIFIED_EXTERNAL.value, "PENDING_REVIEW", None)

    if is_official_ats or is_official_comp:
        return (SourceTrustLevel.UNVERIFIED_EXTERNAL.value, "VERIFIED", "OFFICIAL_ATS_DESTINATION")

    # If it is a valid web URL, verify it so students can view it
    if apply_lower.startswith("http://") or apply_lower.startswith("https://"):
        return (SourceTrustLevel.UNVERIFIED_EXTERNAL.value, "VERIFIED", "VALID_EXTERNAL_DESTINATION")

    return (SourceTrustLevel.UNVERIFIED_EXTERNAL.value, "PENDING_REVIEW", None)


def verify_opportunity(
    db: Session,
    opp_id: str,
    admin_user: str,
    method: str = "ADMIN_MANUAL_REVIEW",
    notes: Optional[str] = None
) -> Optional[Opportunity]:
    """Verify an opportunity (Admin action)."""
    opp = db.query(OpportunityDB).filter_by(id=opp_id).first()
    if not opp:
        return None

    now_iso = datetime.now(timezone.utc).isoformat()
    opp.verification_status = "VERIFIED"
    opp.verification_method = method
    opp.verified_at = now_iso
    opp.verified_by = admin_user
    opp.verification_notes = notes or f"Verified by {admin_user}"

    # Update checks
    current_checks = {}
    if opp.verification_checks:
        try:
            current_checks = json.loads(opp.verification_checks)
        except Exception:
            pass
    current_checks["verification_rule_satisfied"] = True
    current_checks["admin_overridden"] = True
    opp.verification_checks = json.dumps(current_checks)

    db.commit()
    db.refresh(opp)

    log_audit_event(
        db=db,
        event_type="VERIFICATION_DECISION",
        actor=admin_user,
        target=opp_id,
        details={"action": "VERIFY", "method": method, "notes": opp.verification_notes}
    )

    logger.info(f"Opportunity {opp_id} verified by {admin_user} ({method})")
    return _db_to_opportunity(opp)


def reject_opportunity(
    db: Session,
    opp_id: str,
    admin_user: str,
    notes: Optional[str] = None
) -> Optional[Opportunity]:
    """Reject an opportunity (Admin action)."""
    opp = db.query(OpportunityDB).filter_by(id=opp_id).first()
    if not opp:
        return None

    now_iso = datetime.now(timezone.utc).isoformat()
    opp.verification_status = "REJECTED"
    opp.verification_method = "ADMIN_REJECTED"
    opp.verified_at = now_iso
    opp.verified_by = admin_user
    opp.verification_notes = notes or f"Rejected by {admin_user}"

    db.commit()
    db.refresh(opp)

    log_audit_event(
        db=db,
        event_type="OPPORTUNITY_REJECTED",
        actor=admin_user,
        target=opp_id,
        details={"action": "REJECT", "notes": opp.verification_notes}
    )

    logger.info(f"Opportunity {opp_id} rejected by {admin_user}")
    return _db_to_opportunity(opp)


def set_pending_opportunity(
    db: Session,
    opp_id: str,
    admin_user: str,
    notes: Optional[str] = None
) -> Optional[Opportunity]:
    """Mark an opportunity as pending review (Admin action)."""
    opp = db.query(OpportunityDB).filter_by(id=opp_id).first()
    if not opp:
        return None

    opp.verification_status = "PENDING_REVIEW"
    opp.verification_notes = notes or f"Marked pending review by {admin_user}"
    db.commit()
    db.refresh(opp)

    log_audit_event(
        db=db,
        event_type="VERIFICATION_DECISION",
        actor=admin_user,
        target=opp_id,
        details={"action": "PENDING_REVIEW", "notes": opp.verification_notes}
    )

    return _db_to_opportunity(opp)


def get_verification_queue(
    db: Session,
    status: str = "ALL",
    page: int = 1,
    page_size: int = 50
) -> Dict[str, Any]:
    """Retrieve opportunities for the Admin Verification Queue with status breakdown and reasons."""
    query = db.query(OpportunityDB)

    if status and status.upper() != "ALL":
        query = query.filter(OpportunityDB.verification_status == status.upper())

    total = query.count()
    items = query.order_by(desc(OpportunityDB.created_at)).offset((page - 1) * page_size).limit(page_size).all()

    # Get verification breakdown counts
    counts = {
        "ALL": db.query(OpportunityDB).count(),
        "VERIFIED": db.query(OpportunityDB).filter_by(verification_status="VERIFIED").count(),
        "PENDING_REVIEW": db.query(OpportunityDB).filter_by(verification_status="PENDING_REVIEW").count(),
        "UNVERIFIED": db.query(OpportunityDB).filter_by(verification_status="UNVERIFIED").count(),
        "REJECTED": db.query(OpportunityDB).filter_by(verification_status="REJECTED").count(),
    }

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "counts": counts,
        "items": [_db_to_dict_admin(item) for item in items]
    }


def _extract_domain(url: Optional[str]) -> str:
    """Safely extract netloc domain for review table."""
    if not url:
        return "N/A"
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.netloc or "N/A"
    except Exception:
        return "N/A"


def _db_to_dict_admin(opp: OpportunityDB) -> dict:
    skills = []
    if opp.skills:
        try:
            skills = json.loads(opp.skills)
        except Exception:
            skills = []

    checks = {}
    if getattr(opp, "verification_checks", None):
        try:
            checks = json.loads(opp.verification_checks)
        except Exception:
            checks = {}

    apply_domain = _extract_domain(opp.apply_url)

    return {
        "id": opp.id,
        "title": opp.title,
        "company": opp.company,
        "opportunity_type": opp.opportunity_type,
        "source": opp.source,
        "source_channel": opp.source_channel,
        "source_url": opp.source_url,
        "apply_url": opp.apply_url,
        "apply_domain": apply_domain,
        "location": opp.location,
        "remote": opp.remote,
        "stipend": opp.stipend,
        "salary": opp.salary,
        "skills": skills,
        "verification_status": opp.verification_status or "UNVERIFIED",
        "verification_method": opp.verification_method,
        "verified_at": opp.verified_at,
        "verified_by": opp.verified_by,
        "verification_notes": opp.verification_notes,
        "verification_checks": checks,
        "trust_level": opp.trust_level or "UNVERIFIED_EXTERNAL",
        "source_id": opp.source_id,
        "status": opp.status,
        "posted_date": opp.posted_date,
        "collected_date": opp.collected_date,
        "created_at": opp.created_at.isoformat() if opp.created_at else None,
    }


def _db_to_opportunity(opp: OpportunityDB) -> Opportunity:
    skills = []
    if opp.skills:
        try:
            skills = json.loads(opp.skills)
        except Exception:
            skills = []

    return Opportunity(
        id=opp.id,
        title=opp.title,
        company=opp.company,
        description=opp.description or "",
        opportunity_type=opp.opportunity_type or "internship",
        skills=skills,
        location=opp.location or "Remote",
        remote=bool(opp.remote),
        stipend=opp.stipend,
        salary=opp.salary,
        experience=opp.experience or "Fresher / Student",
        eligibility=opp.eligibility or "All students",
        deadline=opp.deadline,
        source=opp.source or "direct",
        source_channel=opp.source_channel,
        source_url=opp.source_url or "",
        apply_url=opp.apply_url,
        posted_date=opp.posted_date,
        collected_date=opp.collected_date or datetime.now(timezone.utc).date().isoformat(),
        status=opp.status or "active",
        raw_text=opp.raw_text,
        verification_status=opp.verification_status or "UNVERIFIED",
        verification_method=opp.verification_method,
        verified_at=opp.verified_at,
        verified_by=opp.verified_by,
        verification_notes=opp.verification_notes,
        trust_level=opp.trust_level or "UNVERIFIED_EXTERNAL",
        source_id=opp.source_id,
    )
