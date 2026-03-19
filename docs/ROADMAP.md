# Development Roadmap

## Phase 1: Foundation (Week 1-2) ← YOU ARE HERE
- [x] Project structure
- [x] Docker Compose (PostgreSQL + pgvector + Redis)
- [x] FastAPI backend with auth
- [x] Database models + Alembic
- [x] User registration/login
- [x] Profile CRUD (skills, certs, preferences)
- [x] Resume upload + parsing
- [x] Next.js frontend (login, register, profile, dashboard)
- [ ] Test everything works locally

## Phase 2: Core AI Features (Week 3-4)
- [ ] Manual job input (paste URL → scrape with Playwright)
- [ ] Manual job creation form
- [ ] Job-profile matching algorithm (rule-based scoring)
- [ ] Resume optimization with Groq LLM
- [ ] ATS-friendly PDF generation
- [ ] Interview question generator
- [ ] Basic email notifications

## Phase 3: Enhanced Job Discovery (Week 5-6)
- [ ] Google Jobs RSS scraping
- [ ] Naukri API/scraping integration
- [ ] Job deduplication
- [ ] Scheduled job discovery (Celery beat)
- [ ] Vector embeddings for semantic job matching (pgvector)
- [ ] Job search filters in frontend

## Phase 4: Application Automation (Week 7-8)
- [ ] Playwright auto-fill for Naukri
- [ ] Playwright auto-fill for company career pages
- [ ] Application status tracking
- [ ] Daily email summaries
- [ ] Application analytics dashboard

## Phase 5: Production Ready (Week 9-10)
- [ ] Docker production build
- [ ] Nginx reverse proxy + SSL
- [ ] Deploy to Oracle Cloud
- [ ] GitHub Actions CI/CD
- [ ] Rate limiting + security hardening
- [ ] Error monitoring

## Phase 6: Scale (Week 11+)
- [ ] Multi-user support
- [ ] Chrome extension for one-click job import
- [ ] Cover letter generation
- [ ] Salary insights
- [ ] Mobile responsive frontend

---

## What's NOT in MVP (and why)

| Feature | Why Skipped |
|---------|-------------|
| Auto-apply to LinkedIn | TOS violation risk, account ban |
| Paid LLM APIs | Budget ₹500, using Groq free |
| AWS S3 | Costs money, local storage works |
| Pinecone | pgvector is free and sufficient |
| Mobile app | Web is enough for MVP |
