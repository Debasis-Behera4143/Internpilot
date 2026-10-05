"""Centralized configuration module for AI-Powered Student Career & Opportunity Hub.
Safely reads environment variables with fallbacks and validates file paths.
"""

import os
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Find project root directory (internpilot root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Load .env file if present
env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
else:
    load_dotenv()


class Settings:
    """Application configuration settings."""

    # Project metadata
    APP_NAME: str = os.getenv("APP_NAME", "AI-Powered Student Career & Opportunity Hub")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # File paths (resolved to absolute paths for consistency)
    ROOT_DIR: Path = PROJECT_ROOT
    DATA_DIR: Path = PROJECT_ROOT / os.getenv("DATA_DIR", "data")
    PROFILE_PATH: Path = PROJECT_ROOT / os.getenv("PROFILE_PATH", "data/profile.json")
    JOBS_PATH: Path = PROJECT_ROOT / os.getenv("JOBS_PATH", "data/jobs.json")
    APPLICATIONS_PATH: Path = PROJECT_ROOT / os.getenv("APPLICATIONS_PATH", "data/applications.json")
    SEEN_JOBS_PATH: Path = PROJECT_ROOT / os.getenv("SEEN_JOBS_PATH", "data/seen_jobs.json")
    DATABASE_PATH: Path = PROJECT_ROOT / "data" / "career_hub.db"
    RESUMES_DIR: Path = PROJECT_ROOT / "data" / "resumes"

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH.as_posix()}")

    # Authentication & Security
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "internpilot-local-secure-jwt-secret-key-32bytes-min!")
    ADMIN_EMAIL: Optional[str] = os.getenv("ADMIN_EMAIL", None)
    ADMIN_PASSWORD: Optional[str] = os.getenv("ADMIN_PASSWORD", None)
    GOOGLE_CLIENT_ID: Optional[str] = os.getenv("GOOGLE_CLIENT_ID", None)
    GOOGLE_CLIENT_SECRET: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET", None)

    # Local AI Models (Open-Source, Local)
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    OUTREACH_MODEL: str = os.getenv("OUTREACH_MODEL", "distilgpt2")
    ENABLE_NEURAL_OUTREACH: bool = os.getenv("ENABLE_NEURAL_OUTREACH", "False").lower() in ("true", "1")
    MIN_MATCH_SCORE_THRESHOLD: float = float(os.getenv("MIN_MATCH_SCORE_THRESHOLD", "40.0"))

    # Hybrid Career Matching Weights (Total = 1.0)
    # Documented configuration: Semantic (35%), Skills (30%), Roles (15%), Eligibility (10%), Location (5%), Experience (5%)
    WEIGHT_SEMANTIC: float = float(os.getenv("WEIGHT_SEMANTIC", "0.35"))
    WEIGHT_SKILL: float = float(os.getenv("WEIGHT_SKILL", "0.30"))
    WEIGHT_ROLE: float = float(os.getenv("WEIGHT_ROLE", "0.15"))
    WEIGHT_ELIGIBILITY: float = float(os.getenv("WEIGHT_ELIGIBILITY", "0.10"))
    WEIGHT_LOCATION: float = float(os.getenv("WEIGHT_LOCATION", "0.05"))
    WEIGHT_EXPERIENCE: float = float(os.getenv("WEIGHT_EXPERIENCE", "0.05"))

    # Telegram alerts (Outbound bot notifications)
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    # Telegram Public Web-Preview Ingestion (Public channels, no credentials required)
    TELEGRAM_PUBLIC_CHANNELS: str = os.getenv(
        "TELEGRAM_PUBLIC_CHANNELS",
        os.getenv("TELEGRAM_CHANNELS", "JOBSANDINTERNSHIPSUPDATES,JobsInternshipsGroup")
    ).strip()
    TELEGRAM_MAX_POSTS_PER_CHANNEL: int = int(os.getenv("TELEGRAM_MAX_POSTS_PER_CHANNEL", "30"))
    TELEGRAM_REQUEST_TIMEOUT: int = int(os.getenv("TELEGRAM_REQUEST_TIMEOUT", "10"))

    # Collectors & Scraping
    PLAYWRIGHT_HEADLESS: bool = os.getenv("PLAYWRIGHT_HEADLESS", "True").lower() in ("true", "1", "t")
    SCRAPER_TIMEOUT_SECONDS: int = int(os.getenv("SCRAPER_TIMEOUT_SECONDS", "10"))
    ENABLE_SAMPLE_FALLBACK: bool = os.getenv("ENABLE_SAMPLE_FALLBACK", "True").lower() in ("true", "1", "t")

    # Automated Background Ingestion Scheduler
    AUTO_INGEST_ON_STARTUP: bool = os.getenv("AUTO_INGEST_ON_STARTUP", "True").lower() in ("true", "1", "t")
    AUTO_INGEST_INTERVAL_MINUTES: int = int(os.getenv("AUTO_INGEST_INTERVAL_MINUTES", "20"))

    @classmethod
    def ensure_directories(cls):
        """Ensures that required data directories exist."""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.RESUMES_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_directories()
