"""
Dashboard Routes
"""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Project, VisibilityScore, AggregatedScore, LLMRun, LLMRunStatus,
    Keyword, BrandMention, Citation, User, LLMProvider
)
from app.schemas.dashboard import (
    DashboardOverview, DashboardMetric, LLMBreakdown, LLMScoreData,
    KeywordBreakdown, KeywordScoreData, CompetitorComparison,
    SourceLeaderboard, TimeSeriesData, TimeSeriesPoint
)
from app.utils import get_db
from app.api.middleware.auth import get_current_user
from app.config import LLM_MARKET_WEIGHTS

router = APIRouter()


@router.get("/{project_id}/overview", response_model=DashboardOverview)
async def get_dashboard_overview(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get dashboard overview for a project"""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    # Current period scores
    result = await db.execute(
        select(func.avg(VisibilityScore.total_score))
        .where(
            VisibilityScore.project_id == project_id,
            VisibilityScore.score_date >= week_ago
        )
    )
    current_score = result.scalar() or 0

    # Previous period scores
    result = await db.execute(
        select(func.avg(VisibilityScore.total_score))
        .where(
            VisibilityScore.project_id == project_id,
            VisibilityScore.score_date >= two_weeks_ago,
            VisibilityScore.score_date < week_ago
        )
    )
    prev_score = result.scalar() or 0

    score_delta = current_score - prev_score if prev_score else 0
    score_trend = "up" if score_delta > 0 else "down" if score_delta < 0 else "stable"

    # Mention rate
    from app.models import LLMResponse
    result = await db.execute(
        select(func.count(LLMRun.id))
        .where(
            LLMRun.project_id == project_id,
            LLMRun.status == LLMRunStatus.COMPLETED,
            LLMRun.completed_at >= week_ago
        )
    )
    total_runs = result.scalar() or 0

    result = await db.execute(
        select(func.count(func.distinct(BrandMention.response_id)))
        .join(LLMResponse)
        .join(LLMRun)
        .where(
            LLMRun.project_id == project_id,
            BrandMention.is_own_brand == True,
            LLMRun.completed_at >= week_ago
        )
    )
    runs_with_mentions = result.scalar() or 0
    mention_rate = (runs_with_mentions / total_runs * 100) if total_runs > 0 else 0

    # Citation rate
    result = await db.execute(
        select(func.count(func.distinct(Citation.response_id)))
        .join(LLMResponse)
        .join(LLMRun)
        .where(
            LLMRun.project_id == project_id,
            LLMRun.completed_at >= week_ago
        )
    )
    runs_with_citations = result.scalar() or 0
    citation_rate = (runs_with_citations / total_runs * 100) if total_runs > 0 else 0

    # Top 3 rate
    result = await db.execute(
        select(func.count(func.distinct(BrandMention.response_id)))
        .join(LLMResponse)
        .join(LLMRun)
        .where(
            LLMRun.project_id == project_id,
            BrandMention.is_own_brand == True,
            BrandMention.mention_position <= 3,
            LLMRun.completed_at >= week_ago
        )
    )
    top3_count = result.scalar() or 0
    top3_rate = (top3_count / total_runs * 100) if total_runs > 0 else 0

    # Keyword count
    result = await db.execute(
        select(func.count(Keyword.id))
        .where(Keyword.project_id == project_id, Keyword.is_active == True)
    )
    keyword_count = result.scalar() or 0

    # Pending/failed runs
    result = await db.execute(
        select(func.count(LLMRun.id))
        .where(LLMRun.project_id == project_id, LLMRun.status == LLMRunStatus.PENDING)
    )
    pending_runs = result.scalar() or 0

    result = await db.execute(
        select(func.count(LLMRun.id))
        .where(
            LLMRun.project_id == project_id,
            LLMRun.status == LLMRunStatus.FAILED,
            LLMRun.created_at >= week_ago
        )
    )
    failed_runs = result.scalar() or 0

    return DashboardOverview(
        project_id=project_id,
        project_name=project.name,
        last_updated=now,
        visibility_score=DashboardMetric(
            label="Visibility Score",
            value=current_score,
            format="score",
            trend=score_trend,
            trend_delta=score_delta,
            trend_period="vs last week",
        ),
        mention_rate=DashboardMetric(
            label="Mention Rate",
            value=mention_rate,
            format="percent",
            trend="stable",
            trend_delta=None,
            trend_period="vs last week",
        ),
        citation_rate=DashboardMetric(
            label="Citation Rate",
            value=citation_rate,
            format="percent",
            trend="stable",
            trend_delta=None,
            trend_period="vs last week",
        ),
        top3_rate=DashboardMetric(
            label="Top 3 Rate",
            value=top3_rate,
            format="percent",
            trend="stable",
            trend_delta=None,
            trend_period="vs last week",
        ),
        total_keywords=keyword_count,
        total_runs_this_period=total_runs,
        active_llms=project.enabled_llms,
        best_keyword=None,
        worst_keyword=None,
        best_llm=None,
        worst_llm=None,
        recent_runs=total_runs,
        pending_runs=pending_runs,
        failed_runs=failed_runs,
    )


@router.get("/{project_id}/llm-breakdown", response_model=LLMBreakdown)
async def get_llm_breakdown(
    project_id: UUID,
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get visibility breakdown by LLM provider"""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Get scores by provider
    result = await db.execute(
        select(
            VisibilityScore.provider,
            func.avg(VisibilityScore.total_score),
            func.avg(VisibilityScore.mention_score),
            func.count(VisibilityScore.id)
        )
        .where(
            VisibilityScore.project_id == project_id,
            VisibilityScore.score_date >= start_date
        )
        .group_by(VisibilityScore.provider)
    )
    provider_data = result.all()

    llms = []
    overall_total = 0
    overall_count = 0

    provider_names = {
        "openai": "ChatGPT",
        "anthropic": "Claude",
        "google": "Gemini",
        "perplexity": "Perplexity",
    }

    for row in provider_data:
        provider, avg_score, avg_mention, count = row
        if provider is None:
            continue

        provider_value = provider.value if hasattr(provider, 'value') else str(provider)
        avg_score = float(avg_score) if avg_score else 0

        llms.append(LLMScoreData(
            provider=provider_value,
            display_name=provider_names.get(provider_value, provider_value),
            avg_score=avg_score,
            mention_rate=float(avg_mention) if avg_mention else 0,
            top3_rate=0,  # Would need additional query
            citation_rate=0,
            total_runs=count,
            trend="stable",
            trend_delta=None,
        ))

        overall_total += avg_score * count
        overall_count += count

    overall_avg = overall_total / overall_count if overall_count > 0 else 0

    return LLMBreakdown(
        project_id=project_id,
        period_start=start_date,
        period_end=end_date,
        llms=llms,
        overall_avg=overall_avg,
    )


@router.get("/{project_id}/keyword-breakdown", response_model=KeywordBreakdown)
async def get_keyword_breakdown(
    project_id: UUID,
    days: int = Query(30, ge=7, le=90),
    limit: int = Query(20, ge=5, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get visibility breakdown by keyword"""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Get scores by keyword
    result = await db.execute(
        select(
            Keyword.id,
            Keyword.keyword,
            func.avg(VisibilityScore.total_score),
            func.count(VisibilityScore.id)
        )
        .join(VisibilityScore, VisibilityScore.keyword_id == Keyword.id)
        .where(
            Keyword.project_id == project_id,
            VisibilityScore.score_date >= start_date
        )
        .group_by(Keyword.id, Keyword.keyword)
        .order_by(func.avg(VisibilityScore.total_score).desc())
        .limit(limit)
    )
    keyword_data = result.all()

    keywords = []
    for row in keyword_data:
        keyword_id, keyword_text, avg_score, run_count = row
        keywords.append(KeywordScoreData(
            keyword_id=keyword_id,
            keyword=keyword_text,
            avg_score=float(avg_score) if avg_score else 0,
            mention_rate=0,
            top3_rate=0,
            best_llm="",
            worst_llm="",
            run_count=run_count,
            last_run_at=None,
        ))

    # Get top/bottom performers
    sorted_keywords = sorted(keywords, key=lambda k: k.avg_score, reverse=True)
    top_performing = [k.keyword for k in sorted_keywords[:5]]
    bottom_performing = [k.keyword for k in sorted_keywords[-5:]] if len(sorted_keywords) >= 5 else []

    return KeywordBreakdown(
        project_id=project_id,
        period_start=start_date,
        period_end=end_date,
        keywords=keywords,
        top_performing=top_performing,
        bottom_performing=bottom_performing,
    )


@router.get("/{project_id}/time-series")
async def get_time_series(
    project_id: UUID,
    metric: str = Query("visibility_score"),
    granularity: str = Query("daily", regex="^(daily|weekly)$"),
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get time series data for charts"""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Get aggregated scores
    result = await db.execute(
        select(AggregatedScore)
        .where(
            AggregatedScore.project_id == project_id,
            AggregatedScore.period_type == granularity,
            AggregatedScore.period_start >= start_date
        )
        .order_by(AggregatedScore.period_start)
    )
    aggregated = result.scalars().all()

    series = []
    for agg in aggregated:
        value = getattr(agg, f"avg_{metric}", agg.avg_visibility_score)
        series.append(TimeSeriesPoint(
            date=agg.period_start,
            value=float(value) if value else 0,
        ))

    return TimeSeriesData(
        project_id=project_id,
        metric=metric,
        granularity=granularity,
        series=series,
    )
