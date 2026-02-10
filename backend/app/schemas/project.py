"""
Project & Brand Schemas
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class BrandCreate(BaseModel):
    """Brand creation request"""
    name: str = Field(..., min_length=1, max_length=255)
    is_primary: bool = False
    aliases: List[str] = []

    @field_validator("aliases")
    @classmethod
    def clean_aliases(cls, v: List[str]) -> List[str]:
        return [alias.strip() for alias in v if alias.strip()]


class BrandUpdate(BaseModel):
    """Brand update request"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_primary: Optional[bool] = None
    aliases: Optional[List[str]] = None


class BrandResponse(BaseModel):
    """Brand response"""
    id: UUID
    name: str
    is_primary: bool
    aliases: List[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CompetitorCreate(BaseModel):
    """Competitor creation request"""
    name: str = Field(..., min_length=1, max_length=255)
    domain: Optional[str] = Field(None, max_length=255)
    aliases: List[str] = []


class CompetitorUpdate(BaseModel):
    """Competitor update request"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    domain: Optional[str] = None
    aliases: Optional[List[str]] = None


class CompetitorResponse(BaseModel):
    """Competitor response"""
    id: UUID
    name: str
    domain: Optional[str]
    aliases: List[str]
    created_at: datetime

    class Config:
        from_attributes = True


class ProjectCreate(BaseModel):
    """Project creation request"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    domain: str = Field(..., min_length=1, max_length=255)
    industry: str = Field(default="other")
    enabled_llms: List[str] = ["openai", "anthropic", "google", "perplexity"]
    crawl_frequency_days: int = Field(default=7, ge=1, le=30)

    # Initial brands and competitors
    brands: List[BrandCreate] = []
    competitors: List[CompetitorCreate] = []

    @field_validator("industry")
    @classmethod
    def validate_industry(cls, v: str) -> str:
        valid_industries = [
            "technology", "ecommerce", "finance", "healthcare",
            "education", "marketing", "legal", "real_estate",
            "travel", "food_beverage", "other"
        ]
        if v not in valid_industries:
            raise ValueError(f"Industry must be one of: {', '.join(valid_industries)}")
        return v

    @field_validator("enabled_llms")
    @classmethod
    def validate_llms(cls, v: List[str]) -> List[str]:
        valid_llms = ["openai", "anthropic", "google", "perplexity"]
        for llm in v:
            if llm not in valid_llms:
                raise ValueError(f"LLM must be one of: {', '.join(valid_llms)}")
        return v

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, v: str) -> str:
        # Remove protocol and www
        v = v.lower().strip()
        if v.startswith("http://"):
            v = v[7:]
        if v.startswith("https://"):
            v = v[8:]
        if v.startswith("www."):
            v = v[4:]
        # Remove trailing slash
        return v.rstrip("/")


class ProjectUpdate(BaseModel):
    """Project update request"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    industry: Optional[str] = None
    enabled_llms: Optional[List[str]] = None
    crawl_frequency_days: Optional[int] = Field(None, ge=1, le=30)
    is_active: Optional[bool] = None


class ProjectResponse(BaseModel):
    """Project response"""
    id: UUID
    name: str
    description: Optional[str]
    domain: str
    industry: str
    enabled_llms: List[str]
    crawl_frequency_days: int
    last_crawl_at: Optional[datetime]
    next_crawl_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Nested data
    brands: List[BrandResponse] = []
    competitors: List[CompetitorResponse] = []

    # Stats
    keyword_count: int = 0
    total_runs: int = 0

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    """Paginated project list"""
    items: List[ProjectResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class ProjectStats(BaseModel):
    """Project statistics"""
    total_keywords: int
    total_runs: int
    total_mentions: int
    total_citations: int
    avg_visibility_score: float
    last_crawl_at: Optional[datetime]
    runs_this_month: int
    tokens_used_this_month: int
