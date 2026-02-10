"""
Analysis & Scoring Schemas
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field


class BrandMentionResponse(BaseModel):
    """Brand mention in LLM response"""
    id: UUID
    response_id: UUID
    mentioned_text: str
    normalized_name: str
    is_own_brand: bool
    brand_id: Optional[UUID]
    competitor_id: Optional[UUID]
    mention_position: int
    character_offset: Optional[int]
    context_snippet: Optional[str]
    match_type: str
    match_confidence: float
    sentiment: str
    sentiment_score: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


class CitationSourceResponse(BaseModel):
    """Citation source (domain)"""
    id: UUID
    domain: str
    category: str
    site_name: Optional[str]
    description: Optional[str]
    domain_authority: Optional[int]
    total_citations: int
    last_cited_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class CitationResponse(BaseModel):
    """Individual citation"""
    id: UUID
    response_id: UUID
    source_id: Optional[UUID]
    cited_url: str
    anchor_text: Optional[str]
    context_snippet: Optional[str]
    citation_position: Optional[int]
    is_valid_url: Optional[bool]
    is_accessible: Optional[bool]
    http_status_code: Optional[int]
    is_hallucinated: bool
    last_validated_at: Optional[datetime]
    created_at: datetime

    # Nested source info
    source: Optional[CitationSourceResponse] = None

    class Config:
        from_attributes = True


class ScoreBreakdown(BaseModel):
    """Detailed score breakdown"""
    mention_score: float = Field(description="Score for brand mention presence")
    position_score: float = Field(description="Score for mention position")
    citation_score: float = Field(description="Score for brand citations")
    sentiment_score: float = Field(description="Score for sentiment")
    competitor_delta: float = Field(description="Relative score vs competitors")


class VisibilityScoreResponse(BaseModel):
    """Visibility score with explanation"""
    id: UUID
    project_id: UUID
    llm_run_id: Optional[UUID]
    keyword_id: Optional[UUID]
    provider: Optional[str]
    mention_score: float
    position_score: float
    citation_score: float
    sentiment_score: float
    competitor_delta: float
    total_score: float
    llm_weight: float
    weighted_score: float
    score_explanation: Dict[str, Any]
    score_date: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class AggregatedScoreResponse(BaseModel):
    """Aggregated scores for a period"""
    id: UUID
    project_id: UUID
    period_type: str
    period_start: datetime
    period_end: datetime
    avg_visibility_score: float
    avg_mention_score: float
    avg_position_score: float
    avg_citation_score: float
    scores_by_llm: Dict[str, float]
    score_delta_vs_previous: Optional[float]
    total_queries: int
    total_mentions: int
    total_citations: int
    created_at: datetime

    class Config:
        from_attributes = True


class ScoreCalculationRequest(BaseModel):
    """Request to calculate scores"""
    project_id: UUID
    llm_run_ids: Optional[List[UUID]] = None  # If None, calculate for all pending
    recalculate: bool = False  # Recalculate existing scores


class CompetitorMentionStats(BaseModel):
    """Competitor mention statistics"""
    competitor_id: UUID
    competitor_name: str
    total_mentions: int
    mention_rate: float
    avg_position: float
    top3_rate: float
    sentiment_breakdown: Dict[str, int]


class SourceCitationStats(BaseModel):
    """Source citation statistics"""
    source_id: UUID
    domain: str
    category: str
    total_citations: int
    citation_rate: float
    cites_own_brand: int
    cites_competitors: int
    exclusive_to_competitors: bool


class AnalysisReport(BaseModel):
    """Comprehensive analysis report"""
    project_id: UUID
    period_start: datetime
    period_end: datetime

    # Overall metrics
    total_runs: int
    total_mentions: int
    total_citations: int
    avg_visibility_score: float
    score_trend: str  # "up", "down", "stable"

    # Breakdown by LLM
    scores_by_llm: Dict[str, float]
    mentions_by_llm: Dict[str, int]

    # Brand performance
    mention_rate: float
    top3_rate: float
    citation_rate: float

    # Competitor analysis
    competitor_stats: List[CompetitorMentionStats]

    # Source intelligence
    top_sources: List[SourceCitationStats]
    competitor_exclusive_sources: List[SourceCitationStats]

    # Recommendations
    recommendations: List[str]
