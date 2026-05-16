# AI-Powered Internship Matcher
### Final Year Project — Complete Full-Stack Application

---

## Project Structure

```
ai-internship-matcher/
├── backend/                  ← FastAPI backend (Part 1)
│   ├── main.py               ← App entry point, CORS, routers
│   ├── database.py           ← SQLAlchemy models + DB connection
│   ├── models/
│   │   └── schemas.py        ← Pydantic request/response schemas
│   ├── routes/
│   │   ├── auth.py           ← Register, login, JWT auth
│   │   ├── resume.py         ← PDF upload + NLP skill extraction
│   │   ├── jobs.py           ← Internship listings + applications
│   │   └── matching.py       ← AI matching + skill gap endpoints
│   ├── utils/
│   │   ├── pdf_parser.py     ← PyPDF2 text extraction
│   │   ├── skill_extractor.py← spaCy skill detection
│   │   └── matcher.py        ← Cosine similarity engine
│   ├── requirements.txt
│   └── .env.example
│
├── scraper/                  ← Web scraping pipeline (Part 2)
│   ├── base_scraper.py       ← Abstract base class for all scrapers
│   ├── sites/
│   │   ├── indeed_scraper.py
│   │   ├── linkedin_scraper.py
│   │   ├── rozee_scraper.py
│   │   ├── internshala_scraper.py
│   │   └── glassdoor_scraper.py
│   ├── api_scrapers/
│   │   ├── adzuna_scraper.py
│   │   └── jsearch_scraper.py
│   ├── utils/ (copy from scraper flat files)
│   │   ├── driver_manager.py
│   │   ├── proxy_rotator.py
│   │   ├── data_cleaner.py
│   │   └── deduplicator.py
│   ├── tasks.py              ← Celery scheduled tasks
│   ├── celery_config.py      ← Redis + Celery settings
│   ├── db_additions.py       ← ScraperStats model
│   ├── run_scraper.py        ← Manual trigger script
│   └── scraper_requirements.txt
│
└── frontend/                 ← React application (Part 3)
    ├── src/
    │   ├── api/              ← Axios API calls
    │   ├── components/       ← Reusable UI components
    │   ├── pages/            ← Full page components
    │   ├── store/            ← Zustand global state
    │   ├── hooks/            ← Custom React hooks
    │   └── utils/            ← Helper functions
    ├── package.json
    └── .env.example
```

---

## Quick Start

### Step 1 — Backend Setup
```bash
cd backend
pip install -r requirements.txt
python -m spacy download en_core_web_sm
cp .env.example .env        # Fill in DATABASE_URL and SECRET_KEY
uvicorn main:app --reload
# API docs: http://localhost:8000/docs
```

### Step 2 — Frontend Setup
```bash
cd frontend
npm install
cp .env.example .env        # Add VITE_API_URL and VITE_OPENAI_API_KEY
npm run dev
# App: http://localhost:5173
```

### Step 3 — Scraper Setup (optional, run separately)
```bash
cd scraper
pip install -r scraper_requirements.txt
# Start Redis first: redis-server
celery -A scraper.tasks worker --loglevel=info   # Terminal 1
celery -A scraper.tasks beat --loglevel=info     # Terminal 2
python run_scraper.py --site indeed              # Manual test run
```

---

## Bug Fixes Applied (vs original 3 parts)

| # | File | Bug | Fix |
|---|------|-----|-----|
| 1 | `frontend/src/api/resume.js` | Called `/resumes/upload` but backend prefix is `/resume` | Updated URLs to `/resume/...` |
| 2 | `frontend/src/api/applications.js` | Called `/applications/my-applications` (doesn't exist) and sent `job_id` instead of `internship_id` | Fixed to `GET /applications` and `internship_id` |
| 3 | `scraper/db_additions.py` | `ScraperStats` class didn't inherit `Base` — table would never be created | Added `Base` inheritance with fallback |
| 4 | `scraper/tasks.py` | `from scraper import celery_config` fails when run directly | Added try/except fallback import |
| 5 | All packages | Missing `__init__.py` — Python won't treat folders as packages | Added `__init__.py` to all package folders |
| 6 | `backend/database.py` | `ScraperStats` not imported — `create_all()` wouldn't create its table | Added try/except import at bottom of file |
| 7 | `frontend/.env.example` | Missing `VITE_OPENAI_API_KEY` (needed by Chatbot) | Added both env vars |

---

## API Endpoints Reference

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Create student account |
| POST | `/auth/login` | Login → JWT token |
| GET | `/auth/me` | Get my profile |
| PUT | `/auth/me` | Update my profile |

### Resume
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/resume/upload` | Upload PDF resume |
| GET | `/resume/my-resumes` | List my resumes |
| DELETE | `/resume/{id}` | Delete a resume |

### Jobs
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/jobs` | List internships (filterable) |
| GET | `/jobs/{id}` | Single internship detail |
| GET | `/jobs/stats` | Aggregate statistics |
| POST | `/jobs` | Add internship (admin only) |

### Applications
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/applications` | Apply to internship |
| GET | `/applications` | My applications |
| PUT | `/applications/{id}` | Update status/notes |

### Matching
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/match/my-matches` | AI-ranked internship list |
| GET | `/match/skill-gap` | Missing skills analysis |

