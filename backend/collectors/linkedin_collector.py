"""Compliant Authorized LinkedIn Opportunity Collector and Adapter.

Adheres strictly to ethical automation:
- Supports authorized API configurations when credentials/partner access exist
- Supports authorized user-exported CSV and JSON files
- Validates imported LinkedIn records for completeness and authenticity
- Preserves LinkedIn source and reference metadata
- Preserves original destination application URL when legitimately available
- Imported LinkedIn records do NOT automatically become verified (set to PENDING_REVIEW)
- Does NOT perform unauthorized web scraping, browser automation, fake accounts,
  login automation, or CAPTCHA bypass
- When API credentials are unavailable, explicitly states "Authorized import required"
"""

import os
import csv
import io
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional, Union
from datetime import date
import requests

from backend.collectors.base_collector import BaseCollector
from backend.collectors.normalizer import normalize_opportunity, clean_whitespace
from backend.models.opportunity import Opportunity
from backend.models.source import SourceTrustLevel
from backend.utils.url_validator import validate_application_url
from backend.utils.config import settings
from backend.utils.logger import get_logger

logger = get_logger("collector_linkedin")


class LinkedInCollector(BaseCollector):
    """Compliant adapter for authorized LinkedIn data feeds and user exports."""

    def __init__(self):
        super().__init__(name="linkedin")
        self.client_id = os.getenv("LINKEDIN_CLIENT_ID", "").strip()
        self.client_secret = os.getenv("LINKEDIN_CLIENT_SECRET", "").strip()
        self.access_token = os.getenv("LINKEDIN_ACCESS_TOKEN", "").strip()
        self.export_json_file = settings.DATA_DIR / "linkedin_export.json"
        self.export_csv_file = settings.DATA_DIR / "linkedin_export.csv"
        self.export_file = self.export_json_file
        self.last_run_stats: Dict[str, Any] = {
            "total_found": 0,
            "accepted": 0,
            "rejected": 0,
            "duplicates": 0,
            "reasons": []
        }

    def has_api_credentials(self) -> bool:
        """Check if authorized LinkedIn API credentials or partner tokens exist."""
        return bool(self.access_token or (self.client_id and self.client_secret))

    def is_configured(self) -> bool:
        """Check whether credentials or a user-provided export file are present."""
        has_file = (
            (self.export_file and self.export_file.exists())
            or (self.export_json_file and self.export_json_file.exists())
            or (self.export_csv_file and self.export_csv_file.exists())
        )
        return self.has_api_credentials() or bool(has_file)

    def get_connection_status(self) -> Dict[str, Any]:
        """Return truthful connection status without pretending to have live access."""
        api_ok = self.has_api_credentials()
        has_file = self.export_json_file.exists() or self.export_csv_file.exists()

        if api_ok:
            status = "CONNECTED"
            msg = "Authorized LinkedIn Partner API active"
        else:
            status = "NOT CONNECTED"
            msg = "Authorized API or CSV/JSON import required"

        return {
            "connection_status": status,
            "api_available": api_ok,
            "message": msg,
            "notice": "Authorized API or CSV/JSON import required",
            "export_file_present": has_file,
            "stats": self.last_run_stats
        }

    def get_status(self) -> str:
        """Return the exact status string required by specification."""
        return "LinkedIn authorization/import required"

    @staticmethod
    def _get_raw_val(raw: Dict[str, Any], *keys: str) -> str:
        for k in keys:
            if k in raw and raw[k] is not None:
                val = str(raw[k]).strip()
                if val:
                    return val
        # Case-insensitive fallback
        lower_map = {str(k).strip().lower(): v for k, v in raw.items()}
        for k in keys:
            lk = k.strip().lower()
            if lk in lower_map and lower_map[lk] is not None:
                val = str(lower_map[lk]).strip()
                if val:
                    return val
        return ""

    def validate_linkedin_record(self, raw: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate a single raw LinkedIn record before accepting it."""
        from backend.services.job_classifier import classify_opportunity_content, is_company_identifiable

        title = clean_whitespace(self._get_raw_val(raw, "title", "job title", "position", "role"))
        company = clean_whitespace(self._get_raw_val(raw, "company", "company name", "organization", "employer"))
        apply_url = clean_whitespace(self._get_raw_val(
            raw, "apply_url", "apply url", "application url", "job_url", "job url", "url", "link"
        ))
        desc = clean_whitespace(self._get_raw_val(raw, "description", "job description", "summary") or title)

        # Check company identity
        co_valid, co_msg = is_company_identifiable(company)
        if not co_valid:
            return False, co_msg

        # Check title
        if len(title) < 3 or title.lower() in ("untitled", "job", "intern", "hiring"):
            return False, "Job title is too short or generic"

        # Check URL
        if not apply_url or not apply_url.startswith(("http://", "https://")):
            return False, f"Invalid or missing apply URL: '{apply_url}'"

        is_valid_url, url_reason, _ = validate_application_url(apply_url)
        if not is_valid_url:
            return False, f"URL validation failed: {url_reason}"

        # Check genuine job classification
        is_genuine, reject_cat, reasons = classify_opportunity_content(title, company, desc, apply_url)
        if not is_genuine:
            return False, f"Classified as non-job ({reject_cat}): {'; '.join(reasons)}"

        return True, "Valid"

    def parse_linkedin_record(self, raw: Dict[str, Any], source_label: str = "LinkedIn Import") -> Optional[Opportunity]:
        """Parse and normalize a validated LinkedIn dictionary into an Opportunity.
        
        Imported records are NOT automatically verified (verification_status='PENDING_REVIEW').
        """
        title = clean_whitespace(self._get_raw_val(raw, "title", "job title", "position", "role"))
        company = clean_whitespace(self._get_raw_val(raw, "company", "company name", "organization", "employer"))
        
        # Preserve original apply URL when available; fall back to LinkedIn posting reference
        raw_apply = clean_whitespace(self._get_raw_val(raw, "apply_url", "apply url", "application url"))
        raw_posting = clean_whitespace(self._get_raw_val(raw, "job_url", "job url", "source_url", "url", "link"))

        # If only one is provided, use it for apply_url
        apply_url = raw_apply or raw_posting or "https://www.linkedin.com"
        source_url = raw_posting or raw_apply or "https://www.linkedin.com"

        job_id = clean_whitespace(self._get_raw_val(raw, "job_id", "job id", "id"))
        location = clean_whitespace(self._get_raw_val(raw, "location", "job location", "city") or "Remote")
        
        workplace_type = self._get_raw_val(raw, "workplace_types", "workplace types", "work_mode", "work mode").lower()
        remote_val = self._get_raw_val(raw, "remote").lower()
        remote = "remote" in location.lower() or "remote" in workplace_type or remote_val in ("true", "1", "yes")

        mode = "remote" if remote else ("hybrid" if "hybrid" in workplace_type or "hybrid" in location.lower() else "on-site")

        opp_type_raw = self._get_raw_val(raw, "opportunity_type", "employment type", "type") or "internship"
        opp_type = "internship" if "intern" in opp_type_raw.lower() else "full-time"

        desc = clean_whitespace(self._get_raw_val(raw, "description", "job description", "summary") or f"{title} at {company}")
        if len(desc) < 15:
            desc = f"{title} position at {company}. Location: {location}."

        raw_skills = raw.get("skills") or raw.get("Skills") or []
        if isinstance(raw_skills, str):
            skills = [s.strip() for s in raw_skills.split(",") if s.strip()]
        elif isinstance(raw_skills, list):
            skills = [str(s).strip() for s in raw_skills if str(s).strip()]
        else:
            skills = []

        ref_note = f"LinkedIn Reference ID: {job_id}" if job_id else "Authorized LinkedIn Record"

        opp = Opportunity(
            title=title,
            company=company,
            description=desc,
            opportunity_type=opp_type,
            skills=skills,
            location=location,
            remote=remote,
            work_mode=mode,
            stipend=self._get_raw_val(raw, "stipend") or None,
            salary=self._get_raw_val(raw, "salary") or None,
            experience=self._get_raw_val(raw, "experience") or ("Fresher / Student" if opp_type == "internship" else "Entry Level"),
            eligibility=self._get_raw_val(raw, "eligibility") or "All eligible students",
            deadline=self._get_raw_val(raw, "deadline") or None,
            source="LinkedIn",
            source_url=source_url,
            apply_url=apply_url,
            application_url=apply_url,
            posted_date=str(self._get_raw_val(raw, "posted_date", "posted date") or date.today().isoformat())[:10],
            status="active",
            raw_text=json.dumps({"linkedin_job_id": job_id, "source_label": source_label, "imported_at": date.today().isoformat()}),
            # Step 9: LinkedIn imports must NOT automatically become verified
            verification_status="PENDING_REVIEW",
            verification_method="LINKEDIN_AUTHORIZED_IMPORT",
            trust_level=SourceTrustLevel.IMPORTED_DATA.value,
            verification_notes=ref_note,
            source_id="src_linkedin_authorized_default"
        )
        return normalize_opportunity(opp)

    def parse_csv_content(self, csv_text: str, source_label: str = "LinkedIn CSV Import") -> Tuple[List[Opportunity], List[str]]:
        """Parse raw CSV text into Opportunity models with validation diagnostics."""
        opportunities: List[Opportunity] = []
        rejections: List[str] = []

        reader = csv.DictReader(io.StringIO(csv_text))
        for idx, row in enumerate(reader, start=1):
            is_valid, reason = self.validate_linkedin_record(row)
            if not is_valid:
                rejections.append(f"Row {idx} ({row.get('Job Title') or row.get('title') or 'Record'}): {reason}")
                continue
            opp = self.parse_linkedin_record(row, source_label=source_label)
            if opp:
                opportunities.append(opp)

        return opportunities, rejections

    def parse_json_content(self, json_data: Union[str, List[Dict[str, Any]], Dict[str, Any]], source_label: str = "LinkedIn JSON Import") -> Tuple[List[Opportunity], List[str]]:
        """Parse JSON text or data into Opportunity models with validation diagnostics."""
        opportunities: List[Opportunity] = []
        rejections: List[str] = []

        if isinstance(json_data, str):
            try:
                parsed = json.loads(json_data)
            except Exception as e:
                return [], [f"Malformed JSON: {e}"]
        else:
            parsed = json_data

        if isinstance(parsed, dict):
            items = parsed.get("jobs") or parsed.get("elements") or [parsed]
        elif isinstance(parsed, list):
            items = parsed
        else:
            return [], ["JSON root must be a list of records or dictionary"]

        for idx, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                rejections.append(f"Index {idx}: Record is not a valid JSON object")
                continue
            is_valid, reason = self.validate_linkedin_record(item)
            if not is_valid:
                rejections.append(f"Index {idx} ({item.get('title') or item.get('Job Title') or 'Record'}): {reason}")
                continue
            opp = self.parse_linkedin_record(item, source_label=source_label)
            if opp:
                opportunities.append(opp)

        return opportunities, rejections

    def collect(self) -> List[Opportunity]:
        """Collect opportunities from authorized LinkedIn feeds or user-provided files."""
        opportunities: List[Opportunity] = []
        rejections: List[str] = []

        # 1. Check for authorized user CSV export file
        if self.export_csv_file.exists():
            self.logger.info(f"Ingesting opportunities from LinkedIn CSV export: {self.export_csv_file.name}")
            try:
                with open(self.export_csv_file, "r", encoding="utf-8", errors="replace") as f:
                    csv_text = f.read()
                opps, rejs = self.parse_csv_content(csv_text, source_label=self.export_csv_file.name)
                opportunities.extend(opps)
                rejections.extend(rejs)
            except Exception as e:
                self.logger.warning(f"Error parsing {self.export_csv_file.name}: {e}")

        # 2. Check for authorized user JSON export file
        if self.export_json_file.exists():
            self.logger.info(f"Ingesting opportunities from LinkedIn JSON export: {self.export_json_file.name}")
            try:
                with open(self.export_json_file, "r", encoding="utf-8") as f:
                    json_data = json.load(f)
                opps, rejs = self.parse_json_content(json_data, source_label=self.export_json_file.name)
                opportunities.extend(opps)
                rejections.extend(rejs)
            except Exception as e:
                self.logger.warning(f"Error parsing {self.export_json_file.name}: {e}")

        # 3. Check for official LinkedIn API credentials
        if self.has_api_credentials():
            self.logger.info("Authorized LinkedIn Partner API active. Dispatching authorized queries...")
            api_opps = self._fetch_authorized_api()
            opportunities.extend(api_opps)

        if not self.is_configured():
            self.logger.info("LinkedIn adapter notice: No authorized API credentials or export file present. Authorized import required.")

        self.last_run_stats = {
            "total_found": len(opportunities) + len(rejections),
            "accepted": len(opportunities),
            "rejected": len(rejections),
            "duplicates": 0,
            "reasons": rejections[:20]
        }
        return opportunities

    def _fetch_authorized_api(self) -> List[Opportunity]:
        """Execute authorized query against official LinkedIn Jobs API when permitted token is present."""
        if not self.access_token:
            return []
        
        # Official endpoint requires verified partner program permissions
        url = "https://api.linkedin.com/v2/jobPostings"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-Restli-Protocol-Version": "2.0.0"
        }
        results = []
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("elements", [])
                opps, _ = self.parse_json_content(items, source_label="LinkedIn Partner API")
                results.extend(opps)
            else:
                self.logger.warning(f"LinkedIn Partner API returned HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            self.logger.warning(f"Error querying authorized LinkedIn API: {e}")
        return results
