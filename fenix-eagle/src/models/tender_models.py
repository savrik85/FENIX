from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum

class ScrapingStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TenderSource(str, Enum):
    SAM_GOV = "sam.gov"
    DODGE = "dodge"
    CUSTOM = "custom"

class TenderData(BaseModel):
    id: Optional[str] = None
    title: str
    description: str
    source: TenderSource
    source_url: str
    posting_date: datetime
    response_deadline: Optional[datetime] = None
    estimated_value: Optional[float] = None
    location: Optional[str] = None
    naics_codes: List[str] = Field(default=[])
    keywords_found: List[str] = Field(default=[])
    relevance_score: Optional[float] = Field(default=None, ge=0, le=1)
    contact_info: Dict[str, Any] = Field(default={})
    requirements: List[str] = Field(default=[])
    extracted_data: Dict[str, Any] = Field(default={})
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None

class ScrapingJob(BaseModel):
    id: str
    source: TenderSource
    keywords: List[str] = Field(default=[])
    filters: Dict[str, Any] = Field(default={})
    max_results: int = Field(default=100)
    status: ScrapingStatus = ScrapingStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None
    progress: int = Field(default=0, ge=0, le=100)
    results_count: int = Field(default=0)
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default={})

class CrawlerConfig(BaseModel):
    source: TenderSource
    base_url: str
    search_endpoints: List[str]
    headers: Dict[str, str] = Field(default={})
    rate_limits: Dict[str, int] = Field(default={})
    extraction_rules: Dict[str, Any] = Field(default={})
    ai_prompts: Dict[str, str] = Field(default={})

class ExtractedContent(BaseModel):
    url: str
    title: Optional[str] = None
    content: str
    metadata: Dict[str, Any] = Field(default={})
    extracted_at: datetime = Field(default_factory=datetime.now)
    extraction_method: str = "crawl4ai"
    ai_processed: bool = False
    structured_data: Dict[str, Any] = Field(default={})

class RelevanceFilter(BaseModel):
    keywords: List[str]
    required_terms: List[str] = Field(default=[])
    excluded_terms: List[str] = Field(default=[])
    min_relevance_score: float = Field(default=0.5, ge=0, le=1)
    location_filters: List[str] = Field(default=[])
    value_range: Optional[Dict[str, float]] = None
    date_range: Optional[Dict[str, datetime]] = None