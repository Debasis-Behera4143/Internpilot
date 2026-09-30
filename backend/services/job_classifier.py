"""Genuine Job & Internship Classification Engine.

Enforces strict content quality rules to filter out non-job content, scams,
and promotional material before opportunities reach the verification pipeline:
- Promotional posts & courses
- Paid training & placement fee scams
- Advertisements & affiliate marketing
- Referral-only requests
- Vague hiring posts with unrealistic claims
- "DM to apply" & WhatsApp-only leads
- Posts without identifiable company information
- Suspicious links or unauthorized redirectors
- Unrelated Telegram broadcasts (crypto, trading, news, memes)
"""

import re
from typing import Tuple, List, Optional
from backend.utils.logger import get_logger

logger = get_logger("job_classifier")

# 1. Promotional and course selling patterns
PROMOTIONAL_PATTERNS = [
    r"buy\s+course",
    r"course\s+fee",
    r"certification\s+program\s+fee",
    r"certification\s+course",
    r"enroll\s+now",
    r"enroll\s+in\s+our",
    r"discount\s+code",
    r"use\s+coupon",
    r"\d+%\s+discount",
    r"paid\s+webinar",
    r"paid\s+masterclass",
    r"\bbootcamp\b",
    r"bootcamp\s+fee",
    r"join\s+our\s+bootcamp",
    r"limited\s+seats\s+at\s+just\s+rs",
    r"registration\s+charges?\s+apply",
    r"training\s+cum\s+placement\s+fee",
    r"pay\s+after\s+placement\s+fees?",
    r"course\s+with\s+\d+%\s+discount",
]

# 2. Paid training and placement fee scam patterns
PAID_TRAINING_SCAM_PATTERNS = [
    r"paid\s+training",
    r"training\s+fee",
    r"registration\s+fee",
    r"refundable\s+security\s+deposit",
    r"security\s+deposit\s+required",
    r"pay\s+for\s+training",
    r"pay\s+to\s+learn",
    r"stipend\s+after\s+paying\s+fee",
    r"charge\s+for\s+interview",
    r"processing\s+fee\s+for\s+job",
    r"hiring\s+fee",
]

# 3. Commercial advertisements and spam
ADVERTISEMENT_PATTERNS = [
    r"sponsored\s+post",
    r"\bairdrop\b",
    r"crypto\s+bounty",
    r"free\s+gift",
    r"giveaway",
    r"100%\s+money\s+back",
    r"subscribe\s+to\s+(?:our\s+)?channel",
    r"paid\s+promotion",
    r"free\s+bitcoin",
    r"trading\s+signals?",
    r"forex\s+trading",
    r"earn\s+daily\s+profit",
]

# 4. Referral-only posts (not direct applications)
REFERRAL_ONLY_PATTERNS = [
    r"dm\s+for\s+referral",
    r"referral\s+only",
    r"contact\s+me\s+for\s+referral",
    r"ping\s+for\s+referral",
    r"ask\s+for\s+referral",
    r"referral\s+link\s+only",
    r"i\s+will\s+refer\s+you",
    r"giving\s+referrals?",
    r"referral\s+available",
    r"referrals?\s+for\s+[a-z0-9]+",
]

# 5. Vague hiring posts without genuine job context
VAGUE_HIRING_PATTERNS = [
    r"immediate\s+hiring\s+without\s+interview",
    r"no\s+interview\s+required",
    r"earn\s+50k\s+daily",
    r"earn\s+from\s+home\s+fast",
    r"simple\s+typing\s+work",
    r"data\s+entry\s+earn\s+daily",
    r"work\s+1\s+hour\s+daily\s+earn",
    r"no\s+resume\s+required",
    r"guaranteed\s+selection",
    r"daily\s+payout\s+guaranteed",
]

# 6. "DM to apply" / "WhatsApp to apply" without official careers link
DM_TO_APPLY_PATTERNS = [
    r"dm\s+to\s+apply",
    r"dm\s+me\s+your\s+resume",
    r"message\s+on\s+whatsapp",
    r"send\s+(?:your\s+)?cv\s+on\s+whatsapp",
    r"send\s+resume\s+to\s+whatsapp",
    r"whatsapp\s+your\s+cv",
    r"whatsapp\s+\+?\d+",
    r"contact\s+on\s+telegram\s+to\s+apply",
    r"inbox\s+me\s+to\s+apply",
    r"ping\s+on\s+whatsapp",
    r"comment\s+interested",
    r"drop\s+your\s+number\s+in\s+comments",
    r"no\s+website\s+application",
]

# 7. Unidentifiable or generic company names
UNIDENTIFIED_COMPANIES = {
    "unknown", "n/a", "none", "company", "placeholder", "test company",
    "stealth", "confidential", "confidential client", "top mnc", "leading startup",
    "hiring company", "client", "tbd", "anonymous", "reputed company",
    "private limited", "various companies", "multiple companies", "urgent hiring"
}

# 8. Unrelated Telegram broadcast content
UNRELATED_CONTENT_PATTERNS = [
    r"crypto\s+alert",
    r"buy\s+bitcoin",
    r"cricket\s+score",
    r"match\s+prediction",
    r"betting\s+tip",
    r"breaking\s+news\s+today",
    r"pump\s+and\s+dump",
    r"vip\s+signal",
    r"binance",
    r"\bbtc\b",
    r"crypto\s+signals?",
    r"movie\s+download\s+link",
    r"web\s+series\s+free\s+download",
    r"apk\s+mod\s+download",
]


def is_company_identifiable(company: Optional[str]) -> Tuple[bool, str]:
    """Validate that the opportunity specifies an identifiable, legitimate hiring company."""
    if not company:
        return False, "Missing company name"

    clean_co = company.strip().lower()
    if len(clean_co) < 2:
        return False, "Company name is too short (< 2 characters)"

    if clean_co in UNIDENTIFIED_COMPANIES:
        return False, f"Generic placeholder company: '{company}'"

    # Reject names that look like generic placeholders or stealth entities
    SUSPICIOUS_COMPANY_PATTERNS = [
        "confidential", "unknown", "top mnc", "leading mnc", "stealth", "secret",
        "undisclosed", "anonymous", "reputed company", "leading startup", "top startup"
    ]
    if any(p in clean_co for p in SUSPICIOUS_COMPANY_PATTERNS):
        return False, f"Unidentified or stealth company name: '{company}'"

    return True, "Valid company"


def classify_opportunity_content(
    title: str,
    company: str,
    description: str,
    apply_url: str = ""
) -> Tuple[bool, Optional[str], List[str]]:
    """Evaluate opportunity text and metadata against genuine-job quality rules.
    
    Returns:
        (is_genuine: bool, rejection_category: Optional[str], failure_reasons: List[str])
    """
    reasons: List[str] = []
    combined = f"{title or ''} {company or ''} {description or ''}".lower()

    # 1. Identifiable Company Check
    co_valid, co_msg = is_company_identifiable(company)
    if not co_valid:
        reasons.append(co_msg)
        return False, "UNIDENTIFIED_COMPANY", reasons

    # 2. Minimum Title Check
    clean_title = (title or "").strip()
    if len(clean_title) < 3 or clean_title.lower() in ("untitled", "job", "intern", "hiring"):
        reasons.append("Job title is too short or generic placeholder")
        return False, "GENERIC_TITLE", reasons

    # 3. Minimum Description Sanity
    clean_desc = (description or "").strip()
    if len(clean_desc) < 15:
        reasons.append("Opportunity description is insufficient (< 15 characters)")
        return False, "INSUFFICIENT_DESCRIPTION", reasons

    # 4. Paid Training & Placement Fee Scams
    for pattern in PAID_TRAINING_SCAM_PATTERNS:
        if re.search(pattern, combined):
            reasons.append(f"Matched paid training/placement fee scam pattern: '{pattern}'")
            return False, "PAID_TRAINING_SCAM", reasons

    # 5. Promotional & Course Selling
    for pattern in PROMOTIONAL_PATTERNS:
        if re.search(pattern, combined):
            reasons.append(f"Matched promotional course selling pattern: '{pattern}'")
            return False, "PROMOTIONAL_CONTENT", reasons

    # 6. Commercial Advertisements & Spam
    for pattern in ADVERTISEMENT_PATTERNS:
        if re.search(pattern, combined):
            reasons.append(f"Matched commercial advertisement/spam pattern: '{pattern}'")
            return False, "ADVERTISEMENT", reasons

    # 7. Unrelated Telegram Content
    for pattern in UNRELATED_CONTENT_PATTERNS:
        if re.search(pattern, combined):
            reasons.append(f"Matched non-job unrelated broadcast pattern: '{pattern}'")
            return False, "UNRELATED_BROADCAST", reasons

    # 8. Referral-Only Posts
    for pattern in REFERRAL_ONLY_PATTERNS:
        if re.search(pattern, combined):
            reasons.append(f"Matched referral-only request pattern: '{pattern}'")
            return False, "REFERRAL_ONLY", reasons

    # 9. Vague Hiring Posts
    for pattern in VAGUE_HIRING_PATTERNS:
        if re.search(pattern, combined):
            reasons.append(f"Matched vague hiring/get-rich-quick pattern: '{pattern}'")
            return False, "VAGUE_HIRING", reasons

    # 10. "DM to apply" / WhatsApp Leads
    # Only reject if there is no official career apply URL
    has_official_portal = any(
        portal in (apply_url or "").lower()
        for portal in [
            "greenhouse.io", "lever.co", "myworkdayjobs.com", "smartrecruiters.com",
            "careers.google.com", "amazon.jobs", "microsoft.com", "apple.com"
        ]
    )
    if not has_official_portal:
        for pattern in DM_TO_APPLY_PATTERNS:
            if re.search(pattern, combined):
                reasons.append(f"Matched 'DM to apply' / informal lead pattern: '{pattern}'")
                return False, "DM_TO_APPLY", reasons

    return True, None, []
