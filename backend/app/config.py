from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://jobflow:jobflow123@localhost:5432/jobflow"
    database_url_sync: str = "postgresql://jobflow:jobflow123@localhost:5432/jobflow"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM
    groq_api_key: str = ""

    # JWT
    jwt_secret: str = "change-this-to-a-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # Email
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # Storage
    upload_dir: str = "./uploads/resumes"

    # Frontend
    frontend_url: str = "http://localhost:3000"

    # Environment
    env: str = "development"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
