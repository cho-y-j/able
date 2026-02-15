from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "able",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

# Build price update schedule string from interval
_price_interval = max(1, settings.schedule_price_interval_minutes)
_price_cron_minute = f"*/{_price_interval}" if _price_interval < 60 else "0"
_price_hours = f"{settings.schedule_price_start_hour}-{settings.schedule_price_end_hour}"

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
        "tasks.generate_daily_report": {"queue": "periodic"},
    },

    # Beat schedule for periodic tasks (all times KST, configurable via .env)
    beat_schedule={
        # 아침 브리핑 (기본 06:30 KST — 미장 마감 후 기사 반영)
        "daily-market-intelligence": {
            "task": "tasks.generate_daily_report",
            "schedule": crontab(
                minute=settings.schedule_briefing_minute,
                hour=settings.schedule_briefing_hour,
                day_of_week="1-5",
            ),
        },
        # 포지션 가격 업데이트 (기본 1분 간격, NXT 프리마켓 08:00~장마감 16:00)
        "update-position-prices": {
            "task": "tasks.update_position_prices",
            "schedule": crontab(
                minute=_price_cron_minute,
                hour=_price_hours,
                day_of_week="1-5",
            ),
        },
        # 장 시작 에이전트 (기본 08:00 KST — NXT 프리마켓 시작)
        "auto-agent-market-open": {
            "task": "tasks.scheduled_agent_run",
            "schedule": crontab(
                minute=settings.schedule_agent_open_minute,
                hour=settings.schedule_agent_open_hour,
                day_of_week="1-5",
            ),
        },
        # 점심 포트폴리오 점검 (기본 12:30 KST)
        "midday-portfolio-check": {
            "task": "tasks.scheduled_agent_run",
            "schedule": crontab(
                minute=settings.schedule_agent_midday_minute,
                hour=settings.schedule_agent_midday_hour,
                day_of_week="1-5",
            ),
        },
    },
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["app.tasks"])
