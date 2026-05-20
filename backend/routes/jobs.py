"""
routes/jobs.py — Internship listing endpoints + Application tracker.

Internship Endpoints:
  GET  /jobs           → Paginated list with optional filters
  GET  /jobs/stats     → Aggregate stats (by city, field, top skills)
  GET  /jobs/{id}      → Single internship detail
  POST /jobs           → Admin-only: manually add an internship

Application Endpoints:
  POST /applications        → Apply to an internship
  GET  /applications        → List current user's applications
  PUT  /applications/{id}   → Update application status or notes
"""

import json
import logging
from collections import Counter
from datetime import datetime, timezone
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import Application, Internship, get_db
from models.schemas import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationUpdate,
    InternshipCreate,
    InternshipImportResponse,
    InternshipResponse,
    InternshipStats,
)
from routes.auth import get_current_user, require_admin
from utils.skill_extractor import extract_skills

logger = logging.getLogger(__name__)

jobs_router = APIRouter(prefix="/jobs", tags=["Internships"])
apps_router = APIRouter(prefix="/applications", tags=["Applications"])


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_skills(skills_json: Optional[str]) -> List[str]:
    """
    Parse a skills JSON string into a Python list.
    Returns [] if the string is null, empty, or invalid JSON.
    """
    if not skills_json:
        return []
    try:
        return json.loads(skills_json)
    except (json.JSONDecodeError, TypeError):
        return []


def _internship_to_schema(job: Internship) -> InternshipResponse:
    """Convert an Internship ORM object to its Pydantic response schema."""
    return InternshipResponse(
        id              = job.id,
        title           = job.title,
        company         = job.company,
        location        = job.location,
        description     = job.description,
        required_skills = _parse_skills(job.required_skills),
        stipend         = job.stipend,
        deadline        = job.deadline,
        source_url      = job.source_url,
        source_site     = job.source_site,
        scraped_at      = job.scraped_at,
        is_active       = job.is_active,
    )


def _dedupe_key(title: str, company: str, source_url: Optional[str]) -> tuple:
    """Build a stable duplicate key for imported jobs."""
    return ((source_url or "").strip().lower(), title.strip().lower(), company.strip().lower())


def _normalize_external_job(raw: dict) -> Optional[dict]:
    """Convert a job from a supported external API into our Internship fields."""
    source = raw.get("_source")
    if source == "Remotive":
        title = raw.get("title") or ""
        company = raw.get("company_name") or "Unknown company"
        description = raw.get("description") or ""
        location = raw.get("candidate_required_location") or "Remote"
        source_url = raw.get("url")
        tags = raw.get("tags") or []
    elif source == "Arbeitnow":
        title = raw.get("title") or ""
        company = raw.get("company_name") or "Unknown company"
        description = raw.get("description") or ""
        location = raw.get("location") or ("Remote" if raw.get("remote") else "Not specified")
        source_url = raw.get("url")
        tags = raw.get("tags") or []
    else:
        return None

    title = title.strip()
    company = company.strip()
    if not title or not company:
        return None

    skill_text = " ".join(str(tag) for tag in tags) + " " + title + " " + description
    skills = extract_skills(skill_text)[:12]

    return {
        "title": title[:255],
        "company": company[:200],
        "location": str(location or "Not specified")[:150],
        "description": description,
        "required_skills": json.dumps(skills),
        "stipend": None,
        "deadline": None,
        "source_url": source_url,
        "source_site": source,
        "scraped_at": datetime.now(timezone.utc),
        "is_active": True,
    }


async def _fetch_external_jobs(keyword: str, limit: int) -> list[dict]:
    """Fetch internships/jobs from API-backed sources instead of scraping Google HTML."""
    jobs: list[dict] = []
    timeout = httpx.Timeout(15.0, connect=8.0)
    headers = {"User-Agent": "AI-Internship-Matcher-FYP/1.0"}

    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as client:
        try:
            remotive = await client.get(
                "https://remotive.com/api/remote-jobs",
                params={"search": keyword},
            )
            remotive.raise_for_status()
            for item in remotive.json().get("jobs", [])[:limit]:
                item["_source"] = "Remotive"
                jobs.append(item)
        except Exception as exc:
            logger.warning("Remotive fetch failed: %s", exc)

        try:
            arbeitnow = await client.get("https://www.arbeitnow.com/api/job-board-api")
            arbeitnow.raise_for_status()
            keyword_lower = keyword.lower()
            for item in arbeitnow.json().get("data", []):
                haystack = f"{item.get('title', '')} {item.get('description', '')} {' '.join(item.get('tags') or [])}".lower()
                if keyword_lower in haystack or "intern" in haystack:
                    item["_source"] = "Arbeitnow"
                    jobs.append(item)
                if len(jobs) >= limit * 2:
                    break
        except Exception as exc:
            logger.warning("Arbeitnow fetch failed: %s", exc)

    return jobs[:limit]


# ─── Internship Routes ────────────────────────────────────────────────────────

@jobs_router.get(
    "/stats",
    response_model=InternshipStats,
    summary="Aggregated internship statistics",
)
def get_stats(db: Session = Depends(get_db)):
    """
    Returns aggregate stats across all active internships:
      - total_active: count of live listings
      - by_city: distribution across cities (includes Remote)
      - top_skills: 10 most-requested skills
      - by_field: grouped by common tech fields (heuristic keyword matching)

    This endpoint is public (no auth required) — useful for a dashboard landing page.
    Note: /stats must be registered BEFORE /{id} so FastAPI doesn't try to
    interpret "stats" as an integer route parameter.
    """
    jobs = db.query(Internship).filter(Internship.is_active == True).all()

    # ── By city ────────────────────────────────────────────────────────────────
    city_counter: Counter = Counter()
    for job in jobs:
        city = (job.location or "Unknown").strip()
        city_counter[city] += 1

    # ── Top required skills ────────────────────────────────────────────────────
    skill_counter: Counter = Counter()
    for job in jobs:
        for skill in _parse_skills(job.required_skills):
            skill_counter[skill.lower()] += 1

    top_skills = [skill for skill, _ in skill_counter.most_common(10)]

    # ── By field (heuristic grouping by title keywords) ────────────────────────
    field_keywords = {
        "Software Engineering": ["software", "backend", "frontend", "fullstack", "developer", "engineer"],
        "Data Science":         ["data science", "data analyst", "ml", "machine learning", "ai"],
        "DevOps / Cloud":       ["devops", "cloud", "aws", "azure", "kubernetes", "sre"],
        "UI/UX Design":         ["ui", "ux", "design", "figma", "product design"],
        "Cybersecurity":        ["security", "cyber", "penetration", "soc"],
        "Mobile Development":   ["mobile", "android", "ios", "flutter", "react native"],
        "Other":                [],
    }
    field_counter: Counter = Counter()
    for job in jobs:
        title_lower = job.title.lower()
        matched = False
        for field, keywords in field_keywords.items():
            if field == "Other":
                continue
            if any(kw in title_lower for kw in keywords):
                field_counter[field] += 1
                matched = True
                break
        if not matched:
            field_counter["Other"] += 1

    return InternshipStats(
        total_active = len(jobs),
        by_city      = dict(city_counter.most_common()),
        top_skills   = top_skills,
        by_field     = dict(field_counter.most_common()),
    )


@jobs_router.get(
    "",
    response_model=List[InternshipResponse],
    summary="List active internships with optional filters",
)
def list_jobs(
    skill:  Optional[str] = Query(None, description="Filter by required skill, e.g. 'python'"),
    city:   Optional[str] = Query(None, description="Filter by city, e.g. 'Karachi'"),
    remote: Optional[bool]= Query(None, description="True = remote only listings"),
    limit:  int           = Query(20, ge=1, le=100),
    offset: int           = Query(0, ge=0),
    db:     Session       = Depends(get_db),
):
    """
    Return a paginated list of active internships.

    Filters can be combined:
      - ?skill=python         → jobs where required_skills JSON contains "python"
      - ?city=karachi         → case-insensitive city match
      - ?remote=true          → jobs where location contains "remote"
      - ?limit=10&offset=20   → second page of 10 results
    """
    query = db.query(Internship).filter(Internship.is_active == True)

    # City filter — case-insensitive substring match
    if city:
        escaped_city = city.replace("%", "\\%").replace("_", "\\_")
        query = query.filter(Internship.location.ilike(f"%{escaped_city}%"))

    # Remote filter — checks for "remote" in location string
    if remote is True:
        query = query.filter(Internship.location.ilike("%remote%"))

    # Skill filter is done in Python because skills are stored as a JSON string.
    # We must filter BEFORE pagination to return the correct number of results.
    if skill:
        skill_lower = skill.lower()
        all_matching = query.order_by(Internship.scraped_at.desc()).all()
        all_matching = [j for j in all_matching if skill_lower in [s.lower() for s in _parse_skills(j.required_skills)]]
        jobs = all_matching[offset : offset + limit]
    else:
        jobs = query.order_by(Internship.scraped_at.desc()).offset(offset).limit(limit).all()

    return [_internship_to_schema(j) for j in jobs]


@jobs_router.get(
    "/{job_id}",
    response_model=InternshipResponse,
    summary="Get a single internship by ID",
)
def get_job(job_id: int, db: Session = Depends(get_db)):
    """Return full details for a single internship listing."""
    job = db.query(Internship).filter(Internship.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Internship with id={job_id} not found.",
        )
    return _internship_to_schema(job)


@jobs_router.post(
    "",
    response_model=InternshipResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Admin] Manually add an internship listing",
)
def create_job(
    job_in:       InternshipCreate,
    _admin_user               = Depends(require_admin),  # Enforces admin-only access
    db:           Session     = Depends(get_db),
):
    """
    Allow an admin user to manually add an internship (e.g., from a partner company).
    required_skills list is serialized to JSON for storage.
    """
    new_job = Internship(
        title           = job_in.title,
        company         = job_in.company,
        location        = job_in.location,
        description     = job_in.description,
        required_skills = json.dumps(job_in.required_skills or []),
        stipend         = job_in.stipend,
        deadline        = job_in.deadline,
        source_url      = job_in.source_url,
        source_site     = job_in.source_site or "Manual",
        is_active       = True,
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    return _internship_to_schema(new_job)


@jobs_router.post(
    "/import-external",
    response_model=InternshipImportResponse,
    summary="Fetch internships from external job platforms and save them",
)
async def import_external_jobs(
    keyword: str = Query("internship", min_length=2, max_length=80),
    limit: int = Query(20, ge=1, le=50),
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Import live listings from API-backed job platforms.

    Google search result scraping is intentionally avoided because it is fragile
    and frequently blocked. These sources provide structured job data that can be
    saved and shown in the existing internship detail pages.
    """
    raw_jobs = await _fetch_external_jobs(keyword=keyword, limit=limit)
    if not raw_jobs:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not fetch jobs from external platforms right now. Please try again later.",
        )

    existing = {
        _dedupe_key(r.title, r.company, r.source_url)
        for r in db.query(Internship.title, Internship.company, Internship.source_url).all()
    }

    imported_jobs: list[Internship] = []
    skipped = 0
    sources = set()

    for raw in raw_jobs:
        normalized = _normalize_external_job(raw)
        if not normalized:
            skipped += 1
            continue

        key = _dedupe_key(normalized["title"], normalized["company"], normalized["source_url"])
        if key in existing:
            skipped += 1
            continue

        job = Internship(**normalized)
        db.add(job)
        imported_jobs.append(job)
        existing.add(key)
        sources.add(normalized["source_site"])

    db.commit()
    for job in imported_jobs:
        db.refresh(job)

    return InternshipImportResponse(
        imported=len(imported_jobs),
        skipped=skipped,
        sources=sorted(sources),
        internships=[_internship_to_schema(job) for job in imported_jobs],
    )


# ─── Application Routes ───────────────────────────────────────────────────────

@apps_router.post(
    "",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apply to an internship",
)
def apply(
    app_in:       ApplicationCreate,
    current_user              = Depends(get_current_user),
    db:           Session     = Depends(get_db),
):
    """
    Create an Application record linking the current user to an internship.
    Status starts as 'applied'.
    Prevents duplicate applications for the same (user, internship) pair.
    """
    # Ensure the internship exists and is active
    job = db.query(Internship).filter(
        Internship.id == app_in.internship_id,
        Internship.is_active == True,
    ).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Active internship with id={app_in.internship_id} not found.",
        )

    # Prevent duplicate applications
    existing = db.query(Application).filter(
        Application.user_id       == current_user.id,
        Application.internship_id == app_in.internship_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You have already applied to this internship.",
        )

    application = Application(
        user_id       = current_user.id,
        internship_id = app_in.internship_id,
        status        = "applied",
        notes         = app_in.notes,
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    # Build response manually since we need the nested internship object
    return ApplicationResponse(
        id          = application.id,
        internship  = _internship_to_schema(job),
        status      = application.status,
        applied_at  = application.applied_at,
        notes       = application.notes,
    )


@apps_router.get(
    "",
    response_model=List[ApplicationResponse],
    summary="List all applications for the current user",
)
def list_applications(
    current_user = Depends(get_current_user),
    db: Session  = Depends(get_db),
):
    """Return all applications for the logged-in student, most recent first."""
    apps = (
        db.query(Application)
        .filter(Application.user_id == current_user.id)
        .order_by(Application.applied_at.desc())
        .all()
    )
    return [
        ApplicationResponse(
            id         = a.id,
            internship = _internship_to_schema(a.internship),
            status     = a.status,
            applied_at = a.applied_at,
            notes      = a.notes,
        )
        for a in apps
    ]


@apps_router.put(
    "/{app_id}",
    response_model=ApplicationResponse,
    summary="Update application status or notes",
)
def update_application(
    app_id:       int,
    updates:      ApplicationUpdate,
    current_user              = Depends(get_current_user),
    db:           Session     = Depends(get_db),
):
    """
    Update the status or personal notes on an application.
    Only the owner of the application can update it.
    """
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application with id={app_id} not found.",
        )
    if app.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update your own applications.",
        )

    if updates.status is not None:
        app.status = updates.status
    if updates.notes is not None:
        app.notes = updates.notes

    db.commit()
    db.refresh(app)

    return ApplicationResponse(
        id         = app.id,
        internship = _internship_to_schema(app.internship),
        status     = app.status,
        applied_at = app.applied_at,
        notes      = app.notes,
    )
