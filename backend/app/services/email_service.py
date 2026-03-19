"""
Email service — sends emails via SMTP (Gmail free tier).
Sync version for Celery tasks.
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def send_email_sync(to_email: str, subject: str, html_body: str) -> bool:
    """Send an email synchronously. Returns True on success."""
    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("SMTP not configured (smtp_user/smtp_password empty), skipping email")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = f"JobFlow <{settings.smtp_user}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        logger.info(f"Email sent to {to_email}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


def build_job_alert_html(user_name: str, matched_jobs: list[dict]) -> str:
    """Build HTML email for job alert notification.

    Each job dict: {title, company, location, source, match_score, job_url}
    """
    job_rows = ""
    for job in matched_jobs:
        score = int(job["match_score"])
        score_color = "#10b981" if score >= 75 else "#f59e0b" if score >= 50 else "#ef4444"
        source = job.get("source", "").capitalize()
        location = job.get("location") or "Not specified"
        job_url = job.get("job_url") or "#"

        job_rows += f"""
        <tr>
          <td style="padding:12px 16px;">
            <div style="font-weight:600;color:#e8e8f0;">{job["title"]}</div>
            <div style="font-size:13px;color:#9ca3af;margin-top:2px;">{job["company"]} &bull; {location}</div>
          </td>
          <td style="padding:12px 16px;text-align:center;">
            <span style="background:{score_color}22;color:{score_color};padding:4px 10px;border-radius:12px;font-weight:600;font-size:13px;">
              {score}%
            </span>
          </td>
          <td style="padding:12px 16px;text-align:center;">
            <span style="background:#6366f122;color:#6366f1;padding:4px 10px;border-radius:12px;font-size:12px;">
              {source}
            </span>
          </td>
          <td style="padding:12px 16px;text-align:center;">
            <a href="{job_url}" style="color:#6366f1;text-decoration:none;font-size:13px;">View &rarr;</a>
          </td>
        </tr>"""

    return f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin:0;padding:0;background:#0a0a0f;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
      <div style="max-width:600px;margin:0 auto;padding:32px 16px;">
        <div style="text-align:center;margin-bottom:24px;">
          <span style="color:#6366f1;font-weight:700;font-size:20px;">Job</span>
          <span style="color:#e8e8f0;font-weight:600;font-size:20px;">Flow</span>
        </div>

        <div style="background:#1a1a2e;border:1px solid #2a2a3e;border-radius:12px;padding:24px;margin-bottom:24px;">
          <h2 style="color:#e8e8f0;margin:0 0 8px;">New Job Matches Found!</h2>
          <p style="color:#9ca3af;margin:0;font-size:14px;">
            Hi {user_name}, we found {len(matched_jobs)} new job{"s" if len(matched_jobs) != 1 else ""}
            matching your profile.
          </p>
        </div>

        <div style="background:#1a1a2e;border:1px solid #2a2a3e;border-radius:12px;overflow:hidden;">
          <table style="width:100%;border-collapse:collapse;">
            <thead>
              <tr style="border-bottom:1px solid #2a2a3e;">
                <th style="padding:12px 16px;text-align:left;color:#6b7280;font-size:12px;text-transform:uppercase;">Job</th>
                <th style="padding:12px 16px;text-align:center;color:#6b7280;font-size:12px;text-transform:uppercase;">Match</th>
                <th style="padding:12px 16px;text-align:center;color:#6b7280;font-size:12px;text-transform:uppercase;">Source</th>
                <th style="padding:12px 16px;text-align:center;color:#6b7280;font-size:12px;text-transform:uppercase;">Link</th>
              </tr>
            </thead>
            <tbody>
              {job_rows}
            </tbody>
          </table>
        </div>

        <div style="text-align:center;margin-top:24px;">
          <a href="{settings.frontend_url}/jobs" style="display:inline-block;background:#6366f1;color:#fff;padding:12px 32px;border-radius:8px;text-decoration:none;font-weight:600;">
            View All Jobs
          </a>
        </div>

        <div style="text-align:center;margin-top:24px;color:#6b7280;font-size:12px;">
          You're receiving this because you have email notifications enabled.
          <br>Update your preferences in Profile Settings.
        </div>
      </div>
    </body>
    </html>
    """
