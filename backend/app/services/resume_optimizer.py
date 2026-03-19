"""
Resume optimization service — uses LLM to tailor resume for a specific job.
Uses Groq free tier (llama-3.3-70b-versatile).
"""

import os
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from groq import Groq

from app.models import User, Job, Resume
from app.config import get_settings
from app.services.resume_parser import extract_text_from_resume
from app.services.pdf_generator import generate_resume_pdf

settings = get_settings()


def get_llm_client() -> Groq:
    return Groq(api_key=settings.groq_api_key)


async def optimize_resume_for_job(user: User, job: Job, db: AsyncSession) -> Resume:
    """
    1. Read user's base resume
    2. Send to LLM with job description
    3. Get optimized content
    4. Generate ATS-friendly PDF
    5. Save and return Resume record
    """
    # Get base resume
    result = await db.execute(
        select(Resume).where(Resume.user_id == user.id, Resume.is_base.is_(True))
    )
    base_resume = result.scalar_one_or_none()
    if not base_resume:
        raise ValueError("No base resume uploaded. Please upload your resume first.")

    # Extract text from resume
    resume_text = extract_text_from_resume(base_resume.file_path)

    # Build the optimization prompt
    jd_text = f"""
Title: {job.title}
Company: {job.company}
Location: {job.location or 'Not specified'}
Description: {job.description or 'Not provided'}
Requirements: {job.requirements or 'Not provided'}
""".strip()

    optimized_content = call_llm_for_optimization(resume_text, jd_text)

    # Generate PDF
    filename = f"{user.id}_optimized_{job.id}_{uuid.uuid4().hex[:8]}.pdf"
    filepath = os.path.join(settings.upload_dir, filename)
    os.makedirs(settings.upload_dir, exist_ok=True)
    generate_resume_pdf(optimized_content, filepath)

    # Count existing optimized versions for this job
    version_result = await db.execute(
        select(Resume).where(Resume.user_id == user.id, Resume.job_id == job.id)
    )
    version_count = len(version_result.scalars().all()) + 1

    # Save record
    resume = Resume(
        user_id=user.id,
        file_path=filepath,
        original_filename=f"resume_optimized_{job.company}_{job.title}.pdf",
        is_base=False,
        job_id=job.id,
        version=version_count,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return resume


def call_llm_for_optimization(resume_text: str, jd_text: str) -> str:
    """Call Groq LLM to optimize resume for the job description."""
    client = get_llm_client()

    system_prompt = """You are an expert resume optimizer. Your job is to take a candidate's
existing resume and a job description, then produce an optimized version of the resume.

STRICT RULES:
1. NEVER fabricate skills, experiences, or achievements the candidate doesn't have
2. Reorder sections to highlight the most relevant experience first
3. Mirror keywords from the job description naturally in bullet points
4. Quantify achievements where the original resume supports it
5. Use strong action verbs: Led, Built, Deployed, Automated, Reduced, Managed, etc.
6. Keep the resume to 1-2 pages worth of content
7. Use clean, ATS-friendly formatting with standard section headings
8. Focus on the intersection of the candidate's experience and the job requirements

OUTPUT FORMAT:
Return ONLY the optimized resume content in clean text format with these sections:
- FULL NAME
- Contact info line
- PROFESSIONAL SUMMARY (2-3 lines tailored to this role)
- SKILLS (relevant skills highlighted first)
- EXPERIENCE (bullet points optimized for this JD)
- CERTIFICATIONS (if any)
- EDUCATION

Do NOT include any commentary or explanation. Just the resume content."""

    user_prompt = f"""CURRENT RESUME:
{resume_text}

---

TARGET JOB DESCRIPTION:
{jd_text}

---

Generate the optimized resume now."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        max_tokens=3000,
    )

    return response.choices[0].message.content
