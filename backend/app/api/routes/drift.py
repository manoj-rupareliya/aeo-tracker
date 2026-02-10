"""
Change & Drift Detection API Routes
Track how LLM behavior changes over time
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, User
from app.models.database import LLMProvider, SentimentPolarity
from app.models.models_v2 import ResponseSnapshot, DriftRecord, DriftType, DriftSeverity
from app.services.drift_service import DriftDetectionEngine
from app.utils import get_db
from app.api.middleware.auth import get_current_user

router = APIRouter()


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class SnapshotResponse(BaseModel):
    """Response model for snapshots."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    keyword_id: UUID
    prompt_hash: str
    provider: str
    llm_run_id: Optional[UUID]
    response_hash: str
    brand_mentioned: bool
    brand_position: Optional[int]
    competitor_positions: dict
    citations: list
    sentiment: Optional[str]
    visibility_score: Optional[float]
    snapshot_date: datetime
    is_baseline: bool


class DriftRecordResponse(BaseModel):
    """Response model for drift records."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    keyword_id: Optional[UUID]
    provider: str
    drift_type: str
    severity: str
    previous_value: Optional[str]
    current_value: Optional[str]
    change_description: str
    score_delta: Optional[float]
    position_delta: Optional[int]
    affected_entity: Optional[str]
    related_entities: list
    probable_cause: Optional[str]
    recommended_action: Optional[str]
    is_alerted: bool
    alerted_at: Optional[datetime]
    detected_at: datetime
    baseline_date: datetime
    current_date: datetime


class CreateSnapshotRequest(BaseModel):
    """Request to create a new snapshot."""
    keyword_id: UUID
    prompt_hash: str
    provider: str
    llm_run_id: UUID
    response_hash: str
    brand_mentioned: bool
    brand_position: Optional[int] = None
    competitor_positions: Optional[dict] = None
    citations: Optional[list] = None
    sentiment: Optional[str] = None
    visibility_score: Optional[float] = None


# ============================================================================
# SNAPSHOT ENDPOINTS
# ============================================================================

@router.post("/snapshots/{project_id}", response_model=SnapshotResponse)
async def create_snapshot(
    project_id: UUID,
    request: CreateSnapshotRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Create a new response snapshot for drift comparison.
    Snapshots capture the state of an LLM response at a point in time.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        provider = LLMProvider(request.provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {request.provider}")

    sentiment = None
    if request.sentiment:
        try:
            sentiment = SentimentPolarity(request.sentiment)
        except ValueError:
            pass

    drift_engine = DriftDetectionEngine(db)
    snapshot = await drift_engine.create_snapshot(
        project_id=project_id,
        keyword_id=request.keyword_id,
        prompt_hash=request.prompt_hash,
        provider=provider,
        llm_run_id=request.llm_run_id,
        response_hash=request.response_hash,
        brand_mentioned=request.brand_mentioned,
        brand_position=request.brand_position,
        competitor_positions=request.competitor_positions,
        citations=request.citations,
        sentiment=sentiment,
        visibility_score=request.visibility_score,
    )

    await db.commit()
    return snapshot


@router.get("/snapshots/{project_id}/latest")
async def get_latest_snapshots(
    project_id: UUID,
    keyword_id: Optional[UUID] = Query(None),
    provider: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get the latest snapshots for a project.
    Optionally filter by keyword or provider.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    from sqlalchemy import and_

    query = select(ResponseSnapshot).where(ResponseSnapshot.project_id == project_id)

    if keyword_id:
        query = query.where(ResponseSnapshot.keyword_id == keyword_id)
    if provider:
        try:
            llm_provider = LLMProvider(provider)
            query = query.where(ResponseSnapshot.provider == llm_provider)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")

    query = query.order_by(ResponseSnapshot.snapshot_date.desc()).limit(100)

    result = await db.execute(query)
    snapshots = list(result.scalars().all())

    return [SnapshotResponse.model_validate(s) for s in snapshots]


@router.get("/snapshots/{project_id}/history/{keyword_id}")
async def get_snapshot_history(
    project_id: UUID,
    keyword_id: UUID,
    provider: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get snapshot history for a specific keyword.
    Useful for visualizing changes over time.
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

    drift_engine = DriftDetectionEngine(db)
    snapshots = await drift_engine.get_snapshot_history(
        project_id, keyword_id, llm_provider, days
    )

    return {
        "keyword_id": str(keyword_id),
        "period_days": days,
        "snapshot_count": len(snapshots),
        "snapshots": [SnapshotResponse.model_validate(s) for s in snapshots],
    }


# ============================================================================
# DRIFT DETECTION ENDPOINTS
# ============================================================================

@router.post("/detect/{project_id}")
async def detect_drift_for_snapshot(
    project_id: UUID,
    snapshot_id: UUID,
    baseline_snapshot_id: Optional[UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Run drift detection on a snapshot against baseline.
    Returns all detected changes.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Get the snapshot
    result = await db.execute(
        select(ResponseSnapshot).where(
            ResponseSnapshot.id == snapshot_id,
            ResponseSnapshot.project_id == project_id,
        )
    )
    current_snapshot = result.scalar_one_or_none()
    if not current_snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    # Get baseline if specified
    baseline_snapshot = None
    if baseline_snapshot_id:
        result = await db.execute(
            select(ResponseSnapshot).where(ResponseSnapshot.id == baseline_snapshot_id)
        )
        baseline_snapshot = result.scalar_one_or_none()

    drift_engine = DriftDetectionEngine(db)
    drifts = await drift_engine.detect_drift(current_snapshot, baseline_snapshot)

    await db.commit()

    return {
        "snapshot_id": str(snapshot_id),
        "baseline_snapshot_id": str(baseline_snapshot_id) if baseline_snapshot_id else None,
        "drifts_detected": len(drifts),
        "drifts": [DriftRecordResponse.model_validate(d) for d in drifts],
    }


@router.get("/records/{project_id}")
async def get_drift_records(
    project_id: UUID,
    days: int = Query(7, ge=1, le=90),
    severity: Optional[str] = Query(None),
    drift_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get drift records for a project.
    Filter by severity, type, or time period.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    sev = None
    if severity:
        try:
            sev = DriftSeverity(severity)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")

    dt = None
    if drift_type:
        try:
            dt = DriftType(drift_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid drift type: {drift_type}")

    drift_engine = DriftDetectionEngine(db)
    drifts = await drift_engine.get_recent_drifts(
        project_id, days=days, severity=sev, drift_type=dt, limit=limit
    )

    return {
        "project_id": str(project_id),
        "period_days": days,
        "total_drifts": len(drifts),
        "drifts": [DriftRecordResponse.model_validate(d) for d in drifts],
    }


@router.get("/alerts/{project_id}")
async def get_unalerted_drifts(
    project_id: UUID,
    min_severity: str = Query("moderate"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get drift records that need attention (not yet alerted).
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        sev = DriftSeverity(min_severity)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid severity: {min_severity}")

    drift_engine = DriftDetectionEngine(db)
    drifts = await drift_engine.get_unalerted_drifts(project_id, sev)

    return {
        "project_id": str(project_id),
        "unalerted_count": len(drifts),
        "min_severity": min_severity,
        "drifts": [DriftRecordResponse.model_validate(d) for d in drifts],
    }


@router.post("/alerts/{drift_id}/acknowledge")
async def acknowledge_drift(
    drift_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Mark a drift as acknowledged/alerted.
    """
    # Get drift and verify access
    result = await db.execute(
        select(DriftRecord).where(DriftRecord.id == drift_id)
    )
    drift = result.scalar_one_or_none()
    if not drift:
        raise HTTPException(status_code=404, detail="Drift record not found")

    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == drift.project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Access denied")

    drift_engine = DriftDetectionEngine(db)
    await drift_engine.mark_drift_alerted(drift_id)
    await db.commit()

    return {"status": "acknowledged", "drift_id": str(drift_id)}


@router.get("/summary/{project_id}")
async def get_drift_summary(
    project_id: UUID,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get a summary of drift activity for a project.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    drift_engine = DriftDetectionEngine(db)
    summary = await drift_engine.get_drift_summary(project_id, days)

    return {
        "project_id": str(project_id),
        **summary,
    }


# ============================================================================
# TREND ANALYSIS ENDPOINTS
# ============================================================================

@router.get("/trend/{project_id}/{keyword_id}")
async def get_visibility_trend(
    project_id: UUID,
    keyword_id: UUID,
    provider: Optional[str] = Query(None),
    days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Analyze visibility score trend for a keyword.
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

    drift_engine = DriftDetectionEngine(db)
    trend = await drift_engine.analyze_visibility_trend(
        project_id, keyword_id, llm_provider, days
    )

    return {
        "project_id": str(project_id),
        "keyword_id": str(keyword_id),
        "provider": provider,
        **trend,
    }


@router.get("/timeline/{project_id}")
async def get_drift_timeline(
    project_id: UUID,
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get a timeline of all drift events for visualization.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    drift_engine = DriftDetectionEngine(db)
    drifts = await drift_engine.get_recent_drifts(project_id, days=days, limit=500)

    # Group by date
    from collections import defaultdict
    timeline = defaultdict(list)

    for drift in drifts:
        date_key = drift.detected_at.strftime("%Y-%m-%d")
        timeline[date_key].append({
            "id": str(drift.id),
            "type": drift.drift_type.value,
            "severity": drift.severity.value,
            "provider": drift.provider.value,
            "description": drift.change_description,
            "time": drift.detected_at.isoformat(),
        })

    # Sort dates
    sorted_timeline = [
        {"date": date, "events": events}
        for date, events in sorted(timeline.items())
    ]

    return {
        "project_id": str(project_id),
        "period_days": days,
        "total_events": len(drifts),
        "timeline": sorted_timeline,
    }
