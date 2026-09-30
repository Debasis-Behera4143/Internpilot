"""Multi-signal Opportunity Deduplication Service.

Identifies duplicate opportunities appearing across multiple sources using
hierarchical signals without accidentally merging distinct roles at the same company.
"""

import re
import difflib
from typing import List, Tuple, Set, Optional
from backend.models.opportunity import Opportunity
from backend.collectors.normalizer import normalize_url, normalize_company, clean_whitespace
from backend.utils.logger import get_logger

logger = get_logger("deduplication_service")

# Role distinguishing keywords that indicate DIFFERENT positions even at the same company
DISTINCT_ROLE_KEYWORDS = [
    {"frontend", "backend", "fullstack", "full-stack"},
    {"ios", "android"},
    {"mobile", "web"},
    {"devops", "sre", "cloud", "security"},
    {"ml", "machine learning", "data science", "data engineer", "data analyst", "business analyst"},
    {"hardware", "software", "firmware", "embedded"},
    {"product", "design", "ux", "ui", "marketing", "sales", "hr", "finance", "legal"}
]


def tokenize_title(title: str) -> Set[str]:
    """Tokenize and clean job title into canonical words."""
    clean = re.sub(r"[^a-zA-Z0-9\s]", " ", title.lower())
    stop_words = {"a", "an", "the", "and", "or", "in", "at", "for", "with", "to", "of", "level", "team"}
    tokens = {w for w in clean.split() if w and w not in stop_words and len(w) > 1}
    return tokens


def has_conflicting_role_keywords(title_a: str, title_b: str) -> bool:
    """Check if titles belong to fundamentally different specializations."""
    tokens_a = tokenize_title(title_a)
    tokens_b = tokenize_title(title_b)

    for keyword_cluster in DISTINCT_ROLE_KEYWORDS:
        a_matches = tokens_a & keyword_cluster
        b_matches = tokens_b & keyword_cluster
        # If both match the cluster but have no intersection, they are distinct roles!
        if a_matches and b_matches and not (a_matches & b_matches):
            return True
    return False


def is_duplicate(opp_a: Opportunity, opp_b: Opportunity) -> Tuple[bool, Optional[str]]:
    """Determine if two opportunities represent the exact same opening.
    Returns (is_dup, reason).
    """
    url_a = normalize_url(opp_a.apply_url)
    url_b = normalize_url(opp_b.apply_url)

    # Priority 1: Exact apply URL match (ignoring generic landing pages)
    if url_a and url_b and url_a == url_b:
        parsed_a = url_a.split("?")[0].rstrip("/")
        # Ensure it's not just a generic homepage like https://google.com
        if parsed_a.count("/") >= 3:
            return (True, "exact_apply_url")

    # Priority 2: Exact source URL match
    src_a = normalize_url(opp_a.source_url)
    src_b = normalize_url(opp_b.source_url)
    if src_a and src_b and src_a == src_b:
        parsed_src = src_a.split("?")[0].rstrip("/")
        if parsed_src.count("/") >= 3:
            return (True, "exact_source_url")

    # Priority 3: Same normalized company + title similarity
    comp_a = normalize_company(opp_a.company).lower()
    comp_b = normalize_company(opp_b.company).lower()

    # If companies differ, do NOT merge by title alone
    if comp_a != "unknown" and comp_b != "unknown" and comp_a == comp_b:
        title_a = clean_whitespace(opp_a.title)
        title_b = clean_whitespace(opp_b.title)

        # Exact title string match at the same company
        if title_a.lower() == title_b.lower():
            return (True, "exact_title_and_company")

        # Check for conflicting role keywords (e.g. Backend vs Frontend Engineer)
        if has_conflicting_role_keywords(title_a, title_b):
            return (False, None)

        tokens_a = tokenize_title(title_a)
        tokens_b = tokenize_title(title_b)

        if tokens_a and tokens_b:
            intersection = tokens_a & tokens_b
            union = tokens_a | tokens_b
            jaccard = len(intersection) / len(union)

            # High token overlap between titles at the same company (e.g., 'ML Intern' vs 'Machine Learning Intern')
            if jaccard >= 0.65:
                return (True, f"company_title_jaccard_{round(jaccard, 2)}")

        # String ratio similarity for slight spelling variations
        ratio = difflib.SequenceMatcher(None, title_a.lower(), title_b.lower()).ratio()
        if ratio >= 0.85:
            return (True, f"company_title_ratio_{round(ratio, 2)}")

    return (False, None)


def merge_opportunity_records(primary: Opportunity, secondary: Opportunity) -> Opportunity:
    """Merge duplicate records, enriching missing fields and combining unique metadata."""
    # Combine skills
    combined_skills = list(dict.fromkeys(primary.skills + secondary.skills))

    # Keep longer, more detailed description
    desc = primary.description if len(primary.description or "") >= len(secondary.description or "") else secondary.description

    # Merge sources if different
    sources = set()
    for s in (primary.source, secondary.source):
        if s:
            for part in s.split(","):
                clean = part.strip()
                if clean:
                    sources.add(clean)
    merged_source = ", ".join(sorted(sources)) if sources else primary.source

    # Prefer non-empty stipend
    stipend = primary.stipend or secondary.stipend
    salary = primary.salary or secondary.salary

    # Prefer explicit deadline
    deadline = primary.deadline or secondary.deadline

    # Prefer latest valid posted date so newly re-posted opportunities appear as fresh
    valid_dates = [d for d in (primary.posted_date, secondary.posted_date) if d]
    posted_date = max(valid_dates) if valid_dates else (primary.collected_date or secondary.collected_date)

    # Preserve and prioritize VERIFIED status
    ver_status = "UNVERIFIED"
    if (primary.verification_status or "").upper() == "VERIFIED" or (secondary.verification_status or "").upper() == "VERIFIED":
        ver_status = "VERIFIED"
    elif (primary.verification_status or "").upper() == "PENDING_REVIEW" or (secondary.verification_status or "").upper() == "PENDING_REVIEW":
        ver_status = "PENDING_REVIEW"
    elif primary.title and primary.company and primary.apply_url:
        ver_status = "VERIFIED"

    trust = primary.trust_level if (primary.trust_level and primary.trust_level != "UNVERIFIED_EXTERNAL") else (secondary.trust_level or "OFFICIAL_COMPANY")
    ver_method = primary.verification_method or secondary.verification_method or "AUTO_VERIFIED"
    source_chan = primary.source_channel or secondary.source_channel
    app_url = getattr(primary, "application_url", None) or getattr(secondary, "application_url", None) or primary.apply_url

    return Opportunity(
        id=primary.id or secondary.id,
        title=primary.title,
        company=primary.company if primary.company != "Unknown" else secondary.company,
        description=desc,
        opportunity_type=primary.opportunity_type or secondary.opportunity_type,
        skills=combined_skills,
        location=primary.location if primary.location != "Not Specified" else secondary.location,
        remote=primary.remote or secondary.remote,
        stipend=stipend,
        salary=salary,
        experience=primary.experience or secondary.experience,
        eligibility=primary.eligibility or secondary.eligibility,
        deadline=deadline,
        source=merged_source,
        source_channel=source_chan,
        source_url=primary.source_url or secondary.source_url,
        apply_url=primary.apply_url or secondary.apply_url,
        application_url=app_url,
        posted_date=posted_date,
        collected_date=max([d for d in (primary.collected_date, secondary.collected_date) if d] or [date.today().isoformat()]),
        status="active" if ("active" in (primary.status, secondary.status) or "open" in (primary.status, secondary.status)) else primary.status,
        match_score=primary.match_score or secondary.match_score,
        missing_skills=primary.missing_skills or secondary.missing_skills,
        verification_status=ver_status,
        verification_method=ver_method,
        trust_level=trust,
        source_id=primary.source_id or secondary.source_id
    )


def deduplicate_opportunities(opportunities: List[Opportunity]) -> Tuple[List[Opportunity], int]:
    """Deduplicate a list of Opportunity objects using multi-signal matching."""
    if not opportunities:
        return ([], 0)

    unique_list: List[Opportunity] = []
    duplicates_count = 0

    for candidate in opportunities:
        matched_idx = -1
        for idx, existing in enumerate(unique_list):
            is_dup, reason = is_duplicate(candidate, existing)
            if is_dup:
                matched_idx = idx
                logger.debug(f"Duplicate found ({reason}): '{candidate.title}' matched with '{existing.title}'")
                break

        if matched_idx >= 0:
            # Merge candidate into existing
            unique_list[matched_idx] = merge_opportunity_records(unique_list[matched_idx], candidate)
            duplicates_count += 1
        else:
            unique_list.append(candidate)

    return (unique_list, duplicates_count)
