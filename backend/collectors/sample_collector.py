"""Sample & offline opportunity collector.
Ensures the application always has working data even without live web scraping.
"""

import json
from typing import List
from datetime import date
from backend.collectors.base_collector import BaseCollector
from backend.models.opportunity import Opportunity
from backend.utils.config import settings


class SampleCollector(BaseCollector):
    """Loads existing opportunities from data/jobs.json or provides curated student opportunities."""

    def __init__(self):
        super().__init__(name="sample_offline")

    def collect(self) -> List[Opportunity]:
        opportunities: List[Opportunity] = []

        # 1. Load from data/jobs.json if available
        if settings.JOBS_PATH.exists():
            try:
                with open(settings.JOBS_PATH, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                for item in raw_data:
                    if "apply_url" in item:
                        opportunities.append(Opportunity(**item))
                    else:
                        opportunities.append(Opportunity.from_legacy_job(item))
                if opportunities:
                    self.logger.info(f"Loaded {len(opportunities)} opportunities from {settings.JOBS_PATH.name}")
                    return opportunities
            except Exception as e:
                self.logger.warning(f"Failed loading from jobs.json: {e}")

        # 2. Curated starter opportunities for fresh installations
        curated = [
            Opportunity(
                title="AI / ML Research Intern",
                company="OpenLabs Research",
                description="Work on fine-tuning open-source LLMs and multimodal vision-language models for edge devices.",
                opportunity_type="internship",
                skills=["Python", "PyTorch", "Hugging Face", "NLP", "Machine Learning"],
                location="Bengaluru / Hybrid",
                remote=True,
                stipend="₹45,000 / month",
                salary=None,
                experience="Final-year student / Fresher",
                eligibility="B.Tech / M.Tech / M.S. in CS, AI, DS or related field",
                deadline=date.today().isoformat(),
                source="Campus Outreach",
                source_url="https://example.com/careers/ml-intern",
                apply_url="https://example.com/careers/ml-intern/apply",
                posted_date=date.today().isoformat(),
                status="open"
            ),
            Opportunity(
                title="Full Stack Software Engineer Intern",
                company="NovaCloud Systems",
                description="Design and implement REST APIs, asynchronous workers, and modern interactive web dashboards.",
                opportunity_type="internship",
                skills=["Python", "FastAPI", "JavaScript", "SQL", "Docker", "Git"],
                location="Remote",
                remote=True,
                stipend="₹35,000 / month",
                salary=None,
                experience="Student / 2025-2026 Batch",
                eligibility="Good problem solving and CS fundamentals",
                deadline=date.today().isoformat(),
                source="Student Hub Direct",
                source_url="https://example.com/careers/fullstack-intern",
                apply_url="https://example.com/careers/fullstack-intern/apply",
                posted_date=date.today().isoformat(),
                status="open"
            ),
            Opportunity(
                title="Quantitative Analytics & Data Science Intern",
                company="AlphaQuant Capital",
                description="Analyze financial time-series data, build predictive econometric models, and evaluate algorithmic strategies.",
                opportunity_type="internship",
                skills=["Python", "Pandas", "Scikit-learn", "Data Analysis", "Statistics"],
                location="Mumbai",
                remote=False,
                stipend="₹60,000 / month",
                salary=None,
                experience="Pre-final or final year student",
                eligibility="Strong mathematical and programming aptitude",
                deadline=date.today().isoformat(),
                source="FinTech Portal",
                source_url="https://example.com/careers/quant-intern",
                apply_url="https://example.com/careers/quant-intern/apply",
                posted_date=date.today().isoformat(),
                status="open"
            )
        ]
        return curated
