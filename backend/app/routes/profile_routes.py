from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import os
import uuid

from app.database import get_db
from app.models import User, UserSkill, UserCertification, Resume
from app.schemas import ProfileUpdate, UserResponse, ResumeResponse
from app.auth import get_current_user
from app.config import get_settings

router = APIRouter(prefix="/profile", tags=["profile"])
settings = get_settings()


@router.put("", response_model=UserResponse)
async def update_profile(
    data: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Update simple fields
    for field in ["full_name", "phone", "linkedin_url", "years_of_experience",
                  "salary_min", "salary_max", "preferred_locations",
                  "target_roles", "target_companies", "target_portals",
                  "email_notifications", "notify_threshold"]:
        value = getattr(data, field, None)
        if value is not None:
            setattr(user, field, value)

    # Replace skills if provided
    if data.skills is not None:
        # Delete existing
        existing_skills = await db.execute(
            select(UserSkill).where(UserSkill.user_id == user.id)
        )
        for skill in existing_skills.scalars():
            await db.delete(skill)

        # Add new
        for s in data.skills:
            db.add(UserSkill(user_id=user.id, **s.model_dump()))

    # Replace certifications if provided
    if data.certifications is not None:
        existing_certs = await db.execute(
            select(UserCertification).where(UserCertification.user_id == user.id)
        )
        for cert in existing_certs.scalars():
            await db.delete(cert)

        for c in data.certifications:
            db.add(UserCertification(user_id=user.id, **c.model_dump()))

    await db.commit()

    # Regenerate profile embedding if roles or skills changed
    if data.target_roles is not None or data.skills is not None:
        try:
            from app.services.embedding_service import generate_profile_embedding
            await db.refresh(user, ["skills", "certifications"])
            embedding = generate_profile_embedding(
                roles=user.target_roles or [],
                skills=[s.skill_name for s in user.skills],
                experience_years=user.years_of_experience,
                certifications=[c.name for c in user.certifications] if user.certifications else [],
            )
            if embedding:
                user.profile_embedding = embedding
                await db.commit()
        except Exception:
            pass  # Embedding generation is optional

    # Eagerly load relationships for response serialization
    result = await db.execute(
        select(User)
        .options(selectinload(User.skills), selectinload(User.certifications))
        .where(User.id == user.id)
    )
    return result.scalar_one()


@router.post("/resume", response_model=ResumeResponse, status_code=201)
async def upload_resume(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Validate file type
    allowed_types = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files allowed")

    # Validate file size (5MB max)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")

    # Save file
    ext = os.path.splitext(file.filename)[1] if file.filename else ".pdf"
    filename = f"{user.id}_{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(settings.upload_dir, filename)

    os.makedirs(settings.upload_dir, exist_ok=True)
    with open(filepath, "wb") as f:
        f.write(content)

    # Mark old base resumes as non-base
    existing = await db.execute(
        select(Resume).where(Resume.user_id == user.id, Resume.is_base.is_(True))
    )
    for old_resume in existing.scalars():
        old_resume.is_base = False

    resume = Resume(
        user_id=user.id,
        file_path=filepath,
        original_filename=file.filename,
        is_base=True,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return resume


@router.get("/resumes", response_model=list[ResumeResponse])
async def list_resumes(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Resume).where(Resume.user_id == user.id).order_by(Resume.created_at.desc())
    )
    return result.scalars().all()


@router.post("/test-notification")
async def test_notification(
    user: User = Depends(get_current_user),
):
    """Send a test email notification to verify SMTP works."""
    from app.services.email_service import send_email_sync, build_job_alert_html

    sample_jobs = [{
        "title": "Senior DevOps Engineer (Test)",
        "company": "Test Company",
        "location": "Bangalore",
        "source": "linkedin",
        "match_score": 85,
        "job_url": f"{settings.frontend_url}/jobs",
    }]

    html = build_job_alert_html(user.full_name, sample_jobs)
    success = send_email_sync(user.email, "Test Notification - JobFlow", html)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to send email. Check SMTP settings in .env")
    return {"message": f"Test email sent to {user.email}"}
