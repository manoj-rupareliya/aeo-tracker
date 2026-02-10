"""
Scoring Tasks
Calculate visibility scores for LLM responses
"""

import asyncio
from datetime import datetime
from typing import Dict, List

from celery.utils.log import get_task_logger

from app.workers.celery_app import celery_app
from app.utils.database import get_sync_db
from app.models import LLMRun, LLMRunStatus

logger = get_task_logger(__name__)


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
    name="app.workers.tasks.scoring_tasks.calculate_score",
    max_retries=2,
    default_retry_delay=10,
)
def calculate_score(self, llm_run_id: str) -> Dict:
    """
    Calculate visibility score for an LLM run.

    Args:
        llm_run_id: UUID of the LLMRun to score

    Returns:
        Dict with scoring results
    """
    db = get_sync_db()

    try:
        # Get LLM run
        llm_run = db.query(LLMRun).filter(LLMRun.id == llm_run_id).first()
        if not llm_run:
            return {"error": "LLM run not found"}

        # Use async scoring engine
        from app.utils.database import get_db_context
        from app.services.scoring_engine import ScoringEngine

        async def score():
            async with get_db_context() as async_db:
                engine = ScoringEngine(async_db)
                return await engine.calculate_score(llm_run_id, save=True)

        breakdown = run_async(score())

        # Update LLM run status
        llm_run.status = LLMRunStatus.COMPLETED
        db.commit()

        logger.info(f"Scoring completed for run {llm_run_id}: {breakdown.total_weighted:.2f}")

        return {
            "success": True,
            "run_id": llm_run_id,
            "score": {
                "total_raw": breakdown.total_raw,
                "llm_weight": breakdown.llm_weight,
                "total_weighted": breakdown.total_weighted,
                "components": {
                    "mention": breakdown.mention_score.weighted_value,
                    "position": breakdown.position_score.weighted_value,
                    "citation": breakdown.citation_score.weighted_value,
                    "sentiment": breakdown.sentiment_score.weighted_value,
                    "competitor_delta": breakdown.competitor_delta.weighted_value,
                },
            },
            "explanation": breakdown.explanation,
        }

    except Exception as e:
        logger.exception(f"Scoring error for run {llm_run_id}: {e}")
        db.rollback()

        # Mark as completed even if scoring fails (data is still valid)
        try:
            llm_run = db.query(LLMRun).filter(LLMRun.id == llm_run_id).first()
            if llm_run:
                llm_run.status = LLMRunStatus.COMPLETED
                db.commit()
        except:
            pass

        raise self.retry(exc=e)
    finally:
        db.close()


@celery_app.task(
    name="app.workers.tasks.scoring_tasks.calculate_batch_scores",
)
def calculate_batch_scores(llm_run_ids: List[str]) -> Dict:
    """
    Calculate scores for multiple LLM runs.

    Args:
        llm_run_ids: List of LLMRun IDs to score

    Returns:
        Dict with batch scoring results
    """
    results = []
    for run_id in llm_run_ids:
        try:
            result = calculate_score(run_id)
            results.append(result)
        except Exception as e:
            results.append({"error": str(e), "run_id": run_id})

    successful = sum(1 for r in results if r.get("success"))
    return {
        "total": len(llm_run_ids),
        "successful": successful,
        "failed": len(llm_run_ids) - successful,
        "results": results,
    }


@celery_app.task(
    name="app.workers.tasks.scoring_tasks.recalculate_project_scores",
)
def recalculate_project_scores(project_id: str) -> Dict:
    """
    Recalculate all scores for a project.
    Useful when scoring algorithm changes.

    Args:
        project_id: Project ID

    Returns:
        Dict with recalculation results
    """
    db = get_sync_db()

    try:
        # Get all completed runs for project
        runs = db.query(LLMRun).filter(
            LLMRun.project_id == project_id,
            LLMRun.status == LLMRunStatus.COMPLETED
        ).all()

        run_ids = [str(r.id) for r in runs]

        logger.info(f"Recalculating scores for {len(run_ids)} runs in project {project_id}")

        return calculate_batch_scores(run_ids)

    except Exception as e:
        logger.exception(f"Error recalculating project scores: {e}")
        return {"error": str(e)}
    finally:
        db.close()
