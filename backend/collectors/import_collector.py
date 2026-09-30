"""Generic CSV and JSON Opportunity Importer.

Allows bulk ingestion from local files (CSV, JSON) for testing, offline operation,
and administrator uploads without external network reliance.
"""

import csv
import json
from pathlib import Path
from typing import List, Union, Dict, Any, Tuple
from datetime import date
from backend.collectors.base_collector import BaseCollector
from backend.collectors.normalizer import normalize_opportunity, clean_whitespace
from backend.models.opportunity import Opportunity
from backend.utils.config import settings
from backend.utils.logger import get_logger

logger = get_logger("collector_import")


class ImportCollector(BaseCollector):
    """Imports opportunities from local CSV and JSON files."""

    def __init__(self, imports_dir: Union[str, Path] = None):
        super().__init__(name="import_file")
        self.imports_dir = Path(imports_dir) if imports_dir else (settings.DATA_DIR / "imports")
        self.imports_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def validate_raw_record(row: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate that minimum required fields exist in a record."""
        title = clean_whitespace(str(row.get("title", "")))
        company = clean_whitespace(str(row.get("company", "")))
        apply_url = clean_whitespace(str(row.get("apply_url", row.get("link", ""))))

        if not title:
            return (False, "Missing title")
        if not company:
            return (False, "Missing company")
        if not apply_url or not apply_url.startswith(("http://", "https://")):
            return (False, f"Invalid or missing apply_url: '{apply_url}'")

        return (True, "valid")

    def parse_csv(self, file_path: Path) -> List[Opportunity]:
        """Parse opportunities from a CSV file."""
        opportunities: List[Opportunity] = []
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.DictReader(f)
            for line_no, row in enumerate(reader, start=2):
                is_valid, reason = self.validate_raw_record(row)
                if not is_valid:
                    self.logger.warning(f"Skipping CSV row {line_no} in {file_path.name}: {reason}")
                    continue

                # Parse skills string into list
                raw_skills = row.get("skills", "")
                if isinstance(raw_skills, str):
                    skills_list = [s.strip() for s in re_split_skills(raw_skills) if s.strip()]
                else:
                    skills_list = list(raw_skills)

                # Parse remote boolean
                raw_remote = str(row.get("remote", "")).strip().lower()
                remote_bool = raw_remote in ("true", "1", "yes", "wfh", "remote")

                opp = Opportunity(
                    title=clean_whitespace(row.get("title")),
                    company=clean_whitespace(row.get("company")),
                    description=clean_whitespace(row.get("description", row.get("title"))),
                    opportunity_type=clean_whitespace(row.get("opportunity_type", row.get("type", "internship"))),
                    skills=skills_list,
                    location=clean_whitespace(row.get("location", "Remote")),
                    remote=remote_bool,
                    stipend=row.get("stipend") or None,
                    salary=row.get("salary") or None,
                    experience=row.get("experience", "Fresher / Student"),
                    eligibility=row.get("eligibility", "All students"),
                    deadline=row.get("deadline") or None,
                    source=row.get("source", f"CSV Import ({file_path.name})"),
                    source_url=row.get("source_url", row.get("apply_url", "")),
                    apply_url=row.get("apply_url", row.get("link", "")),
                    posted_date=row.get("posted_date", date.today().isoformat()),
                    status="active"
                )
                opportunities.append(normalize_opportunity(opp))
        return opportunities

    def parse_json(self, file_path: Path) -> List[Opportunity]:
        """Parse opportunities from a JSON file."""
        opportunities: List[Opportunity] = []
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            data = [data]

        for idx, item in enumerate(data):
            is_valid, reason = self.validate_raw_record(item)
            if not is_valid:
                self.logger.warning(f"Skipping JSON index {idx} in {file_path.name}: {reason}")
                continue

            raw_skills = item.get("skills", [])
            if isinstance(raw_skills, str):
                skills_list = [s.strip() for s in re_split_skills(raw_skills) if s.strip()]
            else:
                skills_list = list(raw_skills)

            opp = Opportunity(
                title=clean_whitespace(item.get("title")),
                company=clean_whitespace(item.get("company")),
                description=clean_whitespace(item.get("description", item.get("title"))),
                opportunity_type=item.get("opportunity_type", item.get("type", "internship")),
                skills=skills_list,
                location=item.get("location", "Remote"),
                remote=bool(item.get("remote", True)),
                stipend=item.get("stipend"),
                salary=item.get("salary"),
                experience=item.get("experience", "Fresher / Student"),
                eligibility=item.get("eligibility", "All students"),
                deadline=item.get("deadline"),
                source=item.get("source", f"JSON Import ({file_path.name})"),
                source_url=item.get("source_url", item.get("apply_url", "")),
                apply_url=item.get("apply_url", item.get("link", "")),
                posted_date=item.get("posted_date", date.today().isoformat()),
                status="active"
            )
            opportunities.append(normalize_opportunity(opp))
        return opportunities

    def import_from_file(self, file_path: Union[str, Path]) -> List[Opportunity]:
        """Import from an explicit file path (CSV or JSON)."""
        p = Path(file_path)
        if not p.exists():
            self.logger.warning(f"File not found: {p}")
            return []

        if p.suffix.lower() == ".csv":
            return self.parse_csv(p)
        elif p.suffix.lower() == ".json":
            return self.parse_json(p)
        else:
            self.logger.warning(f"Unsupported file extension: {p.suffix}")
            return []

    def collect(self) -> List[Opportunity]:
        """Scan the data/imports/ directory for any CSV and JSON files to ingest."""
        opportunities: List[Opportunity] = []
        if not self.imports_dir.exists():
            return opportunities

        for f in self.imports_dir.iterdir():
            if f.is_file() and f.suffix.lower() in (".csv", ".json"):
                self.logger.info(f"Ingesting opportunities from file: {f.name}")
                try:
                    opps = self.import_from_file(f)
                    opportunities.extend(opps)
                    self.logger.info(f"Successfully loaded {len(opps)} valid opportunities from {f.name}")
                except Exception as e:
                    self.logger.warning(f"Failed parsing import file {f.name}: {e}")

        return opportunities


def re_split_skills(text: str) -> List[str]:
    """Helper to split comma, semicolon, or pipe-separated skills."""
    import re
    return re.split(r"[,;|]", text)
