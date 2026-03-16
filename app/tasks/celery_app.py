"""
Celery application configuration.
"""
from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "drax",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.scheduled"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",    # Always UTC internally; per-user local times handled in tasks
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
)

# ── Periodic task schedule ─────────────────────────────────────────────────────
# All tasks run every 30 minutes and check each user's configured time/day
# in their own timezone before sending. This supports any timezone worldwide.
celery_app.conf.beat_schedule = {
    # Runs every 30 min — sends to users whose morning_plan time is in this window
    "morning-plan": {
        "task": "app.tasks.scheduled.send_morning_plan",
        "schedule": crontab(minute="0,30"),
    },
    # Runs every 30 min — sends to users whose preworkout time is in this window
    "pre-gym-motivation": {
        "task": "app.tasks.scheduled.send_pre_workout_motivation",
        "schedule": crontab(minute="0,30"),
    },
    # Runs every 30 min — sends to users whose evening_checkin time is in this window
    "evening-checkin": {
        "task": "app.tasks.scheduled.send_evening_checkin",
        "schedule": crontab(minute="0,30"),
    },
    # Runs every 30 min — sends to users due for a water reminder based on their interval
    "water-reminder": {
        "task": "app.tasks.scheduled.send_water_reminder",
        "schedule": crontab(minute="0,30"),
    },
    # Runs every 30 min — sends to users whose weekly_report day+time is now
    "weekly-report": {
        "task": "app.tasks.scheduled.send_weekly_report",
        "schedule": crontab(minute="0,30"),
    },
}
