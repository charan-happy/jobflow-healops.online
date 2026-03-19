from pydantic import BaseModel, EmailStr, Field
from datetime import datetime


# --- Auth ---
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- User Profile ---
class SkillCreate(BaseModel):
    skill_name: str
    years_experience: int = 0
    proficiency: str = "intermediate"
    is_primary: bool = False


class CertificationCreate(BaseModel):
    name: str
    issuer: str | None = None
    year_obtained: int | None = None


class ProfileUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    linkedin_url: str | None = None
    years_of_experience: int | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    preferred_locations: list[str] | None = None
    target_roles: list[str] | None = None
    target_companies: list[str] | None = None
    target_portals: list[str] | None = None
    email_notifications: bool | None = None
    notify_threshold: int | None = None
    skills: list[SkillCreate] | None = None
    certifications: list[CertificationCreate] | None = None


class SkillResponse(BaseModel):
    id: int
    skill_name: str
    years_experience: int
    proficiency: str
    is_primary: bool

    model_config = {"from_attributes": True}


class CertificationResponse(BaseModel):
    id: int
    name: str
    issuer: str | None
    year_obtained: int | None

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    phone: str | None
    linkedin_url: str | None
    years_of_experience: int | None
    salary_min: int | None
    salary_max: int | None
    preferred_locations: list[str]
    target_roles: list[str]
    target_companies: list[str]
    target_portals: list[str]
    email_notifications: bool
    notify_threshold: int
    skills: list[SkillResponse]
    certifications: list[CertificationResponse]
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Jobs ---
class JobCreate(BaseModel):
    title: str
    company: str
    location: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    description: str | None = None
    requirements: str | None = None
    job_url: str | None = None
    source: str = "manual"


class JobURLInput(BaseModel):
    url: str
    source: str = "manual"


class JobSkillResponse(BaseModel):
    skill_name: str

    model_config = {"from_attributes": True}


class JobResponse(BaseModel):
    id: int
    title: str
    company: str
    location: str | None
    salary_min: int | None
    salary_max: int | None
    description: str | None
    requirements: str | None
    job_url: str | None
    source: str
    posted_date: datetime | None
    skills: list[JobSkillResponse]
    scraped_at: datetime

    model_config = {"from_attributes": True}


class JobMatchResponse(BaseModel):
    job: JobResponse
    match_score: float
    match_reasons: list[str]


# --- Applications ---
class ApplicationResponse(BaseModel):
    id: int
    job: JobResponse
    status: str
    match_score: float | None
    applied_at: datetime | None
    platform: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApplicationStatusUpdate(BaseModel):
    status: str


# --- Resume ---
class ResumeResponse(BaseModel):
    id: int
    file_path: str
    original_filename: str | None
    is_base: bool
    job_id: int | None
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Agent ---
class AgentRunResponse(BaseModel):
    id: int
    run_type: str
    status: str
    jobs_found: int
    jobs_matched: int
    jobs_applied: int
    errors: str | None
    started_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ResumeOptimizeRequest(BaseModel):
    job_id: int


# --- Cover Letter ---
class CoverLetterResponse(BaseModel):
    id: int
    job_id: int
    content: str
    file_path: str | None
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Application Events ---
class ApplicationEventResponse(BaseModel):
    id: int
    event_type: str
    old_status: str | None
    new_status: str | None
    note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApplicationNoteCreate(BaseModel):
    note: str


# --- Auto Apply ---
class AutoApplyStatusResponse(BaseModel):
    application_id: int
    status: str
    step: str | None
    error_message: str | None
    portal: str

    model_config = {"from_attributes": True}
