# JobFlow

## Project Overview
AI-powered job application automation platform hosted at **jobflow.healops.online**. Discovers jobs from multiple portals, matches them against user profiles, optimizes resumes with LLM, generates ATS-friendly PDFs, and prepares interview questions. Built for ₹0/month using free-tier technologies.

## Tech Stack
- **Backend**: FastAPI (Python 3.12), SQLAlchemy async, Pydantic
- **Frontend**: Next.js 15 (TypeScript), React 19
- **Database**: PostgreSQL 16 + pgvector (vector similarity search)
- **LLM**: Groq free tier (llama-3.3-70b-versatile)
- **Task Queue**: Celery + Redis
- **Browser Automation**: Playwright (headless Chromium)
- **PDF Generation**: ReportLab
- **Auth**: JWT (python-jose) + bcrypt

## Architecture
```
Frontend (Next.js :3001) → Backend (FastAPI :8001) → PostgreSQL (:5433)
                                  ↓
                           Celery Workers → Playwright (scraping)
                                  ↓            ↓
                              Redis (:6380)   Groq LLM (JD parsing)
```

## Running the Project

### Docker Compose (recommended)
```bash
docker compose up --build
```

### Services & Ports
| Service | Container | Port |
|---------|-----------|------|
| Frontend | jobflow-frontend | 3001 → 3000 |
| Backend | jobflow-backend | 8001 → 8000 |
| PostgreSQL | jobflow-db | 5433 → 5432 |
| Redis | jobflow-redis | 6380 → 6379 |
| Celery Worker | jobflow-celery | — |
| Celery Beat | jobflow-beat | — |

### Manual Development
```bash
# Start infra
docker compose up -d db redis

# Backend
cd backend && source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev

# Workers (optional)
celery -A app.worker.celery_app worker --loglevel=info
celery -A app.worker.celery_app beat --loglevel=info
```

## Project Structure

### Backend (`/backend/app/`)
- `main.py` — FastAPI app, CORS, route registration, DB init
- `config.py` — Pydantic settings from .env
- `database.py` — AsyncPG engine, session dependency
- `models.py` — SQLAlchemy models (User, Job, Application, Resume, AgentRun, etc.)
- `schemas.py` — Pydantic request/response schemas
- `auth.py` — JWT auth, password hashing, `get_current_user` dependency
- `worker.py` — Celery config, beat schedule (discovery every 6h)
- `routes/` — API route modules:
  - `auth_routes.py` — `/api/auth` (register, login, me)
  - `profile_routes.py` — `/api/profile` (update profile, upload resume)
  - `job_routes.py` — `/api/jobs` (CRUD, matching, apply, optimize resume)
  - `agent_routes.py` — `/api/agent` (discover, scrape-url, interview-prep)
- `services/` — Business logic:
  - `job_matcher.py` — Rule-based match scoring (skills 40pts, location 20pts, salary 20pts, experience 20pts)
  - `resume_optimizer.py` — LLM-powered resume rewriting + PDF generation
  - `resume_parser.py` — PDF/DOCX text extraction
  - `pdf_generator.py` — ReportLab ATS-friendly PDF builder
- `agents/` — AI agent modules:
  - `job_discovery.py` — Multi-portal scraping (LinkedIn, Naukri, Indeed, Wellfound, Arc, Torre, GetOnBoard, Google Jobs), LLM JD parsing, Celery task
  - `interview_prep.py` — Interview question generation via Groq
  - `follow_up_agent.py` — Application follow-up email reminders
  - `auto_apply.py` — Automated job application via Playwright

### Frontend (`/frontend/src/`)
- `app/` — Next.js App Router pages (login, register, dashboard, profile, jobs)
- `lib/api.ts` — Centralized API client with JWT token management

## Key Database Models
- **User** — profile, preferences, target_roles, preferred_locations, target_portals
- **UserSkill** — skill_name, proficiency, years_experience
- **Job** — title, company, location, description, source, embedding (vector)
- **Application** — user_id, job_id, status, match_score
- **Resume** — file_path, is_base, job_id (null=base, set=optimized)
- **AgentRun** — audit trail for discovery runs

## Environment Variables (`.env`)
Required:
- `GROQ_API_KEY` — Groq LLM API key (free tier)
- `JWT_SECRET` — Random string for JWT signing
- `DATABASE_URL` — PostgreSQL async connection string
- `REDIS_URL` — Redis connection string

Optional:
- `SMTP_HOST/PORT/USER/PASSWORD` — Email notifications
- `UPLOAD_DIR` — Resume storage path (default: ./uploads/resumes)

## Development Notes

### Celery Tasks
- Tasks are in `app/agents/job_discovery.py`, registered via `celery_app.conf.include`
- `discover_jobs_task` — per-user job discovery (Playwright scraping + LLM parsing)
- `discover_jobs_all_users` — periodic task (every 6h) that triggers per-user discovery
- `check_follow_up_reminders` — daily task (9 AM IST) that sends follow-up emails
- Tasks use sync SQLAlchemy (separate from the async FastAPI engine)

### Job Discovery Pipeline
1. Build search URLs per portal based on user profile
2. Scrape search result pages with Playwright (stealth mode)
3. Extract job cards (title, company, location, URL)
4. Scrape full JD from each job URL
5. Parse JD with Groq LLM → structured data + skills
6. Deduplicate by (external_id, source), store in PostgreSQL

### Job Matching
Rule-based scoring (0-100):
- Skills overlap: 40 points
- Location match: 20 points
- Salary range fit: 20 points
- Experience match: 20 points

### Resume Optimization
1. Extract text from base resume (PDF/DOCX)
2. Send resume + JD to Groq LLM with optimization prompt
3. LLM rewrites bullets with job-specific keywords (no fabrication)
4. Generate ATS-friendly PDF with ReportLab

## Monitoring & Analytics
- **Grafana**: grafana.jobflow.healops.online (prod) / localhost:3002 (dev)
- **Prometheus**: scrapes `/metrics` from backend every 15s
- **Metrics collected**:
  - `jobflow_http_requests_total` — HTTP request counter (method, path, status)
  - `jobflow_http_request_duration_seconds` — Request latency histogram
  - `jobflow_user_logins_total` — Login counter
  - `jobflow_user_registrations_total` — Registration counter
  - `jobflow_site_visits_total` — Unique visitor counter
  - `jobflow_unique_visitors_today` — Daily unique IPs gauge
  - `jobflow_daily_active_users` — Daily active logged-in users gauge
  - `jobflow_total_users` / `jobflow_total_jobs` / `jobflow_total_applications` — DB count gauges
- **Dashboard**: Pre-provisioned "JobFlow Analytics" dashboard with visitor tracking, login/registration charts, API performance, and request breakdown
- **Config files**: `monitoring/prometheus/prometheus.yml`, `monitoring/grafana/`

## Deployment
- **Domain**: jobflow.healops.online
- **Grafana**: grafana.jobflow.healops.online
- **Production**: `docker-compose.prod.yml` with Nginx + Let's Encrypt SSL
- **Deploy script**: `bash scripts/deploy.sh --domain jobflow.healops.online --email your@email.com`
- **DNS**: Point both `jobflow.healops.online` and `grafana.jobflow.healops.online` A records to your server IP

## Common Commands
```bash
# View logs
docker compose logs -f backend
docker compose logs -f celery-worker

# Restart after code changes (backend hot-reloads, celery does not)
docker compose restart celery-worker celery-beat

# DB shell
docker exec -it jobflow-db psql -U jobflow

# Run backend tests
cd backend && pytest

# Check API docs
open http://localhost:8001/docs
```
