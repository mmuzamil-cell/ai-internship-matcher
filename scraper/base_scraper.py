"""
scraper/base_scraper.py — Abstract base class for all site scrapers.

Every site-specific scraper (Indeed, LinkedIn, Rozee, etc.) inherits from
BaseScraper and must implement two abstract methods:
  - search(keyword, location) → raw job dicts
  - extract_job_data(element) → single standardized job dict

BaseScraper handles the shared orchestration pipeline:
  run() → search() → clean → deduplicate → save_to_db()

This design means each site scraper only needs to know how to find and
parse jobs on that site — all the save/dedup/log logic lives here.

Standard job dict format (ALL scrapers must return this shape):
  {
    "title":           str,
    "company":         str,
    "location":        str,         # Raw location string (cleaner normalizes it)
    "description":     str,         # Full job description text or HTML
    "required_skills": list[str],   # Skills explicitly listed (can be [])
    "stipend_text":    str|None,    # Raw salary/stipend string
    "deadline":        str|None,    # Raw date string (cleaner parses it)
    "source_url":      str,         # Canonical URL to the job posting
    "source_site":     str,         # "Indeed", "LinkedIn", "Rozee.pk", etc.
    "scraped_at":      str,         # ISO timestamp (set by base class)
  }
"""

import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

import redis
from sqlalchemy.orm import Session

from scraper.utils.data_cleaner import clean_job
from scraper.utils.deduplicator import Deduplicator
from scraper.utils.driver_manager import create_driver, random_delay

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Abstract base class that all job site scrapers inherit from.

    Subclasses must implement:
      - search(keyword, location) → list of raw job dicts
      - extract_job_data(element) → single raw job dict

    Subclasses may optionally override:
      - setup() → called after __init__ for site-specific setup
      - teardown() → called after scraping for cleanup
    """

    # Subclasses set this to identify themselves in logs and DB records
    SITE_NAME: str = "Unknown"

    def __init__(
        self,
        db_session:   Session,
        redis_client: redis.Redis,
        headless:     bool         = True,
        proxy:        Optional[str] = None,
        dry_run:      bool         = False,
    ):
        """
        Initialize the scraper with database and cache connections.

        Args:
            db_session:   SQLAlchemy session for PostgreSQL writes.
            redis_client: Redis client for deduplication cache.
            headless:     Run Chrome headless (False for local debugging).
            proxy:        Optional proxy string "http://host:port".
            dry_run:      If True, parse jobs but do NOT write to database.
        """
        self.db           = db_session
        self.redis        = redis_client
        self.headless     = headless
        self.proxy        = proxy
        self.dry_run      = dry_run
        self.driver       = None          # Initialized lazily in _get_driver()
        self.deduplicator = Deduplicator(redis_client, db_session)

        # Run statistics (reset per run() call)
        self._stats = {
            "jobs_found":  0,
            "jobs_saved":  0,
            "jobs_updated": 0,
            "jobs_skipped": 0,
            "errors":      0,
        }

        self.setup()

    def setup(self) -> None:
        """
        Optional hook called at end of __init__.
        Subclasses can override to do site-specific initialization
        (e.g., logging in, loading cookies) without overriding __init__.
        """
        pass

    def teardown(self) -> None:
        """
        Optional hook called after run() completes.
        Subclasses can override to clean up sessions, cookies, etc.
        """
        pass

    def _get_driver(self):
        """
        Lazily initialize the Selenium driver on first use.
        Not all scrapers need a browser (API scrapers and BS4 scrapers don't).
        """
        if self.driver is None:
            logger.info("[%s] Starting Chrome WebDriver…", self.SITE_NAME)
            self.driver = create_driver(headless=self.headless, proxy=self.proxy)
        return self.driver

    def _quit_driver(self) -> None:
        """Safely quit the WebDriver if it was initialized."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("[%s] WebDriver closed.", self.SITE_NAME)
            except Exception as e:
                logger.warning("[%s] Error closing WebDriver: %s", self.SITE_NAME, e)
            finally:
                self.driver = None

    @abstractmethod
    def search(self, keyword: str, location: str) -> list[dict]:
        """
        Search for internships matching keyword in location.

        Each implementing scraper navigates to the site's search page,
        extracts job cards, and returns a list of raw job dicts.

        Args:
            keyword:  Job keyword to search (e.g. "software engineer", "data science").
            location: City or region to filter by (e.g. "Karachi", "Remote").

        Returns:
            List of raw job dicts (inconsistent format — base class cleans them).
        """
        ...

    @abstractmethod
    def extract_job_data(self, element) -> Optional[dict]:
        """
        Extract structured data from a single job card element.

        Args:
            element: A Selenium WebElement or BeautifulSoup Tag representing
                     a single job listing card on the page.

        Returns:
            Raw job dict, or None if extraction fails (bad card, missing fields).
        """
        ...

    def save_to_db(self, jobs: list[dict]) -> dict:
        """
        Clean, deduplicate, and save a list of raw jobs to PostgreSQL.

        Pipeline:
          1. clean_job()          → normalize fields (location, stipend, deadline, skills)
          2. deduplicator         → check Redis + PostgreSQL for existing records
          3. INSERT or UPDATE     → new jobs inserted, refreshed jobs get updated timestamp
          4. Update stats         → track counts for the scraper_stats table

        Args:
            jobs: List of raw job dicts returned by search().

        Returns:
            Dict with counts: jobs_found, jobs_saved, jobs_updated, jobs_skipped, errors.
        """
        if not jobs:
            logger.info("[%s] No jobs to save.", self.SITE_NAME)
            return self._stats

        logger.info("[%s] Processing %d jobs…", self.SITE_NAME, len(jobs))

        for raw_job in jobs:
            try:
                # ── Step 1: Clean and normalize ───────────────────────────────
                cleaned = clean_job(raw_job)
                if cleaned is None:
                    # clean_job returns None for jobs missing title or company
                    self._stats["jobs_skipped"] += 1
                    continue

                # ── Step 2: Dry run — print but don't save ────────────────────
                if self.dry_run:
                    logger.info(
                        "[DRY RUN] Would save: [%s] %s @ %s (%d skills)",
                        cleaned.get("source_site"),
                        cleaned.get("title"),
                        cleaned.get("company"),
                        cleaned.get("_skills_count", 0),
                    )
                    self._stats["jobs_found"] += 1
                    continue

                # ── Step 3: Deduplicate and save ──────────────────────────────
                is_new, action = self.deduplicator.check_and_save(cleaned)

                if action == "inserted":
                    self._stats["jobs_saved"] += 1
                elif action == "updated":
                    self._stats["jobs_updated"] += 1
                elif action in ("duplicate", "error"):
                    self._stats["jobs_skipped"] += 1

                self._stats["jobs_found"] += 1

            except Exception as e:
                self._stats["errors"] += 1
                logger.error("[%s] Error processing job: %s — %s", self.SITE_NAME, raw_job.get("title"), e)
                continue

        return self._stats

    def save_run_stats(self) -> None:
        """
        Persist scraper run statistics to the scraper_stats database table.
        Called automatically at the end of run().
        """
        try:
            from database import ScraperStats
            stat = ScraperStats(
                site_name  = self.SITE_NAME,
                jobs_found = self._stats["jobs_found"],
                jobs_saved = self._stats["jobs_saved"],
                errors     = self._stats["errors"],
                run_at     = datetime.utcnow(),
            )
            self.db.add(stat)
            self.db.commit()
        except Exception as e:
            logger.warning("[%s] Could not save run stats: %s", self.SITE_NAME, e)

    def run(
        self,
        keywords:  list[str],
        locations: list[str],
        progress_bar=None,
    ) -> dict:
        """
        Main orchestration method — runs the full scraping pipeline.

        For each (keyword, location) combination:
          1. Call search(keyword, location) → raw jobs list
          2. Call save_to_db(raw_jobs) → clean, dedup, persist
          3. Add random delay between searches (anti-detection)

        Args:
            keywords:     List of search terms (e.g. ["software intern", "data intern"]).
            locations:    List of locations (e.g. ["Karachi", "Lahore", "Remote"]).
            progress_bar: Optional tqdm instance for CLI progress display.

        Returns:
            Final stats dict with total counts across all keyword/location combos.
        """
        # Reset stats for this run
        self._stats = {"jobs_found": 0, "jobs_saved": 0, "jobs_updated": 0, "jobs_skipped": 0, "errors": 0}

        logger.info(
            "[%s] Starting scrape — %d keywords × %d locations = %d searches",
            self.SITE_NAME, len(keywords), len(locations), len(keywords) * len(locations),
        )

        try:
            for keyword in keywords:
                for location in locations:
                    try:
                        logger.info("[%s] Searching: '%s' in '%s'", self.SITE_NAME, keyword, location)
                        raw_jobs = self.search(keyword, location)

                        if raw_jobs:
                            self.save_to_db(raw_jobs)

                        if progress_bar:
                            progress_bar.update(1)

                        # Polite delay between searches
                        random_delay(3.0, 7.0)

                    except Exception as e:
                        self._stats["errors"] += 1
                        logger.error(
                            "[%s] Failed on keyword='%s' location='%s': %s",
                            self.SITE_NAME, keyword, location, e,
                        )
                        continue

        finally:
            # Always run cleanup (quit driver, save stats) even if errors occur
            self._quit_driver()
            self.teardown()
            if not self.dry_run:
                self.save_run_stats()

        logger.info(
            "[%s] Done. Found: %d | Saved: %d | Updated: %d | Skipped: %d | Errors: %d",
            self.SITE_NAME,
            self._stats["jobs_found"],
            self._stats["jobs_saved"],
            self._stats["jobs_updated"],
            self._stats["jobs_skipped"],
            self._stats["errors"],
        )
        return self._stats
