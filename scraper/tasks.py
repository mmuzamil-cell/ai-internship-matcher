"""
scraper/tasks.py — Celery task definitions for scheduled and on-demand scraping.

Each task wraps a scraper class instance and calls its run() method.
Tasks are designed to be idempotent — running the same task twice won't
create duplicate listings thanks to the deduplicator.

Worker start command:
    celery -A scraper.tasks worker --loglevel=info --concurrency=2 -Q scraper,maintenance

Beat (scheduler) start command:
    celery -A scraper.tasks beat --loglevel=info

Monitor tasks in real time:
    celery -A scraper.tasks flower   (then open http://localhost:5555)
"""

import logging
import os
from datetime import datetime

import redis
from celery import Celery
from celery.utils.log import get_task_logger
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import the Celery config module
try:
    from scraper import celery_config
except ImportError:
    import celery_config

load_dotenv()
logger = get_task_logger(__name__)

# ─── Celery App Instance ───────────────────────────────────────────────────────
app = Celery("scraper")
app.config_from_object(celery_config)

# ─── DB & Redis factory helpers ────────────────────────────────────────────────
# Tasks create their own DB sessions (Celery workers are separate processes).
# We can't share the FastAPI app's session — each task must manage its own.

def _get_db_session():
    """
    Create a fresh SQLAlchemy session for use within a Celery task.

    Why not reuse the FastAPI session?
    Celery workers run in separate processes. SQLAlchemy sessions are not
    thread-safe or process-safe across boundaries. Each task creates and
    closes its own session to prevent connection leaks.
    """
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set in environment.")
    engine  = create_engine(db_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    return Session()


def _get_redis_client() -> redis.Redis:
    """Create a Redis client for deduplication cache within a Celery task."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return redis.Redis.from_url(redis_url, decode_responses=True)


# ─── Default scraping targets ─────────────────────────────────────────────────
DEFAULT_KEYWORDS  = [
    "software engineer", "data science", "machine learning", "web developer",
    "python developer", "react developer", "devops", "business analyst",
    "ui ux design", "cybersecurity", "cloud engineer", "mobile developer",
]
DEFAULT_LOCATIONS = ["Karachi", "Lahore", "Islamabad", "Remote"]


# ─── Individual site tasks ─────────────────────────────────────────────────────

@app.task(
    bind=True,
    name="scraper.tasks.scrape_indeed",
    max_retries=3,
    default_retry_delay=300,   # Retry after 5 minutes
)
def scrape_indeed(self, keywords: list[str] = None, locations: list[str] = None) -> dict:
    """
    Celery task: Scrape Indeed.com for internship listings.

    Args:
        keywords:  List of job keywords. Defaults to DEFAULT_KEYWORDS.
        locations: List of cities/locations. Defaults to DEFAULT_LOCATIONS.

    Returns:
        Stats dict with counts of found/saved/skipped jobs.
    """
    from scraper.sites.indeed_scraper import IndeedScraper

    keywords  = keywords  or DEFAULT_KEYWORDS[:4]    # Limit to 4 keywords per task
    locations = locations or DEFAULT_LOCATIONS

    db     = _get_db_session()
    redis_ = _get_redis_client()

    try:
        logger.info("Starting Indeed scrape task — %d keywords, %d locations",
                    len(keywords), len(locations))
        scraper = IndeedScraper(db_session=db, redis_client=redis_, headless=True)
        stats   = scraper.run(keywords=keywords, locations=locations)
        logger.info("Indeed task complete: %s", stats)
        return stats

    except Exception as exc:
        logger.error("Indeed task failed: %s", exc)
        # Retry with exponential backoff (300s, 600s, 1200s)
        raise self.retry(exc=exc, countdown=300 * (self.request.retries + 1))

    finally:
        db.close()


@app.task(
    bind=True,
    name="scraper.tasks.scrape_linkedin",
    max_retries=3,
    default_retry_delay=300,
)
def scrape_linkedin(self, keywords: list[str] = None, locations: list[str] = None) -> dict:
    """
    Celery task: Scrape LinkedIn Jobs public search.
    Limited to 50 jobs per run to avoid rate limiting.
    """
    from scraper.sites.linkedin_scraper import LinkedInScraper

    keywords  = keywords  or DEFAULT_KEYWORDS[:3]
    locations = locations or DEFAULT_LOCATIONS

    db     = _get_db_session()
    redis_ = _get_redis_client()

    try:
        logger.info("Starting LinkedIn scrape task")
        scraper = LinkedInScraper(db_session=db, redis_client=redis_, headless=True)
        stats   = scraper.run(keywords=keywords, locations=locations)
        logger.info("LinkedIn task complete: %s", stats)
        return stats

    except Exception as exc:
        logger.error("LinkedIn task failed: %s", exc)
        raise self.retry(exc=exc, countdown=300 * (self.request.retries + 1))

    finally:
        db.close()


@app.task(
    bind=True,
    name="scraper.tasks.scrape_rozee",
    max_retries=3,
    default_retry_delay=180,
)
def scrape_rozee(self, keywords: list[str] = None, locations: list[str] = None) -> dict:
    """
    Celery task: Scrape Rozee.pk for Pakistan-specific internship listings.
    """
    from scraper.sites.rozee_scraper import RozeeScraper

    keywords  = keywords  or DEFAULT_KEYWORDS[:5]
    locations = locations or ["Karachi", "Lahore", "Islamabad", "Rawalpindi"]

    db     = _get_db_session()
    redis_ = _get_redis_client()

    try:
        logger.info("Starting Rozee.pk scrape task")
        scraper = RozeeScraper(db_session=db, redis_client=redis_)
        stats   = scraper.run(keywords=keywords, locations=locations)
        logger.info("Rozee task complete: %s", stats)
        return stats

    except Exception as exc:
        logger.error("Rozee task failed: %s", exc)
        raise self.retry(exc=exc, countdown=180 * (self.request.retries + 1))

    finally:
        db.close()


@app.task(
    bind=True,
    name="scraper.tasks.scrape_internshala",
    max_retries=3,
    default_retry_delay=180,
)
def scrape_internshala(self, keywords: list[str] = None, locations: list[str] = None) -> dict:
    """
    Celery task: Scrape Internshala.com — includes remote internships open to all.
    """
    from scraper.sites.internshala_scraper import IntershalaScraper

    keywords  = keywords  or DEFAULT_KEYWORDS[:4]
    locations = locations or ["Remote", "Work From Home", "Karachi"]

    db     = _get_db_session()
    redis_ = _get_redis_client()

    try:
        logger.info("Starting Internshala scrape task")
        scraper = IntershalaScraper(db_session=db, redis_client=redis_)
        stats   = scraper.run(keywords=keywords, locations=locations)
        logger.info("Internshala task complete: %s", stats)
        return stats

    except Exception as exc:
        logger.error("Internshala task failed: %s", exc)
        raise self.retry(exc=exc, countdown=180)

    finally:
        db.close()


@app.task(
    bind=True,
    name="scraper.tasks.scrape_glassdoor",
    max_retries=2,
    default_retry_delay=600,   # Longer retry for Glassdoor (more fragile)
)
def scrape_glassdoor(self, keywords: list[str] = None, locations: list[str] = None) -> dict:
    """
    Celery task: Scrape Glassdoor internship listings.
    Uses fewer keywords due to Glassdoor's aggressive bot protection.
    """
    from scraper.sites.glassdoor_scraper import GlassdoorScraper

    keywords  = keywords  or DEFAULT_KEYWORDS[:2]    # Very conservative for Glassdoor
    locations = locations or ["Pakistan", "Remote"]

    db     = _get_db_session()
    redis_ = _get_redis_client()

    try:
        logger.info("Starting Glassdoor scrape task")
        scraper = GlassdoorScraper(db_session=db, redis_client=redis_, headless=True)
        stats   = scraper.run(keywords=keywords, locations=locations)
        logger.info("Glassdoor task complete: %s", stats)
        return stats

    except Exception as exc:
        logger.error("Glassdoor task failed: %s", exc)
        raise self.retry(exc=exc, countdown=600)

    finally:
        db.close()


@app.task(
    bind=True,
    name="scraper.tasks.scrape_api_sources",
    max_retries=3,
    default_retry_delay=60,
)
def scrape_api_sources(self, keywords: list[str] = None, locations: list[str] = None) -> dict:
    """
    Celery task: Fetch from Adzuna and JSearch APIs (more reliable than web scrapers).
    Runs twice daily since API calls are fast and don't risk bot detection.

    Returns combined stats from both API scrapers.
    """
    from scraper.api_scrapers.adzuna_scraper import AdzunaScraper
    from scraper.api_scrapers.jsearch_scraper import JSearchScraper

    keywords  = keywords  or DEFAULT_KEYWORDS
    locations = locations or DEFAULT_LOCATIONS

    db     = _get_db_session()
    redis_ = _get_redis_client()

    combined_stats = {"jobs_found": 0, "jobs_saved": 0, "jobs_updated": 0,
                      "jobs_skipped": 0, "errors": 0}

    try:
        # ── Adzuna ─────────────────────────────────────────────────────────────
        try:
            adzuna  = AdzunaScraper(db_session=db, redis_client=redis_)
            a_stats = adzuna.run(keywords=keywords, locations=locations)
            for k in combined_stats:
                combined_stats[k] += a_stats.get(k, 0)
            logger.info("Adzuna complete: %s", a_stats)
        except Exception as e:
            logger.error("Adzuna sub-task failed: %s", e)
            combined_stats["errors"] += 1

        # ── JSearch ────────────────────────────────────────────────────────────
        try:
            jsearch  = JSearchScraper(db_session=db, redis_client=redis_)
            j_stats  = jsearch.run(keywords=keywords, locations=locations)
            for k in combined_stats:
                combined_stats[k] += j_stats.get(k, 0)
            logger.info("JSearch complete: %s", j_stats)
        except Exception as e:
            logger.error("JSearch sub-task failed: %s", e)
            combined_stats["errors"] += 1

        logger.info("API sources task complete: %s", combined_stats)
        return combined_stats

    except Exception as exc:
        logger.error("API sources task failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)

    finally:
        db.close()


@app.task(name="scraper.tasks.scrape_all_sites")
def scrape_all_sites(keywords: list[str] = None, locations: list[str] = None) -> dict:
    """
    Orchestrator task: Triggers all site scrapers sequentially.

    Why sequential instead of parallel?
    - Running all scrapers simultaneously from one IP is a strong bot signal.
    - Sequential execution naturally introduces delays between sites.
    - Total runtime (~60-90 minutes) fits within the 24-hour scrape window.

    Each individual scraper is called as a Celery subtask so failures
    are isolated (one site failing doesn't stop the others).

    Returns:
        Aggregated stats from all scrapers.
    """
    keywords  = keywords  or DEFAULT_KEYWORDS
    locations = locations or DEFAULT_LOCATIONS

    logger.info("=== Starting full scrape_all_sites run at %s ===", datetime.utcnow().isoformat())

    # Build task chains using Celery's delay() for proper async dispatch
    # Each task runs after the previous one completes (sequential)
    task_results = {}

    tasks_to_run = [
        ("rozee",        scrape_rozee),        # Start with Pakistani sites (low anti-bot)
        ("internshala",  scrape_internshala),  # Then Indian platform with remote jobs
        ("api_sources",  scrape_api_sources),  # Reliable API-based scrapers
        ("linkedin",     scrape_linkedin),     # LinkedIn (rate-limit sensitive)
        ("indeed",       scrape_indeed),       # Indeed (bot-detection sensitive)
        ("glassdoor",    scrape_glassdoor),    # Glassdoor last (most aggressive protection)
    ]

    combined: dict = {"jobs_found": 0, "jobs_saved": 0, "jobs_updated": 0,
                      "jobs_skipped": 0, "errors": 0}

    for task_name, task_fn in tasks_to_run:
        try:
            logger.info("--- Launching task: %s ---", task_name)
            # apply() runs synchronously within the orchestrator context
            # This ensures sequential execution with proper error isolation
            result = task_fn.apply(kwargs={"keywords": keywords, "locations": locations})
            stats  = result.get(timeout=3600)   # Wait up to 1 hour per scraper

            task_results[task_name] = stats or {}
            for k in combined:
                combined[k] += (stats or {}).get(k, 0)

        except Exception as e:
            logger.error("Task %s failed in orchestrator: %s", task_name, e)
            task_results[task_name] = {"error": str(e)}
            combined["errors"] += 1

    logger.info("=== scrape_all_sites complete. Combined stats: %s ===", combined)
    logger.info("Per-site breakdown: %s", task_results)
    return {"combined": combined, "by_site": task_results}


@app.task(name="scraper.tasks.cleanup_old_jobs")
def cleanup_old_jobs() -> dict:
    """
    Maintenance task: Mark internship listings older than 60 days as inactive.

    Runs every Sunday at midnight PKT (configured in celery_config.beat_schedule).
    This keeps the job board fresh — students don't see expired listings.

    Returns:
        Dict with count of jobs marked inactive.
    """
    db     = _get_db_session()
    redis_ = _get_redis_client()

    try:
        from scraper.utils.deduplicator import Deduplicator
        dedup   = Deduplicator(redis_=redis_, db=db)
        count   = dedup.expire_old_jobs()
        result  = {"jobs_deactivated": count, "run_at": datetime.utcnow().isoformat()}
        logger.info("Cleanup task complete: %d jobs marked inactive.", count)
        return result

    except Exception as e:
        logger.error("Cleanup task failed: %s", e)
        return {"jobs_deactivated": 0, "error": str(e)}

    finally:
        db.close()
