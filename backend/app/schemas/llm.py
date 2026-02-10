"""
LLM Execution Schemas
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any
from uuid import UUID

from pydantic import BaseModel, Field


class LLMExecutionConfig(BaseModel):
    """Configuration for LLM execution"""
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2000, ge=100, le=8000)
    timeout_seconds: int = Field(default=60, ge=10, le=300)


class LLMRunCreate(BaseModel):
    """Create an LLM run request"""
    prompt_id: UUID
    provider: str = Field(..., pattern="^(openai|anthropic|google|perplexity)$")
    model_name: Optional[str] = None  # Uses default if not specified
    config: LLMExecutionConfig = LLMExecutionConfig()
    priority: str = Field(default="medium", pattern="^(high|medium|low)$")


class LLMBatchRunCreate(BaseModel):
    """Create batch LLM runs for keywords"""
    keyword_ids: List[UUID] = Field(..., min_items=1, max_items=50)
    providers: List[str] = Field(
        default=["openai", "anthropic", "google", "perplexity"],
        min_items=1
    )
    prompt_types: List[str] = Field(
        default=["informational", "comparative", "recommendation"],
        min_items=1
    )
    config: LLMExecutionConfig = LLMExecutionConfig()
    priority: str = Field(default="medium")


class LLMRunResponse(BaseModel):
    """LLM run response"""
    id: UUID
    project_id: UUID
    prompt_id: Optional[UUID]
    provider: str
    model_name: str
    temperature: float
    max_tokens: int
    status: str
    priority: str
    queued_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    estimated_cost_usd: Optional[Decimal]
    is_cached_result: bool
    retry_count: int
    error_message: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class LLMResponseData(BaseModel):
    """LLM response data"""
    id: UUID
    llm_run_id: UUID
    raw_response: str
    response_metadata: Dict[str, Any]
    parsed_response: Dict[str, Any]
    response_hash: str
    created_at: datetime

    class Config:
        from_attributes = True


class LLMExecutionRequest(BaseModel):
    """Request to execute LLM queries"""
    project_id: UUID
    keyword_ids: Optional[List[UUID]] = None  # If None, process all active keywords
    providers: Optional[List[str]] = None  # If None, use project's enabled LLMs
    prompt_types: Optional[List[str]] = None  # If None, use all types
    force_refresh: bool = False  # Ignore cache


class LLMExecutionStatus(BaseModel):
    """Status of LLM execution batch"""
    batch_id: UUID
    total_runs: int
    pending: int
    processing: int
    completed: int
    failed: int
    cached: int
    estimated_completion_time: Optional[datetime]
    runs: List[LLMRunResponse]


class LLMRunDetail(BaseModel):
    """Detailed LLM run with response"""
    run: LLMRunResponse
    response: Optional[LLMResponseData]
    mentions: List["BrandMentionResponse"] = []
    citations: List["CitationResponse"] = []
    visibility_score: Optional["VisibilityScoreResponse"] = None


class LLMCostSummary(BaseModel):
    """Cost summary for LLM runs"""
    project_id: UUID
    period_start: datetime
    period_end: datetime
    total_runs: int
    total_tokens_input: int
    total_tokens_output: int
    total_cost_usd: Decimal
    cost_by_provider: Dict[str, Decimal]
    cost_by_day: Dict[str, Decimal]


# Forward references for circular imports
from .analysis import BrandMentionResponse, CitationResponse, VisibilityScoreResponse

LLMRunDetail.model_rebuild()
