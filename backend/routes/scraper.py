"""
routes/scraper.py — Web scraping endpoints for fetching internships from external sources.

These endpoints use lightweight HTTP requests (httpx + BeautifulSoup) to scrape
internship listings from multiple free sources and save them to the database.
No Selenium, Redis, or Docker required — works out of the box.

Sources:
  1. Remotive API        — Remote tech jobs (structured JSON API)
  2. Arbeitnow API       — European/international job board (JSON API)
  3. GitHub Jobs (via RSS)— Developer-focused jobs
  4. Internshala (HTML)   — Indian/Pakistani internships (HTML scraping)
  5. Indeed RSS           — General job listings via RSS feeds
"""

import json
import logging
import re
from datetime import datetime
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import Internship, get_db
from models.schemas import InternshipImportResponse, InternshipResponse
from routes.auth import get_current_user
from utils.skill_extractor import extract_skills

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scraper", tags=["Web Scraper"])

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_skills(skills_json: Optional[str]) -> List[str]:
    if not skills_json:
        return []
    try:
        return json.loads(skills_json)
    except (json.JSONDecodeError, TypeError):
        return []


def _internship_to_schema(job: Internship) -> InternshipResponse:
    return InternshipResponse(
        id=job.id,
        title=job.title,
        company=job.company,
        location=job.location,
        description=job.description,
        required_skills=_parse_skills(job.required_skills),
        stipend=job.stipend,
        deadline=job.deadline,
        source_url=job.source_url,
        source_site=job.source_site,
        scraped_at=job.scraped_at,
        is_active=job.is_active,
    )


def _dedupe_key(title: str, company: str, source_url: Optional[str]) -> tuple:
    return (
        (source_url or "").strip().lower(),
        title.strip().lower(),
        company.strip().lower(),
    )


def _clean_html(html_text: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:5000]  # Cap description length


def _build_rich_description(
    title: str,
    company: str,
    location: str,
    raw_desc: str,
    extra_info: dict = None,
) -> str:
    """Build a rich, readable description from available data."""
    parts = []

    # Main intro
    parts.append(f"{title} at {company}")
    if location:
        parts.append(f"Location: {location}")

    # Clean and add the raw description
    if raw_desc:
        cleaned = _clean_html(raw_desc)
        if cleaned:
            parts.append("")
            parts.append(cleaned)

    # Extra info (salary, date, etc.)
    if extra_info:
        if extra_info.get("salary"):
            parts.append(f"\nCompensation: {extra_info['salary']}")
        if extra_info.get("job_type"):
            parts.append(f"Job Type: {extra_info['job_type']}")
        if extra_info.get("date_posted"):
            parts.append(f"Posted: {extra_info['date_posted']}")
        if extra_info.get("category"):
            parts.append(f"Category: {extra_info['category']}")

    return "\n".join(parts) if parts else f"{title} position at {company}."


# ─── Source Scrapers ──────────────────────────────────────────────────────────

async def _scrape_remotive(keyword: str, limit: int, client: httpx.AsyncClient) -> list[dict]:
    """Fetch from Remotive API — structured JSON, very reliable."""
    jobs = []
    try:
        resp = await client.get(
            "https://remotive.com/api/remote-jobs",
            params={"search": keyword, "limit": min(limit, 50)},
        )
        resp.raise_for_status()
        for item in resp.json().get("jobs", [])[:limit]:
            title = (item.get("title") or "").strip()
            company = (item.get("company_name") or "").strip()
            if not title or not company:
                continue

            raw_desc = item.get("description", "")
            location = (item.get("candidate_required_location") or "Remote").strip()
            salary = item.get("salary") or None
            category = item.get("category") or ""
            job_type = item.get("job_type") or ""
            pub_date = item.get("publication_date") or ""

            description = _build_rich_description(
                title, company, location, raw_desc,
                extra_info={
                    "salary": salary,
                    "job_type": job_type,
                    "date_posted": pub_date[:10] if pub_date else "",
                    "category": category,
                },
            )

            tags = item.get("tags") or []
            skill_text = " ".join(str(t) for t in tags) + " " + title + " " + description
            skills = extract_skills(skill_text)[:12]

            jobs.append({
                "title": title[:255],
                "company": company[:200],
                "location": location[:150],
                "description": description,
                "required_skills": json.dumps(skills),
                "stipend": salary,
                "deadline": None,
                "source_url": item.get("url"),
                "source_site": "Remotive",
                "scraped_at": datetime.utcnow(),
                "is_active": True,
            })
    except Exception as exc:
        logger.warning("Remotive scrape failed: %s", exc)
    return jobs


async def _scrape_arbeitnow(keyword: str, limit: int, client: httpx.AsyncClient) -> list[dict]:
    """Fetch from Arbeitnow API — international jobs."""
    jobs = []
    try:
        resp = await client.get("https://www.arbeitnow.com/api/job-board-api")
        resp.raise_for_status()
        keyword_lower = keyword.lower()
        for item in resp.json().get("data", []):
            haystack = f"{item.get('title', '')} {item.get('description', '')} {' '.join(item.get('tags') or [])}".lower()
            if keyword_lower not in haystack and "intern" not in haystack:
                continue

            title = (item.get("title") or "").strip()
            company = (item.get("company_name") or "").strip()
            if not title or not company:
                continue

            raw_desc = item.get("description", "")
            is_remote = item.get("remote", False)
            location = (item.get("location") or ("Remote" if is_remote else "Not specified")).strip()

            description = _build_rich_description(
                title, company, location, raw_desc,
                extra_info={
                    "job_type": "Remote" if is_remote else "On-site",
                },
            )

            tags = item.get("tags") or []
            skill_text = " ".join(str(t) for t in tags) + " " + title + " " + description
            skills = extract_skills(skill_text)[:12]

            jobs.append({
                "title": title[:255],
                "company": company[:200],
                "location": location[:150],
                "description": description,
                "required_skills": json.dumps(skills),
                "stipend": None,
                "deadline": None,
                "source_url": item.get("url"),
                "source_site": "Arbeitnow",
                "scraped_at": datetime.utcnow(),
                "is_active": True,
            })
            if len(jobs) >= limit:
                break
    except Exception as exc:
        logger.warning("Arbeitnow scrape failed: %s", exc)
    return jobs


async def _scrape_github_jobs(keyword: str, limit: int, client: httpx.AsyncClient) -> list[dict]:
    """Scrape SimplifyJobs/Summer2025-Internships from GitHub as a source."""
    jobs = []
    try:
        resp = await client.get(
            "https://raw.githubusercontent.com/SimplifyJobs/Summer2025-Internships/dev/README.md"
        )
        if resp.status_code != 200:
            # Try alternate branch
            resp = await client.get(
                "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/README.md"
            )
        if resp.status_code != 200:
            return jobs

        lines = resp.text.split("\n")
        keyword_lower = keyword.lower()
        for line in lines:
            if "|" not in line or "---" in line or "Company" in line:
                continue

            cols = [c.strip() for c in line.split("|")]
            if len(cols) < 5:
                continue

            company = _clean_html(cols[1])
            title = _clean_html(cols[2])
            location = _clean_html(cols[3])
            date_added = _clean_html(cols[4]) if len(cols) > 4 else ""

            if not title or not company or company.lower() == "company":
                continue

            haystack = f"{title} {company} {location}".lower()
            if keyword_lower not in haystack and "intern" not in haystack:
                continue

            link_match = re.search(r'\[.*?\]\((https?://[^\)]+)\)', cols[1] + cols[2])
            source_url = link_match.group(1) if link_match else None

            description = _build_rich_description(
                title, company, location, "",
                extra_info={
                    "date_posted": date_added,
                    "category": "Summer Internship",
                },
            )
            description += (
                "\n\nThis internship is from the SimplifyJobs curated internship tracker on GitHub. "
                "Apply through the company's career page for full job description and requirements."
            )

            skills = extract_skills(title + " " + company + " " + location)[:8]

            jobs.append({
                "title": title[:255],
                "company": company[:200],
                "location": location[:150],
                "description": description,
                "required_skills": json.dumps(skills),
                "stipend": None,
                "deadline": None,
                "source_url": source_url,
                "source_site": "GitHub/SimplifyJobs",
                "scraped_at": datetime.utcnow(),
                "is_active": True,
            })
            if len(jobs) >= limit:
                break
    except Exception as exc:
        logger.warning("GitHub jobs scrape failed: %s", exc)
    return jobs


async def _scrape_findwork(keyword: str, limit: int, client: httpx.AsyncClient) -> list[dict]:
    """Fetch from FindWork.dev API — developer-focused jobs with good descriptions."""
    jobs = []
    try:
        resp = await client.get(
            "https://findwork.dev/api/jobs/",
            params={"search": keyword, "order_by": "-date_posted"},
            headers={"Accept": "application/json"},
        )
        if resp.status_code != 200:
            return jobs

        data = resp.json()
        results = data.get("results", []) if isinstance(data, dict) else []

        for item in results[:limit]:
            title = (item.get("role") or item.get("title") or "").strip()
            company = (item.get("company_name") or "").strip()
            if not title or not company:
                continue

            raw_desc = item.get("text") or item.get("description") or ""
            location = (item.get("location") or "Remote").strip()
            source_url = item.get("url") or None
            date_posted = (item.get("date_posted") or "")[:10]
            keywords_list = item.get("keywords") or []

            description = _build_rich_description(
                title, company, location, raw_desc,
                extra_info={
                    "date_posted": date_posted,
                    "category": ", ".join(keywords_list[:5]) if keywords_list else "",
                },
            )

            skill_text = " ".join(keywords_list) + " " + title + " " + raw_desc
            skills = extract_skills(skill_text)[:12]

            jobs.append({
                "title": title[:255],
                "company": company[:200],
                "location": location[:150],
                "description": description,
                "required_skills": json.dumps(skills),
                "stipend": None,
                "deadline": None,
                "source_url": source_url,
                "source_site": "FindWork.dev",
                "scraped_at": datetime.utcnow(),
                "is_active": True,
            })
    except Exception as exc:
        logger.warning("FindWork scrape failed: %s", exc)
    return jobs


async def _scrape_himalayas(keyword: str, limit: int, client: httpx.AsyncClient) -> list[dict]:
    """Fetch from Himalayas.app API — remote job board with rich descriptions."""
    jobs = []
    try:
        resp = await client.get(
            "https://himalayas.app/jobs/api",
            params={"limit": limit, "offset": 0},
        )
        if resp.status_code != 200:
            return jobs

        data = resp.json()
        items = data.get("jobs", []) if isinstance(data, dict) else []
        keyword_lower = keyword.lower()

        for item in items:
            title = (item.get("title") or "").strip()
            company = (item.get("companyName") or item.get("company_name") or "").strip()
            if not title or not company:
                continue

            haystack = f"{title} {company} {item.get('description', '')}".lower()
            if keyword_lower not in haystack and "intern" not in haystack:
                continue

            raw_desc = item.get("description") or ""
            location = (item.get("location") or "Remote").strip()
            salary_min = item.get("minSalary") or item.get("salary_min")
            salary_max = item.get("maxSalary") or item.get("salary_max")
            salary = None
            if salary_min and salary_max:
                salary = f"${salary_min:,} - ${salary_max:,}"
            elif salary_min:
                salary = f"From ${salary_min:,}"

            categories = item.get("categories") or []
            source_url = item.get("applicationLink") or item.get("url") or None

            description = _build_rich_description(
                title, company, location, raw_desc,
                extra_info={
                    "salary": salary,
                    "category": ", ".join(categories[:3]) if categories else "",
                },
            )

            skill_text = " ".join(categories) + " " + title + " " + raw_desc
            skills = extract_skills(skill_text)[:12]

            jobs.append({
                "title": title[:255],
                "company": company[:200],
                "location": location[:150],
                "description": description,
                "required_skills": json.dumps(skills),
                "stipend": salary,
                "deadline": None,
                "source_url": source_url,
                "source_site": "Himalayas",
                "scraped_at": datetime.utcnow(),
                "is_active": True,
            })
            if len(jobs) >= limit:
                break
    except Exception as exc:
        logger.warning("Himalayas scrape failed: %s", exc)
    return jobs


# ─── Available Sources ─────────────────────────────────────────────────────────

SCRAPER_REGISTRY = {
    "remotive": {
        "name": "Remotive",
        "description": "Remote tech jobs worldwide",
        "icon": "🌍",
        "fn": _scrape_remotive,
    },
    "arbeitnow": {
        "name": "Arbeitnow",
        "description": "International job board with tech focus",
        "icon": "🇪🇺",
        "fn": _scrape_arbeitnow,
    },
    "github": {
        "name": "GitHub/SimplifyJobs",
        "description": "Curated tech internship listings from GitHub",
        "icon": "🐙",
        "fn": _scrape_github_jobs,
    },
    "findwork": {
        "name": "FindWork.dev",
        "description": "Developer-focused job listings",
        "icon": "💻",
        "fn": _scrape_findwork,
    },
    "himalayas": {
        "name": "Himalayas",
        "description": "Remote jobs with detailed descriptions",
        "icon": "🏔️",
        "fn": _scrape_himalayas,
    },
}


# ─── API Routes ────────────────────────────────────────────────────────────────

@router.get(
    "/sources",
    summary="List all available scraping sources",
)
def list_sources():
    """Return the list of all available scraping sources with their metadata."""
    return {
        key: {
            "name": val["name"],
            "description": val["description"],
            "icon": val["icon"],
        }
        for key, val in SCRAPER_REGISTRY.items()
    }


@router.post(
    "/scrape",
    response_model=InternshipImportResponse,
    summary="Scrape internships from selected sources",
)
async def scrape_internships(
    keyword: str = Query("internship", min_length=2, max_length=80),
    sources: str = Query(
        "all",
        description="Comma-separated source keys (e.g., 'remotive,github') or 'all'",
    ),
    limit: int = Query(15, ge=1, le=50, description="Max results per source"),
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Scrape internship listings from one or multiple external sources.

    This endpoint fetches jobs using lightweight HTTP requests — no Selenium
    or browser automation required. Results are deduplicated against existing
    database entries and saved automatically.
    """
    # Determine which sources to scrape
    if sources.strip().lower() == "all":
        selected = list(SCRAPER_REGISTRY.keys())
    else:
        selected = [s.strip().lower() for s in sources.split(",") if s.strip()]
        invalid = [s for s in selected if s not in SCRAPER_REGISTRY]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown sources: {', '.join(invalid)}. Available: {', '.join(SCRAPER_REGISTRY.keys())}",
            )

    # Build existing dedupe set
    existing = {
        _dedupe_key(job.title, job.company, job.source_url)
        for job in db.query(Internship).all()
    }

    timeout = httpx.Timeout(25.0, connect=12.0)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    imported_jobs: list[Internship] = []
    skipped = 0
    source_names: set[str] = set()
    errors: list[str] = []

    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as client:
        for source_key in selected:
            source_info = SCRAPER_REGISTRY[source_key]
            scrape_fn = source_info["fn"]

            try:
                logger.info("Scraping %s for keyword '%s'...", source_info["name"], keyword)
                raw_jobs = await scrape_fn(keyword, limit, client)
                logger.info("Got %d jobs from %s", len(raw_jobs), source_info["name"])

                for job_data in raw_jobs:
                    key = _dedupe_key(
                        job_data["title"],
                        job_data["company"],
                        job_data.get("source_url"),
                    )
                    if key in existing:
                        skipped += 1
                        continue

                    job = Internship(**job_data)
                    db.add(job)
                    imported_jobs.append(job)
                    existing.add(key)
                    source_names.add(job_data["source_site"])

            except Exception as exc:
                logger.error("Error scraping %s: %s", source_key, exc)
                errors.append(f"{source_info['name']}: {str(exc)[:100]}")

    if imported_jobs:
        db.commit()
        for job in imported_jobs:
            db.refresh(job)

    if not imported_jobs and not skipped:
        if errors:
            detail = f"Scraping failed for all sources. Errors: {'; '.join(errors)}"
        else:
            detail = f"No internships found for keyword '{keyword}'. Try a different search term."
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)

    return InternshipImportResponse(
        imported=len(imported_jobs),
        skipped=skipped,
        sources=sorted(source_names),
        internships=[_internship_to_schema(job) for job in imported_jobs],
    )


@router.get(
    "/status",
    summary="Get scraping statistics",
)
def scraper_status(db: Session = Depends(get_db)):
    """Return statistics about scraped internships in the database."""
    total = db.query(Internship).count()
    active = db.query(Internship).filter(Internship.is_active == True).count()

    # Count by source
    all_jobs = db.query(Internship).all()
    by_source: dict[str, int] = {}
    for job in all_jobs:
        source = job.source_site or "Unknown"
        by_source[source] = by_source.get(source, 0) + 1

    # Find latest scrape time
    latest = db.query(Internship).order_by(Internship.scraped_at.desc()).first()
    last_scraped = latest.scraped_at.isoformat() if latest else None

    return {
        "total_internships": total,
        "active_internships": active,
        "by_source": by_source,
        "last_scraped_at": last_scraped,
        "available_sources": list(SCRAPER_REGISTRY.keys()),
    }
