"""
Auto-Apply Agent — uses Playwright to fill and submit job applications automatically.

Supports:
- LinkedIn Easy Apply
- Naukri Quick Apply

Each portal has its own applicator function registered via PORTAL_APPLICATORS.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone

from playwright.async_api import Page

from app.config import get_settings
from app.agents.job_discovery import _create_browser

settings = get_settings()
logger = logging.getLogger(__name__)

PORTAL_APPLICATORS = {}


def _register_applicator(name: str):
    def decorator(fn):
        PORTAL_APPLICATORS[name] = fn
        return fn
    return decorator


@_register_applicator("linkedin")
async def apply_linkedin_easy(
    page: Page, job_url: str, user_data: dict, resume_path: str
) -> tuple[bool, str, str | None]:
    """
    LinkedIn Easy Apply automation.
    Returns (success, step_reached, error_message).
    """
    try:
        await page.goto(job_url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

        # Look for Easy Apply button
        easy_apply_btn = await page.query_selector(
            "button.jobs-apply-button, "
            "button[aria-label*='Easy Apply'], "
            "button[class*='jobs-apply'], "
            "button:has-text('Easy Apply')"
        )

        if not easy_apply_btn:
            # Check if it's an external apply (no Easy Apply available)
            external_btn = await page.query_selector(
                "button:has-text('Apply'), a:has-text('Apply on company')"
            )
            if external_btn:
                return False, "external_apply_only", "This job requires applying on the company website directly"
            return False, "no_apply_button", "Could not find Easy Apply or Apply button"

        await easy_apply_btn.click()
        await page.wait_for_timeout(2000)

        # Handle multi-step modal
        max_steps = 8
        for step in range(max_steps):
            # Fill any visible text inputs
            inputs = await page.query_selector_all(
                ".jobs-easy-apply-modal input[type='text']:visible, "
                ".jobs-easy-apply-modal input[type='tel']:visible, "
                ".jobs-easy-apply-modal input[type='email']:visible"
            )
            for inp in inputs:
                label = await inp.evaluate("el => el.closest('.fb-dash-form-element')?.querySelector('label')?.innerText || el.getAttribute('aria-label') || ''")
                label_lower = label.lower()
                value = await inp.input_value()
                if value:
                    continue  # Already filled

                if "email" in label_lower:
                    await inp.fill(user_data.get("email", ""))
                elif "phone" in label_lower or "mobile" in label_lower:
                    await inp.fill(user_data.get("phone", ""))
                elif "name" in label_lower and "first" in label_lower:
                    parts = user_data.get("full_name", "").split()
                    await inp.fill(parts[0] if parts else "")
                elif "name" in label_lower and "last" in label_lower:
                    parts = user_data.get("full_name", "").split()
                    await inp.fill(parts[-1] if len(parts) > 1 else "")
                elif "city" in label_lower or "location" in label_lower:
                    locations = user_data.get("preferred_locations", [])
                    await inp.fill(locations[0] if locations else "")

            # Handle file upload (resume)
            file_input = await page.query_selector(
                ".jobs-easy-apply-modal input[type='file']"
            )
            if file_input and resume_path and os.path.exists(resume_path):
                await file_input.set_input_files(resume_path)
                await page.wait_for_timeout(1000)

            # Look for Submit button
            submit_btn = await page.query_selector(
                ".jobs-easy-apply-modal button[aria-label*='Submit'], "
                ".jobs-easy-apply-modal button:has-text('Submit application'), "
                ".jobs-easy-apply-modal button:has-text('Submit')"
            )
            if submit_btn:
                btn_text = (await submit_btn.inner_text()).strip().lower()
                if "submit" in btn_text:
                    await submit_btn.click()
                    await page.wait_for_timeout(2000)

                    # Check for success
                    success_el = await page.query_selector(
                        "[class*='post-apply'], "
                        "h2:has-text('Application sent'), "
                        "[class*='success']"
                    )
                    if success_el:
                        return True, "submitted", None
                    return True, "submit_clicked", None

            # Look for Next button
            next_btn = await page.query_selector(
                ".jobs-easy-apply-modal button[aria-label*='next'], "
                ".jobs-easy-apply-modal button[aria-label*='Next'], "
                ".jobs-easy-apply-modal button[aria-label*='Continue'], "
                ".jobs-easy-apply-modal button:has-text('Next'), "
                ".jobs-easy-apply-modal button:has-text('Review')"
            )
            if next_btn:
                await next_btn.click()
                await page.wait_for_timeout(1500)
            else:
                break

        return False, f"stuck_at_step_{step}", "Could not complete all form steps"

    except Exception as e:
        logger.error(f"LinkedIn Easy Apply failed: {e}")
        return False, "error", str(e)[:500]


@_register_applicator("naukri")
async def apply_naukri(
    page: Page, job_url: str, user_data: dict, resume_path: str
) -> tuple[bool, str, str | None]:
    """
    Naukri Apply automation.
    Returns (success, step_reached, error_message).
    """
    try:
        await page.goto(job_url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(3000)

        # Look for Apply button
        apply_btn = await page.query_selector(
            "button#apply-button, "
            "button.apply-button, "
            "button[class*='apply-btn'], "
            "button:has-text('Apply'), "
            "a:has-text('Apply on company')"
        )

        if not apply_btn:
            return False, "no_apply_button", "Could not find Apply button on Naukri"

        await apply_btn.click()
        await page.wait_for_timeout(3000)

        # Naukri often opens a chatbot/form dialog
        # Check if resume upload is needed
        file_input = await page.query_selector("input[type='file']")
        if file_input and resume_path and os.path.exists(resume_path):
            await file_input.set_input_files(resume_path)
            await page.wait_for_timeout(1500)

        # Fill any additional fields
        inputs = await page.query_selector_all("input[type='text']:visible, input[type='tel']:visible")
        for inp in inputs:
            placeholder = await inp.get_attribute("placeholder") or ""
            value = await inp.input_value()
            if value:
                continue
            placeholder_lower = placeholder.lower()
            if "name" in placeholder_lower:
                await inp.fill(user_data.get("full_name", ""))
            elif "email" in placeholder_lower:
                await inp.fill(user_data.get("email", ""))
            elif "phone" in placeholder_lower or "mobile" in placeholder_lower:
                await inp.fill(user_data.get("phone", ""))

        # Click submit/apply
        submit = await page.query_selector(
            "button:has-text('Submit'), "
            "button:has-text('Apply'), "
            "button[type='submit']"
        )
        if submit:
            await submit.click()
            await page.wait_for_timeout(2000)
            return True, "submitted", None

        return False, "no_submit_button", "Could not find submit button after filling form"

    except Exception as e:
        logger.error(f"Naukri Apply failed: {e}")
        return False, "error", str(e)[:500]


async def auto_apply_to_job(
    user_data: dict,
    portal: str,
    job_url: str,
    resume_path: str | None,
) -> tuple[bool, str, str | None]:
    """Run auto-apply for a single job. Returns (success, step, error)."""
    applicator = PORTAL_APPLICATORS.get(portal)
    if not applicator:
        return False, "unsupported", f"Auto-apply not supported for portal: {portal}"

    pw, browser, context = await _create_browser()
    try:
        page = await context.new_page()
        success, step, error = await applicator(page, job_url, user_data, resume_path or "")
        return success, step, error
    finally:
        await browser.close()
        await pw.stop()


# --- Celery task ---

from app.worker import celery_app


@celery_app.task(name="auto_apply_job", bind=True, max_retries=1, time_limit=300, soft_time_limit=270)
def auto_apply_job_task(self, user_id: int, job_id: int):
    """Celery task: auto-apply to a job for a user."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from app.models import User, Job, Application, AutoApplyLog, Resume

    engine = create_engine(settings.database_url_sync)

    with Session(engine) as db:
        user = db.query(User).filter(User.id == user_id).first()
        job = db.query(Job).filter(Job.id == job_id).first()

        if not user or not job:
            return {"error": "User or job not found"}

        if not job.job_url:
            return {"error": "Job has no URL"}

        portal = job.source
        if portal not in PORTAL_APPLICATORS:
            return {"error": f"Auto-apply not supported for {portal}"}

        # Get or create application
        app = db.query(Application).filter(
            Application.user_id == user_id,
            Application.job_id == job_id,
        ).first()

        if not app:
            app = Application(
                user_id=user_id,
                job_id=job_id,
                status="auto_applying",
                platform=portal,
            )
            db.add(app)
            db.flush()
        else:
            app.status = "auto_applying"
            db.flush()

        # Create log entry
        log = AutoApplyLog(
            application_id=app.id,
            user_id=user_id,
            portal=portal,
            status="in_progress",
            step="starting",
        )
        db.add(log)
        db.commit()

        # Get resume path
        resume = db.query(Resume).filter(
            Resume.user_id == user_id,
            Resume.job_id == job_id,
        ).first()
        if not resume:
            resume = db.query(Resume).filter(
                Resume.user_id == user_id,
                Resume.is_base.is_(True),
            ).first()

        resume_path = resume.file_path if resume else None

        # Build user data dict
        user_data = {
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone or "",
            "linkedin_url": user.linkedin_url or "",
            "years_of_experience": user.years_of_experience,
            "preferred_locations": user.preferred_locations or [],
        }

        # Run auto-apply
        try:
            success, step, error = asyncio.run(
                auto_apply_to_job(user_data, portal, job.job_url, resume_path)
            )

            log.step = step
            log.status = "success" if success else "failed"
            log.error_message = error
            log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)

            if success:
                app.status = "applied"
                app.applied_at = datetime.now(timezone.utc).replace(tzinfo=None)
            else:
                app.status = "failed"

            db.commit()
            return {"success": success, "step": step, "error": error}

        except Exception as e:
            log.status = "failed"
            log.error_message = str(e)[:500]
            log.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            app.status = "failed"
            db.commit()
            raise self.retry(exc=e, countdown=30)
