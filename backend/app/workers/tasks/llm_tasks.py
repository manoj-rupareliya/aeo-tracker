"""
LLM Execution Tasks
Async task processing for LLM queries
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

from celery import shared_task
from celery.utils.log import get_task_logger
from sqlalchemy import select

from app.workers.celery_app import celery_app
from app.utils.database import get_sync_db
from app.utils.cache import llm_cache
from app.utils.security import generate_cache_key, generate_response_hash
from app.models import (
    LLMRun, LLMResponse, Prompt, LLMRunStatus, LLMProvider
)
from app.adapters.llm import get_adapter, LLMConfig, LLMAdapterError
from app.config import get_settings

logger = get_task_logger(__name__)
settings = get_settings()


def run_async(coro):
    """Run async function in sync context"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    name="app.workers.tasks.llm_tasks.execute_llm_query",
    max_retries=3,
    default_retry_delay=30,
    rate_limit="10/m",
)
def execute_llm_query(self, llm_run_id: str) -> Dict:
    """
    Execute a single LLM query.

    Args:
        llm_run_id: UUID of the LLMRun to execute

    Returns:
        Dict with execution result
    """
    db = get_sync_db()

    try:
        # Get LLM run
        llm_run = db.query(LLMRun).filter(LLMRun.id == llm_run_id).first()
        if not llm_run:
            logger.error(f"LLM run not found: {llm_run_id}")
            return {"error": "LLM run not found", "run_id": llm_run_id}

        # Update status to processing
        llm_run.status = LLMRunStatus.PROCESSING
        llm_run.started_at = datetime.utcnow()
        db.commit()

        # Get prompt
        prompt = db.query(Prompt).filter(Prompt.id == llm_run.prompt_id).first()
        if not prompt:
            llm_run.status = LLMRunStatus.FAILED
            llm_run.error_message = "Prompt not found"
            db.commit()
            return {"error": "Prompt not found", "run_id": llm_run_id}

        # Check cache
        cache_key = generate_cache_key(
            prompt.prompt_hash,
            llm_run.model_name,
            llm_run.temperature
        )

        cached_response = run_async(_check_cache(cache_key))
        if cached_response:
            logger.info(f"Cache hit for run {llm_run_id}")
            return _handle_cached_response(db, llm_run, cached_response, cache_key)

        # Execute LLM query
        llm_run.status = LLMRunStatus.EXECUTING
        db.commit()

        try:
            response = run_async(_execute_llm(
                provider=llm_run.provider.value,
                prompt_text=prompt.prompt_text,
                model=llm_run.model_name,
                temperature=llm_run.temperature,
                max_tokens=llm_run.max_tokens,
            ))
        except LLMAdapterError as e:
            logger.error(f"LLM error for run {llm_run_id}: {e}")
            llm_run.retry_count += 1
            if llm_run.retry_count < settings.LLM_MAX_RETRIES:
                llm_run.status = LLMRunStatus.PENDING
                db.commit()
                raise self.retry(exc=e)
            else:
                llm_run.status = LLMRunStatus.FAILED
                llm_run.error_message = str(e)
                llm_run.completed_at = datetime.utcnow()
                db.commit()
                return {"error": str(e), "run_id": llm_run_id}

        # Save response
        llm_run.status = LLMRunStatus.PARSING
        llm_run.input_tokens = response.usage.prompt_tokens if response.usage else None
        llm_run.output_tokens = response.usage.completion_tokens if response.usage else None
        llm_run.estimated_cost_usd = response.estimated_cost_usd
        llm_run.cache_key = cache_key
        llm_run.cache_expires_at = datetime.utcnow() + timedelta(days=7)

        response_hash = generate_response_hash(response.content)

        llm_response = LLMResponse(
            llm_run_id=llm_run.id,
            raw_response=response.content,
            response_metadata={
                "finish_reason": response.finish_reason,
                "latency_ms": response.latency_ms,
                "citations": response.citations,
            },
            parsed_response={},
            response_hash=response_hash,
        )
        db.add(llm_response)

        llm_run.completed_at = datetime.utcnow()
        llm_run.status = LLMRunStatus.PARSING
        db.commit()

        # Cache the response
        run_async(_cache_response(cache_key, {
            "content": response.content,
            "metadata": {
                "finish_reason": response.finish_reason,
                "citations": response.citations,
            },
            "hash": response_hash,
        }))

        logger.info(f"LLM query completed for run {llm_run_id}")

        # Trigger parsing task
        from app.workers.tasks.parsing_tasks import parse_llm_response
        parse_llm_response.delay(str(llm_run.id))

        return {
            "success": True,
            "run_id": llm_run_id,
            "response_id": str(llm_response.id),
            "tokens": {
                "input": llm_run.input_tokens,
                "output": llm_run.output_tokens,
            },
            "cost_usd": float(llm_run.estimated_cost_usd) if llm_run.estimated_cost_usd else None,
        }

    except Exception as e:
        logger.exception(f"Unexpected error for run {llm_run_id}: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def _handle_cached_response(db, llm_run: LLMRun, cached: Dict, cache_key: str) -> Dict:
    """Handle a cached response"""
    llm_run.status = LLMRunStatus.CACHED
    llm_run.is_cached_result = True
    llm_run.cache_key = cache_key
    llm_run.completed_at = datetime.utcnow()

    llm_response = LLMResponse(
        llm_run_id=llm_run.id,
        raw_response=cached["content"],
        response_metadata=cached.get("metadata", {}),
        parsed_response={},
        response_hash=cached.get("hash", ""),
    )
    db.add(llm_response)
    db.commit()

    # Trigger parsing
    from app.workers.tasks.parsing_tasks import parse_llm_response
    parse_llm_response.delay(str(llm_run.id))

    return {
        "success": True,
        "run_id": str(llm_run.id),
        "response_id": str(llm_response.id),
        "cached": True,
    }


async def _check_cache(cache_key: str) -> Optional[Dict]:
    """Check cache for existing response"""
    return await llm_cache.get_response(cache_key)


async def _cache_response(cache_key: str, response: Dict):
    """Cache LLM response"""
    await llm_cache.set_response(cache_key, response)


async def _execute_llm(
    provider: str,
    prompt_text: str,
    model: str,
    temperature: float,
    max_tokens: int,
):
    """Execute LLM query"""
    adapter = get_adapter(provider)
    config = LLMConfig(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=settings.LLM_REQUEST_TIMEOUT,
    )

    return await adapter.execute(prompt_text, config=config)


@celery_app.task(
    name="app.workers.tasks.llm_tasks.execute_batch_queries",
)
def execute_batch_queries(
    project_id: str,
    keyword_ids: Optional[List[str]] = None,
    providers: Optional[List[str]] = None,
    prompt_types: Optional[List[str]] = None,
    priority: str = "medium",
) -> Dict:
    """
    Queue LLM queries for multiple keywords.

    Args:
        project_id: Project ID
        keyword_ids: Optional list of keyword IDs (all if None)
        providers: Optional list of providers (project defaults if None)
        prompt_types: Optional prompt types (all if None)
        priority: Queue priority

    Returns:
        Dict with queued run IDs
    """
    from app.workers.celery_app import get_queue_for_priority

    db = get_sync_db()

    try:
        from app.models import Project, Keyword, Prompt

        # Get project
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return {"error": "Project not found"}

        # Get providers
        if providers is None:
            providers = project.enabled_llms
        else:
            providers = [p for p in providers if p in project.enabled_llms]

        # Get keywords
        query = db.query(Keyword).filter(
            Keyword.project_id == project_id,
            Keyword.is_active == True
        )
        if keyword_ids:
            query = query.filter(Keyword.id.in_(keyword_ids))
        keywords = query.all()

        # Get prompts for keywords
        prompt_query = db.query(Prompt).filter(
            Prompt.keyword_id.in_([k.id for k in keywords])
        )
        if prompt_types:
            prompt_query = prompt_query.filter(Prompt.prompt_type.in_(prompt_types))
        prompts = prompt_query.all()

        # Create LLM runs
        queued_runs = []
        queue = get_queue_for_priority(priority)

        for prompt in prompts:
            for provider in providers:
                # Check if run already exists and is not expired
                existing = db.query(LLMRun).filter(
                    LLMRun.prompt_id == prompt.id,
                    LLMRun.provider == provider,
                    LLMRun.status.in_([
                        LLMRunStatus.COMPLETED,
                        LLMRunStatus.CACHED
                    ]),
                    LLMRun.cache_expires_at > datetime.utcnow()
                ).first()

                if existing:
                    continue

                # Get default model for provider
                model_map = {
                    "openai": settings.OPENAI_DEFAULT_MODEL,
                    "anthropic": settings.ANTHROPIC_DEFAULT_MODEL,
                    "google": settings.GOOGLE_DEFAULT_MODEL,
                    "perplexity": settings.PERPLEXITY_DEFAULT_MODEL,
                }

                llm_run = LLMRun(
                    project_id=project_id,
                    prompt_id=prompt.id,
                    provider=LLMProvider(provider),
                    model_name=model_map.get(provider, ""),
                    temperature=settings.LLM_DEFAULT_TEMPERATURE,
                    max_tokens=settings.LLM_DEFAULT_MAX_TOKENS,
                    status=LLMRunStatus.PENDING,
                    priority=priority,
                )
                db.add(llm_run)
                db.flush()

                queued_runs.append(str(llm_run.id))

        db.commit()

        # Queue execution tasks
        for run_id in queued_runs:
            execute_llm_query.apply_async(
                args=[run_id],
                queue=queue,
            )

        logger.info(f"Queued {len(queued_runs)} LLM runs for project {project_id}")

        return {
            "success": True,
            "project_id": project_id,
            "queued_runs": queued_runs,
            "total": len(queued_runs),
        }

    except Exception as e:
        logger.exception(f"Error queuing batch: {e}")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()
