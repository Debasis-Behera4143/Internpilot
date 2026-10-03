"""Opportunity service for retrieving, filtering, saving, and aggregating opportunities."""

import json
import re
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Tuple, Union
from sqlalchemy import func
from backend.models.opportunity import Opportunity
from backend.database.db import SessionLocal, OpportunityDB
from backend.database.sync import compute_job_id, sync_db_to_json
from backend.collectors.normalizer import normalize_opportunity
from backend.utils.logger import get_logger

logger = get_logger("opportunity_service")


def get_all_opportunities(
    query: Optional[str] = None,
    opportunity_type: Optional[str] = None,
    source: Optional[str] = None,
    location: Optional[str] = None,
    remote_only: Optional[bool] = None,
    work_mode: Optional[str] = None,
    experience: Optional[str] = None,
    company: Optional[str] = None,
    posted_within_days: Optional[int] = None,
    has_salary: Optional[bool] = None,
    verified_only: Optional[bool] = None,
    verification_status: Optional[str] = None,
    approval_status: Optional[str] = None,
    unknown_company: Optional[bool] = None,
    low_confidence: Optional[bool] = None,
    duplicate_candidates: Optional[bool] = None,
    skill: Optional[str] = None,
    status: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
    sort_by: Optional[str] = "newest",
    return_total: bool = False
) -> Union[List[Opportunity], Tuple[List[Opportunity], int]]:
    """Retrieve filtered list of opportunities with multi-filter combinations, sorting, and pagination."""
    session = SessionLocal()
    try:
        q = session.query(OpportunityDB)

        today_str = date.today().isoformat()

        # Approval Status filter
        if approval_status:
            q = q.filter(OpportunityDB.approval_status == approval_status.lower())

        # Unknown company filter
        if unknown_company is True:
            q = q.filter((OpportunityDB.company.in_(["Unknown", "Unknown Company", "N/A", "NA", "Not specified", "Company"])) | (OpportunityDB.normalized_company == "Unknown"))
        elif unknown_company is False:
            q = q.filter(~OpportunityDB.company.in_(["Unknown", "Unknown Company", "N/A", "NA", "Not specified", "Company"]))

        # Low confidence filter (< 0.70)
        if low_confidence:
            q = q.filter((OpportunityDB.company_confidence.isnot(None)) & (OpportunityDB.company_confidence < 0.70))

        # Duplicate candidates filter
        if duplicate_candidates:
            q = q.filter(OpportunityDB.duplicate_group.isnot(None))

        # Verified Only filter (Fail-closed: verified, active, not expired)
        if verified_only:
            q = q.filter(
                OpportunityDB.verification_status == "VERIFIED",
                OpportunityDB.status.in_(["active", "open"]),
                (OpportunityDB.deadline.is_(None) | (OpportunityDB.deadline == "") | (OpportunityDB.deadline >= today_str))
            )
        else:
            # Status filter (default to all if not specified, or match specific)
            if status:
                if status.lower() == "active":
                    q = q.filter(OpportunityDB.status.in_(["active", "open"]))
                else:
                    q = q.filter(OpportunityDB.status == status.lower())

            if verification_status:
                q = q.filter(OpportunityDB.verification_status == verification_status.upper())

        # Company filter
        if company:
            q = q.filter(OpportunityDB.company.ilike(f"%{company.strip()}%"))

        # Type filter
        if opportunity_type:
            op_t = opportunity_type.strip().lower()
            if op_t in ["all", ""]:
                pass
            elif op_t in ["internship", "internships"]:
                q = q.filter(OpportunityDB.opportunity_type.ilike("%intern%"))
            elif op_t in ["job", "jobs", "full-time", "fulltime"]:
                q = q.filter((OpportunityDB.opportunity_type.ilike("%job%")) | (OpportunityDB.opportunity_type.ilike("%full%")))
            elif op_t in ["part-time", "parttime"]:
                q = q.filter(OpportunityDB.opportunity_type.ilike("%part%"))
            elif op_t in ["apprenticeship", "apprenticeships"]:
                q = q.filter(OpportunityDB.opportunity_type.ilike("%apprentice%"))
            else:
                q = q.filter(OpportunityDB.opportunity_type.ilike(f"%{op_t}%"))

        # Source filter
        if source:
            q = q.filter(OpportunityDB.source.ilike(f"%{source}%"))

        # Location filter
        if location:
            q = q.filter(OpportunityDB.location.ilike(f"%{location.strip()}%"))

        # Remote / Work mode filter
        if work_mode:
            wm = work_mode.strip().lower()
            if wm == "remote":
                q = q.filter((OpportunityDB.remote == True) | (OpportunityDB.location.ilike("%remote%")))
            elif wm == "hybrid":
                q = q.filter((OpportunityDB.location.ilike("%hybrid%")) | (OpportunityDB.description.ilike("%hybrid%")))
            elif wm in ["on-site", "onsite", "in-office"]:
                q = q.filter(OpportunityDB.remote == False)
        elif remote_only is not None:
            q = q.filter(OpportunityDB.remote == remote_only)

        # Experience level filter
        if experience:
            exp_lower = experience.strip().lower()
            if "fresher" in exp_lower or "student" in exp_lower or "0" in exp_lower:
                q = q.filter(
                    (OpportunityDB.experience.ilike("%fresher%")) |
                    (OpportunityDB.experience.ilike("%student%")) |
                    (OpportunityDB.experience.ilike("%0%")) |
                    (OpportunityDB.eligibility.ilike("%student%")) |
                    (OpportunityDB.eligibility.ilike("%all%"))
                )
            elif "experienced" in exp_lower or "1+" in exp_lower or "2+" in exp_lower:
                q = q.filter(
                    (OpportunityDB.experience.ilike("%year%")) |
                    (OpportunityDB.experience.ilike("%exp%")) |
                    (OpportunityDB.experience.ilike("%1%")) |
                    (OpportunityDB.experience.ilike("%2%")) |
                    (OpportunityDB.experience.ilike("%3%"))
                )

        # Salary / Stipend filter
        if has_salary:
            q = q.filter(
                (OpportunityDB.stipend.isnot(None) & (OpportunityDB.stipend != "")) |
                (OpportunityDB.salary.isnot(None) & (OpportunityDB.salary != ""))
            )

        db_opps = q.all()
        filtered: List[Opportunity] = []
        today_date = date.today()

        for row in db_opps:
            skills = json.loads(row.skills or "[]")

            # Search text query (matches title, company, description, or skills)
            if query:
                q_lower = query.strip().lower()
                combined = f"{row.title} {row.company} {row.description} {' '.join(skills)} {row.location}".lower()
                # Split search terms for multi-word fuzzy matching
                terms = q_lower.split()
                if not all(t in combined for t in terms):
                    continue

            # Skill filter
            if skill:
                s_lower = skill.strip().lower()
                if not any(s_lower in s.lower() for s in skills):
                    continue

            # Posted recently filter
            if posted_within_days:
                try:
                    p_date_str = row.posted_date or row.collected_date
                    if p_date_str:
                        p_date = datetime.strptime(p_date_str[:10], "%Y-%m-%d").date()
                        if (today_date - p_date).days > posted_within_days:
                            continue
                except Exception:
                    pass

            filtered.append(Opportunity(
                id=row.id,
                title=row.title,
                company=row.company,
                description=row.description,
                opportunity_type=row.opportunity_type,
                skills=skills,
                location=row.location,
                remote=row.remote,
                stipend=row.stipend,
                salary=row.salary,
                experience=row.experience,
                eligibility=row.eligibility,
                deadline=row.deadline,
                source=row.source,
                source_channel=getattr(row, "source_channel", None),
                source_url=row.source_url,
                apply_url=row.apply_url,
                application_url=getattr(row, "application_url", None) or row.apply_url,
                normalized_url=getattr(row, "normalized_url", None) or row.apply_url,
                posted_date=row.posted_date,
                collected_date=row.collected_date,
                status=row.status,
                raw_text=getattr(row, "raw_text", None),
                verification_status=getattr(row, "verification_status", None) or "UNVERIFIED",
                verification_method=getattr(row, "verification_method", None),
                verified_at=getattr(row, "verified_at", None),
                verified_by=getattr(row, "verified_by", None),
                verification_notes=getattr(row, "verification_notes", None),
                trust_level=getattr(row, "trust_level", None) or "UNVERIFIED_EXTERNAL",
                source_id=getattr(row, "source_id", None),
                approval_status=getattr(row, "approval_status", None) or ("approved" if getattr(row, "verification_status", "") == "VERIFIED" else "pending"),
                confidence_score=getattr(row, "confidence_score", 1.0) if getattr(row, "confidence_score", None) is not None else 1.0,
                company_confidence=getattr(row, "company_confidence", 1.0) if getattr(row, "company_confidence", None) is not None else 1.0,
                company_evidence=getattr(row, "company_evidence", None),
                normalized_company=getattr(row, "normalized_company", None) or row.company,
                duplicate_group=getattr(row, "duplicate_group", None),
                rejection_reason=getattr(row, "rejection_reason", None),
                source_name=getattr(row, "source_name", None),
                source_message_id=getattr(row, "source_message_id", None),
                company_url=getattr(row, "company_url", None)
            ))

        # In-memory sorts ensuring consistent order
        sort_mode = (sort_by or "newest").lower()
        if sort_mode == "title":
            filtered.sort(key=lambda o: (o.title or "").lower())
        elif sort_mode == "company":
            filtered.sort(key=lambda o: (o.company or "").lower())
        elif sort_mode in ["deadline", "deadline_soon"]:
            # Soonest non-expired deadlines first, opportunities without deadline last
            filtered.sort(key=lambda o: (o.deadline is None or o.deadline == "", o.deadline or "9999-99-99"))
        elif sort_mode in ["stipend", "highest_stipend", "salary"]:
            def _extract_amount(text):
                if not text:
                    return 0
                nums = re.findall(r"\d+", text.replace(",", ""))
                return int(nums[0]) if nums else 0
            filtered.sort(key=lambda o: max(_extract_amount(o.stipend), _extract_amount(o.salary)), reverse=True)
        elif sort_mode in ["relevance", "most_relevant"] and query:
            # Score by query frequency in title and company
            q_lower = query.lower()
            def _rel_score(o):
                sc = 0
                if q_lower in (o.title or "").lower():
                    sc += 10
                if q_lower in (o.company or "").lower():
                    sc += 5
                if any(q_lower in s.lower() for s in o.skills):
                    sc += 3
                return sc
            filtered.sort(key=_rel_score, reverse=True)
        else:
            # Newest first
            filtered.sort(key=lambda o: (o.posted_date or o.collected_date or "", o.id), reverse=True)

        total_count = len(filtered)

        # Apply pagination
        paginated = filtered
        if offset > 0:
            paginated = paginated[offset:]
        if limit is not None and limit > 0:
            paginated = paginated[:limit]

        if return_total:
            return paginated, total_count
        return paginated
    finally:
        session.close()


def get_opportunity_stats() -> Dict[str, Any]:
    """Return aggregated statistical breakdown of opportunities with data quality metrics."""
    session = SessionLocal()
    try:
        total = session.query(OpportunityDB).count()
        active = session.query(OpportunityDB).filter(OpportunityDB.status.in_(["active", "open"])).count()
        expired = session.query(OpportunityDB).filter_by(status="expired").count()
        closed = session.query(OpportunityDB).filter_by(status="closed").count()

        # Count by source
        by_source_rows = session.query(OpportunityDB.source, func.count(OpportunityDB.id)).group_by(OpportunityDB.source).all()
        by_source = {s or "Unknown": count for s, count in by_source_rows}

        # Count by opportunity type
        by_type_rows = session.query(OpportunityDB.opportunity_type, func.count(OpportunityDB.id)).group_by(OpportunityDB.opportunity_type).all()
        by_type = {t or "other": count for t, count in by_type_rows}

        # Data Quality Indicators across all stored records
        records = session.query(OpportunityDB).all()
        title_count = 0
        company_count = 0
        apply_url_count = 0
        source_count = 0
        deadline_count = 0
        skills_count = 0
        location_count = 0

        for r in records:
            if r.title and len(r.title.strip()) > 1:
                title_count += 1
            if r.company and r.company.strip().lower() not in ("", "unknown"):
                company_count += 1
            if r.apply_url and r.apply_url.strip().startswith(("http://", "https://")):
                apply_url_count += 1
            if r.source and len(r.source.strip()) > 0:
                source_count += 1
            if r.deadline and len(r.deadline.strip()) > 0:
                deadline_count += 1
            try:
                sk = json.loads(r.skills or "[]")
                if len(sk) > 0:
                    skills_count += 1
            except Exception:
                pass
            if r.location and r.location.strip().lower() not in ("", "not specified"):
                location_count += 1

        pct = lambda cnt: round((cnt / total * 100), 1) if total > 0 else 100.0

        data_quality = {
            "title_present_pct": pct(title_count),
            "company_present_pct": pct(company_count),
            "apply_url_present_pct": pct(apply_url_count),
            "source_present_pct": pct(source_count),
            "deadline_available_pct": pct(deadline_count),
            "skills_available_pct": pct(skills_count),
            "location_available_pct": pct(location_count),
            "overall_quality_score": round(
                (pct(title_count) + pct(company_count) + pct(apply_url_count) +
                 pct(source_count) + pct(deadline_count) + pct(skills_count) + pct(location_count)) / 7.0,
                1
            ) if total > 0 else 100.0
        }

        # Count by verification status
        by_verif_rows = session.query(OpportunityDB.verification_status, func.count(OpportunityDB.id)).group_by(OpportunityDB.verification_status).all()
        by_verification = {v or "UNVERIFIED": count for v, count in by_verif_rows}

        return {
            "total": total,
            "active": active,
            "expired": expired,
            "closed": closed,
            "by_source": by_source,
            "by_type": by_type,
            "by_verification": by_verification,
            "data_quality": data_quality
        }
    finally:
        session.close()


def save_opportunity(opp: Opportunity) -> Opportunity:
    """Normalize and persist an opportunity in the database."""
    session = SessionLocal()
    try:
        norm_opp = normalize_opportunity(opp)
        opp_id = norm_opp.id or compute_job_id(norm_opp.company, norm_opp.title, norm_opp.apply_url)
        norm_opp.id = opp_id

        existing = session.query(OpportunityDB).filter_by(id=opp_id).first()
        if not existing:
            db_row = OpportunityDB(
                id=opp_id,
                title=norm_opp.title,
                company=norm_opp.company,
                description=norm_opp.description,
                opportunity_type=norm_opp.opportunity_type,
                skills=json.dumps(norm_opp.skills),
                location=norm_opp.location,
                remote=norm_opp.remote,
                stipend=norm_opp.stipend,
                salary=norm_opp.salary,
                experience=norm_opp.experience,
                eligibility=norm_opp.eligibility,
                deadline=norm_opp.deadline,
                source=norm_opp.source,
                source_channel=norm_opp.source_channel,
                source_url=norm_opp.source_url,
                apply_url=norm_opp.apply_url,
                application_url=norm_opp.application_url or norm_opp.apply_url,
                normalized_url=norm_opp.normalized_url or norm_opp.apply_url,
                posted_date=norm_opp.posted_date,
                collected_date=norm_opp.collected_date,
                status=norm_opp.status,
                raw_text=norm_opp.raw_text,
                verification_status=norm_opp.verification_status or "UNVERIFIED",
                verification_method=norm_opp.verification_method,
                verified_at=norm_opp.verified_at,
                verified_by=norm_opp.verified_by,
                verification_notes=norm_opp.verification_notes,
                trust_level=norm_opp.trust_level or "UNVERIFIED_EXTERNAL",
                source_id=norm_opp.source_id,
                approval_status=norm_opp.approval_status or ("approved" if norm_opp.verification_status == "VERIFIED" else "pending"),
                confidence_score=norm_opp.confidence_score if norm_opp.confidence_score is not None else 1.0,
                company_confidence=norm_opp.company_confidence if norm_opp.company_confidence is not None else 1.0,
                company_evidence=norm_opp.company_evidence,
                normalized_company=norm_opp.normalized_company or norm_opp.company,
                duplicate_group=norm_opp.duplicate_group,
                rejection_reason=norm_opp.rejection_reason,
                source_name=norm_opp.source_name,
                source_message_id=norm_opp.source_message_id,
                company_url=norm_opp.company_url
            )
            session.add(db_row)
        else:
            existing.title = norm_opp.title
            existing.company = norm_opp.company
            existing.normalized_company = norm_opp.normalized_company or norm_opp.company
            existing.description = norm_opp.description
            existing.skills = json.dumps(norm_opp.skills)
            existing.status = norm_opp.status
            existing.remote = norm_opp.remote
            if norm_opp.approval_status:
                existing.approval_status = norm_opp.approval_status
            if norm_opp.company_confidence is not None:
                existing.company_confidence = norm_opp.company_confidence
            if norm_opp.company_evidence:
                existing.company_evidence = norm_opp.company_evidence
            if norm_opp.duplicate_group:
                existing.duplicate_group = norm_opp.duplicate_group
            if norm_opp.source_name:
                existing.source_name = norm_opp.source_name
            if norm_opp.source_message_id:
                existing.source_message_id = norm_opp.source_message_id
            if norm_opp.company_url:
                existing.company_url = norm_opp.company_url
            if norm_opp.verification_status and norm_opp.verification_status != "UNVERIFIED":
                existing.verification_status = norm_opp.verification_status
            if norm_opp.verification_method:
                existing.verification_method = norm_opp.verification_method
            if norm_opp.verified_at:
                existing.verified_at = norm_opp.verified_at
            if norm_opp.verified_by:
                existing.verified_by = norm_opp.verified_by
            if norm_opp.verification_notes:
                existing.verification_notes = norm_opp.verification_notes
            if norm_opp.trust_level:
                existing.trust_level = norm_opp.trust_level
            if norm_opp.source_id:
                existing.source_id = norm_opp.source_id
            if norm_opp.source_channel and not getattr(existing, "source_channel", None):
                existing.source_channel = norm_opp.source_channel
            if norm_opp.raw_text and not getattr(existing, "raw_text", None):
                existing.raw_text = norm_opp.raw_text
            if norm_opp.stipend:
                existing.stipend = norm_opp.stipend
            if norm_opp.deadline:
                existing.deadline = norm_opp.deadline
            if norm_opp.posted_date:
                if not existing.posted_date or norm_opp.posted_date > existing.posted_date:
                    existing.posted_date = norm_opp.posted_date
            if norm_opp.collected_date:
                existing.collected_date = norm_opp.collected_date
            if existing.verification_status in ("UNVERIFIED", None) and norm_opp.title and norm_opp.company and norm_opp.apply_url:
                existing.verification_status = "VERIFIED"
                if not existing.approval_status or existing.approval_status == "pending":
                    existing.approval_status = "approved"
                if existing.status not in ("active", "open"):
                    existing.status = "active"

        session.commit()
        return norm_opp
    finally:
        session.close()


def get_opportunity_by_id(opportunity_id: str) -> Optional[Opportunity]:
    """Retrieve a single opportunity by its ID."""
    session = SessionLocal()
    try:
        row = session.query(OpportunityDB).filter_by(id=opportunity_id).first()
        if not row:
            return None
        skills = []
        if row.skills:
            try:
                skills = json.loads(row.skills)
            except Exception:
                pass
        return Opportunity(
            id=row.id,
            title=row.title,
            company=row.company,
            description=row.description,
            opportunity_type=row.opportunity_type,
            skills=skills,
            location=row.location,
            remote=row.remote,
            stipend=row.stipend,
            salary=row.salary,
            experience=row.experience,
            eligibility=row.eligibility,
            deadline=row.deadline,
            source=row.source,
            source_channel=getattr(row, "source_channel", None),
            source_url=row.source_url,
            apply_url=row.apply_url,
            application_url=getattr(row, "application_url", None) or row.apply_url,
            normalized_url=getattr(row, "normalized_url", None) or row.apply_url,
            posted_date=row.posted_date,
            collected_date=row.collected_date,
            status=row.status,
            raw_text=getattr(row, "raw_text", None),
            verification_status=getattr(row, "verification_status", None) or "UNVERIFIED",
            verification_method=getattr(row, "verification_method", None),
            verified_at=getattr(row, "verified_at", None),
            verified_by=getattr(row, "verified_by", None),
            verification_notes=getattr(row, "verification_notes", None),
            trust_level=getattr(row, "trust_level", None) or "UNVERIFIED_EXTERNAL",
            source_id=getattr(row, "source_id", None),
            approval_status=getattr(row, "approval_status", None) or ("approved" if getattr(row, "verification_status", "") == "VERIFIED" else "pending"),
            confidence_score=getattr(row, "confidence_score", 1.0) if getattr(row, "confidence_score", None) is not None else 1.0,
            company_confidence=getattr(row, "company_confidence", 1.0) if getattr(row, "company_confidence", None) is not None else 1.0,
            company_evidence=getattr(row, "company_evidence", None),
            normalized_company=getattr(row, "normalized_company", None) or row.company,
            duplicate_group=getattr(row, "duplicate_group", None),
            rejection_reason=getattr(row, "rejection_reason", None),
            source_name=getattr(row, "source_name", None),
            source_message_id=getattr(row, "source_message_id", None),
            company_url=getattr(row, "company_url", None)
        )
    finally:
        session.close()


def collect_all_opportunities() -> List[Opportunity]:
    """Compatibility helper: triggers the unified ingestion pipeline."""
    from backend.services.ingestion_service import run_ingestion_pipeline
    report = run_ingestion_pipeline()
    return get_all_opportunities()

