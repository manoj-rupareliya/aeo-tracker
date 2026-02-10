"""
Share of AI Voice (SAIV) API Routes
Quantify brand presence in AI-generated content
"""

from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, User
from app.models.models_v2 import SAIVSnapshot, SAIVBreakdown
from app.services.saiv_service import SAIVEngine
from app.utils import get_db
from app.api.middleware.auth import get_current_user

router = APIRouter()


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class SAIVSnapshotResponse(BaseModel):
    """Response model for SAIV snapshots."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    snapshot_date: datetime
    period_type: str
    overall_saiv: float
    total_brand_mentions: int
    total_entity_mentions: int
    saiv_by_llm: dict
    saiv_by_keyword_cluster: dict
    competitor_saiv: dict
    saiv_delta: Optional[float]
    trend_direction: Optional[str]
    runs_analyzed: int
    calculation_method: str
    created_at: datetime


class SAIVBreakdownResponse(BaseModel):
    """Response model for SAIV breakdowns."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    saiv_snapshot_id: UUID
    dimension_type: str
    dimension_value: str
    saiv_value: float
    brand_mentions: int
    total_mentions: int
    runs_analyzed: int
    created_at: datetime


# ============================================================================
# SAIV CALCULATION ENDPOINTS
# ============================================================================

@router.post("/{project_id}/calculate")
async def calculate_saiv(
    project_id: UUID,
    period_type: str = Query("daily", regex="^(daily|weekly|monthly)$"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Calculate SAIV for a project.

    Formula: SAIV = (Brand Mentions) / (Total Entity Mentions) × 100
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Set default date range based on period type
    now = datetime.utcnow()
    if not end_date:
        end_date = now

    if not start_date:
        if period_type == "daily":
            start_date = end_date.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period_type == "weekly":
            start_date = end_date - timedelta(days=7)
        else:  # monthly
            start_date = end_date - timedelta(days=30)

    saiv_engine = SAIVEngine(db)
    snapshot = await saiv_engine.calculate_saiv(
        project_id, start_date, end_date, period_type
    )

    await db.commit()

    if not snapshot:
        raise HTTPException(status_code=404, detail="No data available for SAIV calculation")

    return SAIVSnapshotResponse.model_validate(snapshot)


@router.get("/{project_id}/current")
async def get_current_saiv(
    project_id: UUID,
    period_type: str = Query("daily", regex="^(daily|weekly|monthly)$"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get the most recent SAIV snapshot.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    saiv_engine = SAIVEngine(db)
    snapshot = await saiv_engine.get_current_saiv(project_id, period_type)

    if not snapshot:
        raise HTTPException(status_code=404, detail="No SAIV data available")

    return SAIVSnapshotResponse.model_validate(snapshot)


@router.get("/{project_id}/history")
async def get_saiv_history(
    project_id: UUID,
    period_type: str = Query("daily", regex="^(daily|weekly|monthly)$"),
    days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get SAIV history for trending and visualization.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    saiv_engine = SAIVEngine(db)
    history = await saiv_engine.get_saiv_history(project_id, period_type, days)

    return {
        "project_id": str(project_id),
        "period_type": period_type,
        "days": days,
        "data_points": len(history),
        "history": [SAIVSnapshotResponse.model_validate(s) for s in history],
    }


# ============================================================================
# SAIV BREAKDOWN ENDPOINTS
# ============================================================================

@router.get("/{project_id}/breakdown/{snapshot_id}")
async def get_saiv_breakdown(
    project_id: UUID,
    snapshot_id: UUID,
    dimension_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get detailed SAIV breakdown by dimension (LLM, keyword, etc.).
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify snapshot belongs to project
    result = await db.execute(
        select(SAIVSnapshot).where(
            SAIVSnapshot.id == snapshot_id,
            SAIVSnapshot.project_id == project_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Snapshot not found")

    saiv_engine = SAIVEngine(db)
    breakdowns = await saiv_engine.get_saiv_breakdown(snapshot_id, dimension_type)

    return {
        "snapshot_id": str(snapshot_id),
        "breakdowns": [SAIVBreakdownResponse.model_validate(b) for b in breakdowns],
    }


@router.get("/{project_id}/by-llm")
async def get_saiv_by_llm(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get current SAIV broken down by LLM provider.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    saiv_engine = SAIVEngine(db)
    snapshot = await saiv_engine.get_current_saiv(project_id, "daily")

    if not snapshot:
        raise HTTPException(status_code=404, detail="No SAIV data available")

    return {
        "project_id": str(project_id),
        "overall_saiv": snapshot.overall_saiv,
        "by_llm": snapshot.saiv_by_llm,
        "snapshot_date": snapshot.snapshot_date.isoformat(),
    }


# ============================================================================
# COMPARISON ENDPOINTS
# ============================================================================

@router.get("/{project_id}/compare")
async def compare_saiv_periods(
    project_id: UUID,
    current_days: int = Query(7, ge=1, le=90),
    previous_days: int = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Compare SAIV between two time periods.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    now = datetime.utcnow()
    current_end = now
    current_start = now - timedelta(days=current_days)
    previous_end = current_start
    previous_start = previous_end - timedelta(days=previous_days)

    saiv_engine = SAIVEngine(db)
    comparison = await saiv_engine.compare_saiv_periods(
        project_id,
        current_start, current_end,
        previous_start, previous_end,
    )

    await db.commit()

    return {
        "project_id": str(project_id),
        **comparison,
    }


@router.get("/{project_id}/vs-competitors")
async def get_saiv_vs_competitors(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get SAIV compared to competitors.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    saiv_engine = SAIVEngine(db)
    snapshot = await saiv_engine.get_current_saiv(project_id, "daily")

    if not snapshot:
        raise HTTPException(status_code=404, detail="No SAIV data available")

    # Sort competitors by SAIV
    sorted_competitors = sorted(
        snapshot.competitor_saiv.items(),
        key=lambda x: x[1],
        reverse=True
    )

    # Calculate rank
    all_brands = [("Your Brand", snapshot.overall_saiv)] + sorted_competitors
    all_brands.sort(key=lambda x: x[1], reverse=True)
    your_rank = next(
        (i + 1 for i, (name, _) in enumerate(all_brands) if name == "Your Brand"),
        None
    )

    return {
        "project_id": str(project_id),
        "your_saiv": snapshot.overall_saiv,
        "your_rank": your_rank,
        "total_tracked": len(all_brands),
        "competitors": [
            {"name": name, "saiv": saiv}
            for name, saiv in sorted_competitors
        ],
        "snapshot_date": snapshot.snapshot_date.isoformat(),
    }


# ============================================================================
# INSIGHTS ENDPOINTS
# ============================================================================

@router.get("/{project_id}/insights")
async def get_saiv_insights(
    project_id: UUID,
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get insights and analysis from SAIV data.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    saiv_engine = SAIVEngine(db)
    insights = await saiv_engine.get_saiv_insights(project_id, days)

    return {
        "project_id": str(project_id),
        **insights,
    }


@router.get("/{project_id}/trend")
async def get_saiv_trend(
    project_id: UUID,
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get SAIV trend data for charting.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    saiv_engine = SAIVEngine(db)
    history = await saiv_engine.get_saiv_history(project_id, "daily", days)

    if not history:
        return {
            "project_id": str(project_id),
            "trend_data": [],
            "summary": None,
        }

    trend_data = [
        {
            "date": s.snapshot_date.strftime("%Y-%m-%d"),
            "saiv": s.overall_saiv,
            "mentions": s.total_brand_mentions,
            "trend": s.trend_direction,
        }
        for s in history
    ]

    # Calculate summary
    saiv_values = [s.overall_saiv for s in history]
    first_value = saiv_values[0] if saiv_values else 0
    last_value = saiv_values[-1] if saiv_values else 0

    return {
        "project_id": str(project_id),
        "days": days,
        "data_points": len(trend_data),
        "trend_data": trend_data,
        "summary": {
            "start_saiv": first_value,
            "end_saiv": last_value,
            "change": last_value - first_value,
            "change_percent": ((last_value - first_value) / first_value * 100)
            if first_value > 0 else 0,
            "average": sum(saiv_values) / len(saiv_values) if saiv_values else 0,
        },
    }


# ============================================================================
# QUICK CALCULATION ENDPOINTS
# ============================================================================

@router.post("/{project_id}/calculate/today")
async def calculate_saiv_today(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Calculate SAIV for today.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    saiv_engine = SAIVEngine(db)
    snapshot = await saiv_engine.calculate_saiv_for_today(project_id)

    await db.commit()

    if not snapshot:
        raise HTTPException(status_code=404, detail="No data available for today")

    return SAIVSnapshotResponse.model_validate(snapshot)


@router.post("/{project_id}/calculate/week")
async def calculate_saiv_week(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Calculate SAIV for current week.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    saiv_engine = SAIVEngine(db)
    snapshot = await saiv_engine.calculate_saiv_for_week(project_id)

    await db.commit()

    if not snapshot:
        raise HTTPException(status_code=404, detail="No data available for this week")

    return SAIVSnapshotResponse.model_validate(snapshot)


@router.post("/{project_id}/calculate/month")
async def calculate_saiv_month(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Calculate SAIV for current month.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    saiv_engine = SAIVEngine(db)
    snapshot = await saiv_engine.calculate_saiv_for_month(project_id)

    await db.commit()

    if not snapshot:
        raise HTTPException(status_code=404, detail="No data available for this month")

    return SAIVSnapshotResponse.model_validate(snapshot)
