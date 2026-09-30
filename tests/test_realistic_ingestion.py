"""Test realistic demonstration data ingestion pipeline (Step 5 Verification)."""

from pathlib import Path
from backend.utils.config import settings
from backend.collectors.import_collector import ImportCollector
from backend.collectors.normalizer import normalize_opportunity
from backend.models.opportunity import Opportunity
from backend.services.opportunity_service import save_opportunity, get_all_opportunities


def test_realistic_csv_file_exists():
    """Verify data/demo_opportunities_realistic.csv exists and has records."""
    csv_path = settings.DATA_DIR / "demo_opportunities_realistic.csv"
    assert csv_path.exists(), "Realistic demo CSV file must exist"
    assert csv_path.stat().st_size > 5000, "CSV file should contain substantial data"


def test_realistic_csv_parsing():
    """Verify parsing realistic CSV yields 75+ valid normalized Opportunity objects."""
    csv_path = settings.DATA_DIR / "demo_opportunities_realistic.csv"
    collector = ImportCollector()
    opportunities = collector.parse_csv(csv_path)

    assert len(opportunities) >= 75, f"Expected at least 75 demo opportunities, got {len(opportunities)}"

    # Check distribution of opportunity types
    types = {o.opportunity_type for o in opportunities}
    assert "internship" in types
    assert "research" in types or "fellowship" in types

    # Check variety of technical skills
    all_skills = {s.lower() for o in opportunities for s in o.skills}
    for expected_skill in ["python", "machine learning", "pytorch", "react", "sql", "docker"]:
        assert any(expected_skill in s for s in all_skills), f"Expected skill '{expected_skill}' not found in dataset"


def test_realistic_opportunity_fields_completeness():
    """Verify key fields are populated without placeholder errors."""
    csv_path = settings.DATA_DIR / "demo_opportunities_realistic.csv"
    collector = ImportCollector()
    opportunities = collector.parse_csv(csv_path)

    for opp in opportunities[:30]:
        assert opp.title, "Opportunity must have a title"
        assert opp.company and opp.company != "Unknown", "Opportunity must have a recognized company"
        assert opp.apply_url.startswith(("http://", "https://")), f"Invalid apply_url: {opp.apply_url}"
        assert opp.source, "Opportunity must have source attribution"
        assert isinstance(opp.skills, list), "Skills must be a list"
        assert isinstance(opp.remote, bool), "Remote flag must be boolean"
