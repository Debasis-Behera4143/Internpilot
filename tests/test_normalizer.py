"""Unit tests for opportunity normalization layer."""

from backend.collectors.normalizer import (
    clean_whitespace,
    normalize_company,
    normalize_location,
    normalize_skills,
    normalize_url,
    normalize_opportunity_type,
    normalize_stipend,
    normalize_opportunity
)
from backend.models.opportunity import Opportunity


def test_clean_whitespace():
    """Verify whitespace stripping and non-breaking space replacement."""
    raw = "  Software   Engineer\u00a0\u00a0Intern   \n  "
    assert clean_whitespace(raw) == "Software Engineer Intern"
    assert clean_whitespace(None) == ""


def test_normalize_company():
    """Verify company name cleaning and legal/batch tag removal."""
    assert normalize_company("Acme Corp.") == "Acme"
    assert normalize_company("DeepScale Inc.") == "DeepScale"
    assert normalize_company("HyperData Solutions LLC") == "HyperData"
    assert normalize_company("SnapMagic (S15) • AI tools") == "SnapMagic"
    assert normalize_company("Alpha Labs (W26)") == "Alpha Labs"
    assert normalize_company("NextGen Pvt. Ltd.") == "NextGen"
    assert normalize_company(None) == "Unknown"


def test_normalize_location_and_remote():
    """Verify location mapping and remote boolean inference."""
    loc, is_remote = normalize_location("Bangalore")
    assert loc == "Bengaluru, India"

    loc, is_remote = normalize_location("WFH")
    assert loc == "Remote"
    assert is_remote is True

    loc, is_remote = normalize_location("Work from home", remote_hint=False)
    assert loc == "Remote"
    assert is_remote is True

    loc, is_remote = normalize_location("Mumbai, India", remote_hint=False)
    assert loc == "Mumbai, India"
    assert is_remote is False


def test_normalize_skills():
    """Verify skill canonical mapping, deduplication, and case preservation."""
    raw_skills = ["ml", "Machine Learning", "tf", "py", "ReactJS", "k8s", "Docker"]
    normalized = normalize_skills(raw_skills)

    # ml and Machine Learning should collapse to a single 'Machine Learning'
    assert normalized.count("Machine Learning") == 1
    assert "TensorFlow" in normalized
    assert "Python" in normalized
    assert "React" in normalized
    assert "Kubernetes" in normalized
    assert "Docker" in normalized


def test_normalize_url():
    """Verify URL sanitization and marketing tracker stripping."""
    dirty_url = "https://careers.example.com/jobs/123/?utm_source=linkedin&utm_medium=feed&ref=banner"
    cleaned = normalize_url(dirty_url)
    assert "utm_source" not in cleaned
    assert "ref" not in cleaned
    assert cleaned == "https://careers.example.com/jobs/123"

    url_no_scheme = "jobs.startup.com/apply"
    assert normalize_url(url_no_scheme).startswith("https://jobs.startup.com/apply")


def test_normalize_opportunity_type():
    """Verify opportunity type categorization."""
    assert normalize_opportunity_type("Summer Intern 2026") == "internship"
    assert normalize_opportunity_type("AI Research Fellow") == "fellowship"
    assert normalize_opportunity_type("Research Associate") == "research"
    assert normalize_opportunity_type("FTE Software Engineer") == "full-time"
    assert normalize_opportunity_type("Global AI Hackathon") == "hackathon"


def test_normalize_stipend():
    """Verify stipend currency formatting."""
    assert normalize_stipend("INR 40000/mo") == "₹40000 / month"
    assert normalize_stipend("Rs. 35,000 / month") == "₹35,000 / month"
    assert normalize_stipend("Unpaid") == "Unpaid"


def test_normalize_opportunity_pipeline():
    """Verify end-to-end Opportunity model normalization."""
    opp = Opportunity(
        title="  Machine  Learning   Intern (Summer 2026)  ",
        company="Cognitive Systems Inc. (W26)",
        description="Build NLP models using Python and PyTorch.",
        opportunity_type="intern",
        skills=["ml", "py", "NLP", "PyTorch", "torch"],
        location="Bangalore",
        remote=False,
        stipend="INR 45000/mo",
        apply_url="https://cognitive.example/apply?utm_campaign=campus"
    )

    norm = normalize_opportunity(opp)
    assert norm.title == "Machine Learning Intern (Summer 2026)"
    assert norm.company == "Cognitive Systems"
    assert norm.location == "Bengaluru, India"
    assert norm.opportunity_type == "internship"
    assert "Machine Learning" in norm.skills
    assert "Python" in norm.skills
    assert norm.skills.count("PyTorch") == 1  # torch and PyTorch deduplicated
    assert "utm_campaign" not in norm.apply_url
    assert norm.stipend == "₹45000 / month"
