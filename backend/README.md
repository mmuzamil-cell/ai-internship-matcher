# AI-Powered Internship Matcher — Backend API

Final Year Project | Python · FastAPI · PostgreSQL · sentence-transformers · spaCy

---

## What It Does

Students upload their PDF resume → the system extracts skills using NLP → computes
cosine-similarity scores against all internship listings → returns personalized ranked
matches with skill gap analysis and course recommendations.

---

## Tech Stack

| Layer        | Technology                                      |
|--------------|-------------------------------------------------|
| Framework    | FastAPI 0.111 (async, auto-docs)                |
| Database     | PostgreSQL 15 via SQLAlchemy 2.0                |
| AI Matching  | sentence-transformers `all-MiniLM-L6-v2`        |
| NLP Skills   | spaCy `en_core_web_sm` + curated keyword list   |
| PDF Parsing  | PyPDF2                                          |
| Auth         | JWT (HS256) + bcrypt password hashing           |
| Rate Limit   | slowapi (5 login attempts/minute/IP)            |

---

## Project Structure

```
ai-internship-matcher/
├── main.py                  # FastAPI app, CORS, routers, startup
├── database.py              # SQLAlchemy models + DB connection
├── requirements.txt
├── .env.example             # Copy to .env and fill in values
│
├── models/
│   └── schemas.py           # All Pydantic request/response schemas
│
├── routes/
│   ├── auth.py              # Register, login, JWT, profile
│   ├── resume.py            # PDF upload, skill extraction
│   ├── jobs.py              # Internship CRUD + application tracker
│   └── matching.py          # AI matching + skill gap analysis
│
└── utils/
    ├── pdf_parser.py        # PyPDF2 text extraction
    ├── skill_extractor.py   # spaCy + keyword skill detection (60+ skills)
    └── matcher.py           # Cosine similarity with sentence-transformers
```

---

## Setup & Installation

### Prerequisites
- Python 3.11+
- PostgreSQL 15+
- pip

### 1. Clone and enter directory
```bash
git clone <your-repo-url>
cd ai-internship-matcher
```

### 2. Create a virtual environment
```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Download the spaCy model
```bash
python -m spacy download en_core_web_sm
```

### 5. Set up the database
Create a PostgreSQL database:
```sql
CREATE DATABASE internship_matcher;
```

### 6. Configure environment variables
```bash
cp .env.example .env
```
Edit `.env` and fill in all values (see Environment Variables section below).

### 7. Run the server
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Tables are auto-created on first startup (no migrations needed for development).

---

## Environment Variables

| Variable                     | Description                                      | Example                                     |
|------------------------------|--------------------------------------------------|---------------------------------------------|
| `DATABASE_URL`               | PostgreSQL connection string                     | `postgresql://user:pass@localhost/db`       |
| `SECRET_KEY`                 | 64-char random hex for signing JWTs             | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ALGORITHM`                  | JWT signing algorithm                            | `HS256`                                     |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| Token lifetime in minutes                        | `1440` (24 hours)                           |
| `UPLOAD_DIR`                 | Directory for saved resumes                      | `uploads/resumes`                           |
| `ALLOWED_ORIGINS`            | Comma-separated frontend origins for CORS        | `http://localhost:3000`                     |
| `LOGIN_RATE_LIMIT`           | Max login attempts per minute per IP             | `5/minute`                                  |

---

## API Endpoints

Interactive docs available at **http://localhost:8000/docs** after starting the server.

### Authentication

| Method | Endpoint           | Auth | Description                         |
|--------|--------------------|------|-------------------------------------|
| POST   | `/auth/register`   | ❌   | Register new student account        |
| POST   | `/auth/login`      | ❌   | Login → receive JWT (rate limited)  |
| GET    | `/auth/me`         | ✅   | Get current user profile            |
| PUT    | `/auth/me`         | ✅   | Update name, university, major      |

### Resume

| Method | Endpoint                | Auth | Description                              |
|--------|-------------------------|------|------------------------------------------|
| POST   | `/resume/upload`        | ✅   | Upload PDF → extract text & skills       |
| GET    | `/resume/my-resumes`    | ✅   | List all uploaded resumes with skills    |
| DELETE | `/resume/{id}`          | ✅   | Delete resume file and DB record         |

### Internships

| Method | Endpoint       | Auth      | Description                                        |
|--------|----------------|-----------|----------------------------------------------------|
| GET    | `/jobs`        | ❌        | List internships (filter: ?skill= &city= &remote=) |
| GET    | `/jobs/stats`  | ❌        | Aggregate stats by city, field, top skills         |
| GET    | `/jobs/{id}`   | ❌        | Single internship detail                           |
| POST   | `/jobs`        | ✅ Admin  | Manually add internship listing                    |

### AI Matching

| Method | Endpoint              | Auth | Description                                    |
|--------|-----------------------|------|------------------------------------------------|
| GET    | `/match/my-matches`   | ✅   | Top-20 AI-matched internships with scores      |
| GET    | `/match/skill-gap`    | ✅   | Missing skills + Coursera/YouTube course links |

### Applications

| Method | Endpoint              | Auth | Description                        |
|--------|-----------------------|------|------------------------------------|
| POST   | `/applications`       | ✅   | Apply to an internship             |
| GET    | `/applications`       | ✅   | List all applications with status  |
| PUT    | `/applications/{id}`  | ✅   | Update status or notes             |

### System

| Method | Endpoint   | Auth | Description               |
|--------|------------|------|---------------------------|
| GET    | `/health`  | ❌   | Liveness probe (returns 200 OK) |

---

## Authentication Flow

All protected endpoints require an `Authorization: Bearer <token>` header.

```bash
# 1. Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"full_name": "Ali Hassan", "email": "ali@lums.edu.pk", "password": "SecurePass1"}'

# 2. Login → copy the access_token
curl -X POST http://localhost:8000/auth/login \
  -F "username=ali@lums.edu.pk" \
  -F "password=SecurePass1"

# 3. Use token on protected routes
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer <your_token_here>"
```

---

## Skills Detected

The system detects 60+ skills including:

**Languages:** Python, JavaScript, TypeScript, Java, C++, C#, Go, Rust, Swift, Kotlin, PHP, Ruby, R, Scala

**Frameworks:** React, Next.js, Vue, Angular, FastAPI, Django, Flask, Express, Spring Boot, Node.js

**Databases:** SQL, PostgreSQL, MySQL, MongoDB, Redis, SQLite, Elasticsearch, Firebase

**Cloud/DevOps:** AWS, Azure, Google Cloud, Docker, Kubernetes, CI/CD, Git, Linux

**AI/ML:** Machine Learning, Deep Learning, TensorFlow, PyTorch, scikit-learn, Pandas, NumPy, NLP, Computer Vision, Tableau, Power BI

**Other:** REST API, GraphQL, Agile/Scrum, UI/UX, Testing, Data Structures, OOP

---

## Database Schema

```
users           → id, full_name, email, password_hash, university, major, is_admin, created_at
resumes         → id, user_id, filename, file_path, extracted_text, skills_json, uploaded_at
internships     → id, title, company, location, description, required_skills, stipend,
                   deadline, source_url, source_site, scraped_at, is_active
applications    → id, user_id, internship_id, status, applied_at, notes
match_scores    → id, user_id, internship_id, score, computed_at
```

---

## Common Errors

| Code | Meaning                                |
|------|----------------------------------------|
| 400  | Invalid input (bad file type, etc.)    |
| 401  | Missing or expired JWT                 |
| 403  | Insufficient permissions               |
| 404  | Resource not found                     |
| 409  | Duplicate (email exists, already applied) |
| 413  | File too large (> 5 MB)                |
| 422  | Validation error (missing field, etc.) |
| 429  | Rate limit exceeded (login endpoint)   |

All errors return `{"detail": "...", "code": "..."}`.

---

## Making a User Admin

Connect to PostgreSQL and run:
```sql
UPDATE users SET is_admin = true WHERE email = 'admin@example.com';
```

---

## Notes for Scraper Integration

To add scraped internships programmatically, insert directly into the `internships` table:
```python
new_job = Internship(
    title="Software Engineer Intern",
    company="Systems Ltd",
    location="Karachi",
    required_skills=json.dumps(["python", "django", "postgresql"]),
    source_url="https://rozee.pk/...",
    source_site="Rozee.pk",
)
```
The matcher will include these automatically on the next `/match/my-matches` call.
