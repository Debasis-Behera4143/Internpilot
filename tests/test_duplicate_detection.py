"""Test multi-signal deduplication and company variation handling (Step 5 Verification)."""

from backend.models.opportunity import Opportunity
from backend.services.deduplication_service import (
    is_duplicate,
    deduplicate_opportunities,
    merge_opportunity_records,
    has_conflicting_role_keywords
)
from backend.collectors.normalizer import normalize_company


def test_exact_apply_url_deduplication():
    """Identical apply URLs indicate the same opportunity regardless of minor title differences."""
    opp_a = Opportunity(
        title="Software Engineer Intern",
        company="TechCorp Inc",
        apply_url="https://techcorp.com/careers/swe-intern-2026",
        source="Telegram"
    )
    opp_b = Opportunity(
        title="SWE Intern - Summer 2026",
        company="TechCorp",
        apply_url="https://techcorp.com/careers/swe-intern-2026",
        source="College Submission"
    )
    is_dup, reason = is_duplicate(opp_a, opp_b)
    assert is_dup
    assert reason == "exact_apply_url"


def test_exact_source_url_deduplication():
    """Identical source URLs indicate the same posting across aggregators."""
    opp_a = Opportunity(
        title="Machine Learning Intern",
        company="AI Research Lab",
        apply_url="https://aggregator1.com/apply",
        source_url="https://original-portal.org/jobs/ml-intern-101"
    )
    opp_b = Opportunity(
        title="ML Intern",
        company="AI Research Lab",
        apply_url="https://aggregator2.com/apply",
        source_url="https://original-portal.org/jobs/ml-intern-101"
    )
    is_dup, reason = is_duplicate(opp_a, opp_b)
    assert is_dup
    assert reason == "exact_source_url"


def test_distinct_role_conflict_prevention():
    """Distinct specializations at the same company must NOT be merged."""
    opp_frontend = Opportunity(
        title="Frontend Developer Intern",
        company="CloudScale Solutions",
        apply_url="https://cloudscale.io/frontend-intern"
    )
    opp_backend = Opportunity(
        title="Backend Developer Intern",
        company="CloudScale Solutions",
        apply_url="https://cloudscale.io/backend-intern"
    )
    assert has_conflicting_role_keywords(opp_frontend.title, opp_backend.title)
    is_dup, _ = is_duplicate(opp_frontend, opp_backend)
    assert not is_dup, "Frontend and Backend roles at the same company should not be merged"


def test_distinct_specializations_mobile():
    """iOS and Android developer positions must remain separate."""
    opp_ios = Opportunity(
        title="iOS Mobile Developer Intern",
        company="AppCraft Inc",
        apply_url="https://appcraft.io/ios"
    )
    opp_android = Opportunity(
        title="Android Mobile Developer Intern",
        company="AppCraft Inc",
        apply_url="https://appcraft.io/android"
    )
    assert has_conflicting_role_keywords(opp_ios.title, opp_android.title)
    is_dup, _ = is_duplicate(opp_ios, opp_android)
    assert not is_dup


def test_company_name_variations_normalization():
    """Test normalization and deduplication behavior across company naming variants.
    Legal suffixes ('Pvt Ltd', 'Inc') should normalize to canonical company name.
    """
    comp1 = normalize_company("Google India Pvt Ltd")
    comp2 = normalize_company("Google India")
    comp3 = normalize_company("Google")

    # 'Google India Pvt Ltd' -> 'Google India'
    assert comp1 == comp2, "Legal suffix Pvt Ltd must be stripped to match Google India"

    # Opps with same normalized company and high title similarity should deduplicate
    opp_1 = Opportunity(
        title="Software Engineering Intern",
        company="Google India Pvt Ltd",
        apply_url="https://careers.google.com/jobs/results/1"
    )
    opp_2 = Opportunity(
        title="Software Engineering Intern",
        company="Google India",
        apply_url="https://careers.google.com/jobs/results/2"
    )
    is_dup, reason = is_duplicate(opp_1, opp_2)
    assert is_dup
    assert reason == "exact_title_and_company"


def test_unrelated_companies_never_merge():
    """Unrelated companies with identical titles must never be merged."""
    opp_a = Opportunity(
        title="Machine Learning Intern",
        company="Microsoft",
        apply_url="https://careers.microsoft.com/ml"
    )
    opp_b = Opportunity(
        title="Machine Learning Intern",
        company="Google",
        apply_url="https://careers.google.com/ml"
    )
    is_dup, _ = is_duplicate(opp_a, opp_b)
    assert not is_dup, "Different companies must never be considered duplicates"


def test_merge_preserves_enriched_metadata():
    """When merging duplicate records, metadata like skills, longer descriptions, and sources must combine."""
    primary = Opportunity(
        title="AI Engineer Intern",
        company="Nexus AI",
        skills=["Python", "PyTorch"],
        source="Telegram",
        description="Short description",
        apply_url="https://nexus.ai/jobs/1"
    )
    secondary = Opportunity(
        title="AI Engineer Intern",
        company="Nexus AI",
        skills=["PyTorch", "Transformers", "Docker"],
        source="College Submission",
        description="Detailed description with responsibilities and requirements",
        apply_url="https://nexus.ai/jobs/1"
    )
    merged = merge_opportunity_records(primary, secondary)
    assert "Python" in merged.skills
    assert "Transformers" in merged.skills
    assert "Docker" in merged.skills
    assert "Telegram" in merged.source and "College Submission" in merged.source
    assert len(merged.description) >= len(secondary.description)
