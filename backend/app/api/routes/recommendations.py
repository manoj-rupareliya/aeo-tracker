"""
GEO Recommendation API Routes
Actionable, evidence-based recommendations for improving LLM visibility
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, User
from app.models.database import LLMProvider
from app.models.models_v2 import (
    GEORecommendation, GapAnalysis, RecommendationType, ConfidenceLevel
)
from app.services.recommendation_service import GEORecommendationEngine
from app.utils import get_db
from app.api.middleware.auth import get_current_user

router = APIRouter()


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class GEORecommendationResponse(BaseModel):
    """Response model for GEO recommendations."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    recommendation_type: str
    target_keyword_id: Optional[UUID]
    target_provider: Optional[str]
    title: str
    description: str
    action_items: list
    evidence_summary: str
    supporting_data: dict
    target_sources: list
    competitor_context: dict
    priority_score: float
    confidence: str
    confidence_score: float
    potential_visibility_gain: Optional[float]
    effort_level: Optional[str]
    is_dismissed: bool
    is_completed: bool
    completed_at: Optional[datetime]
    valid_until: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class GapAnalysisResponse(BaseModel):
    """Response model for gap analysis."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    keyword_id: UUID
    provider: Optional[str]
    analysis_date: datetime
    brand_absent_rate: float
    competitor_present_rate: Optional[float]
    sources_cited_when_absent: dict
    opportunity_score: Optional[float]
    suggested_actions: list
    created_at: datetime


# ============================================================================
# RECOMMENDATION ENDPOINTS
# ============================================================================

@router.get("/{project_id}")
async def get_recommendations(
    project_id: UUID,
    recommendation_type: Optional[str] = Query(None),
    include_dismissed: bool = Query(False),
    include_completed: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get GEO recommendations for a project.
    Filter by type, or include dismissed/completed recommendations.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    rec_type = None
    if recommendation_type:
        try:
            rec_type = RecommendationType(recommendation_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid type: {recommendation_type}")

    rec_engine = GEORecommendationEngine(db)
    recommendations = await rec_engine.get_recommendations(
        project_id,
        recommendation_type=rec_type,
        include_dismissed=include_dismissed,
        include_completed=include_completed,
        limit=limit,
    )

    return {
        "project_id": str(project_id),
        "total": len(recommendations),
        "recommendations": [
            GEORecommendationResponse.model_validate(r) for r in recommendations
        ],
    }


@router.post("/{project_id}/generate")
async def generate_recommendations(
    project_id: UUID,
    days: int = Query(30, ge=7, le=90),
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Generate new recommendations based on current data.
    Analyzes gaps, sources, and competitors.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    rec_engine = GEORecommendationEngine(db)
    recommendations = await rec_engine.generate_recommendations(
        project_id, days=days, limit=limit
    )

    await db.commit()

    return {
        "project_id": str(project_id),
        "generated": len(recommendations),
        "analysis_period_days": days,
        "recommendations": [
            GEORecommendationResponse.model_validate(r) for r in recommendations
        ],
    }


@router.get("/{project_id}/summary")
async def get_recommendation_summary(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get a summary of recommendations for a project.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    rec_engine = GEORecommendationEngine(db)
    summary = await rec_engine.get_recommendation_summary(project_id)

    return {
        "project_id": str(project_id),
        **summary,
    }


@router.post("/{recommendation_id}/dismiss")
async def dismiss_recommendation(
    recommendation_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Dismiss a recommendation (won't show again).
    """
    # Get recommendation and verify access
    result = await db.execute(
        select(GEORecommendation).where(GEORecommendation.id == recommendation_id)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == rec.project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Access denied")

    rec_engine = GEORecommendationEngine(db)
    await rec_engine.dismiss_recommendation(recommendation_id)
    await db.commit()

    return {"status": "dismissed", "recommendation_id": str(recommendation_id)}


@router.post("/{recommendation_id}/complete")
async def complete_recommendation(
    recommendation_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Mark a recommendation as completed.
    """
    # Get recommendation and verify access
    result = await db.execute(
        select(GEORecommendation).where(GEORecommendation.id == recommendation_id)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == rec.project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Access denied")

    rec_engine = GEORecommendationEngine(db)
    await rec_engine.complete_recommendation(recommendation_id)
    await db.commit()

    return {"status": "completed", "recommendation_id": str(recommendation_id)}


# ============================================================================
# GAP ANALYSIS ENDPOINTS
# ============================================================================

@router.get("/{project_id}/gaps")
async def get_gap_analyses(
    project_id: UUID,
    keyword_id: Optional[UUID] = Query(None),
    provider: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get gap analyses for a project.
    Shows where the brand is absent.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    from sqlalchemy import and_

    query = select(GapAnalysis).where(GapAnalysis.project_id == project_id)

    if keyword_id:
        query = query.where(GapAnalysis.keyword_id == keyword_id)

    if provider:
        try:
            llm_provider = LLMProvider(provider)
            query = query.where(GapAnalysis.provider == llm_provider)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

    query = query.order_by(GapAnalysis.analysis_date.desc()).limit(limit)

    result = await db.execute(query)
    gaps = list(result.scalars().all())

    return {
        "project_id": str(project_id),
        "total": len(gaps),
        "gaps": [GapAnalysisResponse.model_validate(g) for g in gaps],
    }


@router.post("/{project_id}/gaps/{keyword_id}/analyze")
async def analyze_keyword_gap(
    project_id: UUID,
    keyword_id: UUID,
    provider: Optional[str] = Query(None),
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Analyze gap for a specific keyword.
    Returns detailed analysis of where brand is absent.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    llm_provider = None
    if provider:
        try:
            llm_provider = LLMProvider(provider)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

    rec_engine = GEORecommendationEngine(db)
    gap = await rec_engine.analyze_keyword_gap(
        project_id, keyword_id, llm_provider, days
    )

    await db.commit()

    if not gap:
        raise HTTPException(status_code=404, detail="No data available for analysis")

    return GapAnalysisResponse.model_validate(gap)


# ============================================================================
# EVIDENCE ENDPOINTS
# ============================================================================

@router.get("/{recommendation_id}/evidence")
async def get_recommendation_evidence(
    recommendation_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get detailed evidence supporting a recommendation.
    Shows the data that led to this recommendation.
    """
    # Get recommendation
    result = await db.execute(
        select(GEORecommendation).where(GEORecommendation.id == recommendation_id)
    )
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == rec.project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Access denied")

    return {
        "recommendation_id": str(recommendation_id),
        "title": rec.title,
        "type": rec.recommendation_type.value,
        "evidence": {
            "summary": rec.evidence_summary,
            "supporting_data": rec.supporting_data,
            "target_sources": rec.target_sources,
            "competitor_context": rec.competitor_context,
        },
        "confidence": {
            "level": rec.confidence.value,
            "score": rec.confidence_score,
        },
        "generated_at": rec.created_at.isoformat(),
        "valid_until": rec.valid_until.isoformat() if rec.valid_until else None,
    }


@router.get("/{project_id}/actionable")
async def get_top_actionable_recommendations(
    project_id: UUID,
    limit: int = Query(5, ge=1, le=20),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get top actionable recommendations sorted by priority and effort.
    Best for quick wins and high-impact actions.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    rec_engine = GEORecommendationEngine(db)
    recommendations = await rec_engine.get_recommendations(project_id, limit=50)

    # Sort by priority / effort ratio (quick wins first)
    effort_weights = {"low": 1, "medium": 2, "high": 3}

    def sort_key(r):
        effort = effort_weights.get(r.effort_level, 2)
        return r.priority_score / effort

    sorted_recs = sorted(recommendations, key=sort_key, reverse=True)[:limit]

    return {
        "project_id": str(project_id),
        "recommendations": [
            {
                "id": str(r.id),
                "title": r.title,
                "type": r.recommendation_type.value,
                "priority_score": r.priority_score,
                "effort_level": r.effort_level,
                "confidence": r.confidence.value,
                "action_items": r.action_items[:3],  # Top 3 actions
                "target_sources": r.target_sources[:3],  # Top 3 sources
            }
            for r in sorted_recs
        ],
    }
