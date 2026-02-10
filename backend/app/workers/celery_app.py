"""
Celery Application Configuration
Queue-based task processing for LLM execution
"""

from celery import Celery
from kombu import Queue, Exchange

from app.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "llmrefs",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.tasks.llm_tasks",
        "app.workers.tasks.parsing_tasks",
        "app.workers.tasks.scoring_tasks",
        "app.workers.tasks.scheduled_tasks",
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Result backend settings
    result_expires=86400,  # 24 hours

    # Task execution settings
    task_acks_late=True,  # Acknowledge after task completion
    task_reject_on_worker_lost=True,
    task_time_limit=300,  # 5 minutes max
    task_soft_time_limit=240,  # 4 minutes soft limit

    # Worker settings
    worker_prefetch_multiplier=1,  # Fair distribution
    worker_concurrency=4,  # Number of concurrent tasks

    # Rate limiting
    task_default_rate_limit="10/m",  # Default 10 per minute

    # Retry settings
    task_default_retry_delay=30,
    task_max_retries=3,

    # Queue configuration
    task_queues=(
        Queue("high_priority", Exchange("high_priority"), routing_key="high"),
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("low_priority", Exchange("low_priority"), routing_key="low"),
        Queue("llm_execution", Exchange("llm_execution"), routing_key="llm"),
        Queue("parsing", Exchange("parsing"), routing_key="parse"),
        Queue("scoring", Exchange("scoring"), routing_key="score"),
    ),

    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",

    # Route tasks to appropriate queues
    task_routes={
        "app.workers.tasks.llm_tasks.*": {"queue": "llm_execution"},
        "app.workers.tasks.parsing_tasks.*": {"queue": "parsing"},
        "app.workers.tasks.scoring_tasks.*": {"queue": "scoring"},
    },

    # Beat scheduler for periodic tasks
    beat_schedule={
        "process-scheduled-crawls": {
            "task": "app.workers.tasks.scheduled_tasks.process_scheduled_crawls",
            "schedule": 3600.0,  # Every hour
        },
        "aggregate-daily-scores": {
            "task": "app.workers.tasks.scheduled_tasks.aggregate_daily_scores",
            "schedule": 86400.0,  # Daily
        },
        "validate-citations": {
            "task": "app.workers.tasks.scheduled_tasks.validate_pending_citations",
            "schedule": 21600.0,  # Every 6 hours
        },
    },
)


def get_queue_for_priority(priority: str) -> str:
    """Get queue name for given priority"""
    priority_queues = {
        "high": "high_priority",
        "medium": "default",
        "low": "low_priority",
    }
    return priority_queues.get(priority, "default")
