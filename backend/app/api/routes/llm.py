"""
LLM Execution Routes
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime
import asyncio
import httpx

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.models import Project, LLMRun, LLMResponse, LLMRunStatus, User, Keyword, Prompt, LLMProvider, JobPriority
from app.schemas.llm import (
    LLMRunResponse, LLMExecutionRequest, LLMExecutionStatus, LLMRunDetail
)
from app.utils import get_db
from app.api.middleware.auth import get_current_user
from app.config import get_settings

router = APIRouter()
settings = get_settings()


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


# ============================================================================
# SYNCHRONOUS EXECUTION (For local development without Celery/Redis)
# ============================================================================

class SyncExecutionRequest(BaseModel):
    keyword_ids: Optional[List[UUID]] = None
    provider: str = "openai"  # Default provider
    providers: Optional[List[str]] = None  # Multiple providers (overrides 'provider' if set)
    # Note: country is now set at project level, no longer passed in request


# Country names for prompt context
COUNTRY_NAMES = {
    "in": "India",
    "us": "United States",
    "uk": "United Kingdom",
    "au": "Australia",
    "ca": "Canada",
    "de": "Germany",
    "fr": "France",
    "jp": "Japan",
    "sg": "Singapore",
    "ae": "UAE",
}


class SyncExecutionResponse(BaseModel):
    success: bool
    message: str
    results: List[dict] = []
    errors: List[str] = []


@router.post("/{project_id}/execute-sync", response_model=SyncExecutionResponse)
async def execute_llm_queries_sync(
    project_id: UUID,
    request: SyncExecutionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Synchronously execute LLM queries (for local development without Celery).
    This directly calls the LLM API and returns results immediately.
    """
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Determine which providers to use
    providers_to_use = request.providers if request.providers else [request.provider.lower()]
    providers_to_use = [p.lower() for p in providers_to_use]

    # Get API keys for all providers
    provider_keys = {}
    missing_keys = []
    for provider in providers_to_use:
        if provider == "openai" and settings.OPENAI_API_KEY:
            provider_keys["openai"] = settings.OPENAI_API_KEY
        elif provider == "anthropic" and settings.ANTHROPIC_API_KEY:
            provider_keys["anthropic"] = settings.ANTHROPIC_API_KEY
        elif provider == "google" and settings.GOOGLE_API_KEY:
            provider_keys["google"] = settings.GOOGLE_API_KEY
        elif provider == "perplexity" and settings.PERPLEXITY_API_KEY:
            provider_keys["perplexity"] = settings.PERPLEXITY_API_KEY
        else:
            missing_keys.append(provider)

    if not provider_keys:
        raise HTTPException(
            status_code=400,
            detail=f"No API keys configured for any of: {', '.join(providers_to_use)}. Please add them to your .env file."
        )

    # Get keywords
    keyword_query = select(Keyword).where(Keyword.project_id == project_id, Keyword.is_active == True)
    if request.keyword_ids:
        keyword_query = keyword_query.where(Keyword.id.in_(request.keyword_ids))

    result = await db.execute(keyword_query.limit(5))  # Limit to 5 keywords for sync mode
    keywords = result.scalars().all()

    if not keywords:
        raise HTTPException(status_code=400, detail="No keywords found for this project")

    results = []
    errors = []

    # Execute queries for each keyword with each provider
    async with httpx.AsyncClient(timeout=60.0) as client:
        for keyword in keywords:
            for provider, api_key in provider_keys.items():
                try:
                    # Create prompt with country context (use project's country)
                    project_country = project.country or "in"
                    country_name = COUNTRY_NAMES.get(project_country.lower(), project_country)
                    prompt_text = f"What are the best {keyword.keyword} in {country_name}? Please provide a comprehensive answer with specific product or service recommendations relevant to {country_name}."

                    if provider == "openai":
                        response = await _call_openai(client, api_key, prompt_text)
                    elif provider == "anthropic":
                        response = await _call_anthropic(client, api_key, prompt_text)
                    elif provider == "google":
                        response = await _call_google(client, api_key, prompt_text)
                    elif provider == "perplexity":
                        response = await _call_perplexity(client, api_key, prompt_text)
                    else:
                        response = {"error": f"Provider {provider} not supported"}

                    # Create LLM run record
                    llm_run = LLMRun(
                        project_id=project_id,
                        prompt_id=None,  # No prompt record in sync mode
                        provider=LLMProvider(provider),
                        model_name=response.get("model", "unknown"),
                        temperature=0.7,
                        max_tokens=2000,
                        status=LLMRunStatus.COMPLETED,
                        priority=JobPriority.MEDIUM,
                        queued_at=datetime.utcnow(),
                        started_at=datetime.utcnow(),
                        completed_at=datetime.utcnow(),
                        input_tokens=response.get("input_tokens", 0),
                        output_tokens=response.get("output_tokens", 0),
                        is_cached_result=False,
                    )
                    db.add(llm_run)
                    await db.flush()

                    # Create LLM response record
                    import hashlib
                    response_text = response.get("content", "")
                    llm_response = LLMResponse(
                        llm_run_id=llm_run.id,
                        raw_response=response_text,
                        response_metadata={"provider": provider, "model": response.get("model")},
                        response_hash=hashlib.sha256(response_text.encode()).hexdigest(),
                    )
                    db.add(llm_response)
                    await db.flush()

                    # Run visibility analysis on the response
                    from app.services import VisibilityAnalyzer
                    analyzer = VisibilityAnalyzer(db)
                    analysis = None
                    try:
                        # For Perplexity, append citations to response text if available
                        enhanced_response_text = response_text
                        perplexity_citations = response.get("citations", [])
                        if perplexity_citations and provider == "perplexity":
                            # Append Perplexity's citations to the response text for extraction
                            citation_text = "\n\nSources:\n"
                            for i, cit_url in enumerate(perplexity_citations):
                                citation_text += f"[{i+1}] {cit_url}\n"
                            enhanced_response_text = response_text + citation_text

                        analysis = await analyzer.analyze_response(
                            llm_run_id=llm_run.id,
                            response_text=enhanced_response_text,
                            project_id=project_id,
                            keyword_id=keyword.id
                        )
                        # Save analysis results
                        await analyzer.save_analysis_results(
                            llm_run_id=llm_run.id,
                            response_id=llm_response.id,
                            analysis=analysis
                        )
                    except Exception as analysis_error:
                        import traceback
                        # Rollback the session to recover from any DB errors
                        await db.rollback()
                        errors.append(f"Analysis error for '{keyword.keyword}': {str(analysis_error)}")

                    results.append({
                        "keyword": keyword.keyword,
                        "keyword_id": str(keyword.id),
                        "provider": provider,
                        "response": response_text[:500] + "..." if len(response_text) > 500 else response_text,
                        "tokens": response.get("output_tokens", 0),
                        "brand_mentioned": analysis.get("brand_mentioned", False) if analysis else False,
                        "visibility_score": analysis.get("total_visibility_score", 0) if analysis else 0,
                        "brands_found": len(analysis.get("mentions", [])) if analysis else 0,
                        "citations_found": len(analysis.get("citations", [])) if analysis else 0,
                        "top_brands": [
                            {"name": m["name"], "position": m["position"]}
                            for m in (analysis.get("mentions", []) if analysis else [])[:5]
                        ],
                        # AIO status
                        "has_aio": analysis.get("has_aio", True) if analysis else True,
                        "brand_in_aio": analysis.get("brand_in_aio", False) if analysis else False,
                        "domain_in_aio": analysis.get("domain_in_aio", False) if analysis else False,
                    })

                except Exception as e:
                    errors.append(f"Error processing '{keyword.keyword}' with {provider}: {str(e)}")

    await db.commit()

    return SyncExecutionResponse(
        success=len(results) > 0,
        message=f"Processed {len(results)} keywords" + (f" with {len(errors)} errors" if errors else ""),
        results=results,
        errors=errors,
    )


async def _call_openai(client: httpx.AsyncClient, api_key: str, prompt: str) -> dict:
    """Call OpenAI API directly"""
    response = await client.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant that provides information about products and services. When asked about recommendations, mention specific brands and products."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 1000,
        }
    )

    if response.status_code != 200:
        raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")

    data = response.json()
    return {
        "content": data["choices"][0]["message"]["content"],
        "model": data["model"],
        "input_tokens": data["usage"]["prompt_tokens"],
        "output_tokens": data["usage"]["completion_tokens"],
    }


async def _call_anthropic(client: httpx.AsyncClient, api_key: str, prompt: str) -> dict:
    """Call Anthropic API directly"""
    response = await client.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": "claude-3-haiku-20240307",
            "max_tokens": 1000,
            "messages": [
                {"role": "user", "content": prompt}
            ],
        }
    )

    if response.status_code != 200:
        raise Exception(f"Anthropic API error: {response.status_code} - {response.text}")

    data = response.json()
    return {
        "content": data["content"][0]["text"],
        "model": data["model"],
        "input_tokens": data["usage"]["input_tokens"],
        "output_tokens": data["usage"]["output_tokens"],
    }


async def _call_google(client: httpx.AsyncClient, api_key: str, prompt: str) -> dict:
    """Call Google Gemini API directly"""
    response = await client.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}",
        headers={
            "Content-Type": "application/json",
        },
        json={
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 1000,
            }
        }
    )

    if response.status_code != 200:
        raise Exception(f"Google API error: {response.status_code} - {response.text}")

    data = response.json()
    content = ""
    if "candidates" in data and len(data["candidates"]) > 0:
        candidate = data["candidates"][0]
        if "content" in candidate and "parts" in candidate["content"]:
            content = candidate["content"]["parts"][0].get("text", "")

    # Token counts from usage metadata
    usage = data.get("usageMetadata", {})
    return {
        "content": content,
        "model": "gemini-1.5-flash",
        "input_tokens": usage.get("promptTokenCount", 0),
        "output_tokens": usage.get("candidatesTokenCount", 0),
    }


async def _call_perplexity(client: httpx.AsyncClient, api_key: str, prompt: str) -> dict:
    """Call Perplexity API directly - uses online models with web search"""
    response = await client.post(
        "https://api.perplexity.ai/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": "llama-3.1-sonar-small-128k-online",  # Online model with web search
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that provides comprehensive information about products and services. Include specific brand recommendations and cite sources when possible."
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 1000,
        }
    )

    if response.status_code != 200:
        raise Exception(f"Perplexity API error: {response.status_code} - {response.text}")

    data = response.json()
    content = data["choices"][0]["message"]["content"]

    # Perplexity returns citations in the response
    citations = data.get("citations", [])

    return {
        "content": content,
        "model": data.get("model", "llama-3.1-sonar-small-128k-online"),
        "input_tokens": data.get("usage", {}).get("prompt_tokens", 0),
        "output_tokens": data.get("usage", {}).get("completion_tokens", 0),
        "citations": citations,  # Perplexity provides citations
    }
