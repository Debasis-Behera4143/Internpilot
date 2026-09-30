"""Collectors package initialization."""

from backend.collectors.base_collector import BaseCollector
from backend.collectors.sample_collector import SampleCollector
from backend.collectors.yc_collector import YCCollector
from backend.collectors.wellfound_collector import WellfoundCollector
from backend.collectors.internshala_collector import InternshalaCollector
from backend.collectors.telegram_collector import TelegramCollector
from backend.collectors.linkedin_collector import LinkedInCollector
from backend.collectors.import_collector import ImportCollector
from backend.collectors.ats_adapter import ATSAdapter
from backend.collectors.company_careers_adapter import CompanyCareersAdapter
from backend.collectors.linkedin_adapter import LinkedInAdapter
from backend.collectors.internshala_adapter import InternshalaAdapter
from backend.collectors.csv_collector import CSVCollector
from backend.collectors.json_collector import JSONCollector
from backend.collectors.normalizer import (
    normalize_opportunity,
    normalize_company,
    normalize_location,
    normalize_skills,
    normalize_url,
    normalize_opportunity_type,
    clean_whitespace
)

__all__ = [
    "BaseCollector",
    "SampleCollector",
    "YCCollector",
    "WellfoundCollector",
    "InternshalaCollector",
    "TelegramCollector",
    "LinkedInCollector",
    "ImportCollector",
    "ATSAdapter",
    "CompanyCareersAdapter",
    "LinkedInAdapter",
    "InternshalaAdapter",
    "CSVCollector",
    "JSONCollector",
    "normalize_opportunity",
    "normalize_company",
    "normalize_location",
    "normalize_skills",
    "normalize_url",
    "normalize_opportunity_type",
    "clean_whitespace"
]
