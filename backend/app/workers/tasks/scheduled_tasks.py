"""
Scheduled Tasks
Periodic tasks for crawling, aggregation, and maintenance
"""

from datetime import datetime, timedelta
from typing import Dict

from celery.utils.log import get_task_logger

from app.workers.celery_app import celery_app
from app.utils.database import get_sync_db
from app.models import (
    Project, ScheduledJob, LLMRun, LLMRunStatus,
    VisibilityScore, AggregatedScore, Citation
)

logger = get_task_logger(__name__)


@celery_app.task(
    name="app.workers.tasks.scheduled_tasks.process_scheduled_crawls",
)
def process_scheduled_crawls() -> Dict:
    """
    Process scheduled crawls for all projects.
    Runs hourly, checks which projects need re-crawling.
    """
    db = get_sync_db()

    try:
        now = datetime.utcnow()

        # Find projects due for crawl
        due_projects = db.query(Project).filter(
            Project.is_active == True,
            Project.next_crawl_at <= now
        ).all()

        logger.info(f"Found {len(due_projects)} projects due for crawl")

        queued = 0
        for project in due_projects:
            # Create scheduled job
            job = ScheduledJob(
                project_id=project.id,
                job_type="full_crawl",
                scheduled_for=now,
                status="running",
            )
            db.add(job)

            # Queue batch execution
            from app.workers.tasks.llm_tasks import execute_batch_queries
            execute_batch_queries.delay(
                project_id=str(project.id),
                priority="low",
            )

            # Update next crawl time
            project.last_crawl_at = now
            project.next_crawl_at = now + timedelta(days=project.crawl_frequency_days)

            queued += 1

        db.commit()

        return {
            "success": True,
            "projects_queued": queued,
            "timestamp": now.isoformat(),
        }

    except Exception as e:
        logger.exception(f"Error processing scheduled crawls: {e}")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@celery_app.task(
    name="app.workers.tasks.scheduled_tasks.aggregate_daily_scores",
)
def aggregate_daily_scores() -> Dict:
    """
    Aggregate visibility scores daily for trending analysis.
    Runs once per day.
    """
    db = get_sync_db()

    try:
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        period_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end = period_start + timedelta(days=1)

        # Get all active projects
        projects = db.query(Project).filter(Project.is_active == True).all()

        aggregated = 0
        for project in projects:
            # Get scores for this period
            scores = db.query(VisibilityScore).filter(
                VisibilityScore.project_id == project.id,
                VisibilityScore.score_date >= period_start,
                VisibilityScore.score_date < period_end
            ).all()

            if not scores:
                continue

            # Calculate aggregates
            total_score = sum(s.total_score for s in scores)
            avg_score = total_score / len(scores)

            avg_mention = sum(s.mention_score for s in scores) / len(scores)
            avg_position = sum(s.position_score for s in scores) / len(scores)
            avg_citation = sum(s.citation_score for s in scores) / len(scores)

            # Group by LLM
            scores_by_llm = {}
            for s in scores:
                if s.provider:
                    provider = s.provider.value
                    if provider not in scores_by_llm:
                        scores_by_llm[provider] = []
                    scores_by_llm[provider].append(s.total_score)

            llm_averages = {
                llm: sum(scores) / len(scores)
                for llm, scores in scores_by_llm.items()
            }

            # Get previous period for comparison
            prev_start = period_start - timedelta(days=1)
            prev_scores = db.query(AggregatedScore).filter(
                AggregatedScore.project_id == project.id,
                AggregatedScore.period_type == "daily",
                AggregatedScore.period_start == prev_start
            ).first()

            delta = None
            if prev_scores:
                delta = avg_score - prev_scores.avg_visibility_score

            # Count mentions and citations
            from app.models import BrandMention, Citation, LLMResponse

            response_ids = db.query(LLMResponse.id).join(LLMRun).filter(
                LLMRun.project_id == project.id,
                LLMRun.completed_at >= period_start,
                LLMRun.completed_at < period_end
            ).all()
            response_ids = [r[0] for r in response_ids]

            total_mentions = db.query(BrandMention).filter(
                BrandMention.response_id.in_(response_ids),
                BrandMention.is_own_brand == True
            ).count()

            total_citations = db.query(Citation).filter(
                Citation.response_id.in_(response_ids)
            ).count()

            # Create aggregated score
            agg = AggregatedScore(
                project_id=project.id,
                period_type="daily",
                period_start=period_start,
                period_end=period_end,
                avg_visibility_score=avg_score,
                avg_mention_score=avg_mention,
                avg_position_score=avg_position,
                avg_citation_score=avg_citation,
                scores_by_llm=llm_averages,
                score_delta_vs_previous=delta,
                total_queries=len(scores),
                total_mentions=total_mentions,
                total_citations=total_citations,
            )
            db.add(agg)
            aggregated += 1

        db.commit()

        logger.info(f"Aggregated scores for {aggregated} projects")

        return {
            "success": True,
            "projects_aggregated": aggregated,
            "period": period_start.isoformat(),
        }

    except Exception as e:
        logger.exception(f"Error aggregating scores: {e}")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@celery_app.task(
    name="app.workers.tasks.scheduled_tasks.validate_pending_citations",
)
def validate_pending_citations() -> Dict:
    """
    Validate citations that haven't been checked.
    Runs every 6 hours.
    """
    import asyncio
    from app.adapters.parsing import CitationExtractor

    db = get_sync_db()

    try:
        # Get citations not yet validated
        pending = db.query(Citation).filter(
            Citation.is_accessible == None,
            Citation.is_valid_url == True
        ).limit(100).all()  # Process in batches

        logger.info(f"Validating {len(pending)} citations")

        extractor = CitationExtractor(validate_urls=True)

        validated = 0
        hallucinated = 0

        for citation in pending:
            try:
                # Create a temporary ExtractedCitation for validation
                from app.adapters.parsing.citation_extractor import ExtractedCitation

                temp = ExtractedCitation(
                    url=citation.cited_url,
                    domain=citation.source.domain if citation.source else "",
                    anchor_text=citation.anchor_text,
                    context_snippet=citation.context_snippet or "",
                    position=citation.citation_position or 0,
                    is_valid_url=citation.is_valid_url,
                )

                # Validate
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(extractor.validate_citation(temp))
                finally:
                    loop.close()

                citation.is_accessible = result.is_accessible
                citation.http_status_code = result.http_status_code
                citation.is_hallucinated = result.is_hallucinated
                citation.last_validated_at = datetime.utcnow()

                if result.is_hallucinated:
                    hallucinated += 1

                validated += 1

            except Exception as e:
                logger.warning(f"Error validating citation {citation.id}: {e}")

        db.commit()

        return {
            "success": True,
            "validated": validated,
            "hallucinated": hallucinated,
        }

    except Exception as e:
        logger.exception(f"Error validating citations: {e}")
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()


@celery_app.task(
    name="app.workers.tasks.scheduled_tasks.cleanup_old_data",
)
def cleanup_old_data(days_to_keep: int = 90) -> Dict:
    """
    Clean up old data to manage database size.
    Keeps aggregated scores but removes raw responses.
    """
    db = get_sync_db()

    try:
        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)

        # Count old runs
        old_runs = db.query(LLMRun).filter(
            LLMRun.created_at < cutoff
        ).count()

        logger.info(f"Found {old_runs} runs older than {days_to_keep} days")

        # Note: In production, you might want to archive rather than delete
        # For now, we'll just log the count
        # Actual deletion would require careful consideration of data retention policies

        return {
            "success": True,
            "old_runs_found": old_runs,
            "cutoff_date": cutoff.isoformat(),
            "note": "Data retention policy should be implemented based on business requirements",
        }

    except Exception as e:
        logger.exception(f"Error during cleanup: {e}")
        return {"error": str(e)}
    finally:
        db.close()
