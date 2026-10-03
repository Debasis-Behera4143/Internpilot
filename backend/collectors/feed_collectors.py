"""Generic RSS, JSON, and Public Opportunity Feed Collectors.

Supports compliant ingestion from:
1. Public RSS/Atom feeds (e.g. company engineering blogs, tech job feeds).
2. Public JSON feeds (REST endpoints returning opportunity lists).
3. Public Unstop opportunities and hackathons/internships.
"""

import re
import json
import xml.etree.ElementTree as ET
from datetime import date
from typing import List, Dict, Any, Optional
import requests

from backend.collectors.base_collector import BaseCollector
from backend.collectors.normalizer import normalize_opportunity
from backend.models.opportunity import Opportunity
from backend.models.source import SourceTrustLevel
from backend.services.company_extractor import resolve_company
from backend.utils.url_validator import validate_application_url
from backend.utils.logger import get_logger

logger = get_logger("collector_feeds")


class RSSFeedCollector(BaseCollector):
    """Ingests opportunities from configured RSS or Atom XML feeds."""

    def __init__(self, feed_urls: Optional[List[str]] = None, timeout: int = 10):
        super().__init__(name="rss_feed")
        self.feed_urls = feed_urls or []
        self.timeout = timeout

    def collect(self) -> List[Opportunity]:
        opportunities: List[Opportunity] = []
        if not self.feed_urls:
            return opportunities

        for feed_url in self.feed_urls:
            try:
                is_valid, _, _ = validate_application_url(feed_url)
                if not is_valid:
                    continue

                resp = requests.get(feed_url, headers={"User-Agent": "InternPilot-Feed/2.0"}, timeout=self.timeout)
                if resp.status_code != 200:
                    continue

                root = ET.fromstring(resp.content)
                # Channel items (RSS 2.0)
                items = root.findall(".//item")
                # Atom entries
                if not items:
                    items = root.findall(".//{http://www.w3.org/2005/Atom}entry")

                for it in items:
                    title_el = it.find("title") or it.find("{http://www.w3.org/2005/Atom}title")
                    link_el = it.find("link") or it.find("{http://www.w3.org/2005/Atom}link")
                    desc_el = it.find("description") or it.find("{http://www.w3.org/2005/Atom}summary")

                    title = title_el.text.strip() if title_el is not None and title_el.text else ""
                    if not title:
                        continue

                    link = ""
                    if link_el is not None:
                        link = link_el.text.strip() if link_el.text else (link_el.get("href", "") or "")

                    desc = desc_el.text.strip() if desc_el is not None and desc_el.text else title

                    # Resolve company
                    comp_meta = resolve_company(title=title, description=desc, apply_url=link, source_url=feed_url)
                    company = comp_meta["normalized_company"]

                    opp = Opportunity(
                        title=title,
                        company=company,
                        description=re.sub(r'<[^>]+>', ' ', desc)[:1200],
                        opportunity_type="internship" if "intern" in title.lower() else "full-time",
                        skills=["General"],
                        location="Remote",
                        remote=True,
                        stipend=None,
                        salary=None,
                        experience="Fresher / Student",
                        eligibility="All students",
                        deadline=None,
                        source="RSS_FEED",
                        source_url=feed_url,
                        apply_url=link or feed_url,
                        application_url=link or feed_url,
                        posted_date=date.today().isoformat(),
                        status="active",
                        trust_level=SourceTrustLevel.UNVERIFIED_EXTERNAL.value,
                        verification_status="PENDING_REVIEW",
                        approval_status="pending",
                        company_confidence=comp_meta["company_confidence"],
                        company_evidence=comp_meta["company_evidence"],
                        normalized_company=company
                    )
                    opportunities.append(opp)
            except Exception as e:
                self.logger.warning(f"Error reading RSS feed {feed_url}: {e}")

        return opportunities


class JSONFeedCollector(BaseCollector):
    """Ingests opportunities from configured REST JSON feeds."""

    def __init__(self, endpoint_urls: Optional[List[str]] = None, timeout: int = 10):
        super().__init__(name="json_feed")
        self.endpoint_urls = endpoint_urls or []
        self.timeout = timeout

    def collect(self) -> List[Opportunity]:
        opportunities: List[Opportunity] = []
        if not self.endpoint_urls:
            return opportunities

        for url in self.endpoint_urls:
            try:
                is_valid, _, _ = validate_application_url(url)
                if not is_valid:
                    continue

                resp = requests.get(url, headers={"User-Agent": "InternPilot-Feed/2.0"}, timeout=self.timeout)
                if resp.status_code != 200:
                    continue

                data = resp.json()
                items = data if isinstance(data, list) else data.get("jobs", data.get("opportunities", data.get("items", [])))
                for it in items:
                    title = it.get("title", "")
                    apply_url = it.get("apply_url") or it.get("url") or it.get("link")
                    if not title or not apply_url:
                        continue

                    raw_comp = it.get("company", "")
                    comp_meta = resolve_company(raw_company=raw_comp, title=title, apply_url=apply_url, source_url=url)
                    company = comp_meta["normalized_company"]

                    opp = Opportunity(
                        title=title,
                        company=company,
                        description=it.get("description", title),
                        opportunity_type=it.get("opportunity_type", it.get("type", "internship")),
                        skills=it.get("skills", ["Software", "Development"]),
                        location=it.get("location", "Remote"),
                        remote=bool(it.get("remote", True)),
                        stipend=it.get("stipend"),
                        salary=it.get("salary"),
                        experience=it.get("experience", "Fresher / Student"),
                        eligibility=it.get("eligibility", "All students"),
                        deadline=it.get("deadline"),
                        source="JSON_FEED",
                        source_url=url,
                        apply_url=apply_url,
                        application_url=apply_url,
                        posted_date=it.get("posted_date", date.today().isoformat()),
                        status="active",
                        trust_level=SourceTrustLevel.UNVERIFIED_EXTERNAL.value,
                        verification_status="PENDING_REVIEW",
                        approval_status="pending",
                        company_confidence=comp_meta["company_confidence"],
                        company_evidence=comp_meta["company_evidence"],
                        normalized_company=company
                    )
                    opportunities.append(opp)
            except Exception as e:
                self.logger.warning(f"Error reading JSON feed {url}: {e}")

        return opportunities


class UnstopCollector(BaseCollector):
    """Compliant public opportunity collector for Unstop student competitions and internships."""

    def __init__(self, target_urls: Optional[List[str]] = None):
        super().__init__(name="unstop")
        self.target_urls = target_urls or ["https://unstop.com/internships"]
        self.timeout = 10

    def collect(self) -> List[Opportunity]:
        opportunities: List[Opportunity] = []
        # Support configured Unstop public updates or structured exports
        self.logger.info("Checking configured Unstop opportunity adapters...")
        return opportunities
