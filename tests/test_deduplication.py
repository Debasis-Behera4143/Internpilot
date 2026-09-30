"""Unit tests for multi-signal opportunity deduplication."""

from backend.models.opportunity import Opportunity
from backend.services.deduplication_service import (
    is_duplicate,
    merge_opportunity_records,
    deduplicate_opportunities,
    has_conflicting_role_keywords
)


def test_exact_duplicate_by_apply_url():
    """Verify that identical apply URLs are flagged as exact duplicates."""
    opp1 = Opportunity(
        title="Software Engineer Intern",
        company="Tech Corp",
        apply_url="https://techcorp.example/jobs/swe-101",
        source="yc"
    )
    opp2 = Opportunity(
        title="SWE Intern - Summer",
        company="Tech Corp",
        apply_url="https://techcorp.example/jobs/swe-101",
        source="wellfound"
    )

    is_dup, reason = is_duplicate(opp1, opp2)
    assert is_dup is True
    assert reason == "exact_apply_url"


def test_same_job_from_two_sources():
    """Verify that same job listed on different portals with different URLs gets deduplicated by company + title."""
    opp_yc = Opportunity(
        title="Machine Learning Engineer Intern",
        company="Alpha AI Inc.",
        skills=["Python", "PyTorch"],
        apply_url="https://workatastartup.com/jobs/9901",
        source_url="https://workatastartup.com/jobs/9901",
        source="yc"
    )
    opp_internshala = Opportunity(
        title="Machine Learning Engineer Intern",
        company="Alpha AI",
        skills=["Python", "TensorFlow"],
        apply_url="https://internshala.com/internship/detail/ml-9901",
        source_url="https://internshala.com/internship/detail/ml-9901",
        source="internshala"
    )

    is_dup, reason = is_duplicate(opp_yc, opp_internshala)
    assert is_dup is True
    assert "company" in reason or "title" in reason

    # Test merging
    merged = merge_opportunity_records(opp_yc, opp_internshala)
    assert "Python" in merged.skills
    assert "PyTorch" in merged.skills
    assert "TensorFlow" in merged.skills
    assert "yc" in merged.source
    assert "internshala" in merged.source


def test_similar_but_different_jobs_not_merged():
    """Verify that distinct positions at the same company are NEVER merged."""
    opp_frontend = Opportunity(
        title="Frontend Engineering Intern",
        company="CloudScale Systems",
        skills=["React", "TypeScript"],
        apply_url="https://cloudscale.example/jobs/frontend-intern"
    )
    opp_backend = Opportunity(
        title="Backend Engineering Intern",
        company="CloudScale Systems",
        skills=["Python", "PostgreSQL"],
        apply_url="https://cloudscale.example/jobs/backend-intern"
    )

    # Must NOT be identified as duplicate
    is_dup, _ = is_duplicate(opp_frontend, opp_backend)
    assert is_dup is False
    assert has_conflicting_role_keywords(opp_frontend.title, opp_backend.title) is True


def test_same_company_different_disciplines():
    """Verify distinct disciplines (e.g. Data Scientist vs Product Designer) are not merged."""
    opp_ds = Opportunity(
        title="Data Science Intern",
        company="Fintech Labs",
        apply_url="https://fintech.example/jobs/ds"
    )
    opp_design = Opportunity(
        title="Product Design Intern",
        company="Fintech Labs",
        apply_url="https://fintech.example/jobs/design"
    )

    is_dup, _ = is_duplicate(opp_ds, opp_design)
    assert is_dup is False


def test_batch_deduplication():
    """Verify deduplication across a full list of mixed opportunities."""
    batch = [
        Opportunity(title="ML Intern", company="Acme", apply_url="https://acme.example/jobs/ml-1", source="yc"),
        Opportunity(title="ML Intern", company="Acme", apply_url="https://acme.example/jobs/ml-1", source="wellfound"),
        Opportunity(title="Backend Intern", company="Acme", apply_url="https://acme.example/jobs/backend-2", source="yc"),
        Opportunity(title="ML Intern", company="Beta Corp", apply_url="https://beta.example/jobs/ml-3", source="internshala")
    ]

    unique_list, dup_count = deduplicate_opportunities(batch)
    assert dup_count == 1
    assert len(unique_list) == 3
