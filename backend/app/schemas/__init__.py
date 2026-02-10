"""
Pydantic Schemas for API Request/Response validation
"""

from .auth import (
    UserCreate,
    UserLogin,
    UserResponse,
    TokenResponse,
    TokenRefresh,
)
from .project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectListResponse,
    BrandCreate,
    BrandResponse,
    CompetitorCreate,
    CompetitorResponse,
)
from .keyword import (
    KeywordCreate,
    KeywordUpdate,
    KeywordResponse,
    KeywordListResponse,
)
from .prompt import (
    PromptTemplateCreate,
    PromptTemplateResponse,
    PromptResponse,
    GeneratePromptsRequest,
)
from .llm import (
    LLMRunCreate,
    LLMRunResponse,
    LLMResponseData,
    LLMExecutionRequest,
    LLMExecutionStatus,
)
from .analysis import (
    BrandMentionResponse,
    CitationResponse,
    CitationSourceResponse,
    VisibilityScoreResponse,
    AggregatedScoreResponse,
)
from .dashboard import (
    DashboardOverview,
    LLMBreakdown,
    KeywordBreakdown,
    CompetitorComparison,
    SourceLeaderboard,
    TimeSeriesData,
)

__all__ = [
    # Auth
    "UserCreate",
    "UserLogin",
    "UserResponse",
    "TokenResponse",
    "TokenRefresh",
    # Project
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectResponse",
    "ProjectListResponse",
    "BrandCreate",
    "BrandResponse",
    "CompetitorCreate",
    "CompetitorResponse",
    # Keyword
    "KeywordCreate",
    "KeywordUpdate",
    "KeywordResponse",
    "KeywordListResponse",
    # Prompt
    "PromptTemplateCreate",
    "PromptTemplateResponse",
    "PromptResponse",
    "GeneratePromptsRequest",
    # LLM
    "LLMRunCreate",
    "LLMRunResponse",
    "LLMResponseData",
    "LLMExecutionRequest",
    "LLMExecutionStatus",
    # Analysis
    "BrandMentionResponse",
    "CitationResponse",
    "CitationSourceResponse",
    "VisibilityScoreResponse",
    "AggregatedScoreResponse",
    # Dashboard
    "DashboardOverview",
    "LLMBreakdown",
    "KeywordBreakdown",
    "CompetitorComparison",
    "SourceLeaderboard",
    "TimeSeriesData",
]
