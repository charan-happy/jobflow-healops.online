"""
Cover letter generation service — uses Groq LLM to create tailored cover letters.
"""

import logging
from groq import Groq
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def generate_cover_letter(
    user_name: str,
    user_skills: list[str],
    user_experience_years: int | None,
    resume_text: str | None,
    job_title: str,
    company: str,
    description: str,
    requirements: str | None = None,
) -> str:
    """Generate a tailored cover letter using Groq LLM."""
    client = Groq(api_key=settings.groq_api_key)

    skills_str = ", ".join(user_skills) if user_skills else "Not specified"
    exp_str = f"{user_experience_years} years" if user_experience_years else "Not specified"
    resume_section = f"\nCANDIDATE RESUME EXCERPT:\n{resume_text[:2000]}\n" if resume_text else ""

    prompt = f"""Write a professional cover letter for this job application.

CANDIDATE:
- Name: {user_name}
- Key Skills: {skills_str}
- Experience: {exp_str}
{resume_section}
JOB TITLE: {job_title}
COMPANY: {company}
JOB DESCRIPTION:
{description[:2000]}

{f"REQUIREMENTS: {requirements[:1000]}" if requirements else ""}

RULES:
1. Keep it to 3-4 paragraphs, under 400 words
2. Opening paragraph: Express genuine interest in the specific role and company
3. Body paragraphs: Connect candidate's skills and experience directly to job requirements. Use specific examples
4. Closing paragraph: Express enthusiasm and call to action
5. Do NOT fabricate experience or skills the candidate doesn't have
6. Do NOT use generic filler phrases like "I am writing to express my interest"
7. Be specific to THIS role and THIS company — not a generic template
8. Professional but conversational tone
9. Start with "Dear Hiring Manager," and end with "Sincerely,\\n{user_name}"

Return ONLY the cover letter text, no extra commentary."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=2000,
    )

    return response.choices[0].message.content
