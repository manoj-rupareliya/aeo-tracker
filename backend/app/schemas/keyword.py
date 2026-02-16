"""
Keyword Schemas
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class KeywordCreate(BaseModel):
    """Keyword creation request"""
    keyword: str = Field(..., min_length=1, max_length=500)
    context: Optional[str] = Field(None, max_length=1000)
    priority: str = Field(default="medium", pattern="^(high|medium|low)$")


class KeywordBulkCreate(BaseModel):
    """Bulk keyword creation"""
    keywords: List[str] = Field(..., min_items=1, max_items=100)
    priority: str = Field(default="medium", pattern="^(high|medium|low)$")


class KeywordUpdate(BaseModel):
    """Keyword update request"""
    keyword: Optional[str] = Field(None, min_length=1, max_length=500)
    context: Optional[str] = None
    priority: Optional[str] = Field(None, pattern="^(high|medium|low)$")
    is_active: Optional[bool] = None


class KeywordAnalysisSummary(BaseModel):
    """Summary of latest keyword analysis"""
    brand_mentioned: bool = False
    brand_position: Optional[int] = None
    total_brands_found: int = 0
    total_citations: int = 0
    our_domain_cited: bool = False
    visibility_score: float = 0
    top_brands: List[str] = []
    provider: Optional[str] = None
    analyzed_at: Optional[datetime] = None
    # AIO (AI Overview) fields
    has_aio: bool = False  # Whether this query has an AI Overview
    brand_in_aio: bool = False  # Whether our brand appears in the AIO
    domain_in_aio: bool = False  # Whether our domain appears in the AIO


class KeywordResponse(BaseModel):
    """Keyword response"""
    id: UUID
    keyword: str
    context: Optional[str]
    priority: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Stats
    prompt_count: int = 0
    run_count: int = 0
    avg_visibility_score: Optional[float] = None
    last_run_at: Optional[datetime] = None

    # Latest analysis summary
    latest_analysis: Optional[KeywordAnalysisSummary] = None

    class Config:
        from_attributes = True


class KeywordListResponse(BaseModel):
    """Paginated keyword list"""
    items: List[KeywordResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class KeywordStats(BaseModel):
    """Keyword statistics"""
    keyword_id: UUID
    keyword: str
    total_runs: int
    avg_visibility_score: float
    mention_rate: float  # % of runs where brand was mentioned
    top3_rate: float     # % of runs where brand was in top 3
    citation_rate: float # % of runs where brand was cited
    scores_by_llm: dict  # {llm: avg_score}
