from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ScrapingStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TenderSource(str, Enum):
    SAM_GOV = "sam.gov"
    DODGE = "dodge"
    CONSTRUCTION_COM = "construction.com"
    NYC_OPEN_DATA = "nyc.opendata"
    SHOVELS_AI = "shovels.ai"
    AUTODESK_ACC = "autodesk_acc"
    BUILDING_CONNECTED = "building_connected"
    POPTAVKY_CZ = "poptavky.cz"
    CUSTOM = "custom"


class TenderData(BaseModel):
    tender_id: str | None = None
    title: str
    description: str
    source: TenderSource
    source_url: str
    posting_date: datetime
    response_deadline: datetime | None = None
    estimated_value: float | None = None
    location: str | None = None
    naics_codes: list[str] = Field(default=[])
    keywords_found: list[str] = Field(default=[])
    relevance_score: float | None = Field(default=None, ge=0, le=1)
    contact_info: dict[str, Any] = Field(default={})
    requirements: list[str] = Field(default=[])
    extracted_data: dict[str, Any] = Field(default={})
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime | None = None


class ScrapingJob(BaseModel):
    job_id: str
    source: TenderSource
    keywords: list[str] = Field(default=[])
    filters: dict[str, Any] = Field(default={})
    max_results: int = Field(default=100)
    status: ScrapingStatus = ScrapingStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    estimated_completion: datetime | None = None
    progress: int = Field(default=0, ge=0, le=100)
    results_count: int = Field(default=0)
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default={})


class CrawlerConfig(BaseModel):
    source: TenderSource
    base_url: str
    search_endpoints: list[str]
    headers: dict[str, str] = Field(default={})
    rate_limits: dict[str, int] = Field(default={})
    extraction_rules: dict[str, Any] = Field(default={})
    ai_prompts: dict[str, str] = Field(default={})


class ExtractedContent(BaseModel):
    url: str
    title: str | None = None
    content: str
    metadata: dict[str, Any] = Field(default={})
    extracted_at: datetime = Field(default_factory=datetime.now)
    extraction_method: str = "crawl4ai"
    ai_processed: bool = False
    structured_data: dict[str, Any] = Field(default={})


class RelevanceFilter(BaseModel):
    keywords: list[str]
    required_terms: list[str] = Field(default=[])
    excluded_terms: list[str] = Field(default=[])
    min_relevance_score: float = Field(default=0.5, ge=0, le=1)
    location_filters: list[str] = Field(default=[])
    value_range: dict[str, float] | None = None
    date_range: dict[str, datetime] | None = None
