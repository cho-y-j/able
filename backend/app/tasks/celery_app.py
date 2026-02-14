from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "able",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # Resilience settings
    task_soft_time_limit=300,      # 5 min soft limit (raises SoftTimeLimitExceeded)
    task_time_limit=360,           # 6 min hard kill
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks (prevent memory leaks)

    # Queue routing
    task_routes={
        "tasks.run_agent_session": {"queue": "agents"},
        "tasks.scheduled_agent_run": {"queue": "agents"},
        "tasks.update_position_prices": {"queue": "periodic"},
    },

    # Beat schedule for periodic tasks
    beat_schedule={
        # Update position prices every 5 minutes during market hours (09:00-15:30 KST, Mon-Fri)
        "update-position-prices": {
            "task": "tasks.update_position_prices",
            "schedule": crontab(minute="*/5", hour="9-15", day_of_week="1-5"),
        },
        # Auto-start agent sessions at market open (09:05 KST, Mon-Fri)
        "auto-agent-market-open": {
            "task": "tasks.scheduled_agent_run",
            "schedule": crontab(minute=5, hour=9, day_of_week="1-5"),
        },
        # Mid-day portfolio check (12:30 KST, Mon-Fri)
        "midday-portfolio-check": {
            "task": "tasks.scheduled_agent_run",
            "schedule": crontab(minute=30, hour=12, day_of_week="1-5"),
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.tasks"])
