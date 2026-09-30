"""Wellfound opportunity collector."""

from typing import List
from backend.collectors.base_collector import BaseCollector
from backend.models.opportunity import Opportunity
from backend.utils.config import settings


class WellfoundCollector(BaseCollector):
    """Scrapes internships and tech roles from Wellfound."""

    def __init__(self):
        super().__init__(name="wellfound")

    def collect(self) -> List[Opportunity]:
        opportunities: List[Opportunity] = []
        keywords = [
            "intern", "machine learning", "ai", "artificial intelligence",
            "data", "research", "fintech", "quant", "trading", "analytics", "python"
        ]

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.logger.warning("Playwright is not installed. Skipping live Wellfound scraping.")
            return opportunities

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=settings.PLAYWRIGHT_HEADLESS)
                page = browser.new_page()
                page.goto("https://wellfound.com/jobs", timeout=settings.SCRAPER_TIMEOUT_SECONDS * 1000)
                page.wait_for_timeout(4000)

                links = page.locator("a")
                count = links.count()
                self.logger.info(f"Wellfound links found: {count}")

                for i in range(count):
                    try:
                        text = links.nth(i).inner_text().strip()
                        href = links.nth(i).get_attribute("href")
                        if text and href and any(k in text.lower() for k in keywords):
                            full_link = href
                            if href.startswith("/"):
                                full_link = "https://wellfound.com" + href

                            lower = text.lower()
                            opp_type = "internship"
                            if any(w in lower for w in ["ai", "machine learning", "data", "research"]):
                                opp_type = "ai/ml"
                            elif any(w in lower for w in ["fintech", "quant", "trading", "analytics"]):
                                opp_type = "fintech"

                            legacy_dict = {
                                "title": text,
                                "link": full_link,
                                "type": opp_type,
                                "description": text,
                                "source": "wellfound"
                            }
                            opportunities.append(Opportunity.from_legacy_job(legacy_dict))
                    except Exception:
                        continue
                browser.close()
        except Exception as e:
            self.logger.warning(f"Live Wellfound scraping encountered an error: {e}")

        return opportunities
