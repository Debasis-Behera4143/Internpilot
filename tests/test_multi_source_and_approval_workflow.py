"""
Test suite covering multi-source aggregation, company extraction heuristics,
deduplication with multi-source attribution, admin approval workflows,
bulk actions, and student fail-closed visibility.
"""

import pytest
from backend.models.opportunity import Opportunity
from backend.services.company_extractor import resolve_company, clean_legal_suffixes
from backend.collectors.normalizer import normalize_opportunity
from backend.services.deduplication_service import deduplicate_opportunities
from backend.services.opportunity_service import (
    save_opportunity,
    get_all_opportunities,
    get_opportunity_by_id,
)
from backend.services.verification_service import (
    bulk_approve_opportunities,
    bulk_verify_opportunities,
    bulk_reject_opportunities,
)
from backend.services.ingestion_service import get_default_collectors
from backend.database.db import SessionLocal


def test_company_extraction_heuristics():
    """Verify company extraction handles Unknown/N/A and extracts from domains, ATS urls, and titles."""
    # 1. ATS Greenhouse URL
    res1 = resolve_company("Unknown", title="Backend Intern", apply_url="https://boards.greenhouse.io/stripe/jobs/12345")
    assert res1["normalized_company"].lower() == "stripe"
    assert res1["company_confidence"] >= 0.85
    assert "Greenhouse" in res1["company_evidence"]

    # 2. Lever URL
    res2 = resolve_company("N/A", title="Frontend Intern", apply_url="https://jobs.lever.co/figma/abc-def-123")
    assert res2["normalized_company"].lower() == "figma"
    assert res2["company_confidence"] >= 0.85

    # 3. Workday URL
    res3 = resolve_company("", title="Software Engineer", apply_url="https://adobe.wd5.myworkdayjobs.com/en-US/careers/job/123")
    assert res3["normalized_company"].lower() == "adobe"

    # 4. Domain inference
    res4 = resolve_company("Unknown Company", title="Data Science Intern", apply_url="https://careers.databricks.com/jobs/999")
    assert res4["normalized_company"].lower() == "databricks"

    # 5. Title pattern: "Software Intern at Notion"
    res5 = resolve_company("Unknown", title="Software Engineering Intern at Notion", apply_url="https://example.com/listing/77")
    assert res5["normalized_company"].lower() == "notion"

    # 6. Suffix stripping (e.g. Inc, LLC)
    res6 = resolve_company("Palantir Technologies Inc.", title="Software Engineer", apply_url="https://palantir.com")
    assert res6["normalized_company"] == "Palantir Technologies"


def test_normalizer_company_resolution():
    """Verify normalizer integrates company resolution and populates pipeline fields."""
    raw_opp = Opportunity(
        title="Machine Learning Intern at Anthropic",
        company="Unknown",
        description="Work on LLM research and evaluations.",
        apply_url="https://anthropic.com/careers/eval-intern",
        source="RSS Feed: YCombinator"
    )
    norm = normalize_opportunity(raw_opp)
    assert norm.company.lower() == "anthropic"
    assert norm.normalized_company.lower() == "anthropic"
    assert norm.company_confidence > 0.5
    assert norm.approval_status == "pending"


def test_deduplication_retains_sources_and_urls():
    """Verify deduplication aggregates source names, preserves URLs, and groups duplicates."""
    opp1 = Opportunity(
        title="Backend Software Intern",
        company="Datadog",
        description="Build scalable distributed telemetry systems.",
        apply_url="https://datadog.com/careers/101",
        source="Career Page Crawler",
    )
    opp2 = Opportunity(
        title="Backend Software Intern",
        company="Datadog",
        description="Build scalable distributed telemetry systems.",
        apply_url="https://rss-feed.example.com/datadog-101",
        source="Tech Careers RSS",
    )
    
    unique_opps, dup_count = deduplicate_opportunities([opp1, opp2])
    assert len(unique_opps) == 1
    assert dup_count == 1
    m = unique_opps[0]
    assert "Career Page Crawler" in m.source
    assert "Tech Careers RSS" in m.source
    assert "https://datadog.com/careers/101" in m.apply_url or "https://rss-feed.example.com/datadog-101" in m.apply_url
    assert m.duplicate_group is not None


def test_bulk_approval_and_verification_pipeline():
    """Verify bulk approve, bulk verify, and bulk reject operations."""
    opp_a = Opportunity(
        id="opp_test_bulk_a",
        title="DevOps Intern A",
        company="CloudScale",
        description="Kubernetes automation and monitoring.",
        apply_url="https://cloudscale.io/jobs/1",
        source="JSON Feed",
        approval_status="pending",
        verification_status="PENDING_REVIEW",
    )
    opp_b = Opportunity(
        id="opp_test_bulk_b",
        title="DevOps Intern B",
        company="CloudScale",
        description="Terraform infrastructure.",
        apply_url="https://cloudscale.io/jobs/2",
        source="JSON Feed",
        approval_status="pending",
        verification_status="PENDING_REVIEW",
    )
    save_opportunity(opp_a)
    save_opportunity(opp_b)

    db = SessionLocal()
    try:
        # 1. Bulk Approve
        res_approve = bulk_approve_opportunities(db, [opp_a.id, opp_b.id])
        assert res_approve["approved_count"] == 2
        
        rec_a = get_opportunity_by_id(opp_a.id)
        assert rec_a.approval_status == "approved"

        # 2. Bulk Verify
        res_verify = bulk_verify_opportunities(db, [opp_a.id, opp_b.id])
        assert res_verify["verified_count"] == 2
        rec_a = get_opportunity_by_id(opp_a.id)
        assert rec_a.verification_status == "VERIFIED"
        assert rec_a.approval_status == "approved"

        # 3. Bulk Reject
        res_reject = bulk_reject_opportunities(db, [opp_a.id], reason="Duplicate listing")
        assert res_reject["rejected_count"] == 1
        rec_a = get_opportunity_by_id(opp_a.id)
        assert rec_a.approval_status == "rejected"
        assert rec_a.verification_status == "REJECTED"
        assert rec_a.rejection_reason == "Duplicate listing"
    finally:
        db.close()


def test_student_fail_closed_gate():
    """Verify normal student opportunity endpoints hide unapproved/unverified records."""
    unapproved = Opportunity(
        id="opp_test_unapproved_secret",
        title="Secret Unapproved Role",
        company="SecretCorp",
        description="Only admins should see this before approval.",
        apply_url="https://secretcorp.io/job/1",
        source="External Crawler",
        approval_status="pending",
        verification_status="PENDING_REVIEW",
    )
    approved_unverified = Opportunity(
        id="opp_test_approved_unverified",
        title="Approved But Unverified Role",
        company="PendingCorp",
        description="Approved by triage but unverified.",
        apply_url="https://pendingcorp.io/job/2",
        source="External Crawler",
        approval_status="approved",
        verification_status="PENDING_REVIEW",
    )
    fully_verified = Opportunity(
        id="opp_test_fully_verified_public",
        title="Fully Public Role",
        company="PublicCorp",
        description="Ready for students.",
        apply_url="https://publiccorp.io/job/3",
        source="Official Portal",
        approval_status="approved",
        verification_status="VERIFIED",
    )

    save_opportunity(unapproved)
    save_opportunity(approved_unverified)
    save_opportunity(fully_verified)

    # Student query: approval_status="approved", verified_only=True
    student_results = get_all_opportunities(approval_status="approved", verified_only=True)
    student_ids = [o.id for o in student_results]

    assert unapproved.id not in student_ids
    assert approved_unverified.id not in student_ids
    assert fully_verified.id in student_ids

    # Admin query: all records accessible without filter
    admin_results = get_all_opportunities()
    admin_ids = [o.id for o in admin_results]

    assert unapproved.id in admin_ids
    assert approved_unverified.id in admin_ids
    assert fully_verified.id in admin_ids


def test_multi_source_collectors_registered():
    """Verify all required ingestion collectors are configured in default collectors."""
    collectors = get_default_collectors()
    names = [c.name.lower() for c in collectors]
    
    assert any("career" in n for n in names)
    assert any("rss" in n or "feed" in n for n in names)
    assert any("json" in n for n in names)
    assert any("telegram" in n for n in names)
    assert any("whatsapp" in n for n in names)
    assert any("unstop" in n for n in names)
