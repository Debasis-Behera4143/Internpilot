"""Source data models for multi-source job ingestion, registry, and import workflows."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SourceType(str, Enum):
    TELEGRAM = "TELEGRAM"
    LINKEDIN_AUTHORIZED = "LINKEDIN_AUTHORIZED"
    INTERNSHALA_AUTHORIZED_OR_IMPORT = "INTERNSHALA_AUTHORIZED_OR_IMPORT"
    ATS_PUBLIC_FEED = "ATS_PUBLIC_FEED"
    COMPANY_CAREERS = "COMPANY_CAREERS"
    EMPLOYER_SUBMISSION = "EMPLOYER_SUBMISSION"
    COLLEGE_SUBMISSION = "COLLEGE_SUBMISSION"
    CSV = "CSV"
    JSON = "JSON"


class SourceStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PAUSED = "PAUSED"
    DISABLED = "DISABLED"


class SourceTrustLevel(str, Enum):
    OFFICIAL_COMPANY = "OFFICIAL_COMPANY"
    AUTHORIZED_API = "AUTHORIZED_API"
    ATS_PUBLIC = "ATS_PUBLIC"
    EMPLOYER_SUBMITTED = "EMPLOYER_SUBMITTED"
    COLLEGE_SUBMITTED = "COLLEGE_SUBMITTED"
    PUBLIC_TELEGRAM = "PUBLIC_TELEGRAM"
    IMPORTED_DATA = "IMPORTED_DATA"
    UNVERIFIED_EXTERNAL = "UNVERIFIED_EXTERNAL"


class SourceModel(BaseModel):
    """Source registry entity."""
    id: str
    name: str
    type: SourceType
    status: SourceStatus = SourceStatus.ACTIVE
    trust_level: SourceTrustLevel = SourceTrustLevel.UNVERIFIED_EXTERNAL
    configuration: Dict[str, Any] = Field(default_factory=dict)
    last_ingested_at: Optional[str] = None
    last_success_at: Optional[str] = None
    last_error: Optional[str] = None
    items_count: int = 0
    items_accepted: int = 0
    items_rejected: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @property
    def source_type(self) -> str:
        return self.type.value if hasattr(self.type, "value") else str(self.type)

    @property
    def active(self) -> bool:
        return (self.status == SourceStatus.ACTIVE) if hasattr(self.status, "value") else (str(self.status).upper() == "ACTIVE")

    @property
    def last_run_at(self) -> Optional[str]:
        return self.last_ingested_at

    @property
    def last_success(self) -> Optional[str]:
        return self.last_success_at

    @property
    def last_ingestion(self) -> Optional[str]:
        return self.last_ingested_at

    @property
    def items_found(self) -> int:
        return self.items_count

    @property
    def items_verified(self) -> int:
        return self.items_accepted

    def to_dict(self) -> dict:
        d = self.model_dump()
        d["source_type"] = self.source_type
        d["active"] = self.active
        d["last_run_at"] = self.last_run_at
        d["last_success"] = self.last_success
        d["last_ingestion"] = self.last_ingestion
        d["items_found"] = self.items_found
        d["items_verified"] = self.items_verified
        return d


class SourceCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    type: SourceType
    trust_level: Optional[SourceTrustLevel] = None
    status: SourceStatus = SourceStatus.ACTIVE
    configuration: Dict[str, Any] = Field(default_factory=dict)


class SourceUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=255)
    status: Optional[SourceStatus] = None
    trust_level: Optional[SourceTrustLevel] = None
    configuration: Optional[Dict[str, Any]] = None


class TelegramChannelCreateRequest(BaseModel):
    channel_name: str = Field(..., min_length=2, max_length=255, description="Display name for channel")
    channel_username: str = Field(..., min_length=2, max_length=128, description="Channel handle e.g. @jobs_daily or jobs_daily")
    preview_url: Optional[str] = Field(default=None, description="Public preview URL e.g. https://t.me/s/channel")
    status: SourceStatus = SourceStatus.ACTIVE


class ImportPreviewItem(BaseModel):
    index: int
    title: str
    company: str
    location: str = "Remote"
    opportunity_type: str = "internship"
    apply_url: str
    is_valid: bool
    is_duplicate: bool = False
    validation_status: str = "VALID"
    rejection_reason: Optional[str] = None


class ImportPreviewResponse(BaseModel):
    total_records: int
    valid_count: int
    rejected_count: int
    duplicate_count: int
    sample_preview: List[ImportPreviewItem]
    rejection_summary: List[str]


class ImportConfirmRequest(BaseModel):
    source_name: str = Field(default="Authorized Import", min_length=2)
    source_type: SourceType = SourceType.CSV
    records: List[Dict[str, Any]]


class LinkedInStatusResponse(BaseModel):
    connection_status: str = "NOT CONNECTED"
    api_available: bool = False
    message: str = "Authorized API or CSV/JSON import required"
    export_file_present: bool = False
    last_import: Optional[str] = None
    imported_jobs: int = 0
    accepted: int = 0
    rejected: int = 0
    duplicates: int = 0
    source_details: Optional[Dict[str, Any]] = None
