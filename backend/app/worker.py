"""
Celery worker for background tasks.
Includes Celery Beat schedule for periodic job discovery.
"""

from celery import Celery
from celery.schedules import crontab
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "jobflow",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,  # 30 min max per task
    worker_max_tasks_per_child=50,
    # Beat schedule — run discovery for all users every 6 hours
    beat_schedule={
        "discover-jobs-all-users": {
            "task": "discover_jobs_all_users",
            "schedule": crontab(minute=0, hour="*/6"),  # every 6 hours
        },
        "check-follow-up-reminders": {
            "task": "check_follow_up_reminders",
            "schedule": crontab(minute=30, hour=3),  # daily at 9:00 AM IST (3:30 UTC)
        },
    },
)

# Explicitly include task modules
celery_app.conf.include = [
    "app.agents.job_discovery",
    "app.agents.auto_apply",
    "app.agents.follow_up_agent",
]


@celery_app.task(name="discover_jobs_all_users")
def discover_jobs_all_users():
    """Trigger job discovery for every user who has target_roles configured."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    engine = create_engine(settings.database_url_sync)

    with Session(engine) as db:
        # Find all users with target_roles set
        rows = db.execute(
            text("SELECT id FROM users WHERE target_roles IS NOT NULL AND array_length(target_roles, 1) > 0")
        ).fetchall()

        triggered = 0
        for row in rows:
            # Import here to avoid circular import
            from app.agents.job_discovery import discover_jobs_task
            discover_jobs_task.delay(row[0])
            triggered += 1

    return {"users_triggered": triggered}
