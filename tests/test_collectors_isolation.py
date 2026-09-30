"""Unit tests for collector fault tolerance and credential-absence safety."""

from typing import List
from backend.collectors.base_collector import BaseCollector
from backend.collectors.telegram_collector import TelegramCollector
from backend.collectors.linkedin_collector import LinkedInCollector
from backend.models.opportunity import Opportunity
from backend.services.ingestion_service import run_ingestion_pipeline


class FaultyCrashingCollector(BaseCollector):
    """Mock collector designed to simulate an unhandled network or parsing exception."""

    def __init__(self):
        super().__init__(name="faulty_crasher")

    def collect(self) -> List[Opportunity]:
        raise ConnectionResetError("Simulated socket connection reset by peer during scraping")


class HealthyMockCollector(BaseCollector):
    """Mock collector that reliably returns valid opportunities."""

    def __init__(self):
        super().__init__(name="healthy_mock")

    def collect(self) -> List[Opportunity]:
        return [
            Opportunity(
                title="Mock Systems Intern",
                company="MockTech",
                apply_url="https://mocktech.example/jobs/1",
                source="mock"
            )
        ]


def test_telegram_collector_without_credentials():
    """Verify that Telegram collector runs safely without credentials."""
    col = TelegramCollector()
    # Force empty channels to simulate unconfigured state
    col.channels = []
    assert col.is_configured() is False
    res = col.collect()
    assert res == []


def test_linkedin_collector_without_credentials():
    """Verify that LinkedIn adapter runs safely without credentials or export file."""
    col = LinkedInCollector()
    col.client_id = ""
    col.client_secret = ""
    col.export_file = col.export_file.parent / "non_existent_file.json"
    assert col.is_configured() is False
    res = col.collect()
    assert res == []


def test_ingestion_pipeline_failure_isolation():
    """Verify that an exception in one collector does not stop other collectors."""
    crashing = FaultyCrashingCollector()
    healthy = HealthyMockCollector()

    report = run_ingestion_pipeline(collectors=[crashing, healthy], allow_sample_fallback=False)

    assert "faulty_crasher" in report["sources_attempted"]
    assert "faulty_crasher" in report["errors"]
    assert "healthy_mock" in report["sources_successful"]
    assert report["collected"] >= 1
