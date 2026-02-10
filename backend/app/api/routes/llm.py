"""
LLM Execution Routes
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Project, LLMRun, LLMResponse, LLMRunStatus, User
from app.schemas.llm import (
    LLMRunResponse, LLMExecutionRequest, LLMExecutionStatus, LLMRunDetail
)
from app.utils import get_db
from app.api.middleware.auth import get_current_user

router = APIRouter()


@router.post("/{project_id}/execute", response_model=LLMExecutionStatus)
async def execute_llm_queries(
    project_id: UUID,
    request: LLMExecutionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Queue LLM queries for execution.
    Returns immediately with job IDs for tracking.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Queue execution via Celery
    from app.workers.tasks.llm_tasks import execute_batch_queries

    task_result = execute_batch_queries.delay(
        project_id=str(project_id),
        keyword_ids=[str(kid) for kid in request.keyword_ids] if request.keyword_ids else None,
        providers=request.providers,
        prompt_types=request.prompt_types,
        priority="high" if request.force_refresh else "medium",
    )

    # Get queued runs count
    result = await db.execute(
        select(func.count(LLMRun.id)).where(
            LLMRun.project_id == project_id,
            LLMRun.status == LLMRunStatus.PENDING
        )
    )
    pending_count = result.scalar()

    return LLMExecutionStatus(
        batch_id=UUID(task_result.id) if task_result.id else UUID(int=0),
        total_runs=pending_count,
        pending=pending_count,
        processing=0,
        completed=0,
        failed=0,
        cached=0,
        estimated_completion_time=None,
        runs=[],
    )


@router.get("/{project_id}/runs", response_model=List[LLMRunResponse])
async def list_runs(
    project_id: UUID,
    status: Optional[str] = Query(None),
    provider: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List LLM runs for a project"""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Build query
    query = select(LLMRun).where(LLMRun.project_id == project_id)

    if status:
        query = query.where(LLMRun.status == status)
    if provider:
        query = query.where(LLMRun.provider == provider)

    result = await db.execute(
        query
        .order_by(LLMRun.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    runs = result.scalars().all()

    return [_run_to_response(r) for r in runs]


@router.get("/{project_id}/runs/{run_id}", response_model=LLMRunDetail)
async def get_run_detail(
    project_id: UUID,
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get detailed LLM run with response and analysis"""
    result = await db.execute(
        select(LLMRun)
        .options(selectinload(LLMRun.response))
        .join(Project)
        .where(
            LLMRun.id == run_id,
            LLMRun.project_id == project_id,
            Project.owner_id == user.id
        )
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Get mentions and citations
    from app.models import BrandMention, Citation, VisibilityScore
    from app.schemas.analysis import BrandMentionResponse, CitationResponse, VisibilityScoreResponse

    mentions = []
    citations = []
    score = None

    if run.response:
        # Get mentions
        result = await db.execute(
            select(BrandMention).where(BrandMention.response_id == run.response.id)
        )
        mentions = [BrandMentionResponse.model_validate(m) for m in result.scalars().all()]

        # Get citations
        result = await db.execute(
            select(Citation).where(Citation.response_id == run.response.id)
        )
        citations = [CitationResponse.model_validate(c) for c in result.scalars().all()]

    # Get visibility score
    result = await db.execute(
        select(VisibilityScore).where(VisibilityScore.llm_run_id == run_id)
    )
    score_obj = result.scalar_one_or_none()
    if score_obj:
        score = VisibilityScoreResponse.model_validate(score_obj)

    return LLMRunDetail(
        run=_run_to_response(run),
        response=_response_to_data(run.response) if run.response else None,
        mentions=mentions,
        citations=citations,
        visibility_score=score,
    )


@router.get("/{project_id}/status")
async def get_execution_status(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get current execution status for a project"""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Count runs by status
    status_counts = {}
    for status in LLMRunStatus:
        result = await db.execute(
            select(func.count(LLMRun.id)).where(
                LLMRun.project_id == project_id,
                LLMRun.status == status
            )
        )
        status_counts[status.value] = result.scalar()

    return {
        "project_id": project_id,
        "status_counts": status_counts,
        "total": sum(status_counts.values()),
    }


@router.post("/{project_id}/runs/{run_id}/retry")
async def retry_failed_run(
    project_id: UUID,
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retry a failed LLM run"""
    result = await db.execute(
        select(LLMRun)
        .join(Project)
        .where(
            LLMRun.id == run_id,
            LLMRun.project_id == project_id,
            Project.owner_id == user.id,
            LLMRun.status == LLMRunStatus.FAILED
        )
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=404, detail="Failed run not found")

    # Reset status and queue
    run.status = LLMRunStatus.PENDING
    run.retry_count = 0
    run.error_message = None
    await db.commit()

    # Queue execution
    from app.workers.tasks.llm_tasks import execute_llm_query
    execute_llm_query.delay(str(run_id))

    return {"message": "Run queued for retry", "run_id": str(run_id)}


def _run_to_response(run: LLMRun) -> LLMRunResponse:
    """Convert LLMRun to response"""
    return LLMRunResponse(
        id=run.id,
        project_id=run.project_id,
        prompt_id=run.prompt_id,
        provider=run.provider.value,
        model_name=run.model_name,
        temperature=run.temperature,
        max_tokens=run.max_tokens,
        status=run.status.value,
        priority=run.priority.value,
        queued_at=run.queued_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        estimated_cost_usd=run.estimated_cost_usd,
        is_cached_result=run.is_cached_result,
        retry_count=run.retry_count,
        error_message=run.error_message,
        created_at=run.created_at,
    )


def _response_to_data(response: LLMResponse):
    """Convert LLMResponse to data"""
    from app.schemas.llm import LLMResponseData
    return LLMResponseData(
        id=response.id,
        llm_run_id=response.llm_run_id,
        raw_response=response.raw_response,
        response_metadata=response.response_metadata,
        parsed_response=response.parsed_response,
        response_hash=response.response_hash,
        created_at=response.created_at,
    )
