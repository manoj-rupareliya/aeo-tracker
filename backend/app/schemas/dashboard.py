"""
Dashboard & Reporting Schemas
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID

from pydantic import BaseModel


class LLMScoreData(BaseModel):
    """Score data for a single LLM"""
    provider: str
    display_name: str
    avg_score: float
    mention_rate: float
    top3_rate: float
    citation_rate: float
    total_runs: int
    trend: str  # "up", "down", "stable"
    trend_delta: Optional[float]


class LLMBreakdown(BaseModel):
    """Breakdown of visibility by LLM provider"""
    project_id: UUID
    period_start: datetime
    period_end: datetime
    llms: List[LLMScoreData]
    overall_avg: float


class KeywordScoreData(BaseModel):
    """Score data for a single keyword"""
    keyword_id: UUID
    keyword: str
    avg_score: float
    mention_rate: float
    top3_rate: float
    best_llm: str
    worst_llm: str
    run_count: int
    last_run_at: Optional[datetime]


class KeywordBreakdown(BaseModel):
    """Breakdown of visibility by keyword"""
    project_id: UUID
    period_start: datetime
    period_end: datetime
    keywords: List[KeywordScoreData]
    top_performing: List[str]
    bottom_performing: List[str]


class CompetitorData(BaseModel):
    """Competitor comparison data"""
    competitor_id: UUID
    name: str
    mention_count: int
    mention_rate: float
    avg_position: float
    sentiment_positive: int
    sentiment_neutral: int
    sentiment_negative: int
    top_keywords: List[str]


class CompetitorComparison(BaseModel):
    """Comparison with competitors"""
    project_id: UUID
    period_start: datetime
    period_end: datetime
    own_brand: Dict[str, Any]  # Same structure as CompetitorData
    competitors: List[CompetitorData]
    brand_advantage_keywords: List[str]  # Keywords where brand beats competitors
    competitor_advantage_keywords: List[str]  # Keywords where competitors win


class SourceData(BaseModel):
    """Source citation data"""
    source_id: UUID
    domain: str
    category: str
    site_name: Optional[str]
    citation_count: int
    citation_rate: float
    cites_brand: bool
    cites_competitors: bool
    exclusive_to: Optional[str]  # "brand", "competitor", or None
    last_cited_at: datetime


class SourceLeaderboard(BaseModel):
    """Leaderboard of citation sources"""
    project_id: UUID
    period_start: datetime
    period_end: datetime
    total_citations: int
    unique_sources: int
    sources: List[SourceData]
    brand_cited_sources: List[SourceData]
    competitor_only_sources: List[SourceData]
    hallucinated_count: int


class TimeSeriesPoint(BaseModel):
    """Single point in time series"""
    date: datetime
    value: float
    label: Optional[str] = None


class TimeSeriesData(BaseModel):
    """Time series data for charts"""
    project_id: UUID
    metric: str  # "visibility_score", "mention_rate", "citation_rate", etc.
    granularity: str  # "daily", "weekly", "monthly"
    series: List[TimeSeriesPoint]

    # Comparison series (optional)
    comparison_series: Optional[List[TimeSeriesPoint]] = None
    comparison_label: Optional[str] = None


class DashboardMetric(BaseModel):
    """Single dashboard metric"""
    label: str
    value: float
    format: str  # "number", "percent", "score"
    trend: str  # "up", "down", "stable"
    trend_delta: Optional[float]
    trend_period: str  # "vs last week", "vs last month"


class DashboardOverview(BaseModel):
    """Main dashboard overview"""
    project_id: UUID
    project_name: str
    last_updated: datetime

    # Key metrics
    visibility_score: DashboardMetric
    mention_rate: DashboardMetric
    citation_rate: DashboardMetric
    top3_rate: DashboardMetric

    # Quick stats
    total_keywords: int
    total_runs_this_period: int
    active_llms: List[str]

    # Best/worst performers
    best_keyword: Optional[str]
    worst_keyword: Optional[str]
    best_llm: Optional[str]
    worst_llm: Optional[str]

    # Recent activity
    recent_runs: int
    pending_runs: int
    failed_runs: int


class ReportExport(BaseModel):
    """Report export configuration"""
    project_id: UUID
    period_start: datetime
    period_end: datetime
    include_sections: List[str] = [
        "overview",
        "llm_breakdown",
        "keyword_breakdown",
        "competitor_comparison",
        "source_analysis",
        "time_series"
    ]
    format: str = "json"  # "json", "csv", "pdf"


class AlertConfig(BaseModel):
    """Alert configuration"""
    project_id: UUID
    alert_type: str  # "score_drop", "competitor_spike", "new_citation"
    threshold: float
    is_active: bool = True
    notification_email: Optional[str] = None
    webhook_url: Optional[str] = None


class Alert(BaseModel):
    """Triggered alert"""
    id: UUID
    project_id: UUID
    alert_type: str
    message: str
    details: Dict[str, Any]
    is_read: bool
    created_at: datetime
