"""
Routes for AI agent operations — auto-discovery, scraping, interview prep.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import User, Job, JobSkill, AgentRun, Application, AutoApplyLog
from app.schemas import JobResponse, AgentRunResponse, AutoApplyStatusResponse
from app.auth import get_current_user
from app.agents.interview_prep import generate_interview_questions

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/discover", status_code=202)
async def trigger_discovery(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Trigger automatic job discovery based on user's profile.
    Uses target_roles + preferred_locations + target_portals to search job sites.
    Runs in background via Celery.
    """
    await db.refresh(user, ["skills"])

    if not user.target_roles:
        raise HTTPException(
            status_code=400,
            detail="No target roles configured. Go to Profile and add roles like 'DevOps Engineer', 'SRE', etc.",
        )
    if not user.preferred_locations:
        raise HTTPException(
            status_code=400,
            detail="No preferred locations set. Go to Profile and select at least one location.",
        )

    from app.agents.job_discovery import discover_jobs_task
    task = discover_jobs_task.delay(user.id)

    return {
        "message": f"Job discovery started for roles: {user.target_roles}",
        "portals": user.target_portals or ["linkedin", "naukri", "wellfound", "arc", "getonboard"],
        "locations": user.preferred_locations,
        "task_id": task.id,
    }


@router.get("/discover/status", response_model=list[AgentRunResponse])
async def discovery_status(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get recent discovery run statuses."""
    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.user_id == user.id, AgentRun.run_type == "discovery")
        .order_by(AgentRun.started_at.desc())
        .limit(10)
    )
    return result.scalars().all()


@router.post("/scrape-url", response_model=JobResponse, status_code=201)
async def scrape_single_url(
    url: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Scrape a single job URL and add to database (fallback for manual entry)."""
    from app.agents.job_discovery import scrape_full_jd, parse_jd_with_llm, _create_browser

    pw, browser, context = await _create_browser()
    try:
        page = await context.new_page()
        jd_text = await scrape_full_jd(page, url)
    finally:
        await browser.close()
        await pw.stop()

    if not jd_text:
        raise HTTPException(status_code=422, detail="Could not fetch page content")

    parsed = parse_jd_with_llm(jd_text)
    skills_list = parsed.pop("skills", [])

    job = Job(
        title=parsed.get("title", "Unknown"),
        company=parsed.get("company", "Unknown"),
        location=parsed.get("location"),
        salary_min=parsed.get("salary_min"),
        salary_max=parsed.get("salary_max"),
        description=parsed.get("description"),
        requirements=parsed.get("requirements"),
        job_url=url,
        source="manual",
    )
    db.add(job)
    await db.flush()

    for skill_name in skills_list:
        db.add(JobSkill(job_id=job.id, skill_name=skill_name))

    await db.commit()

    result = await db.execute(
        select(Job).options(selectinload(Job.skills)).where(Job.id == job.id)
    )
    return result.scalar_one()


@router.get("/interview-prep/{job_id}")
async def interview_prep(
    job_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate interview preparation questions for a specific job."""
    result = await db.execute(
        select(Job).options(selectinload(Job.skills)).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    skills = [s.skill_name for s in job.skills] if job.skills else []

    questions = generate_interview_questions(
        job_title=job.title,
        company=job.company,
        description=job.description or "",
        requirements=job.requirements,
        skills=skills,
    )

    return questions


# --- Auto Apply ---


@router.post("/auto-apply/{job_id}", status_code=202)
async def trigger_auto_apply(
    job_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger auto-apply for a job via Playwright. Runs in background via Celery."""
    result = await db.execute(
        select(Job).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.job_url:
        raise HTTPException(status_code=400, detail="Job has no URL to apply to")

    supported_portals = {"linkedin", "naukri"}
    if job.source not in supported_portals:
        raise HTTPException(
            status_code=400,
            detail=f"Auto-apply only supports: {', '.join(supported_portals)}. This job is from {job.source}.",
        )

    # Check if already applied
    existing = await db.execute(
        select(Application).where(
            Application.user_id == user.id, Application.job_id == job_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already applied to this job")

    from app.agents.auto_apply import auto_apply_job_task
    task = auto_apply_job_task.delay(user.id, job_id)

    return {
        "message": f"Auto-apply started for {job.title} at {job.company}",
        "task_id": task.id,
        "portal": job.source,
    }


@router.get("/auto-apply/{job_id}/status", response_model=AutoApplyStatusResponse | None)
async def auto_apply_status(
    job_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check auto-apply status for a specific job."""
    result = await db.execute(
        select(AutoApplyLog)
        .where(AutoApplyLog.user_id == user.id)
        .join(Application, Application.id == AutoApplyLog.application_id)
        .where(Application.job_id == job_id)
        .order_by(AutoApplyLog.created_at.desc())
        .limit(1)
    )
    log = result.scalar_one_or_none()
    if not log:
        return None
    return log
