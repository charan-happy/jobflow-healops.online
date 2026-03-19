"""
Notification service — decides when and what to notify users about.
Called from Celery tasks after job discovery stores new jobs.
"""

import logging
from sqlalchemy.orm import Session

from app.models import User, Job, JobSkill, NotificationLog
from app.services.job_matcher import calculate_match_score
from app.services.email_service import send_email_sync, build_job_alert_html

logger = logging.getLogger(__name__)


def notify_user_new_jobs(db: Session, user: User, new_job_ids: list[int]):
    """
    Score newly discovered jobs against user profile, email if any meet threshold.

    Called from Celery task (sync DB session).
    """
    if not user.email_notifications:
        return

    threshold = user.notify_threshold or 60

    # Load new jobs with skills
    jobs = db.query(Job).filter(Job.id.in_(new_job_ids)).all()
    if not jobs:
        return

    # Score each job
    matched_jobs = []
    for job in jobs:
        score, reasons = calculate_match_score(user, job)
        if score >= threshold:
            matched_jobs.append({
                "title": job.title,
                "company": job.company,
                "location": job.location,
                "source": job.source,
                "match_score": score,
                "job_url": job.job_url,
                "reasons": reasons,
            })

    if not matched_jobs:
        return

    # Sort by score descending
    matched_jobs.sort(key=lambda x: x["match_score"], reverse=True)

    # Build and send email
    subject = f"{len(matched_jobs)} new job match{'es' if len(matched_jobs) != 1 else ''} found!"
    html = build_job_alert_html(user.full_name, matched_jobs)
    success = send_email_sync(user.email, subject, html)

    # Log notification
    log = NotificationLog(
        user_id=user.id,
        type="job_alert",
        subject=subject,
        jobs_included=len(matched_jobs),
        status="sent" if success else "failed",
    )
    db.add(log)
    db.commit()

    if success:
        logger.info(
            f"Notified user {user.id} ({user.email}) about {len(matched_jobs)} matching jobs"
        )
    else:
        logger.warning(f"Failed to notify user {user.id}")
