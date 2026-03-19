# JobFlow

**AI-powered job application automation platform**

JobFlow discovers jobs from 9+ portals, matches them against your profile, optimizes your resume with AI, generates ATS-friendly PDFs, and prepares you for interviews — all for free.

Live at: [jobflow.healops.online](https://jobflow.healops.online)

---

## Features

- **Multi-Portal Job Discovery** — Scrapes LinkedIn, Naukri, Indeed, Wellfound, Arc, Torre, GetOnBoard, and Google Jobs automatically every 6 hours
- **AI Job Matching** — Scores jobs against your profile (skills, location, salary, experience) on a 0-100 scale
- **Resume Optimization** — AI rewrites your resume bullets to match each job description (never fabricates skills)
- **ATS-Friendly PDF Generation** — Clean, parseable resume PDFs that pass applicant tracking systems
- **Cover Letter Generation** — AI-generated cover letters tailored to each position
- **Interview Preparation** — AI-generated interview questions specific to the job and your experience
- **Auto-Apply** — Automated application submission via browser automation (LinkedIn, Naukri)
- **Follow-Up Reminders** — Email alerts for stale applications needing follow-up
- **Application Tracking** — Dashboard to monitor all your applications in one place
- **Email Notifications** — Get notified when high-match jobs are found

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.12), SQLAlchemy, Pydantic |
| Frontend | Next.js 15, React 19, TypeScript |
| Database | PostgreSQL 16 + pgvector |
| LLM | Groq free tier (llama-3.3-70b-versatile) |
| Task Queue | Celery + Redis |
| Browser Automation | Playwright (headless Chromium) |
| PDF Generation | ReportLab |
| Auth | JWT + bcrypt |
| Deployment | Docker Compose, Nginx, Let's Encrypt |

## Architecture

```
User → Next.js (3000) → FastAPI (8000) → PostgreSQL (5432)
                               │
                               ├→ Celery Workers → Playwright (scraping)
                               │       │
                               │       ├→ Groq LLM (JD parsing, resume optimization)
                               │       └→ pgvector (similarity search)
                               │
                               └→ Redis (6379) [task queue]
```

## Quick Start

### Prerequisites
- Docker + Docker Compose
- Groq API key (free at [console.groq.com/keys](https://console.groq.com/keys))

### Run with Docker (recommended)

```bash
# Clone the repo
git clone https://github.com/yourusername/jobflow.git
cd jobflow

# Set up environment
cp .env.example .env
# Edit .env — add your GROQ_API_KEY

# Start everything
docker compose up --build
```

Open [localhost:3001](http://localhost:3001) (frontend) and [localhost:8001/docs](http://localhost:8001/docs) (API docs).

### Run Manually (development)

```bash
# Run setup script
./scripts/setup.sh

# Edit .env with your Groq API key
vim .env

# Terminal 1 — Infrastructure
docker compose up -d db redis

# Terminal 2 — Backend
cd backend && source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Terminal 3 — Frontend
cd frontend && npm run dev

# Terminal 4 — Workers (optional, for job discovery)
celery -A app.worker.celery_app worker --loglevel=info
celery -A app.worker.celery_app beat --loglevel=info
```

## How It Works

### 1. Set Up Your Profile
Register, add your skills, certifications, target roles, preferred locations, and upload your resume.

### 2. Discover Jobs
Click "Find Jobs Now" or let the system auto-discover every 6 hours. JobFlow scrapes your selected portals, parses job descriptions with AI, and stores structured data.

### 3. Review Matches
Jobs are scored 0-100 based on:
- **Skills overlap** (40 pts) — How well your skills match the JD
- **Location match** (20 pts) — Job location vs your preferences
- **Salary fit** (20 pts) — Salary range alignment
- **Experience match** (20 pts) — Years of experience vs requirements

### 4. Optimize & Apply
For each job, you can:
- **Optimize Resume** — AI tailors your resume to the job description
- **Generate Cover Letter** — AI writes a targeted cover letter
- **Interview Prep** — Get role-specific interview questions
- **Apply** — Track manual applications or auto-apply to supported portals

## Project Structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry
│   │   ├── config.py            # Settings (Pydantic)
│   │   ├── database.py          # SQLAlchemy async setup
│   │   ├── models.py            # Database models
│   │   ├── schemas.py           # Request/response schemas
│   │   ├── auth.py              # JWT authentication
│   │   ├── worker.py            # Celery + Beat config
│   │   ├── routes/
│   │   │   ├── auth_routes.py   # Register, login, me
│   │   │   ├── profile_routes.py# Profile CRUD, resume upload
│   │   │   ├── job_routes.py    # Jobs, matching, applications
│   │   │   └── agent_routes.py  # Discovery, scraping, interview prep
│   │   ├── services/
│   │   │   ├── job_matcher.py   # Rule-based scoring
│   │   │   ├── resume_optimizer.py  # LLM resume rewriting
│   │   │   ├── resume_parser.py # PDF/DOCX extraction
│   │   │   ├── pdf_generator.py # ATS PDF builder
│   │   │   └── email_service.py # SMTP notifications
│   │   └── agents/
│   │       ├── job_discovery.py # Multi-portal scraping
│   │       ├── interview_prep.py# Question generation
│   │       ├── auto_apply.py    # Automated applications
│   │       └── follow_up_agent.py # Follow-up reminders
│   ├── alembic/                 # Database migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js App Router pages
│   │   └── lib/api.ts           # API client
│   ├── package.json
│   └── Dockerfile
├── nginx/                       # Reverse proxy config
├── scripts/
│   ├── setup.sh                 # Local dev setup
│   └── deploy.sh                # Production deployment
├── docker-compose.yml           # Development
├── docker-compose.prod.yml      # Production
└── .env.example                 # Environment template
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login |
| GET | `/api/auth/me` | Get current user |
| PUT | `/api/profile` | Update profile + skills |
| POST | `/api/profile/resume` | Upload resume (PDF/DOCX) |
| GET | `/api/jobs` | List discovered jobs |
| GET | `/api/jobs/match/all` | Get jobs ranked by match score |
| POST | `/api/jobs/{id}/optimize-resume` | AI resume optimization |
| POST | `/api/jobs/{id}/apply` | Track/submit application |
| POST | `/api/jobs/{id}/cover-letter` | Generate cover letter |
| GET | `/api/jobs/applications/all` | List all applications |
| POST | `/api/agent/discover` | Trigger job discovery |
| POST | `/api/agent/scrape-job` | Scrape single job URL |
| GET | `/api/agent/interview-prep/{id}` | Generate interview questions |

Full interactive docs at `/docs` (Swagger UI).

## Deployment

### Production (Oracle Cloud / any VPS)

```bash
# 1. Copy production env template
cp .env.production.example .env.production

# 2. Fill in your values
vim .env.production

# 3. Deploy with SSL
bash scripts/deploy.sh --domain jobflow.healops.online --email your@email.com
```

This sets up Docker Compose with Nginx reverse proxy, Let's Encrypt SSL, and all services.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | Yes | Groq LLM API key ([free](https://console.groq.com/keys)) |
| `JWT_SECRET` | Yes | Random string for JWT signing |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `SMTP_USER` | No | Gmail address for notifications |
| `SMTP_PASSWORD` | No | Gmail app password |
| `FRONTEND_URL` | No | Frontend URL for CORS/emails |

## Cost

**₹0/month** — Everything runs on free tiers:
- Groq LLM: Free tier (30 req/min)
- PostgreSQL: Docker (self-hosted)
- Redis: Docker (self-hosted)
- Oracle Cloud VM: Free tier
- Let's Encrypt SSL: Free

## License

MIT
