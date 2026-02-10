"""
Cost & Performance Governance API Routes
Budget management, rate limiting, and caching controls
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, User
from app.models.database import LLMProvider
from app.models.models_v2 import CostBudget, RateLimitState, CacheMetrics
from app.services.cost_service import CostGovernanceService
from app.utils import get_db
from app.api.middleware.auth import get_current_user

router = APIRouter()


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class CostBudgetResponse(BaseModel):
    """Response model for cost budgets."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    daily_token_limit: Optional[int]
    daily_cost_limit_usd: Optional[float]
    monthly_token_limit: Optional[int]
    monthly_cost_limit_usd: Optional[float]
    tokens_used_today: int
    cost_today_usd: float
    tokens_used_this_month: int
    cost_this_month_usd: float
    is_paused: bool
    pause_reason: Optional[str]


class UpdateBudgetRequest(BaseModel):
    """Request to update budget limits."""
    daily_token_limit: Optional[int] = None
    daily_cost_limit_usd: Optional[float] = None
    monthly_token_limit: Optional[int] = None
    monthly_cost_limit_usd: Optional[float] = None


class RateLimitStateResponse(BaseModel):
    """Response model for rate limit state."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    provider: str
    requests_this_minute: int
    requests_this_hour: int
    tokens_this_minute: int
    requests_per_minute_limit: int
    requests_per_hour_limit: int
    tokens_per_minute_limit: int
    is_rate_limited: bool
    rate_limited_until: Optional[datetime]
    consecutive_429s: int


class CacheMetricsResponse(BaseModel):
    """Response model for cache metrics."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    date: datetime
    cache_hits: int
    cache_misses: int
    hit_rate: Optional[float]
    tokens_saved: int
    estimated_cost_saved_usd: float


# ============================================================================
# BUDGET ENDPOINTS
# ============================================================================

@router.get("/{project_id}/budget")
async def get_budget(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get budget settings and current usage for a project.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    cost_service = CostGovernanceService(db)
    budget = await cost_service.get_or_create_budget(project_id)

    return {
        "project_id": str(project_id),
        "budget": {
            "daily_token_limit": budget.daily_token_limit,
            "daily_cost_limit_usd": float(budget.daily_cost_limit_usd) if budget.daily_cost_limit_usd else None,
            "monthly_token_limit": budget.monthly_token_limit,
            "monthly_cost_limit_usd": float(budget.monthly_cost_limit_usd) if budget.monthly_cost_limit_usd else None,
        },
        "usage": {
            "tokens_today": budget.tokens_used_today or 0,
            "cost_today_usd": float(budget.cost_today_usd) if budget.cost_today_usd else 0,
            "tokens_this_month": budget.tokens_used_this_month or 0,
            "cost_this_month_usd": float(budget.cost_this_month_usd) if budget.cost_this_month_usd else 0,
        },
        "status": {
            "is_paused": budget.is_paused,
            "pause_reason": budget.pause_reason,
            "paused_at": budget.paused_at.isoformat() if budget.paused_at else None,
        },
    }


@router.put("/{project_id}/budget")
async def update_budget(
    project_id: UUID,
    request: UpdateBudgetRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Update budget limits for a project.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    cost_service = CostGovernanceService(db)
    budget = await cost_service.update_budget_limits(
        project_id,
        daily_token_limit=request.daily_token_limit,
        daily_cost_limit_usd=Decimal(str(request.daily_cost_limit_usd)) if request.daily_cost_limit_usd else None,
        monthly_token_limit=request.monthly_token_limit,
        monthly_cost_limit_usd=Decimal(str(request.monthly_cost_limit_usd)) if request.monthly_cost_limit_usd else None,
    )

    await db.commit()

    return {
        "status": "updated",
        "project_id": str(project_id),
        "budget": {
            "daily_token_limit": budget.daily_token_limit,
            "daily_cost_limit_usd": float(budget.daily_cost_limit_usd) if budget.daily_cost_limit_usd else None,
            "monthly_token_limit": budget.monthly_token_limit,
            "monthly_cost_limit_usd": float(budget.monthly_cost_limit_usd) if budget.monthly_cost_limit_usd else None,
        },
    }


@router.post("/{project_id}/budget/unpause")
async def unpause_project(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Manually unpause a project that was paused due to budget limits.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    cost_service = CostGovernanceService(db)
    budget = await cost_service.unpause_project(project_id)

    await db.commit()

    return {
        "status": "unpaused",
        "project_id": str(project_id),
        "is_paused": budget.is_paused,
    }


@router.post("/{project_id}/budget/check")
async def check_budget(
    project_id: UUID,
    estimated_tokens: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Check if a request is within budget before making an LLM call.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    cost_service = CostGovernanceService(db)
    allowed, reason = await cost_service.check_budget(project_id, estimated_tokens)

    return {
        "allowed": allowed,
        "reason": reason,
        "estimated_tokens": estimated_tokens,
    }


# ============================================================================
# RATE LIMIT ENDPOINTS
# ============================================================================

@router.get("/{project_id}/rate-limits")
async def get_rate_limits(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get rate limit status for all providers.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    cost_service = CostGovernanceService(db)

    rate_limits = {}
    for provider in LLMProvider:
        state = await cost_service.get_or_create_rate_limit_state(project_id, provider)
        rate_limits[provider.value] = {
            "requests_this_minute": state.requests_this_minute or 0,
            "requests_this_hour": state.requests_this_hour or 0,
            "tokens_this_minute": state.tokens_this_minute or 0,
            "limits": {
                "requests_per_minute": state.requests_per_minute_limit,
                "requests_per_hour": state.requests_per_hour_limit,
                "tokens_per_minute": state.tokens_per_minute_limit,
            },
            "status": {
                "is_rate_limited": state.is_rate_limited,
                "rate_limited_until": state.rate_limited_until.isoformat() if state.rate_limited_until else None,
                "consecutive_429s": state.consecutive_429s or 0,
            },
        }

    return {
        "project_id": str(project_id),
        "providers": rate_limits,
    }


@router.get("/{project_id}/rate-limits/{provider}")
async def get_provider_rate_limit(
    project_id: UUID,
    provider: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get rate limit status for a specific provider.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        llm_provider = LLMProvider(provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

    cost_service = CostGovernanceService(db)
    state = await cost_service.get_or_create_rate_limit_state(project_id, llm_provider)

    return RateLimitStateResponse.model_validate(state)


@router.post("/{project_id}/rate-limits/{provider}/check")
async def check_rate_limit(
    project_id: UUID,
    provider: str,
    estimated_tokens: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Check if a request is within rate limits.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        llm_provider = LLMProvider(provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

    cost_service = CostGovernanceService(db)
    allowed, reason, retry_after = await cost_service.check_rate_limit(
        project_id, llm_provider, estimated_tokens
    )

    return {
        "allowed": allowed,
        "reason": reason,
        "retry_after_seconds": retry_after,
        "provider": provider,
    }


# ============================================================================
# CACHE METRICS ENDPOINTS
# ============================================================================

@router.get("/{project_id}/cache")
async def get_cache_metrics(
    project_id: UUID,
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get cache performance metrics.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    cost_service = CostGovernanceService(db)
    metrics = await cost_service.get_cache_metrics(project_id, days)

    # Calculate totals
    total_hits = sum((m.cache_hits or 0) for m in metrics)
    total_misses = sum((m.cache_misses or 0) for m in metrics)
    total_saved = sum(float(m.estimated_cost_saved_usd or 0) for m in metrics)
    total_tokens_saved = sum((m.tokens_saved or 0) for m in metrics)

    return {
        "project_id": str(project_id),
        "period_days": days,
        "summary": {
            "total_hits": total_hits,
            "total_misses": total_misses,
            "overall_hit_rate": total_hits / (total_hits + total_misses) if (total_hits + total_misses) > 0 else 0,
            "tokens_saved": total_tokens_saved,
            "estimated_cost_saved_usd": total_saved,
        },
        "daily_metrics": [
            {
                "date": m.date.strftime("%Y-%m-%d"),
                "hits": m.cache_hits or 0,
                "misses": m.cache_misses or 0,
                "hit_rate": m.hit_rate or 0,
                "tokens_saved": m.tokens_saved or 0,
                "cost_saved_usd": float(m.estimated_cost_saved_usd or 0),
            }
            for m in metrics
        ],
    }


# ============================================================================
# SUMMARY ENDPOINTS
# ============================================================================

@router.get("/{project_id}/summary")
async def get_cost_summary(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get comprehensive cost and performance summary.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    cost_service = CostGovernanceService(db)
    summary = await cost_service.get_project_cost_summary(project_id)

    return {
        "project_id": str(project_id),
        **summary,
    }


@router.get("/{project_id}/estimate")
async def estimate_cost(
    project_id: UUID,
    provider: str,
    prompt_tokens: int = Query(..., ge=1),
    completion_tokens: int = Query(..., ge=1),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Estimate the cost of an LLM call.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        llm_provider = LLMProvider(provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

    cost_service = CostGovernanceService(db)
    estimated_cost = cost_service.estimate_cost(llm_provider, prompt_tokens, completion_tokens)

    return {
        "provider": provider,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "estimated_cost_usd": float(estimated_cost),
    }
