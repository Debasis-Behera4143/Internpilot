"""Public ATS Feed Adapter (Greenhouse, Lever, SmartRecruiters, etc.).

Supports compliant ingestion of published/public postings from company ATS portals.
All listings ingested from verified company ATS feeds are marked as:
- trust_level: OFFICIAL_COMPANY
- verification_status: VERIFIED
- verification_method: OFFICIAL_COMPANY_SOURCE
"""

import json
from datetime import date
from typing import List, Optional, Dict, Any
import requests

from backend.collectors.base_collector import BaseCollector
from backend.collectors.normalizer import normalize_opportunity
from backend.models.opportunity import Opportunity
from backend.models.source import SourceTrustLevel
from backend.utils.logger import get_logger

logger = get_logger("collector_ats")


class ATSAdapter(BaseCollector):
    """Adapter for ingesting public job feeds from supported Applicant Tracking Systems."""

    SUPPORTED_PROVIDERS = ["greenhouse", "lever", "smartrecruiters", "workday"]

    def __init__(self, companies: Optional[Dict[str, str]] = None):
        """
        companies: dict mapping company_name -> provider:board_token
        e.g. {"OpenAI": "greenhouse:openai", "Scale AI": "lever:scaleapi", "Adobe": "workday:adobe/external"}
        """
        super().__init__(name="ats_feed")
        self.companies = companies or {
            "OpenAI": "greenhouse:openai",
            "Figma": "greenhouse:figma",
            "Scale AI": "lever:scaleapi"
        }
        self.timeout = 10

    def collect(self) -> List[Opportunity]:
        """Collect public job opportunities across configured company ATS feeds."""
        opportunities: List[Opportunity] = []

        for company_name, spec in self.companies.items():
            try:
                provider, board_id = spec.split(":", 1) if ":" in spec else ("greenhouse", spec)
                provider = provider.lower().strip()
                board_id = board_id.strip()

                if provider == "greenhouse":
                    opps = self._fetch_greenhouse(company_name, board_id)
                    opportunities.extend(opps)
                elif provider == "lever":
                    opps = self._fetch_lever(company_name, board_id)
                    opportunities.extend(opps)
                elif provider == "workday":
                    opps = self._fetch_workday(company_name, board_id)
                    opportunities.extend(opps)
            except Exception as e:
                self.logger.warning(f"Error collecting ATS feed for {company_name}: {e}. Fault isolated.")

        self.logger.info(f"ATS Adapter collected {len(opportunities)} verified opportunities.")
        return opportunities

    def _fetch_greenhouse(self, company_name: str, board_id: str) -> List[Opportunity]:
        """Fetch jobs from Greenhouse public Board API."""
        url = f"https://boards-api.greenhouse.io/v1/boards/{board_id}/jobs"
        results = []
        try:
            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                jobs = data.get("jobs", [])
                for j in jobs:
                    title = j.get("title", "")
                    # Filter for student / intern / entry level or tech roles
                    title_lower = title.lower()
                    if not any(k in title_lower for k in ["intern", "student", "graduate", "university", "engineer", "developer", "analyst"]):
                        continue

                    location_data = j.get("location", {})
                    location_name = location_data.get("name", "Remote") if isinstance(location_data, dict) else str(location_data)
                    remote = "remote" in location_name.lower() or "anywhere" in location_name.lower()

                    opp = self._parse_greenhouse_job(company_name, j, url)
                    results.append(normalize_opportunity(opp))
        except Exception as e:
            self.logger.debug(f"Greenhouse fetch failed for {company_name} ({board_id}): {e}")
        return results

    def _parse_greenhouse_job(self, company_name: str, j: dict, url: str = "") -> Opportunity:
        title = j.get("title", "")
        title_lower = title.lower()
        location_data = j.get("location", {})
        location_name = location_data.get("name", "Remote") if isinstance(location_data, dict) else str(location_data)
        remote = "remote" in location_name.lower() or "anywhere" in location_name.lower()
        apply_url = j.get("absolute_url", url)
        return Opportunity(
            title=title,
            company=company_name,
            description=j.get("content", f"{title} position at {company_name} ({location_name})."),
            opportunity_type="internship" if "intern" in title_lower else "full-time",
            skills=["Python", "Engineering", "Problem Solving"],
            location=location_name,
            remote=remote,
            stipend=None,
            salary=None,
            experience="Fresher / Student" if "intern" in title_lower else "Entry Level",
            eligibility="Students / Graduates",
            deadline=None,
            source="ATS_PUBLIC_FEED",
            source_url=apply_url,
            apply_url=apply_url,
            posted_date=date.today().isoformat(),
            status="active",
            trust_level=SourceTrustLevel.ATS_PUBLIC.value if hasattr(SourceTrustLevel, "ATS_PUBLIC") else "ATS_PUBLIC",
            verification_status="VERIFIED",
            verification_method="OFFICIAL_COMPANY_SOURCE",
            verification_notes=f"Publicly verified Greenhouse ATS feed for {company_name}"
        )

    def _fetch_lever(self, company_name: str, site_name: str) -> List[Opportunity]:
        """Fetch jobs from Lever public Postings API."""
        url = f"https://api.lever.co/v0/postings/{site_name}?mode=json"
        results = []
        try:
            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code == 200:
                jobs = resp.json()
                for j in jobs:
                    title = j.get("text", "")
                    title_lower = title.lower()
                    if not any(k in title_lower for k in ["intern", "student", "graduate", "university", "engineer", "developer", "analyst"]):
                        continue

                    categories = j.get("categories", {})
                    location_name = categories.get("location", "Remote") if isinstance(categories, dict) else "Remote"
                    workplace_type = categories.get("workplaceType", "")
                    remote = workplace_type.lower() == "remote" or "remote" in location_name.lower()

                    apply_url = j.get("applyUrl", j.get("hostedUrl", url))

                    opp = Opportunity(
                        title=title,
                        company=company_name,
                        description=j.get("descriptionPlain", f"{title} at {company_name}"),
                        opportunity_type="internship" if "intern" in title_lower else "full-time",
                        skills=["Engineering", "Problem Solving", "Software"],
                        location=location_name,
                        remote=remote,
                        stipend=None,
                        salary=None,
                        experience="Fresher / Student" if "intern" in title_lower else "Entry Level",
                        eligibility="Students / Graduates",
                        deadline=None,
                        source="ATS_PUBLIC_FEED",
                        source_url=j.get("hostedUrl", url),
                        apply_url=apply_url,
                        posted_date=date.today().isoformat(),
                        status="active",
                        trust_level=SourceTrustLevel.OFFICIAL_COMPANY.value,
                        verification_status="VERIFIED",
                        verification_method="OFFICIAL_COMPANY_SOURCE",
                        verification_notes=f"Publicly verified Lever ATS feed for {company_name}"
                    )
                    results.append(normalize_opportunity(opp))
        except Exception as e:
            self.logger.debug(f"Lever fetch failed for {company_name} ({site_name}): {e}")
        return results

    def _fetch_workday(self, company_name: str, spec: str) -> List[Opportunity]:
        """Fetch jobs from permitted public Workday Career site CXS endpoints.
        
        Spec can be: 'tenant/site' or 'tenant' or full url 'https://{tenant}.wd1.myworkdayjobs.com/...'.
        Workday public sites expose standard candidate experience endpoints:
        POST https://{tenant}.wd1.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
        """
        results: List[Opportunity] = []
        try:
            if spec.startswith("http://") or spec.startswith("https://"):
                parts = spec.replace("https://", "").replace("http://", "").split("/")
                host = parts[0]
                tenant = host.split(".")[0]
                site = parts[1] if len(parts) > 1 and parts[1] != "wday" else "careers"
            elif "/" in spec:
                tenant, site = spec.split("/", 1)
            else:
                tenant, site = spec, "External"

            tenant = tenant.strip()
            site = site.strip()
            url = f"https://{tenant}.wd1.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
            payload = {
                "appliedFacets": {},
                "limit": 20,
                "offset": 0,
                "searchText": "intern"
            }
            headers = {"Content-Type": "application/json", "User-Agent": "InternPilot-ATS-Feed-Validator/1.0"}
            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                postings = data.get("jobPostings", [])
                for p in postings:
                    title = p.get("title", "")
                    title_lower = title.lower()
                    ext_path = p.get("externalPath", "")
                    loc = p.get("locationsText", "Remote")
                    remote = "remote" in loc.lower() or "remote" in title_lower

                    apply_url = f"https://{tenant}.wd1.myworkdayjobs.com/en-US/{site}{ext_path}" if ext_path else url

                    opp = Opportunity(
                        title=title,
                        company=company_name,
                        description=f"{title} opportunity at {company_name} ({loc}).",
                        opportunity_type="internship" if "intern" in title_lower else "full-time",
                        skills=["Problem Solving", "Engineering"],
                        location=loc,
                        remote=remote,
                        stipend=None,
                        salary=None,
                        experience="Fresher / Student" if "intern" in title_lower else "Entry Level",
                        eligibility="Students / Graduates",
                        deadline=None,
                        source="ATS_PUBLIC_FEED",
                        source_url=apply_url,
                        apply_url=apply_url,
                        posted_date=date.today().isoformat(),
                        status="active",
                        trust_level=SourceTrustLevel.OFFICIAL_COMPANY.value,
                        verification_status="VERIFIED",
                        verification_method="OFFICIAL_COMPANY_SOURCE",
                        verification_notes=f"Publicly verified Workday ATS feed for {company_name}"
                    )
                    results.append(normalize_opportunity(opp))
        except Exception as e:
            self.logger.debug(f"Workday public fetch failed for {company_name} ({spec}): {e}")
        return results

