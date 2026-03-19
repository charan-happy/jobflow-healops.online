"""
JobFlow — FastAPI Backend
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
import os

from app.config import get_settings
from app.database import engine, Base
from app.routes import auth_routes, profile_routes, job_routes, agent_routes
from app.metrics import PrometheusMiddleware, metrics_endpoint

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (dev only — use Alembic in production)
    async with engine.begin() as conn:
        # Enable pgvector extension before creating tables
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title="JobFlow API",
    description="AI-powered job discovery, resume optimization, and application tracking",
    version="0.1.0",
    lifespan=lifespan,
)

# Prometheus metrics middleware (must be added before CORS)
app.add_middleware(PrometheusMiddleware)

# CORS — allow frontend origin + localhost for dev
_cors_origins = [settings.frontend_url]
if settings.env == "development":
    _cors_origins += ["http://localhost:3000", "http://localhost:3001"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics endpoint
app.add_route("/metrics", metrics_endpoint, methods=["GET"])

# Routes
app.include_router(auth_routes.router, prefix="/api")
app.include_router(profile_routes.router, prefix="/api")
app.include_router(job_routes.router, prefix="/api")
app.include_router(agent_routes.router, prefix="/api")

# Serve uploaded files (dev only)
os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "jobflow"}
