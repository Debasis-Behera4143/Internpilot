"""Internshala opportunity collector."""

from typing import List
from backend.collectors.base_collector import BaseCollector
from backend.models.opportunity import Opportunity
from backend.utils.config import settings


class InternshalaCollector(BaseCollector):
    """Scrapes internship opportunities from Internshala."""

    def __init__(self):
        super().__init__(name="internshala")

    def collect(self) -> List[Opportunity]:
        opportunities: List[Opportunity] = []
        keywords = [
            "intern", "machine learning", "ai", "artificial intelligence",
            "data science", "analytics", "fintech", "python", "research"
        ]

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.logger.warning("Playwright is not installed. Skipping live Internshala scraping.")
            return opportunities

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=settings.PLAYWRIGHT_HEADLESS)
                page = browser.new_page()
                page.goto("https://internshala.com/internships/", timeout=settings.SCRAPER_TIMEOUT_SECONDS * 1000)
                page.wait_for_timeout(4000)

                links = page.locator("a")
                count = links.count()
                self.logger.info(f"Internshala links found: {count}")

                for i in range(count):
                    try:
                        text = links.nth(i).inner_text().strip()
                        href = links.nth(i).get_attribute("href")
                        if text and href and any(k in text.lower() for k in keywords):
                            full_link = href
                            if href.startswith("/"):
                                full_link = "https://internshala.com" + href

                            lower = text.lower()
                            opp_type = "internship"
                            if any(w in lower for w in ["ai", "machine learning", "data science", "research"]):
                                opp_type = "ai/ml"
                            elif any(w in lower for w in ["fintech", "analytics", "trading"]):
                                opp_type = "fintech"

                            legacy_dict = {
                                "title": text,
                                "link": full_link,
                                "type": opp_type,
                                "description": text,
                                "source": "internshala"
                            }
                            opportunities.append(Opportunity.from_legacy_job(legacy_dict))
                    except Exception:
                        continue
                browser.close()
        except Exception as e:
            self.logger.warning(f"Live Internshala scraping encountered an error: {e}")

        return opportunities
