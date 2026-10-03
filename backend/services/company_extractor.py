"""Intelligent Company Name Extraction and Entity Resolution Service.

Implements multi-signal evidence extraction to resolve "Unknown", "N/A", "Unknown Company"
without hallucinating or fabricating company entities:
1. Inspects raw opportunity text, title, and description.
2. Resolves ATS URL paths (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Workday).
3. Resolves direct application domain & email domain.
4. Performs canonical entity resolution (e.g. "Microsoft India" -> "Microsoft", "TCS iON" -> "TCS").
5. Produces normalized_company, company_confidence (0.0 to 1.0), and company_evidence.
"""

import re
import urllib.parse
from typing import Dict, Any, Optional, Tuple, List
from backend.utils.logger import get_logger

logger = get_logger("company_extractor")

UNINFORMATIVE_COMPANY_NAMES = {
    "", "unknown", "unknown company", "n/a", "na", "not specified",
    "not disclosed", "company", "none", "null", "undefined", "tbd",
    "employer", "verified employer", "enterprise partner", "hiring company",
    "various", "confidential", "top mnc", "stealth", "stealth startup"
}


# Canonical Company Normalization Mapping: Alias (lowercase) -> Canonical Name
CANONICAL_COMPANY_ALIASES: Dict[str, str] = {
    # Tech Giants & Top MNCs
    "microsoft": "Microsoft",
    "microsoft india": "Microsoft",
    "microsoft corporation": "Microsoft",
    "microsoft r&d": "Microsoft",
    "google": "Google",
    "google india": "Google",
    "google llc": "Google",
    "google careers": "Google",
    "alphabet": "Google",
    "amazon": "Amazon",
    "amazon india": "Amazon",
    "amazon web services": "Amazon",
    "aws": "Amazon",
    "amazon development centre": "Amazon",
    "apple": "Apple",
    "apple india": "Apple",
    "apple inc": "Apple",
    "meta": "Meta",
    "meta platforms": "Meta",
    "facebook": "Meta",
    "netflix": "Netflix",
    "tcs": "TCS",
    "tcs ion": "TCS",
    "tata consultancy services": "TCS",
    "infosys": "Infosys",
    "infosys limited": "Infosys",
    "wipro": "Wipro",
    "wipro limited": "Wipro",
    "accenture": "Accenture",
    "accenture india": "Accenture",
    "capgemini": "Capgemini",
    "capgemini india": "Capgemini",
    "cognizant": "Cognizant",
    "cognizant technology solutions": "Cognizant",
    "cts": "Cognizant",
    "ibm": "IBM",
    "ibm india": "IBM",
    "intel": "Intel",
    "intel corporation": "Intel",
    "nvidia": "NVIDIA",
    "nvidia graphics": "NVIDIA",
    "adobe": "Adobe",
    "adobe systems": "Adobe",
    "salesforce": "Salesforce",
    "oracle": "Oracle",
    "oracle india": "Oracle",
    "cisco": "Cisco",
    "cisco systems": "Cisco",
    "uber": "Uber",
    "uber technologies": "Uber",
    "swiggy": "Swiggy",
    "zomato": "Zomato",
    "flipkart": "Flipkart",
    "paytm": "Paytm",
    "cred": "CRED",
    "razorpay": "Razorpay",
    "zerodha": "Zerodha",
    "phonepe": "PhonePe",
    "goldman sachs": "Goldman Sachs",
    "jpmorgan chase": "JPMorgan Chase",
    "jp morgan": "JPMorgan Chase",
    "jpmorgan": "JPMorgan Chase",
    "morgan stanley": "Morgan Stanley"
}

# Domain to Canonical Company
DOMAIN_TO_COMPANY: Dict[str, str] = {
    "google.com": "Google",
    "careers.google.com": "Google",
    "microsoft.com": "Microsoft",
    "careers.microsoft.com": "Microsoft",
    "amazon.jobs": "Amazon",
    "amazon.com": "Amazon",
    "apple.com": "Apple",
    "jobs.apple.com": "Apple",
    "meta.com": "Meta",
    "metacareers.com": "Meta",
    "netflix.com": "Netflix",
    "netflix.jobs": "Netflix",
    "tcs.com": "TCS",
    "infosys.com": "Infosys",
    "wipro.com": "Wipro",
    "accenture.com": "Accenture",
    "capgemini.com": "Capgemini",
    "cognizant.com": "Cognizant",
    "ibm.com": "IBM",
    "intel.com": "Intel",
    "nvidia.com": "NVIDIA",
    "adobe.com": "Adobe",
    "salesforce.com": "Salesforce",
    "oracle.com": "Oracle",
    "cisco.com": "Cisco",
    "uber.com": "Uber",
    "swiggy.in": "Swiggy",
    "zomato.com": "Zomato",
    "flipkart.com": "Flipkart",
    "razorpay.com": "Razorpay",
    "zerodha.com": "Zerodha",
    "phonepe.com": "PhonePe",
    "goldmansachs.com": "Goldman Sachs",
    "jpmorganchase.com": "JPMorgan Chase",
    "morganstanley.com": "Morgan Stanley",
    "spotify.com": "Spotify",
    "stripe.com": "Stripe",
    "airbnb.com": "Airbnb"
}

# Common job aggregator / generic hosting domains that CANNOT be used as company identity
GENERIC_DOMAINS = {
    "t.me", "telegram.org", "telegram.me", "whatsapp.com", "chat.whatsapp.com",
    "wa.me", "forms.gle", "docs.google.com", "drive.google.com", "bit.ly",
    "tinyurl.com", "linktr.ee", "unstop.com", "internshala.com", "naukri.com",
    "linkedin.com", "wellfound.com", "angel.co", "instahyre.com", "indeed.com",
    "glassdoor.com", "foundit.in", "cuvette.tech", "cutshort.io", "github.com",
    "medium.com", "notion.site", "notion.so", "typeform.com", "airtable.com",
    "example.com", "example.org", "example.net"
}



def clean_legal_suffixes(name: str) -> str:
    """Strip standard corporate legal suffixes while preserving core company identity."""
    if not name:
        return ""
    clean = name.strip()
    
    # Strip cohort / batch tags e.g. (W26), (YC W21)
    clean = re.sub(r"\s*\([WwSsPpFf]\d{2}\)", "", clean)
    clean = re.sub(r"\s*\(YC\s*[WwSsPpFf]?\d{0,2}\)", "", clean, flags=re.IGNORECASE)
    
    suffixes = [
        r",?\s+Pvt\.?\s+Ltd\.?$",
        r",?\s+Private\s+Limited$",
        r",?\s+Inc\.?$",
        r",?\s+LLC\.?$",
        r",?\s+Ltd\.?$",
        r",?\s+Pvt\.?$",
        r",?\s+Corp\.?$",
        r",?\s+Corporation$"
    ]
    for pat in suffixes:
        sub = re.sub(pat, "", clean, flags=re.IGNORECASE).strip(" ,.-")
        if len(sub) >= 3:
            clean = sub
            
    return clean.strip(" ,.-")


def canonicalize_company_name(name: Optional[str]) -> Tuple[str, float, str]:
    """Map a raw company string to its canonical entity if recognized.
    
    Returns:
        (canonical_name, confidence, evidence)
    """
    if not name:
        return ("Unknown", 0.0, "Company name is missing")
    
    stripped = name.strip()
    if stripped.lower() in UNINFORMATIVE_COMPANY_NAMES:
        return ("Unknown", 0.0, f"Uninformative company placeholder: '{stripped}'")
    
    cleaned = clean_legal_suffixes(stripped)
    cleaned_lower = cleaned.lower()
    
    if cleaned_lower in CANONICAL_COMPANY_ALIASES:
        canonical = CANONICAL_COMPANY_ALIASES[cleaned_lower]
        return (canonical, 0.95, f"Resolved alias '{name}' to canonical '{canonical}'")
    
    raw_lower = stripped.lower()
    if raw_lower in CANONICAL_COMPANY_ALIASES:
        canonical = CANONICAL_COMPANY_ALIASES[raw_lower]
        return (canonical, 0.95, f"Resolved alias '{name}' to canonical '{canonical}'")
    
    if len(cleaned) >= 2 and not any(kw in cleaned_lower for kw in ["internship", "hiring", "fresher", "urgent", "job"]):
        return (cleaned, 0.85, f"Standardized company name '{cleaned}'")
    
    return ("Unknown", 0.0, f"Low quality company name candidate: '{name}'")


def extract_company_from_ats_url(url: str) -> Optional[Tuple[str, float, str]]:
    """Extract company from known ATS URL paths (Greenhouse, Lever, Ashby, Workable, SmartRecruiters)."""
    if not url:
        return None
    
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        path = parsed.path.strip("/")
        parts = [p for p in path.split("/") if p]
        
        # 1. Greenhouse
        if "greenhouse.io" in netloc:
            token = parts[0] if parts else ""
            if token and token.lower() not in ("embed", "api", "v1", "jobs"):
                cand = token.replace("-", " ").replace("_", " ").title()
                canon, conf, _ = canonicalize_company_name(cand)
                return (canon if canon != "Unknown" else cand, 0.92, f"Extracted from Greenhouse ATS token '{token}'")
        
        # 2. Lever
        if "lever.co" in netloc:
            token = parts[0] if parts else ""
            if token and token.lower() not in ("apply", "jobs", "v1"):
                cand = token.replace("-", " ").replace("_", " ").title()
                canon, conf, _ = canonicalize_company_name(cand)
                return (canon if canon != "Unknown" else cand, 0.92, f"Extracted from Lever ATS token '{token}'")
        
        # 3. Ashby
        if "ashbyhq.com" in netloc:
            token = parts[0] if parts else ""
            if token and token.lower() not in ("apply", "jobs"):
                cand = token.replace("-", " ").replace("_", " ").title()
                canon, conf, _ = canonicalize_company_name(cand)
                return (canon if canon != "Unknown" else cand, 0.92, f"Extracted from Ashby ATS token '{token}'")
                
        # 4. Workable
        if "workable.com" in netloc:
            token = parts[0] if parts else ""
            if token and token.lower() not in ("apply", "j", "jobs"):
                cand = token.replace("-", " ").replace("_", " ").title()
                canon, conf, _ = canonicalize_company_name(cand)
                return (canon if canon != "Unknown" else cand, 0.92, f"Extracted from Workable ATS token '{token}'")
        
        # 5. SmartRecruiters
        if "smartrecruiters.com" in netloc:
            token = parts[0] if parts else ""
            if token and token.lower() not in ("jobs", "apply"):
                cand = token.replace("-", " ").replace("_", " ").title()
                canon, conf, _ = canonicalize_company_name(cand)
                return (canon if canon != "Unknown" else cand, 0.92, f"Extracted from SmartRecruiters token '{token}'")
                
        # 6. Workday
        if "myworkdayjobs.com" in netloc:
            sub = netloc.split(".")[0]
            if sub and sub.lower() not in ("www", "myworkdayjobs"):
                cand = sub.replace("-", " ").replace("_", " ").title()
                canon, conf, _ = canonicalize_company_name(cand)
                return (canon if canon != "Unknown" else cand, 0.92, f"Extracted from Workday tenant '{sub}'")
                
    except Exception:
        pass
        
    return None


def extract_company_from_domain(url: str) -> Optional[Tuple[str, float, str]]:
    """Infer company identity from application or career URL domain when evidence is strong."""
    if not url:
        return None
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        if ":" in netloc:
            netloc = netloc.split(":")[0]
            
        if netloc.startswith("www."):
            netloc = netloc[4:]
            
        if netloc in GENERIC_DOMAINS:
            return None
            
        if netloc in DOMAIN_TO_COMPANY:
            canon = DOMAIN_TO_COMPANY[netloc]
            return (canon, 0.95, f"Application domain '{netloc}' directly maps to {canon}")
            
        parts = netloc.split(".")
        if len(parts) >= 2:
            root_domain = ".".join(parts[-2:])
            if root_domain in DOMAIN_TO_COMPANY:
                canon = DOMAIN_TO_COMPANY[root_domain]
                return (canon, 0.93, f"Root domain '{root_domain}' maps to {canon}")
                
            base_name = parts[-2]
            if len(base_name) >= 3 and base_name not in ("careers", "jobs", "apply", "talent", "portal", "hr", "work"):
                cand = base_name.replace("-", " ").title()
                canon, conf, _ = canonicalize_company_name(cand)
                if canon != "Unknown" and canon in CANONICAL_COMPANY_ALIASES.values():
                    return (canon, 0.91, f"Domain base '{base_name}' matches canonical company {canon}")
                elif canon != "Unknown" and len(cand) >= 3:
                    return (canon, 0.82, f"Inferred from application domain root '{base_name}'")
    except Exception:
        pass
        
    return None



def extract_company_from_text(text: str) -> Optional[Tuple[str, float, str]]:
    """Extract company from post text or job title using high-precision patterns."""
    if not text:
        return None
        
    patterns = [
        (r"(?i)(?:company(?:\s*name)?|organization|employer|startup)\s*[:\-–]\s*([A-Za-z0-9&.,' -]{2,40})", 0.90, "Explicit 'Company:' label in text"),
        (r"(?i)(?:^|\n)[^\w\n]*\b([A-Z][A-Za-z0-9&.,'-]{1,35}?)\s+(?:is\s+hiring|hiring\s+for|recruitment\s+drive|off-campus)\b", 0.88, "Text matches '{Company} is hiring' pattern"),
        (r"(?i)\b(?:hiring\s+at|internship\s+at|role\s+at|intern\s+at|engineer\s+at|developer\s+at|\bat)\s+([A-Z][A-Za-z0-9&.,'-]{1,35}?)(?:\s+(?:for|\-|\(|\||,|\n|$)|$)", 0.86, "Text matches 'at {Company}' pattern"),
        (r"^(?:\[([A-Za-z0-9&.,' -]{2,35})\]|([A-Za-z0-9&.,' -]{2,35})\s*[•|]\s*)", 0.85, "Title prefix separator pattern")
    ]

    
    for pat, weight, desc in patterns:
        m = re.search(pat, text)
        if m:
            cand = next((g for g in m.groups() if g), None)
            if cand:
                cand_clean = clean_legal_suffixes(cand.strip("*_#:- "))
                cand_lower = cand_clean.lower()
                invalid = {
                    "hiring", "fresher", "freshers", "internship", "job", "remote",
                    "immediate", "role", "position", "apply", "registration", "urgent",
                    "we", "our", "the", "top", "best", "new", "great", "team"
                }
                if cand_lower not in invalid and len(cand_clean) >= 2 and len(cand_clean) <= 45:
                    canon, _, _ = canonicalize_company_name(cand_clean)
                    resolved = canon if canon != "Unknown" else cand_clean
                    return (resolved, weight, f"{desc}: '{cand_clean}'")
                    
    return None


def resolve_company(
    raw_company: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    apply_url: Optional[str] = None,
    source_url: Optional[str] = None,
    source_channel: Optional[str] = None,
    raw_text: Optional[str] = None
) -> Dict[str, Any]:
    """Execute complete 6-step company resolution pipeline.
    
    Returns dict:
        normalized_company: str
        company_confidence: float (0.0 to 1.0)
        company_evidence: str
    """
    # 1. If existing company name is already specific and valid
    if raw_company and raw_company.strip().lower() not in UNINFORMATIVE_COMPANY_NAMES:
        canon, conf, ev = canonicalize_company_name(raw_company)
        if conf >= 0.70 and canon != "Unknown":
            return {
                "normalized_company": canon,
                "company_confidence": round(conf, 2),
                "company_evidence": ev
            }
            
    # 2. Inspect application URL for ATS tokens (Greenhouse, Lever, etc.)
    for url in [apply_url, source_url]:
        if url:
            ats_res = extract_company_from_ats_url(url)
            if ats_res:
                comp, conf, ev = ats_res
                return {
                    "normalized_company": comp,
                    "company_confidence": round(conf, 2),
                    "company_evidence": ev
                }
                
    # 3. Inspect title for explicit patterns e.g. "at Notion", "Company: Foo"
    if title:
        title_res = extract_company_from_text(title)
        if title_res:
            comp, conf, ev = title_res
            return {
                "normalized_company": comp,
                "company_confidence": round(conf, 2),
                "company_evidence": f"Title extraction: {ev}"
            }
            
    # 4. Inspect application URL for corporate domain resolution
    for url in [apply_url, source_url]:
        if url:
            dom_res = extract_company_from_domain(url)
            if dom_res:
                comp, conf, ev = dom_res
                return {
                    "normalized_company": comp,
                    "company_confidence": round(conf, 2),
                    "company_evidence": ev
                }

            
    # 5. Inspect description and raw post text
    combined_text = f"{raw_text or ''}\n{description or ''}"
    if combined_text.strip():
        text_res = extract_company_from_text(combined_text)
        if text_res:
            comp, conf, ev = text_res
            return {
                "normalized_company": comp,
                "company_confidence": round(conf, 2),
                "company_evidence": f"Body text extraction: {ev}"
            }
            
    # 6. Fallback: Keep Unknown rather than hallucinating
    return {
        "normalized_company": "Unknown",
        "company_confidence": 0.0,
        "company_evidence": "Insufficient evidence to identify company reliably"
    }
