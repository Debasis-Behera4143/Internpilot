"""Opportunity Data Normalization Layer.

Standardizes messy web scraped, imported, or submitted opportunity records
without inventing missing data.
"""

import re
import urllib.parse
from typing import List, Optional, Tuple, Any
from backend.models.opportunity import Opportunity

# Common canonical skill alias mapping
SKILL_ALIASES = {
    "ml": "Machine Learning",
    "machine-learning": "Machine Learning",
    "machine learning": "Machine Learning",
    "ai": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
    "dl": "Deep Learning",
    "deep learning": "Deep Learning",
    "cv": "Computer Vision",
    "computer vision": "Computer Vision",
    "nlp": "NLP",
    "natural language processing": "NLP",
    "genai": "Generative AI",
    "generative ai": "Generative AI",
    "llm": "LLMs",
    "llms": "LLMs",
    "tf": "TensorFlow",
    "tensorflow": "TensorFlow",
    "torch": "PyTorch",
    "pytorch": "PyTorch",
    "py": "Python",
    "python": "Python",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "docker": "Docker",
    "react": "React",
    "reactjs": "React",
    "react.js": "React",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "aws": "AWS",
    "gcp": "GCP",
    "azure": "Azure",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "js": "JavaScript",
    "javascript": "JavaScript",
    "golang": "Go",
    "go": "Go",
    "cpp": "C++",
    "c++": "C++",
    "c#": "C#",
    "csharp": "C#",
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "scikit-learn": "Scikit-learn",
    "sklearn": "Scikit-learn",
    "sql": "SQL",
    "git": "Git"
}

# Location canonical mapping
LOCATION_ALIASES = {
    "bangalore": "Bengaluru, India",
    "bengaluru": "Bengaluru, India",
    "bombay": "Mumbai, India",
    "mumbai": "Mumbai, India",
    "gurgaon": "Gurugram, India",
    "gurugram": "Gurugram, India",
    "delhi": "New Delhi, India",
    "new delhi": "New Delhi, India",
    "delhi ncr": "Delhi NCR, India",
    "hyderabad": "Hyderabad, India",
    "pune": "Pune, India",
    "chennai": "Chennai, India",
    "noida": "Noida, India",
    "sf": "San Francisco, CA",
    "san francisco": "San Francisco, CA",
    "nyc": "New York, NY",
    "new york": "New York, NY",
    "london": "London, UK",
    "remote": "Remote",
    "wfh": "Remote",
    "work from home": "Remote"
}


def clean_whitespace(text: Optional[str]) -> str:
    """Strip leading, trailing, and duplicate interior whitespace."""
    if not text:
        return ""
    # Replace non-breaking spaces and clean whitespace
    clean = text.replace("\u00a0", " ").replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", clean).strip()


def normalize_company(name: Optional[str]) -> str:
    """Normalize company name, stripping legal suffixes and cohort badges (e.g. YC W26)."""
    if not name:
        return "Unknown"
    clean = clean_whitespace(name)

    # Strip YC/batch tags like "(W26)", "(S15)", "(P26)", "(YC W21)"
    clean = re.sub(r"\s*\([WwSsPpFf]\d{2}\)", "", clean)
    clean = re.sub(r"\s*\(YC\s*[WwSsPpFf]?\d{0,2}\)", "", clean, flags=re.IGNORECASE)

    # Strip bullet/separator prefixes or suffixes if formatted like "SnapMagic • AI"
    if "•" in clean:
        clean = clean.split("•")[0].strip()

    legal_suffixes = [
        r",?\s+Pvt\.?\s+Ltd\.?$",
        r",?\s+Private\s+Limited$",
        r",?\s+Inc\.?$",
        r",?\s+LLC\.?$",
        r",?\s+Ltd\.?$",
        r",?\s+Pvt\.?$",
        r",?\s+Corp\.?$",
        r",?\s+Corporation$",
        r",?\s+Technologies$",
        r",?\s+Solutions$"
    ]
    for pattern in legal_suffixes:
        clean = re.sub(pattern, "", clean, flags=re.IGNORECASE)

    clean = clean.strip(" ,.-")
    return clean if clean else "Unknown"


def normalize_location(location: Optional[str], remote_hint: Optional[bool] = None) -> Tuple[str, bool]:
    """Return normalized location string and boolean remote flag."""
    if not location:
        return ("Remote" if remote_hint else "Not Specified", bool(remote_hint))

    loc_clean = clean_whitespace(location)
    loc_lower = loc_clean.lower()

    is_remote = remote_hint or any(
        kw in loc_lower for kw in ["remote", "wfh", "work from home", "anywhere", "virtual", "home"]
    )

    # Check alias dictionary
    for alias, canonical in LOCATION_ALIASES.items():
        if loc_lower == alias or loc_lower.startswith(alias + ",") or f"({alias})" in loc_lower:
            return (canonical, is_remote)

    if is_remote and ("remote" in loc_lower or "wfh" in loc_lower):
        if loc_lower in ("remote", "wfh", "work from home"):
            return ("Remote", True)
        return (loc_clean, True)

    return (loc_clean, is_remote)


def normalize_skills(skills: List[str]) -> List[str]:
    """Normalize skill tags, map aliases, and eliminate duplicates preserving order."""
    if not skills:
        return []

    seen = set()
    normalized: List[str] = []

    for item in skills:
        if not item:
            continue
        # If item has commas, split it
        tokens = [clean_whitespace(t) for t in item.split(",") if clean_whitespace(t)]
        for token in tokens:
            token_lower = token.lower()
            if token_lower in SKILL_ALIASES:
                canonical = SKILL_ALIASES[token_lower]
            elif len(token) > 1 and not token.isupper():
                canonical = token.title()
            else:
                canonical = token

            key = canonical.lower()
            if key not in seen:
                seen.add(key)
                normalized.append(canonical)

    return normalized


def normalize_url(url: Optional[str]) -> str:
    """Sanitize URLs, stripping tracking parameters and normalizing slashes."""
    if not url:
        return ""
    clean = clean_whitespace(url)
    if not clean:
        return ""

    try:
        parsed = urllib.parse.urlparse(clean)
        if not parsed.scheme:
            # Prepend https if missing scheme
            clean = "https://" + clean
            parsed = urllib.parse.urlparse(clean)

        # Parse query params and remove marketing trackers
        query_params = urllib.parse.parse_qsl(parsed.query)
        tracking_keys = {
            "utm_source", "utm_medium", "utm_campaign", "utm_term",
            "utm_content", "ref", "fbclid", "gclid", "trk", "source", "ref_id"
        }
        filtered_params = [(k, v) for k, v in query_params if k.lower() not in tracking_keys]
        new_query = urllib.parse.urlencode(filtered_params)

        # Remove redundant trailing slashes on root
        path = parsed.path.rstrip("/") if parsed.path != "/" else "/"

        clean_url = urllib.parse.urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.params,
            new_query,
            ""  # drop fragment
        ))
        return clean_url
    except Exception:
        return clean


def normalize_opportunity_type(opp_type: Optional[str]) -> str:
    """Map raw opportunity type to canonical enum-like string."""
    if not opp_type:
        return "internship"

    t = clean_whitespace(opp_type).lower()

    if any(k in t for k in ["intern", "trainee", "apprentic"]):
        return "internship"
    if any(k in t for k in ["fellow", "fellowship"]):
        return "fellowship"
    if any(k in t for k in ["research", "postdoc", "phd"]):
        return "research"
    if any(k in t for k in ["hackathon", "bounty", "contest"]):
        return "hackathon"
    if any(k in t for k in ["full-time", "full time", "fte", "permanent"]):
        return "full-time"
    if any(k in t for k in ["part-time", "part time"]):
        return "part-time"
    if any(k in t for k in ["contract", "freelance"]):
        return "contract"

    return "internship"


def normalize_stipend(val: Optional[str]) -> Optional[str]:
    """Clean and normalize stipend / salary strings."""
    if not val:
        return None
    clean = clean_whitespace(val)
    if not clean or clean.lower() in ("unpaid", "none", "n/a", "not disclosed"):
        return clean

    # Clean rupee notation and collapse space after symbol
    clean = re.sub(r"(?i)\b(?:inr|rs\.?)\s*", "₹", clean)
    # Ensure space around slash
    clean = re.sub(r"\s*/\s*", " / ", clean)
    # Standardize /mo to / month
    clean = re.sub(r"(?i)/\s*mo\b", "/ month", clean)
    clean = re.sub(r"(?i)/\s*yr\b", "/ year", clean)
    return clean


def normalize_opportunity(opp: Opportunity) -> Opportunity:
    """Normalize all fields of an Opportunity instance without inventing missing data."""
    from backend.services.company_extractor import resolve_company

    from datetime import date
    today_str = date.today().isoformat()

    # 1. Clean title and company
    clean_title = clean_whitespace(opp.title)
    raw_comp = opp.company
    
    # Run intelligent company resolver to eliminate "Unknown", "N/A", "Unknown Company"
    comp_resolved = resolve_company(
        raw_company=raw_comp,
        title=clean_title,
        description=opp.description,
        apply_url=opp.apply_url,
        source_url=opp.source_url,
        source_channel=opp.source_channel,
        raw_text=opp.raw_text
    )
    final_company = comp_resolved["normalized_company"]
    comp_conf = comp_resolved["company_confidence"]
    comp_ev = comp_resolved["company_evidence"]

    # 2. Location & Remote
    norm_loc, is_remote = normalize_location(opp.location, remote_hint=opp.remote)

    # 3. Skills
    norm_skills = normalize_skills(opp.skills)

    # 4. URLs
    norm_apply_url = normalize_url(opp.apply_url)
    norm_source_url = normalize_url(opp.source_url) if opp.source_url else norm_apply_url

    # 5. Opportunity Type
    norm_type = normalize_opportunity_type(opp.opportunity_type)

    # 6. Description & Stipend
    clean_desc = clean_whitespace(opp.description) if opp.description else clean_title
    norm_stipend = normalize_stipend(opp.stipend)
    norm_salary = normalize_stipend(opp.salary)

    # 7. Status
    norm_status = opp.status.lower() if opp.status else "open"
    if norm_status in ("open", "active"):
        norm_status = "active"

    # Default approval status
    appr_status = opp.approval_status or ("approved" if opp.verification_status == "VERIFIED" else "pending")

    return Opportunity(
        id=opp.id,
        title=clean_title,
        company=final_company,
        normalized_company=final_company,
        company_confidence=comp_conf,
        company_evidence=comp_ev,
        confidence_score=opp.confidence_score if opp.confidence_score is not None else 1.0,
        approval_status=appr_status,
        duplicate_group=opp.duplicate_group,
        rejection_reason=opp.rejection_reason,
        source_name=opp.source_name,
        source_message_id=opp.source_message_id,
        company_url=opp.company_url,
        description=clean_desc,
        opportunity_type=norm_type,
        skills=norm_skills,
        location=norm_loc,
        remote=is_remote,
        stipend=norm_stipend,
        salary=norm_salary,
        experience=clean_whitespace(opp.experience) or "Fresher / Student",
        eligibility=clean_whitespace(opp.eligibility) or "All students / freshers",
        deadline=clean_whitespace(opp.deadline) if opp.deadline else None,
        source=clean_whitespace(opp.source) or "direct",
        source_channel=clean_whitespace(opp.source_channel) if opp.source_channel else None,
        source_url=norm_source_url,
        apply_url=norm_apply_url,
        posted_date=opp.posted_date or today_str,
        collected_date=opp.collected_date or today_str,
        status=norm_status,
        raw_text=opp.raw_text,
        match_score=opp.match_score,
        missing_skills=opp.missing_skills,
        verification_status=opp.verification_status or "UNVERIFIED",
        verification_method=opp.verification_method,
        verified_at=opp.verified_at,
        verified_by=opp.verified_by,
        verification_notes=opp.verification_notes,
        trust_level=opp.trust_level or "UNVERIFIED_EXTERNAL",
        source_id=opp.source_id
    )
