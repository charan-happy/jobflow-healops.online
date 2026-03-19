"""
Follow-up reminder agent — checks for stale applications and sends email reminders.
Runs daily via Celery Beat at 9 AM IST.
"""

import logging
from datetime import datetime, timezone, timedelta

from app.config import get_settings
from app.worker import celery_app

settings = get_settings()
logger = logging.getLogger(__name__)


@celery_app.task(name="check_follow_up_reminders")
def check_follow_up_reminders():
    """
    Find applications with status='applied' for > 7 days without follow-up.
    Send reminder emails.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.models import User, Application, ApplicationEvent, NotificationLog, Job
    from app.services.email_service import send_email_sync

    engine = create_engine(settings.database_url_sync)

    with Session(engine) as db:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)

        # Find stale applications: applied > 7 days ago, still in "applied" status
        stale_apps = (
            db.query(Application)
            .filter(
                Application.status == "applied",
                Application.applied_at < cutoff,
                Application.applied_at.isnot(None),
            )
            .all()
        )

        if not stale_apps:
            logger.info("No stale applications found for follow-up")
            return {"reminders_sent": 0}

        # Group by user
        user_apps: dict[int, list] = {}
        for app in stale_apps:
            # Check if we already sent a reminder in the last 3 days
            recent_reminder = (
                db.query(ApplicationEvent)
                .filter(
                    ApplicationEvent.application_id == app.id,
                    ApplicationEvent.event_type == "reminder_sent",
                    ApplicationEvent.created_at > datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=3),
                )
                .first()
            )
            if recent_reminder:
                continue

            if app.user_id not in user_apps:
                user_apps[app.user_id] = []
            user_apps[app.user_id].append(app)

        total_sent = 0
        for user_id, apps in user_apps.items():
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.email_notifications:
                continue

            # Build reminder email
            app_lines = ""
            for app in apps:
                job = db.query(Job).filter(Job.id == app.job_id).first()
                if not job:
                    continue
                days_ago = (datetime.now(timezone.utc).replace(tzinfo=None) - app.applied_at).days
                app_lines += f"""
                <tr>
                  <td style="padding:10px 16px;color:#e8e8f0;font-weight:500;">{job.title}</td>
                  <td style="padding:10px 16px;color:#9ca3af;">{job.company}</td>
                  <td style="padding:10px 16px;color:#f59e0b;">{days_ago} days ago</td>
                </tr>"""

            if not app_lines:
                continue

            html = f"""
            <!DOCTYPE html>
            <html>
            <body style="margin:0;padding:0;background:#0a0a0f;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
              <div style="max-width:600px;margin:0 auto;padding:32px 16px;">
                <div style="text-align:center;margin-bottom:24px;">
                  <span style="color:#6366f1;font-weight:700;font-size:20px;">Job</span>
                  <span style="color:#e8e8f0;font-weight:600;font-size:20px;">Flow</span>
                </div>
                <div style="background:#1a1a2e;border:1px solid #2a2a3e;border-radius:12px;padding:24px;margin-bottom:24px;">
                  <h2 style="color:#e8e8f0;margin:0 0 8px;">Follow-up Reminder</h2>
                  <p style="color:#9ca3af;margin:0;font-size:14px;">
                    Hi {user.full_name}, these applications haven't had activity in over a week.
                    Consider following up!
                  </p>
                </div>
                <div style="background:#1a1a2e;border:1px solid #2a2a3e;border-radius:12px;overflow:hidden;">
                  <table style="width:100%;border-collapse:collapse;">
                    <thead>
                      <tr style="border-bottom:1px solid #2a2a3e;">
                        <th style="padding:10px 16px;text-align:left;color:#6b7280;font-size:12px;text-transform:uppercase;">Job</th>
                        <th style="padding:10px 16px;text-align:left;color:#6b7280;font-size:12px;text-transform:uppercase;">Company</th>
                        <th style="padding:10px 16px;text-align:left;color:#6b7280;font-size:12px;text-transform:uppercase;">Applied</th>
                      </tr>
                    </thead>
                    <tbody>{app_lines}</tbody>
                  </table>
                </div>
                <div style="text-align:center;margin-top:24px;">
                  <a href="{settings.frontend_url}/jobs" style="display:inline-block;background:#6366f1;color:#fff;padding:12px 32px;border-radius:8px;text-decoration:none;font-weight:600;">
                    View Applications
                  </a>
                </div>
              </div>
            </body>
            </html>
            """

            subject = f"Follow-up reminder: {len(apps)} application{'s' if len(apps) != 1 else ''} pending"
            success = send_email_sync(user.email, subject, html)

            if success:
                total_sent += 1
                # Log reminder events
                for app in apps:
                    db.add(ApplicationEvent(
                        application_id=app.id,
                        event_type="reminder_sent",
                        note="Follow-up reminder email sent",
                    ))
                db.add(NotificationLog(
                    user_id=user_id,
                    type="follow_up_reminder",
                    subject=subject,
                    jobs_included=len(apps),
                    status="sent",
                ))
                db.commit()

        logger.info(f"Follow-up reminders: sent to {total_sent} users")
        return {"reminders_sent": total_sent}
