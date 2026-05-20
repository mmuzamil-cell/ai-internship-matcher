"""
models/schemas.py — All Pydantic request & response schemas.

Pydantic models serve two roles:
  1. REQUEST VALIDATION  — FastAPI automatically rejects invalid input with
     helpful 422 error messages before the route handler even runs.
  2. RESPONSE SERIALIZATION — Controls exactly what fields are returned to the
     client (e.g., password_hash is never exposed).

Naming convention:
  - *Create  → fields accepted when creating a resource (POST body)
  - *Update  → fields accepted when editing a resource (PUT body, all optional)
  - *Response → fields returned to the client (GET / POST response)
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


# ─── Auth Schemas ─────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """Body accepted by POST /auth/register."""
    full_name:  str      = Field(..., min_length=2,  max_length=150,  example="Ali Hassan")
    email:      EmailStr = Field(...,                                  example="ali@lums.edu.pk")
    password:   str      = Field(..., min_length=8,  max_length=128,  example="SecurePass123!")
    university: Optional[str] = Field(None, max_length=200, example="LUMS")
    major:      Optional[str] = Field(None, max_length=150, example="Computer Science")

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Enforce at least one digit and one letter for basic password strength."""
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit.")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter.")
        return v


class UserUpdate(BaseModel):
    """Body accepted by PUT /auth/me — all fields optional so clients send only changes."""
    full_name:  Optional[str] = Field(None, min_length=2, max_length=150)
    university: Optional[str] = Field(None, max_length=200)
    major:      Optional[str] = Field(None, max_length=150)


class UserResponse(BaseModel):
    """Safe user representation — never includes password_hash."""
    id:         int
    full_name:  str
    email:      str
    university: Optional[str]
    major:      Optional[str]
    is_admin:   bool
    created_at: datetime

    model_config = {"from_attributes": True}  # Allows creating from ORM objects


class TokenResponse(BaseModel):
    """Returned by POST /auth/login."""
    access_token: str
    token_type:   str = "bearer"


# ─── Resume Schemas ───────────────────────────────────────────────────────────

class ResumeResponse(BaseModel):
    """Returned after upload or GET /resume/my-resumes."""
    id:           int
    filename:     str
    skills_found: List[str]          # Parsed from skills_json
    total_skills: int
    match_ready:  bool               # True when at least 3 skills detected
    uploaded_at:  datetime

    model_config = {"from_attributes": True}


# ─── Internship Schemas ───────────────────────────────────────────────────────

class InternshipCreate(BaseModel):
    """Body accepted by POST /jobs (admin only)."""
    title:           str            = Field(..., min_length=3, max_length=255)
    company:         str            = Field(..., min_length=2, max_length=200)
    location:        Optional[str]  = Field(None, max_length=150, example="Karachi")
    description:     Optional[str]  = None
    required_skills: Optional[List[str]] = Field(default_factory=list)
    stipend:         Optional[str]  = Field(None, max_length=100, example="PKR 25,000/month")
    deadline:        Optional[datetime] = None
    source_url:      Optional[str]  = Field(None, max_length=512)
    source_site:     Optional[str]  = Field(None, max_length=100, example="LinkedIn")


class InternshipResponse(BaseModel):
    """Full internship detail returned by GET /jobs and GET /jobs/{id}."""
    id:              int
    title:           str
    company:         str
    location:        Optional[str]
    description:     Optional[str]
    required_skills: List[str]      # Parsed from JSON string
    stipend:         Optional[str]
    deadline:        Optional[datetime]
    source_url:      Optional[str]
    source_site:     Optional[str]
    scraped_at:      datetime
    is_active:       bool

    model_config = {"from_attributes": True}


class InternshipStats(BaseModel):
    """Aggregated stats returned by GET /jobs/stats."""
    total_active:      int
    by_city:           dict   # {"Karachi": 12, "Lahore": 8, "Remote": 5}
    top_skills:        List[str]   # Most frequently required skills
    by_field:          dict   # {"Software Engineering": 20, "Data Science": 10}


class InternshipImportResponse(BaseModel):
    """Returned after fetching jobs from external internship/job sources."""
    imported: int
    skipped: int
    sources: List[str]
    internships: List[InternshipResponse]


# ─── Application Schemas ──────────────────────────────────────────────────────

VALID_STATUSES = {"applied", "reviewing", "rejected", "accepted"}

class ApplicationCreate(BaseModel):
    """Body accepted by POST /applications."""
    internship_id: int  = Field(..., gt=0)
    notes:         Optional[str] = Field(None, max_length=1000)


class ApplicationUpdate(BaseModel):
    """Body accepted by PUT /applications/{id}."""
    status: Optional[str] = None
    notes:  Optional[str] = Field(None, max_length=1000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_STATUSES:
            raise ValueError(f"Status must be one of: {', '.join(VALID_STATUSES)}")
        return v


class ApplicationResponse(BaseModel):
    """Returned by GET /applications — includes nested internship summary."""
    id:           int
    internship:   InternshipResponse
    status:       str
    applied_at:   datetime
    notes:        Optional[str]

    model_config = {"from_attributes": True}


# ─── Match Schemas ────────────────────────────────────────────────────────────

class MatchResult(BaseModel):
    """A single internship match result with score breakdown."""
    internship:       InternshipResponse
    score_percent:    float           # 0–100 for display (score * 100)
    matching_skills:  List[str]       # Skills the student HAS that the job needs
    missing_skills:   List[str]       # Skills the student LACKS that the job needs


class SkillGapItem(BaseModel):
    """One entry in the skill gap analysis response."""
    skill_name:          str
    jobs_requiring_it:   int          # How many top-10 jobs need this skill
    suggested_course_url: str         # Hardcoded Coursera / YouTube link


class SkillGapResponse(BaseModel):
    user_skills: List[str]
    missing_skills: List[SkillGapItem]
