from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import User, Job, JobSkill, Application, ApplicationEvent, CoverLetter
from app.schemas import (
    JobCreate, JobResponse, JobMatchResponse,
    ApplicationResponse, ApplicationStatusUpdate,
    ResumeOptimizeRequest, ResumeResponse,
    CoverLetterResponse, ApplicationEventResponse, ApplicationNoteCreate,
)
from app.auth import get_current_user
from app.services.job_matcher import calculate_match_score
from app.services.resume_optimizer import optimize_resume_for_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    data: JobCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually add a job (MVP: user pastes job details)."""
    job = Job(**data.model_dump())
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    source: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Job).options(selectinload(Job.skills)).order_by(Job.scraped_at.desc())
    if source:
        query = query.where(Job.source == source)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Job).options(selectinload(Job.skills)).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/match/all", response_model=list[JobMatchResponse])
async def match_jobs(
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Score all jobs against user profile and return ranked list."""
    jobs_result = await db.execute(
        select(Job).options(selectinload(Job.skills)).order_by(Job.scraped_at.desc()).limit(200)
    )
    jobs = jobs_result.scalars().all()

    # Load user skills
    await db.refresh(user, ["skills", "certifications"])

    scored = []
    for job in jobs:
        score, reasons = calculate_match_score(user, job)
        scored.append(JobMatchResponse(job=job, match_score=score, match_reasons=reasons))

    scored.sort(key=lambda x: x.match_score, reverse=True)
    return scored[:limit]


@router.post("/{job_id}/optimize-resume", response_model=ResumeResponse)
async def optimize_resume(
    job_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate an optimized resume for a specific job."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    resume = await optimize_resume_for_job(user, job, db)
    return resume


# --- Application Tracking ---


@router.post("/{job_id}/apply", response_model=ApplicationResponse, status_code=201)
async def create_application(
    job_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Track that user applied to a job."""
    # Check job exists
    job_result = await db.execute(
        select(Job).options(selectinload(Job.skills)).where(Job.id == job_id)
    )
    job = job_result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if already applied
    existing = await db.execute(
        select(Application).where(
            Application.user_id == user.id, Application.job_id == job_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already applied to this job")

    await db.refresh(user, ["skills"])
    score, _ = calculate_match_score(user, job)

    from datetime import datetime, timezone
    app = Application(
        user_id=user.id,
        job_id=job_id,
        status="applied",
        match_score=score,
        applied_at=datetime.now(timezone.utc).replace(tzinfo=None),
        platform=job.source,
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)

    # Reload with relationships
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.job).selectinload(Job.skills))
        .where(Application.id == app.id)
    )
    return result.scalar_one()


@router.get("/applications/all", response_model=list[ApplicationResponse])
async def list_applications(
    status: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Application)
        .options(selectinload(Application.job).selectinload(Job.skills))
        .where(Application.user_id == user.id)
        .order_by(Application.created_at.desc())
    )
    if status:
        query = query.where(Application.status == status)
    result = await db.execute(query)
    return result.scalars().all()


@router.patch("/applications/{app_id}", response_model=ApplicationResponse)
async def update_application_status(
    app_id: int,
    data: ApplicationStatusUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Application)
        .options(selectinload(Application.job).selectinload(Job.skills))
        .where(Application.id == app_id, Application.user_id == user.id)
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    valid_statuses = {"pending", "applied", "interview", "rejected", "offer", "withdrawn", "auto_applying", "failed"}
    if data.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {valid_statuses}")

    old_status = app.status
    app.status = data.status

    # Log status change event
    event = ApplicationEvent(
        application_id=app.id,
        event_type="status_change",
        old_status=old_status,
        new_status=data.status,
    )
    db.add(event)

    await db.commit()
    await db.refresh(app)
    return app


# --- Cover Letter ---


@router.post("/{job_id}/cover-letter", response_model=CoverLetterResponse, status_code=201)
async def generate_cover_letter_endpoint(
    job_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a tailored cover letter for a specific job."""
    result = await db.execute(
        select(Job).options(selectinload(Job.skills)).where(Job.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    await db.refresh(user, ["skills"])

    # Get resume text if available
    from app.models import Resume
    from app.services.resume_parser import extract_text_from_resume
    resume_text = None
    resume_result = await db.execute(
        select(Resume).where(Resume.user_id == user.id, Resume.is_base.is_(True))
    )
    base_resume = resume_result.scalar_one_or_none()
    if base_resume:
        try:
            resume_text = extract_text_from_resume(base_resume.file_path)
        except Exception:
            pass

    from app.services.cover_letter_generator import generate_cover_letter
    content = generate_cover_letter(
        user_name=user.full_name,
        user_skills=[s.skill_name for s in user.skills],
        user_experience_years=user.years_of_experience,
        resume_text=resume_text,
        job_title=job.title,
        company=job.company,
        description=job.description or "",
        requirements=job.requirements,
    )

    # Generate PDF
    import os
    import uuid
    from app.services.pdf_generator import generate_cover_letter_pdf
    from app.config import get_settings
    settings = get_settings()

    os.makedirs(settings.upload_dir, exist_ok=True)
    filename = f"cover_letter_{user.id}_{job_id}_{uuid.uuid4().hex[:8]}.pdf"
    filepath = os.path.join(settings.upload_dir, filename)
    generate_cover_letter_pdf(content, filepath)

    cl = CoverLetter(
        user_id=user.id,
        job_id=job_id,
        content=content,
        file_path=filepath,
    )
    db.add(cl)
    await db.commit()
    await db.refresh(cl)
    return cl


# --- Application Timeline ---


@router.get("/applications/{app_id}/timeline", response_model=list[ApplicationEventResponse])
async def get_application_timeline(
    app_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get timeline events for an application."""
    # Verify ownership
    app_result = await db.execute(
        select(Application).where(Application.id == app_id, Application.user_id == user.id)
    )
    if not app_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Application not found")

    result = await db.execute(
        select(ApplicationEvent)
        .where(ApplicationEvent.application_id == app_id)
        .order_by(ApplicationEvent.created_at.desc())
    )
    return result.scalars().all()


@router.post("/applications/{app_id}/note", response_model=ApplicationEventResponse, status_code=201)
async def add_application_note(
    app_id: int,
    data: ApplicationNoteCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a note to an application timeline."""
    app_result = await db.execute(
        select(Application).where(Application.id == app_id, Application.user_id == user.id)
    )
    if not app_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Application not found")

    event = ApplicationEvent(
        application_id=app_id,
        event_type="note",
        note=data.note,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return event
