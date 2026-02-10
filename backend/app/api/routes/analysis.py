"""
Analysis & Scoring Routes
"""

from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Project, VisibilityScore, AggregatedScore, BrandMention,
    Citation, CitationSource, LLMRun, User
)
from app.schemas.analysis import (
    VisibilityScoreResponse, AggregatedScoreResponse,
    SourceCitationStats, AnalysisReport
)
from app.utils import get_db
from app.api.middleware.auth import get_current_user

router = APIRouter()


@router.get("/{project_id}/scores")
async def get_visibility_scores(
    project_id: UUID,
    keyword_id: Optional[UUID] = Query(None),
    provider: Optional[str] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get visibility scores for a project"""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Build query
    query = select(VisibilityScore).where(VisibilityScore.project_id == project_id)

    if keyword_id:
        query = query.where(VisibilityScore.keyword_id == keyword_id)
    if provider:
        query = query.where(VisibilityScore.provider == provider)
    if start_date:
        query = query.where(VisibilityScore.score_date >= start_date)
    if end_date:
        query = query.where(VisibilityScore.score_date <= end_date)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    result = await db.execute(count_query)
    total = result.scalar()

    # Get scores
    result = await db.execute(
        query
        .order_by(VisibilityScore.score_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    scores = result.scalars().all()

    return {
        "items": [VisibilityScoreResponse.model_validate(s) for s in scores],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/{project_id}/aggregated")
async def get_aggregated_scores(
    project_id: UUID,
    period_type: str = Query("daily", regex="^(daily|weekly|monthly)$"),
    limit: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get aggregated scores for trending"""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(AggregatedScore)
        .where(
            AggregatedScore.project_id == project_id,
            AggregatedScore.period_type == period_type
        )
        .order_by(AggregatedScore.period_start.desc())
        .limit(limit)
    )
    scores = result.scalars().all()

    return [AggregatedScoreResponse.model_validate(s) for s in scores]


@router.get("/{project_id}/mentions")
async def get_brand_mentions(
    project_id: UUID,
    is_own_brand: Optional[bool] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get brand mentions for a project"""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Build query with joins
    from app.models import LLMResponse

    query = (
        select(BrandMention)
        .join(LLMResponse)
        .join(LLMRun)
        .where(LLMRun.project_id == project_id)
    )

    if is_own_brand is not None:
        query = query.where(BrandMention.is_own_brand == is_own_brand)
    if start_date:
        query = query.where(BrandMention.created_at >= start_date)
    if end_date:
        query = query.where(BrandMention.created_at <= end_date)

    result = await db.execute(
        query
        .order_by(BrandMention.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    mentions = result.scalars().all()

    from app.schemas.analysis import BrandMentionResponse
    return [BrandMentionResponse.model_validate(m) for m in mentions]


@router.get("/{project_id}/citations")
async def get_citations(
    project_id: UUID,
    is_hallucinated: Optional[bool] = Query(None),
    source_category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get citations for a project"""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    from app.models import LLMResponse

    query = (
        select(Citation)
        .join(LLMResponse)
        .join(LLMRun)
        .where(LLMRun.project_id == project_id)
    )

    if is_hallucinated is not None:
        query = query.where(Citation.is_hallucinated == is_hallucinated)
    if source_category:
        query = query.join(CitationSource).where(CitationSource.category == source_category)

    result = await db.execute(
        query
        .order_by(Citation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    citations = result.scalars().all()

    from app.schemas.analysis import CitationResponse
    return [CitationResponse.model_validate(c) for c in citations]


@router.get("/{project_id}/sources")
async def get_citation_sources(
    project_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get top citation sources for a project"""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    from app.models import LLMResponse

    # Get source citation counts for this project
    result = await db.execute(
        select(
            CitationSource,
            func.count(Citation.id).label("citation_count")
        )
        .join(Citation)
        .join(LLMResponse)
        .join(LLMRun)
        .where(LLMRun.project_id == project_id)
        .group_by(CitationSource.id)
        .order_by(func.count(Citation.id).desc())
        .limit(limit)
    )
    sources = result.all()

    return [
        {
            "source": {
                "id": s[0].id,
                "domain": s[0].domain,
                "category": s[0].category.value if s[0].category else None,
                "site_name": s[0].site_name,
            },
            "citation_count": s[1],
        }
        for s in sources
    ]


@router.get("/{project_id}/report")
async def get_analysis_report(
    project_id: UUID,
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get comprehensive analysis report for a project"""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Get overall metrics
    result = await db.execute(
        select(
            func.count(LLMRun.id).label("total_runs"),
            func.avg(VisibilityScore.total_score).label("avg_score")
        )
        .join(VisibilityScore, VisibilityScore.llm_run_id == LLMRun.id, isouter=True)
        .where(
            LLMRun.project_id == project_id,
            LLMRun.created_at >= start_date,
            LLMRun.created_at <= end_date
        )
    )
    metrics = result.one()

    # Get mention count
    from app.models import LLMResponse
    result = await db.execute(
        select(func.count(BrandMention.id))
        .join(LLMResponse)
        .join(LLMRun)
        .where(
            LLMRun.project_id == project_id,
            BrandMention.is_own_brand == True,
            LLMRun.created_at >= start_date
        )
    )
    total_mentions = result.scalar()

    # Get citation count
    result = await db.execute(
        select(func.count(Citation.id))
        .join(LLMResponse)
        .join(LLMRun)
        .where(
            LLMRun.project_id == project_id,
            LLMRun.created_at >= start_date
        )
    )
    total_citations = result.scalar()

    # Scores by LLM
    result = await db.execute(
        select(
            VisibilityScore.provider,
            func.avg(VisibilityScore.total_score)
        )
        .where(
            VisibilityScore.project_id == project_id,
            VisibilityScore.score_date >= start_date
        )
        .group_by(VisibilityScore.provider)
    )
    scores_by_llm = {str(row[0].value): float(row[1]) for row in result.all() if row[0]}

    return {
        "project_id": project_id,
        "period_start": start_date,
        "period_end": end_date,
        "total_runs": metrics[0] or 0,
        "total_mentions": total_mentions or 0,
        "total_citations": total_citations or 0,
        "avg_visibility_score": float(metrics[1]) if metrics[1] else 0,
        "scores_by_llm": scores_by_llm,
    }
