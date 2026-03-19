from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime, timezone

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(20))
    linkedin_url = Column(String(500))
    years_of_experience = Column(Integer)
    salary_min = Column(Integer)  # in LPA
    salary_max = Column(Integer)
    preferred_locations = Column(ARRAY(String), default=[])
    target_roles = Column(ARRAY(String), default=[])  # e.g. ['DevOps Engineer', 'SRE', 'Platform Engineer']
    target_companies = Column(ARRAY(String), default=[])
    target_portals = Column(ARRAY(String), default=[])  # e.g. ['linkedin', 'naukri', 'indeed']
    email_notifications = Column(Boolean, default=True)
    notify_threshold = Column(Integer, default=60)  # min match score to trigger email
    profile_embedding = Column(Vector(384))
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    skills = relationship("UserSkill", back_populates="user", cascade="all, delete-orphan")
    certifications = relationship("UserCertification", back_populates="user", cascade="all, delete-orphan")
    resumes = relationship("Resume", back_populates="user", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="user", cascade="all, delete-orphan")


class UserSkill(Base):
    __tablename__ = "user_skills"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    skill_name = Column(String(100), nullable=False)
    years_experience = Column(Integer, default=0)
    proficiency = Column(String(20), default="intermediate")
    is_primary = Column(Boolean, default=False)

    user = relationship("User", back_populates="skills")


class UserCertification(Base):
    __tablename__ = "user_certifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    issuer = Column(String(255))
    year_obtained = Column(Integer)

    user = relationship("User", back_populates="certifications")


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(String(500), nullable=False)
    original_filename = Column(String(255))
    is_base = Column(Boolean, default=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User", back_populates="resumes")
    job = relationship("Job", back_populates="optimized_resumes")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(255))
    title = Column(String(500), nullable=False)
    company = Column(String(255), nullable=False)
    location = Column(String(255))
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    description = Column(Text)
    requirements = Column(Text)
    job_url = Column(String(1000))
    source = Column(String(50), nullable=False)  # linkedin, naukri, manual, etc.
    posted_date = Column(DateTime)
    scraped_at = Column(DateTime, default=utcnow)
    embedding = Column(Vector(384))

    __table_args__ = (
        UniqueConstraint("external_id", "source", name="uq_job_external_source"),
    )

    skills = relationship("JobSkill", back_populates="job", cascade="all, delete-orphan")
    optimized_resumes = relationship("Resume", back_populates="job")
    applications = relationship("Application", back_populates="job")


class JobSkill(Base):
    __tablename__ = "job_skills"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    skill_name = Column(String(100), nullable=False)

    job = relationship("Job", back_populates="skills")


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=True)
    status = Column(String(50), default="pending")
    match_score = Column(Float)
    applied_at = Column(DateTime)
    platform = Column(String(50))
    notes = Column(Text)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "job_id", name="uq_user_job_application"),
    )

    user = relationship("User", back_populates="applications")
    job = relationship("Job", back_populates="applications")
    resume = relationship("Resume")
    events = relationship("ApplicationEvent", back_populates="application", cascade="all, delete-orphan")


class ApplicationEvent(Base):
    __tablename__ = "application_events"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(String(50), nullable=False)  # status_change, note, reminder_sent
    old_status = Column(String(50))
    new_status = Column(String(50))
    note = Column(Text)
    created_at = Column(DateTime, default=utcnow)

    application = relationship("Application", back_populates="events")


class CoverLetter(Base):
    __tablename__ = "cover_letters"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    file_path = Column(String(500))
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=utcnow)

    user = relationship("User")
    job = relationship("Job")


class AutoApplyLog(Base):
    __tablename__ = "auto_apply_logs"

    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    portal = Column(String(50), nullable=False)
    step = Column(String(100))  # navigated, filled_form, uploaded_resume, submitted
    status = Column(String(20), default="pending")  # pending, in_progress, success, failed, unsupported
    error_message = Column(Text)
    screenshot_path = Column(String(500))
    created_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime)

    application = relationship("Application")


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50), nullable=False)  # job_alert, follow_up_reminder
    subject = Column(String(500))
    jobs_included = Column(Integer, default=0)
    sent_at = Column(DateTime, default=utcnow)
    status = Column(String(20), default="sent")  # sent, failed, skipped


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    run_type = Column(String(50), nullable=False)
    status = Column(String(20), default="running")
    jobs_found = Column(Integer, default=0)
    jobs_matched = Column(Integer, default=0)
    jobs_applied = Column(Integer, default=0)
    errors = Column(Text)
    started_at = Column(DateTime, default=utcnow)
    completed_at = Column(DateTime)
