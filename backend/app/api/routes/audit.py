"""
Trust & Audit Layer API Routes
Provides complete provenance and auditability for all LLM insights
"""

from datetime import datetime
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Project, User
from app.models.models_v2 import ExecutionLog, ResponseArchive, ParseLineage, InsightConfidence
from app.services.audit_service import AuditService
from app.utils import get_db
from app.api.middleware.auth import get_current_user

router = APIRouter()


# ============================================================================
# RESPONSE SCHEMAS
# ============================================================================

class ExecutionLogResponse(BaseModel):
    """Response model for execution logs."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    llm_run_id: UUID
    project_id: UUID
    prompt_hash: str
    template_version: Optional[str]
    provider: str
    model_name: str
    temperature: float
    max_tokens: int
    execution_started_at: datetime
    execution_completed_at: Optional[datetime]
    execution_duration_ms: Optional[int]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    estimated_cost_usd: Optional[float]
    was_cached: bool
    had_error: bool
    error_type: Optional[str]
    triggered_by: Optional[str]
    created_at: datetime


class RawResponseResponse(BaseModel):
    """Response model for archived raw responses."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    llm_run_id: UUID
    raw_response_text: str
    response_hash: str
    content_length: int
    word_count: Optional[int]
    finish_reason: Optional[str]
    archived_at: datetime


class ParseLineageResponse(BaseModel):
    """Response model for parse lineage records."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    response_archive_id: UUID
    entity_type: str
    entity_id: Optional[UUID]
    entity_value: str
    extraction_method: str
    extraction_pattern: Optional[str]
    extraction_version: Optional[str]
    start_offset: Optional[int]
    end_offset: Optional[int]
    context_before: Optional[str]
    context_after: Optional[str]
    confidence: float
    confidence_factors: dict
    extracted_at: datetime


class InsightConfidenceResponse(BaseModel):
    """Response model for insight confidence records."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    insight_type: str
    insight_id: UUID
    confidence_level: str
    confidence_score: float
    data_completeness: Optional[float]
    consistency_score: Optional[float]
    sample_size: Optional[int]
    recency_factor: Optional[float]
    confidence_explanation: dict
    caveats: list
    requires_more_data: bool
    created_at: datetime


class FullAuditTrailResponse(BaseModel):
    """Complete audit trail for an LLM run."""
    execution: dict
    raw_response: dict
    parsed_entities: list
    extraction_summary: dict


# ============================================================================
# AUDIT ENDPOINTS
# ============================================================================

@router.get("/{run_id}/raw", response_model=RawResponseResponse)
async def get_raw_response(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get the raw, unmodified LLM response for an execution.
    This is the immutable source of truth.
    """
    audit_service = AuditService(db)
    archive = await audit_service.get_archived_response(run_id)

    if not archive:
        raise HTTPException(status_code=404, detail="Raw response not found")

    # Verify user has access to this run's project
    exec_result = await db.execute(
        select(ExecutionLog).where(ExecutionLog.llm_run_id == run_id)
    )
    exec_log = exec_result.scalar_one_or_none()

    if exec_log:
        project_result = await db.execute(
            select(Project).where(
                Project.id == exec_log.project_id,
                Project.owner_id == user.id
            )
        )
        if not project_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Access denied")

    return archive


@router.get("/{run_id}/parsed")
async def get_parsed_entities(
    run_id: UUID,
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get all entities parsed from an LLM response.
    Shows what was extracted and how confident we are.
    """
    audit_service = AuditService(db)
    archive = await audit_service.get_archived_response(run_id)

    if not archive:
        raise HTTPException(status_code=404, detail="Response archive not found")

    # Verify access
    exec_result = await db.execute(
        select(ExecutionLog).where(ExecutionLog.llm_run_id == run_id)
    )
    exec_log = exec_result.scalar_one_or_none()

    if exec_log:
        project_result = await db.execute(
            select(Project).where(
                Project.id == exec_log.project_id,
                Project.owner_id == user.id
            )
        )
        if not project_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Access denied")

    # Get lineage records
    lineage = await audit_service.get_lineage_for_response(archive.id)

    # Filter by entity type if specified
    if entity_type:
        lineage = [l for l in lineage if l.entity_type == entity_type]

    return {
        "run_id": run_id,
        "response_hash": archive.response_hash,
        "total_entities": len(lineage),
        "entities": [ParseLineageResponse.model_validate(l) for l in lineage],
    }


@router.get("/{run_id}/lineage")
async def get_extraction_lineage(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get the complete extraction methodology for an LLM response.
    Shows exactly how each piece of data was extracted.
    """
    audit_service = AuditService(db)
    archive = await audit_service.get_archived_response(run_id)

    if not archive:
        raise HTTPException(status_code=404, detail="Response archive not found")

    lineage = await audit_service.get_lineage_for_response(archive.id)

    # Group by extraction method
    by_method = {}
    for l in lineage:
        method = l.extraction_method
        if method not in by_method:
            by_method[method] = []
        by_method[method].append({
            "entity_type": l.entity_type,
            "entity_value": l.entity_value,
            "pattern": l.extraction_pattern,
            "version": l.extraction_version,
            "confidence": l.confidence,
            "position": {"start": l.start_offset, "end": l.end_offset}
            if l.start_offset is not None else None,
        })

    return {
        "run_id": run_id,
        "response_hash": archive.response_hash,
        "raw_text_preview": archive.raw_response_text[:500] + "..."
        if len(archive.raw_response_text) > 500 else archive.raw_response_text,
        "extraction_methods_used": list(by_method.keys()),
        "lineage_by_method": by_method,
        "total_extractions": len(lineage),
        "avg_confidence": sum(l.confidence for l in lineage) / len(lineage)
        if lineage else None,
    }


@router.get("/{run_id}/confidence")
async def get_confidence_breakdown(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get confidence scores and breakdown for insights from this run.
    Explains how certain we are about each derived insight.
    """
    audit_service = AuditService(db)

    # Get execution log to find project
    exec_result = await db.execute(
        select(ExecutionLog).where(ExecutionLog.llm_run_id == run_id)
    )
    exec_log = exec_result.scalar_one_or_none()

    if not exec_log:
        raise HTTPException(status_code=404, detail="Execution log not found")

    # Verify access
    project_result = await db.execute(
        select(Project).where(
            Project.id == exec_log.project_id,
            Project.owner_id == user.id
        )
    )
    if not project_result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Access denied")

    # Get all confidence records for insights related to this run
    result = await db.execute(
        select(InsightConfidence).where(
            InsightConfidence.project_id == exec_log.project_id
        ).order_by(InsightConfidence.created_at.desc()).limit(50)
    )
    confidences = list(result.scalars().all())

    # Get lineage for confidence from parsed entities
    archive = await audit_service.get_archived_response(run_id)
    entity_confidences = []
    if archive:
        lineage = await audit_service.get_lineage_for_response(archive.id)
        entity_confidences = [
            {
                "entity_type": l.entity_type,
                "entity_value": l.entity_value,
                "confidence": l.confidence,
                "factors": l.confidence_factors,
            }
            for l in lineage
        ]

    return {
        "run_id": run_id,
        "entity_confidences": entity_confidences,
        "insight_confidences": [
            InsightConfidenceResponse.model_validate(c) for c in confidences
        ],
        "summary": {
            "total_entities": len(entity_confidences),
            "avg_entity_confidence": sum(e["confidence"] for e in entity_confidences)
            / len(entity_confidences) if entity_confidences else None,
            "high_confidence_count": len([e for e in entity_confidences if e["confidence"] >= 0.9]),
            "low_confidence_count": len([e for e in entity_confidences if e["confidence"] < 0.5]),
        },
    }


@router.get("/{run_id}/full", response_model=FullAuditTrailResponse)
async def get_full_audit_trail(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get the complete audit trail for an LLM run.
    Provides full provenance: raw → parsed → insight.
    """
    audit_service = AuditService(db)

    # Verify access first
    exec_result = await db.execute(
        select(ExecutionLog).where(ExecutionLog.llm_run_id == run_id)
    )
    exec_log = exec_result.scalar_one_or_none()

    if exec_log:
        project_result = await db.execute(
            select(Project).where(
                Project.id == exec_log.project_id,
                Project.owner_id == user.id
            )
        )
        if not project_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Access denied")

    trail = await audit_service.get_full_audit_trail(run_id)

    if not trail["execution"]["id"] and not trail["raw_response"]["id"]:
        raise HTTPException(status_code=404, detail="No audit trail found for this run")

    return trail


# ============================================================================
# PROJECT-LEVEL AUDIT ENDPOINTS
# ============================================================================

@router.get("/project/{project_id}/executions")
async def get_project_executions(
    project_id: UUID,
    include_errors: bool = Query(True, description="Include failed executions"),
    include_cached: bool = Query(True, description="Include cached responses"),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get all execution logs for a project.
    Provides audit trail of all LLM calls made.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    audit_service = AuditService(db)
    logs = await audit_service.get_execution_logs_for_project(
        project_id,
        limit=page_size,
        offset=(page - 1) * page_size,
        include_errors=include_errors,
    )

    # Filter cached if needed
    if not include_cached:
        logs = [l for l in logs if not l.was_cached]

    return {
        "items": [ExecutionLogResponse.model_validate(log) for log in logs],
        "page": page,
        "page_size": page_size,
    }


@router.get("/project/{project_id}/cost-summary")
async def get_project_cost_summary(
    project_id: UUID,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get cost summary for a project based on execution logs.
    """
    from sqlalchemy import func
    from datetime import timedelta

    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    start_date = datetime.utcnow() - timedelta(days=days)

    # Get aggregate metrics
    result = await db.execute(
        select(
            func.count(ExecutionLog.id).label("total_executions"),
            func.sum(ExecutionLog.total_tokens).label("total_tokens"),
            func.sum(ExecutionLog.estimated_cost_usd).label("total_cost"),
            func.count().filter(ExecutionLog.was_cached == True).label("cache_hits"),
            func.count().filter(ExecutionLog.had_error == True).label("errors"),
        )
        .where(
            ExecutionLog.project_id == project_id,
            ExecutionLog.created_at >= start_date,
        )
    )
    metrics = result.one()

    # Cost by provider
    result = await db.execute(
        select(
            ExecutionLog.provider,
            func.count(ExecutionLog.id).label("count"),
            func.sum(ExecutionLog.total_tokens).label("tokens"),
            func.sum(ExecutionLog.estimated_cost_usd).label("cost"),
        )
        .where(
            ExecutionLog.project_id == project_id,
            ExecutionLog.created_at >= start_date,
        )
        .group_by(ExecutionLog.provider)
    )
    by_provider = {
        row[0].value: {
            "executions": row[1],
            "tokens": row[2] or 0,
            "cost_usd": float(row[3]) if row[3] else 0,
        }
        for row in result.all()
    }

    total_executions = metrics[0] or 0
    cache_hits = metrics[3] or 0

    return {
        "project_id": str(project_id),
        "period_days": days,
        "total_executions": total_executions,
        "total_tokens": metrics[1] or 0,
        "total_cost_usd": float(metrics[2]) if metrics[2] else 0,
        "cache_hits": cache_hits,
        "cache_hit_rate": cache_hits / total_executions if total_executions > 0 else 0,
        "error_count": metrics[4] or 0,
        "by_provider": by_provider,
    }


@router.get("/entity/{entity_type}/{entity_id}/lineage")
async def get_entity_lineage(
    entity_type: str,
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get the parse lineage for a specific entity.
    Shows exactly how this entity was extracted.
    """
    audit_service = AuditService(db)
    lineage = await audit_service.get_lineage_for_entity(entity_type, entity_id)

    if not lineage:
        raise HTTPException(status_code=404, detail="Lineage not found for this entity")

    # Get the source response
    archive_result = await db.execute(
        select(ResponseArchive).where(ResponseArchive.id == lineage.response_archive_id)
    )
    archive = archive_result.scalar_one_or_none()

    return {
        "entity": {
            "type": lineage.entity_type,
            "id": str(lineage.entity_id) if lineage.entity_id else None,
            "value": lineage.entity_value,
        },
        "extraction": {
            "method": lineage.extraction_method,
            "pattern": lineage.extraction_pattern,
            "version": lineage.extraction_version,
            "confidence": lineage.confidence,
            "factors": lineage.confidence_factors,
        },
        "position": {
            "start_offset": lineage.start_offset,
            "end_offset": lineage.end_offset,
            "context_before": lineage.context_before,
            "context_after": lineage.context_after,
        } if lineage.start_offset is not None else None,
        "source": {
            "response_hash": archive.response_hash if archive else None,
            "archived_at": archive.archived_at.isoformat() if archive else None,
        },
        "extracted_at": lineage.extracted_at.isoformat(),
    }
