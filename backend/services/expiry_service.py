"""Opportunity Expiry and Lifecycle Management Service.

Evaluates deadlines and staleness to transition opportunities between
'active', 'expired', and 'closed' statuses while preserving historical records.
"""

from datetime import date, datetime, timedelta
from typing import Tuple, Optional, Dict, Any, List
from backend.models.opportunity import Opportunity
from backend.database.db import SessionLocal, OpportunityDB
from backend.database.sync import sync_db_to_json
from backend.utils.logger import get_logger

logger = get_logger("expiry_service")

# Default max age before an opportunity without an explicit deadline is marked stale
DEFAULT_MAX_OPPORTUNITY_AGE_DAYS = 60


def parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse date string into a date object."""
    if not date_str:
        return None
    clean = date_str.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y", "%b %d, %Y"):
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            continue
    return None


DEAD_OR_CLOSED_INDICATORS = [
    "applications closed",
    "position filled",
    "job expired",
    "deadline passed",
    "no longer accepting applications",
    "page not found",
    "404",
    "position unavailable",
    "job posting has expired",
    "this job is no longer available",
    "this position has been closed",
    "the role has been filled"
]


def check_content_for_closed_indicators(text: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Check text (title, description, or scraped page content) for dead/closed job indicators."""
    if not text:
        return (False, None)
    clean = text.lower()
    for phrase in DEAD_OR_CLOSED_INDICATORS:
        if phrase in clean:
            return (True, phrase)
    return (False, None)


def is_opportunity_expired(
    opp: Opportunity,
    reference_date: Optional[date] = None,
    max_age_days: int = DEFAULT_MAX_OPPORTUNITY_AGE_DAYS
) -> Tuple[bool, str]:
    """Evaluate whether an opportunity should be marked expired or closed.
    Returns (is_expired, reason).
    """
    today = reference_date or date.today()

    # 1. Source already indicated closed / expired
    current_status = (opp.status or "").strip().lower()
    if current_status in ("closed", "filled", "inactive"):
        return (True, "source_closed")
    if current_status in ("expired", "unavailable"):
        return (True, "already_expired")

    # 2. Check explicit deadline
    if opp.deadline:
        deadline_dt = parse_date(opp.deadline)
        if deadline_dt:
            if deadline_dt < today:
                return (True, f"deadline_passed ({opp.deadline})")
            else:
                return (False, "deadline_active")

    # 3. Check for obvious closed indicators in title or description
    is_closed, phrase = check_content_for_closed_indicators(opp.title)
    if is_closed:
        return (True, f"closed_indicator_in_title ({phrase})")

    is_closed_desc, phrase_desc = check_content_for_closed_indicators(opp.description)
    if is_closed_desc:
        return (True, f"closed_indicator_in_description ({phrase_desc})")

    # 4. Check staleness based on posted_date or collected_date
    ref_date_str = opp.posted_date or opp.collected_date
    if ref_date_str:
        base_dt = parse_date(ref_date_str)
        if base_dt:
            age_days = (today - base_dt).days
            if age_days > max_age_days:
                return (True, f"stale_inactivity ({age_days} days > {max_age_days} limit)")

    return (False, "active")


def evaluate_opportunity_status(
    opp: Opportunity,
    reference_date: Optional[date] = None,
    max_age_days: int = DEFAULT_MAX_OPPORTUNITY_AGE_DAYS
) -> str:
    """Return 'active', 'expired', or 'closed' for an opportunity."""
    current_status = (opp.status or "").strip().lower()
    if current_status in ("closed", "filled"):
        return "closed"

    expired, reason = is_opportunity_expired(opp, reference_date=reference_date, max_age_days=max_age_days)
    return "expired" if expired else "active"


def evaluate_and_update_expiry_in_db(max_age_days: int = DEFAULT_MAX_OPPORTUNITY_AGE_DAYS) -> Dict[str, Any]:
    """Inspect all database opportunities, mark expired records, and persist updates."""
    session = SessionLocal()
    today = date.today()
    updated_count = 0
    total_checked = 0
    active_count = 0
    expired_count = 0

    try:
        records: List[OpportunityDB] = session.query(OpportunityDB).all()
        total_checked = len(records)

        for rec in records:
            # Reconstruct minimal Opportunity to evaluate
            opp = Opportunity(
                title=rec.title,
                company=rec.company,
                apply_url=rec.apply_url,
                deadline=rec.deadline,
                posted_date=rec.posted_date,
                collected_date=rec.collected_date,
                status=rec.status
            )
            expired, reason = is_opportunity_expired(opp, reference_date=today, max_age_days=max_age_days)

            if expired and rec.status != "expired" and rec.status != "closed":
                rec.status = "expired"
                updated_count += 1
                logger.info(f"Marked opportunity '{rec.title}' as expired: {reason}")
            elif not expired and rec.status == "open":
                rec.status = "active"

            if rec.status in ("active", "open"):
                active_count += 1
            elif rec.status == "expired":
                expired_count += 1

        session.commit()
        if updated_count > 0:
            sync_db_to_json()
    finally:
        session.close()

    return {
        "total_checked": total_checked,
        "newly_expired": updated_count,
        "active_count": active_count,
        "expired_count": expired_count
    }


def revalidate_opportunity_url(apply_url: str, timeout: int = 5) -> Tuple[bool, Optional[str]]:
    """Probe opportunity application URL to detect 404, dead links, or domain errors with retry tolerance.
    Returns (is_available, error_detail).
    """
    import requests
    if not apply_url or not apply_url.startswith(("http://", "https://")):
        return (False, "Invalid URL schema")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        # Try HEAD request first for efficiency
        resp = requests.head(apply_url, headers=headers, timeout=timeout, allow_redirects=True)
        if resp.status_code in (404, 410):
            return (False, f"HTTP {resp.status_code} Not Found")
        if resp.status_code < 400:
            return (True, None)
    except Exception:
        pass

    try:
        # Fallback to GET with small byte stream if HEAD blocked/failed
        resp = requests.get(apply_url, headers=headers, timeout=timeout, stream=True, allow_redirects=True)
        if resp.status_code in (404, 410):
            return (False, f"HTTP {resp.status_code} Not Found")
        if resp.status_code == 403 or resp.status_code < 500:
            # 403/401 may just be bot protection on career portal; do NOT mark dead
            return (True, None)
    except Exception as e:
        logger.debug(f"Network check failed for {apply_url}: {e}")
        # One network error should not immediately delete/mark dead
        return (True, "Temporary network timeout")

    return (True, None)

