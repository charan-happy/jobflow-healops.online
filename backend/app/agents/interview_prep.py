"""
Interview Preparation Agent — generates likely interview questions
based on job description, company, and tech stack.
Uses Groq free tier.
"""

from groq import Groq
from app.config import get_settings

settings = get_settings()


def generate_interview_questions(
    job_title: str,
    company: str,
    description: str,
    requirements: str | None = None,
    skills: list[str] | None = None,
) -> dict:
    """Generate interview preparation questions for a specific job."""
    client = Groq(api_key=settings.groq_api_key)

    skills_text = ", ".join(skills) if skills else "Not specified"

    prompt = f"""You are an interview preparation coach. Generate interview questions for this role.

JOB TITLE: {job_title}
COMPANY: {company}
JOB DESCRIPTION: {description[:2000]}
REQUIREMENTS: {requirements[:1000] if requirements else 'Not specified'}
KEY SKILLS: {skills_text}

Generate questions in these categories:

1. TECHNICAL QUESTIONS (5-7 questions)
   - Based on the specific skills and tech stack mentioned
   - Include system design questions if senior role

2. BEHAVIORAL QUESTIONS (3-5 questions)
   - STAR format questions relevant to the role
   - Company culture fit questions

3. ROLE-SPECIFIC QUESTIONS (3-5 questions)
   - About past experience related to this role
   - Scenario-based questions

4. QUESTIONS TO ASK THE INTERVIEWER (3-5 suggestions)
   - Smart questions that show preparation
   - About team, growth, tech decisions

For each question, provide a brief hint about what a good answer should cover.

Format as clean text with headers and numbered lists."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=3000,
    )

    return {
        "job_title": job_title,
        "company": company,
        "questions": response.choices[0].message.content,
    }
