# JobFlow — System Architecture

## Table of Contents
1. [System Overview](#system-overview)
2. [Architecture Diagram](#architecture-diagram)
3. [Agent Workflow Design](#agent-workflow-design)
4. [Tech Stack Justification](#tech-stack-justification)
5. [Database Schema](#database-schema)
6. [Resume Optimization Pipeline](#resume-optimization-pipeline)
7. [Job Scraping Strategy](#job-scraping-strategy)
8. [MVP vs Full Product Scope](#mvp-vs-full-product-scope)
9. [Legal & Ethical Considerations](#legal--ethical-considerations)
10. [Cost Estimate](#cost-estimate)
11. [Security Considerations](#security-considerations)
12. [Deployment Architecture](#deployment-architecture)

---

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                              JOBFLOW                      │
│                                                                      │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────┐ │
│  │  Next.js  │──▶│   FastAPI     │──▶│  AI Agents   │──▶│ Playwright│ │
│  │ Frontend  │◀──│   Backend    │◀──│  (LangGraph) │◀──│  Browser  │ │
│  └──────────┘   └──────┬───────┘   └──────┬───────┘   └──────────┘ │
│                        │                   │                         │
│                 ┌──────▼───────┐   ┌──────▼───────┐                 │
│                 │  PostgreSQL  │   │  Groq LLM    │                 │
│                 │  + pgvector  │   │  (Free Tier)  │                 │
│                 └──────────────┘   └──────────────┘                 │
│                                                                      │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐            │
│  │ Local Storage │   │  Celery +    │   │  Email via   │            │
│  │  (Resumes)   │   │  Redis Queue │   │  Gmail SMTP  │            │
│  └──────────────┘   └──────────────┘   └──────────────┘            │
└─────────────────────────────────────────────────────────────────────┘
```

### Core Components

| Component | Purpose | Technology |
|-----------|---------|------------|
| Frontend | User dashboard, onboarding | Next.js 15 |
| API Server | REST API, business logic | FastAPI (Python 3.12) |
| Database | User data, jobs, applications | PostgreSQL 16 + pgvector |
| AI Agents | Job discovery, matching, resume optimization | LangGraph + Groq |
| Browser Automation | Scraping, form filling | Playwright |
| Task Queue | Background job processing | Celery + Redis |
| File Storage | Resume PDFs | Local filesystem |

---

## 2. Architecture Diagram

### Request Flow
```
User ──▶ Next.js (3000) ──▶ FastAPI (8000) ──▶ PostgreSQL (5432)
                                  │
                                  ├──▶ Celery Worker ──▶ AI Agents
                                  │         │
                                  │         ├──▶ Groq API (LLM)
                                  │         ├──▶ Playwright (Scraping)
                                  │         └──▶ pgvector (Similarity Search)
                                  │
                                  └──▶ Redis (6379) [Task Queue + Cache]
```

### Multi-Agent Architecture
```
┌─────────────────────────────────────────────────────────┐
│                   AGENT ORCHESTRATOR                      │
│                    (LangGraph Graph)                      │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  Discovery   │  │   Matching   │  │   Resume      │  │
│  │   Agent      │──▶│    Agent     │──▶│  Optimizer   │  │
│  │             │  │              │  │   Agent       │  │
│  │ - Scrape    │  │ - Score jobs │  │ - Analyze JD  │  │
│  │ - Parse JDs │  │ - Rank by   │  │ - Tailor      │  │
│  │ - Dedupe   │  │   fit score  │  │   bullets     │  │
│  └─────────────┘  └──────────────┘  │ - Generate    │  │
│                                      │   ATS PDF     │  │
│  ┌─────────────┐  ┌──────────────┐  └───────────────┘  │
│  │  Applicator  │  │  Notifier    │                      │
│  │   Agent      │  │   Agent      │                      │
│  │             │  │              │                      │
│  │ - Fill forms│  │ - Daily email│                      │
│  │ - Upload CV │  │ - Interview  │                      │
│  │ - Submit    │  │   prep Qs    │                      │
│  └─────────────┘  └──────────────┘                      │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Agent Workflow Design

### Pipeline Flow (LangGraph State Machine)

```
START
  │
  ▼
[discover_jobs] ──▶ Scrape LinkedIn/Naukri/career pages
  │                  Output: List[RawJob]
  ▼
[parse_jobs] ──▶ Extract structured data from JDs using LLM
  │              Output: List[ParsedJob] with skills, salary, location
  ▼
[match_jobs] ──▶ Vector similarity + rule-based scoring
  │              Output: List[ScoredJob] sorted by match %
  ▼
[filter_jobs] ──▶ Remove already-applied, salary mismatch, etc.
  │               Output: List[FilteredJob]
  ▼
[optimize_resume] ──▶ For each top job:
  │                     - Analyze JD keywords
  │                     - Rewrite resume bullets
  │                     - Generate ATS-friendly PDF
  │                     Output: List[OptimizedResume]
  ▼
[apply_jobs] ──▶ For each job (if auto-apply enabled):
  │               - Open job page via Playwright
  │               - Fill form fields
  │               - Upload resume
  │               - Submit
  │               Output: List[ApplicationResult]
  ▼
[notify_user] ──▶ Send email summary
  │               Output: NotificationResult
  ▼
END
```

### State Schema
```python
class AgentState(TypedDict):
    user_id: int
    raw_jobs: list[dict]
    parsed_jobs: list[dict]
    scored_jobs: list[dict]
    filtered_jobs: list[dict]
    optimized_resumes: list[dict]
    application_results: list[dict]
    errors: list[str]
```

---

## 4. Tech Stack Justification

| Choice | Why | Alternatives Considered |
|--------|-----|------------------------|
| **FastAPI** | Async, fast, auto-docs, Python ecosystem for AI | Django (too heavy), Flask (no async) |
| **PostgreSQL + pgvector** | Single DB for relational + vector search, free | Pinecone ($70+/mo), Weaviate (complex) |
| **Groq (free tier)** | 30 req/min, llama-3.3-70b is excellent, ₹0 | OpenAI ($20+/mo), Claude API ($20+/mo) |
| **LangGraph** | Stateful multi-agent graphs, checkpointing | CrewAI (less control), AutoGen (complex) |
| **Playwright** | Best browser automation, stealth mode, Python | Selenium (slow), Puppeteer (Node only) |
| **Next.js** | SSR, great DX, huge ecosystem | React SPA (no SSR), Vue (smaller ecosystem) |
| **Celery + Redis** | Battle-tested task queue, free | RQ (simpler but limited), Dramatiq |
| **Local filesystem** | ₹0 for resume storage | S3 ($0.023/GB), MinIO (extra infra) |

### Why NOT use paid services
- Budget is ₹500 (~$6). A single month of any paid API exceeds this.
- Groq free tier gives 30 requests/minute — enough for an MVP processing ~50 jobs/day.

---

## 5. Database Schema

```sql
-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    linkedin_url VARCHAR(500),
    years_of_experience INTEGER,
    salary_min INTEGER,  -- in LPA
    salary_max INTEGER,
    preferred_locations TEXT[],  -- ['Bangalore', 'Remote']
    target_companies TEXT[],
    target_portals TEXT[],  -- ['linkedin', 'naukri']
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Skills with experience
CREATE TABLE user_skills (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    skill_name VARCHAR(100) NOT NULL,
    years_experience INTEGER DEFAULT 0,
    proficiency VARCHAR(20) DEFAULT 'intermediate',  -- beginner/intermediate/expert
    is_primary BOOLEAN DEFAULT FALSE
);

-- Certifications
CREATE TABLE user_certifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    issuer VARCHAR(255),
    year_obtained INTEGER
);

-- Resumes (base + optimized versions)
CREATE TABLE resumes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    file_path VARCHAR(500) NOT NULL,
    is_base BOOLEAN DEFAULT FALSE,  -- true = original uploaded resume
    job_id INTEGER REFERENCES jobs(id),  -- null for base resume
    version INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Jobs discovered
CREATE TABLE jobs (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(255),  -- ID on the job portal
    title VARCHAR(500) NOT NULL,
    company VARCHAR(255) NOT NULL,
    location VARCHAR(255),
    salary_min INTEGER,
    salary_max INTEGER,
    description TEXT,
    requirements TEXT,
    job_url VARCHAR(1000),
    source VARCHAR(50) NOT NULL,  -- 'linkedin', 'naukri', 'company_career'
    posted_date DATE,
    scraped_at TIMESTAMP DEFAULT NOW(),
    -- Vector embedding for similarity search
    embedding vector(1536),
    UNIQUE(external_id, source)
);

-- Job-skill mapping (extracted from JD)
CREATE TABLE job_skills (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    skill_name VARCHAR(100) NOT NULL
);

-- Applications tracking
CREATE TABLE applications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    job_id INTEGER REFERENCES jobs(id) ON DELETE CASCADE,
    resume_id INTEGER REFERENCES resumes(id),
    status VARCHAR(50) DEFAULT 'pending',
    -- pending, applied, failed, interview, rejected, offer
    match_score FLOAT,  -- 0-100
    applied_at TIMESTAMP,
    platform VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, job_id)
);

-- Agent run logs
CREATE TABLE agent_runs (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    run_type VARCHAR(50) NOT NULL,  -- 'discovery', 'matching', 'optimization', 'application'
    status VARCHAR(20) DEFAULT 'running',  -- running, completed, failed
    jobs_found INTEGER DEFAULT 0,
    jobs_matched INTEGER DEFAULT 0,
    jobs_applied INTEGER DEFAULT 0,
    errors TEXT,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```

---

## 6. Resume Optimization Pipeline

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Base Resume  │────▶│  JD Analyzer  │────▶│  Resume      │
│  (PDF/DOCX)  │     │  (LLM)       │     │  Rewriter    │
└──────────────┘     │              │     │  (LLM)       │
                     │ Extracts:    │     │              │
                     │ - Keywords   │     │ Modifies:    │
                     │ - Skills     │     │ - Bullets    │
                     │ - Tone       │     │ - Keywords   │
                     │ - Requirements│     │ - Order     │
                     └──────────────┘     └──────┬───────┘
                                                  │
                                          ┌──────▼───────┐
                                          │  PDF Generator│
                                          │  (ReportLab)  │
                                          │              │
                                          │ - ATS format │
                                          │ - Clean layout│
                                          │ - 1-2 pages  │
                                          └──────────────┘
```

### Optimization Rules
1. **Truthful** — Never fabricate skills or experience
2. **Keyword-rich** — Mirror JD language in bullet points
3. **Quantified** — Add metrics where possible ("managed 5 servers" → "managed 15+ production servers")
4. **ATS-friendly** — Simple formatting, standard headings, no tables/images
5. **Relevant ordering** — Move matching skills/experience to top

### LLM Prompt Strategy
```
System: You are a resume optimization expert. Given a base resume and a job
description, rewrite the resume bullets to better match the JD.

Rules:
- NEVER lie or add skills the candidate doesn't have
- Reorder sections to highlight relevant experience first
- Mirror keywords from the JD naturally
- Quantify achievements where possible
- Keep it to 1-2 pages
- Use action verbs: Led, Built, Deployed, Automated, Reduced, etc.
```

---

## 7. Job Scraping Strategy

### Approach by Platform

| Platform | Method | Difficulty | Rate Limit Strategy |
|----------|--------|------------|---------------------|
| **LinkedIn** | Playwright + stealth | Hard (anti-bot) | 20 jobs/hour, random delays |
| **Naukri** | Playwright + API | Medium | 50 jobs/hour |
| **Company Career Pages** | Playwright + LLM parse | Easy | Per-site |
| **Job Boards** | RSS/API where available | Easy | As available |

### Anti-Detection Measures
- Random delays between requests (2-8 seconds)
- Rotate User-Agent strings
- Use stealth Playwright settings
- Mimic human scroll/click patterns
- Session persistence (cookies)
- Respect robots.txt

### MVP Scraping: Start Simple
For MVP, skip Playwright scraping entirely. Instead:
1. **Manual CSV import** — User pastes job URLs or uploads CSV
2. **RSS feeds** — Many job boards have RSS
3. **Public APIs** — LinkedIn has limited public job search
4. **Google Jobs** — Scrape Google's job aggregation (simpler anti-bot)

This avoids legal risk and complexity in MVP.

---

## 8. MVP vs Full Product Scope

### MVP (4-6 weeks) ✅
- [x] User registration + login
- [x] Profile setup (skills, certs, preferences)
- [x] Resume upload + parsing
- [x] Manual job URL input (paste a URL → system extracts JD)
- [x] AI job-resume matching score
- [x] AI resume optimization for specific JD
- [x] Download optimized resume as PDF
- [x] Application tracking dashboard
- [x] Basic email notifications

### Phase 2 (8-12 weeks)
- [ ] Automated LinkedIn job scraping
- [ ] Automated Naukri scraping
- [ ] Auto-apply via Playwright
- [ ] Interview question generator
- [ ] Chrome extension for one-click import
- [ ] Bulk processing (100+ jobs/day)

### Phase 3 (16+ weeks)
- [ ] Company career page crawling
- [ ] Cover letter generation
- [ ] Salary negotiation insights
- [ ] Application analytics & trends
- [ ] Multi-user SaaS mode
- [ ] Mobile app (React Native)

---

## 9. Legal & Ethical Considerations

### ⚠️ Critical Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **LinkedIn TOS violation** | HIGH | LinkedIn prohibits scraping. Use only public API or manual input |
| **Naukri TOS violation** | MEDIUM | Check their TOS. Start with manual import |
| **Resume fraud** | HIGH | NEVER fabricate skills. Only reword existing experience |
| **GDPR/Data protection** | MEDIUM | Store minimal PII, allow data deletion |
| **Mass automated applications** | MEDIUM | Can get accounts banned. Apply slowly |
| **Impersonation** | HIGH | Always apply as the actual user, never fake identities |

### Legal Safe Path for MVP
1. **No automated scraping** in MVP — user manually inputs job URLs
2. **No auto-apply** in MVP — generate optimized resume, user applies manually
3. **Truthful resumes only** — system prompt explicitly forbids fabrication
4. **User consent** — clear terms that AI modifies their resume
5. **Data privacy** — all data stored locally, no third-party sharing

---

## 10. Cost Estimate

### MVP Running Costs (Monthly)

| Component | Cost |
|-----------|------|
| Groq API (free tier) | ₹0 |
| PostgreSQL (Docker, local) | ₹0 |
| Redis (Docker, local) | ₹0 |
| Oracle Cloud VM (existing) | ₹0 |
| Domain (optional) | ₹0 (skip for MVP) |
| **Total** | **₹0/month** |

### If Scaling (per 100 users/month)

| Component | Cost |
|-----------|------|
| Groq paid or Ollama local | ₹0-500 |
| AWS RDS (smallest) | ~₹1,500 |
| AWS EC2 (t3.medium) | ~₹2,500 |
| AWS S3 | ~₹50 |
| Domain + SSL | ~₹800/year |
| **Total** | **~₹4,000-5,000/month** |

### One-Time Costs
| Item | Cost |
|------|------|
| Development time | Your time (₹0) |
| **Total** | **₹0** |

---

## 11. Security Considerations

### Authentication
- JWT tokens with httponly cookies
- Password hashing with bcrypt
- Rate limiting on login endpoints

### Data Protection
- Resume files stored outside web root
- File access via signed URLs (time-limited)
- User data encrypted at rest (PostgreSQL encryption)
- No secrets in code — all via environment variables

### API Security
- CORS restricted to frontend origin
- Input validation on all endpoints (Pydantic)
- SQL injection prevention (SQLAlchemy ORM)
- File upload validation (type, size limits)

### Agent Security
- Playwright runs in sandboxed browser
- No credential storage for job portals (user provides session)
- Rate limiting on LLM calls
- Agent actions logged for audit

---

## 12. Deployment Architecture

### Development (Local)
```
Docker Compose:
├── fastapi-backend (port 8000)
├── next-frontend (port 3000)
├── postgresql + pgvector (port 5432)
├── redis (port 6379)
├── celery-worker
└── playwright (headless Chrome)
```

### Production (Oracle Cloud / AWS)
```
┌─────────────────────────────────────┐
│          Oracle Cloud VM             │
│  ┌─────────┐  ┌─────────┐          │
│  │  Nginx   │  │ Certbot │          │
│  │ (Reverse │  │ (SSL)   │          │
│  │  Proxy)  │  └─────────┘          │
│  └────┬─────┘                       │
│       │                             │
│  ┌────▼─────────────────────────┐   │
│  │      Docker Compose          │   │
│  │  ┌────────┐  ┌────────────┐  │   │
│  │  │FastAPI │  │  Next.js   │  │   │
│  │  │ :8000  │  │   :3000    │  │   │
│  │  └────────┘  └────────────┘  │   │
│  │  ┌────────┐  ┌────────────┐  │   │
│  │  │Postgres│  │   Redis    │  │   │
│  │  │ :5432  │  │   :6379    │  │   │
│  │  └────────┘  └────────────┘  │   │
│  │  ┌────────────────────────┐  │   │
│  │  │    Celery Workers      │  │   │
│  │  └────────────────────────┘  │   │
│  └──────────────────────────────┘   │
└─────────────────────────────────────┘
```

### CI/CD
- GitHub Actions for testing + building Docker images
- Deploy via `git push` → GitHub Actions → SSH deploy to Oracle Cloud
- Or manual `docker compose up -d` on server
