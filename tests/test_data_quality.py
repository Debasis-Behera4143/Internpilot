"""Test data quality indicators and statistical reporting endpoint (Step 5 Verification)."""

from fastapi.testclient import TestClient
from backend.api.app import app

client = TestClient(app)


def test_opportunity_stats_endpoint_structure():
    """Verify GET /api/opportunities/stats returns complete metrics."""
    res = client.get("/api/opportunities/stats")
    assert res.status_code == 200
    stats = res.json()

    # Core required counts
    assert "total" in stats
    assert "active" in stats
    assert "expired" in stats
    assert "closed" in stats
    assert "by_source" in stats
    assert "by_type" in stats
    assert "data_quality" in stats

    assert stats["total"] >= 75, f"Expected at least 75 total opportunities in repository, got {stats['total']}"
    assert stats["active"] > 0, "Expected active opportunities to be greater than 0"


def test_data_quality_completeness_metrics():
    """Verify internal data quality indicators compute valid percentage metrics."""
    res = client.get("/api/opportunities/stats")
    assert res.status_code == 200
    dq = res.json()["data_quality"]

    assert "title_present_pct" in dq
    assert "company_present_pct" in dq
    assert "apply_url_present_pct" in dq
    assert "source_present_pct" in dq
    assert "deadline_available_pct" in dq
    assert "skills_available_pct" in dq
    assert "location_available_pct" in dq
    assert "overall_quality_score" in dq

    # Quality metrics are valid percentages (between 0 and 100)
    assert 0.0 <= dq["title_present_pct"] <= 100.0
    assert 0.0 <= dq["company_present_pct"] <= 100.0
    assert 0.0 <= dq["apply_url_present_pct"] <= 100.0
    assert 0.0 <= dq["source_present_pct"] <= 100.0
    assert 0.0 <= dq["deadline_available_pct"] <= 100.0
    assert 0.0 <= dq["skills_available_pct"] <= 100.0
    assert 0.0 <= dq["location_available_pct"] <= 100.0

    # Essential fields have high presence across records
    assert dq["title_present_pct"] == 100.0
    assert dq["apply_url_present_pct"] >= 99.0
    assert dq["company_present_pct"] > 35.0

    # Overall dataset quality score is computed and valid
    assert 0.0 < dq["overall_quality_score"] <= 100.0


def test_sources_transparency_in_stats():
    """Verify multiple distinct sources are accounted for in repository statistics."""
    res = client.get("/api/opportunities/stats")
    assert res.status_code == 200
    by_source = res.json()["by_source"]

    # Must contain multi-source representations
    assert len(by_source) >= 3, "Expected at least 3 distinct source categories"
    source_names_lower = " ".join(by_source.keys()).lower()
    assert any(k in source_names_lower for k in ["telegram", "college", "employer", "csv", "public"])
