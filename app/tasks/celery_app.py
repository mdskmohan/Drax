"""
Celery application configuration.
"""
from celery import Celery
from celery.schedules import crontab
from app.config import settings

celery_app = Celery(
    "fitbot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.scheduled"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
)

# ── Periodic task schedule ─────────────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    # Morning plan — 5:00 AM IST every day (gym at 6:30-7 AM)
    "morning-plan": {
        "task": "app.tasks.scheduled.send_morning_plan",
        "schedule": crontab(hour=23, minute=30),  # 5:00 AM IST = 23:30 UTC (prev day)
    },
    # Pre-gym reminder — 6:00 AM IST (30 min before gym)
    "pre-gym-motivation": {
        "task": "app.tasks.scheduled.send_pre_workout_motivation",
        "schedule": crontab(hour=0, minute=30),  # 6:00 AM IST = 00:30 UTC
    },
    # Evening check-in — 9:00 PM IST
    "evening-checkin": {
        "task": "app.tasks.scheduled.send_evening_checkin",
        "schedule": crontab(hour=15, minute=30),  # 9:00 PM IST = 15:30 UTC
    },
    # Water reminder — Every 2 hours between 8 AM – 8 PM IST
    "water-reminder": {
        "task": "app.tasks.scheduled.send_water_reminder",
        "schedule": crontab(hour="2,4,6,8,10,12", minute=30),
    },
    # Weekly report — Sunday 8:00 AM IST
    "weekly-report": {
        "task": "app.tasks.scheduled.send_weekly_report",
        "schedule": crontab(day_of_week=0, hour=2, minute=30),
    },
}
