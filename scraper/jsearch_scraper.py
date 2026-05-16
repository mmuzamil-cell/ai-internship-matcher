"""
scraper/api_scrapers/jsearch_scraper.py — Fetch internships via JSearch API on RapidAPI.

JSearch aggregates job listings from Google, Indeed, LinkedIn, Glassdoor, and
many other sources into a single API. It's more comprehensive than Adzuna but
requires a RapidAPI subscription (free tier: 200 requests/month).

RapidAPI registration: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch

Environment variables required:
  RAPIDAPI_KEY → Your RapidAPI key (from your RapidAPI dashboard)

JSearch is especially useful for finding remote internships open to candidates
from any country, which significantly expands opportunities for Pakistani students.
"""

import logging
import os
import time
from typing import Optional

import requests
from dotenv import load_dotenv

from scraper.base_scraper import BaseScraper
from scraper.utils.data_cleaner import extract_skills_from_text

load_dotenv()
logger = logging.getLogger(__name__)

JSEARCH_URL      = "https://jsearch.p.rapidapi.com/search"
RESULTS_PER_PAGE = 10    # JSearch returns max 10 per page on free tier
MAX_PAGES        = 5     # 5 pages × 10 = up to 50 results per query

# Queries designed to maximize Pakistani student opportunity coverage
SEARCH_QUERIES = [
    "internship Pakistan",
    "internship remote entry level",
    "software engineer internship Pakistan",
    "data science internship remote",
    "business internship Karachi Lahore",
]


class JSearchScraper(BaseScraper):
    """
    API-based scraper using JSearch via RapidAPI.
    Covers Google Jobs, Indeed, LinkedIn, and Glassdoor in a single API call.
    No browser or HTML parsing needed.
    """

    SITE_NAME = "JSearch"

    def setup(self) -> None:
        """Load RapidAPI key from environment."""
        self.api_key = os.getenv("RAPIDAPI_KEY", "")
        if not self.api_key:
            logger.warning(
                "[JSearch] RAPIDAPI_KEY not set. "
                "Register at https://rapidapi.com and subscribe to JSearch."
            )

        self.headers = {
            "X-RapidAPI-Key":  self.api_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
            "Content-Type":    "application/json",
        }

    def _api_request(self, query: str, page: int) -> Optional[dict]:
        """
        Make a single JSearch API request.

        Args:
            query: Full search query string.
            page:  Page number (1-based).

        Returns:
            Parsed JSON response dict, or None on error.
        """
        if not self.api_key:
            logger.error("[JSearch] Cannot make request — RAPIDAPI_KEY not set.")
            return None

        params = {
            "query":         query,
            "page":          str(page),
            "num_pages":     "1",
            "date_posted":   "month",        # Only last 30 days
            "employment_types": "INTERN",    # Internship filter
        }

        try:
            response = requests.get(
                JSEARCH_URL,
                headers = self.headers,
                params  = params,
                timeout = 20,
            )

            if response.status_code == 403:
                logger.error("[JSearch] Forbidden — check your RapidAPI key and subscription.")
                return None

            if response.status_code == 429:
                # RapidAPI rate limit — wait and retry once
                logger.warning("[JSearch] Rate limited — waiting 30 seconds.")
                time.sleep(30)
                response = requests.get(JSEARCH_URL, headers=self.headers, params=params, timeout=20)

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error("[JSearch] Request failed: %s", e)
            return None
        except ValueError as e:
            logger.error("[JSearch] JSON parse error: %s", e)
            return None

    def search(self, keyword: str, location: str) -> list[dict]:
        """
        Query JSearch API with Pakistan-focused internship search queries.

        The `keyword` and `location` args from BaseScraper.run() are combined
        with our predefined SEARCH_QUERIES for maximum coverage.

        JSearch's `employment_types=INTERN` filter handles the internship
        restriction at the API level, so we don't need to filter client-side.

        Returns:
            List of raw job dicts in standard format.
        """
        all_jobs = []

        # Build query combining base keyword, location, and standard queries
        custom_query = f"internship {keyword} {location}".strip()
        queries_to_run = [custom_query] + SEARCH_QUERIES

        # Deduplicate queries while preserving order
        seen_queries: set[str] = set()
        unique_queries = []
        for q in queries_to_run:
            if q.lower() not in seen_queries:
                seen_queries.add(q.lower())
                unique_queries.append(q)

        for query in unique_queries:
            logger.info("[JSearch] Query: '%s'", query)

            for page in range(1, MAX_PAGES + 1):
                data = self._api_request(query, page)
                if not data:
                    break

                # JSearch wraps results in a "data" key
                results = data.get("data", [])
                if not results:
                    logger.info("[JSearch] No results on page %d for '%s'", page, query)
                    break

                logger.info("[JSearch] Page %d: %d results", page, len(results))

                for item in results:
                    job = self.extract_job_data(item)
                    if job:
                        all_jobs.append(job)

                if len(results) < RESULTS_PER_PAGE:
                    break   # Last page

                time.sleep(1.5)   # Polite delay between pages

            time.sleep(2.0)   # Delay between different queries

        logger.info("[JSearch] Total jobs fetched: %d", len(all_jobs))
        return all_jobs

    def extract_job_data(self, item: dict) -> Optional[dict]:
        """
        Map a JSearch API result object to the standard job dict format.

        JSearch response fields (from Google Jobs schema):
          - job_title              → title
          - employer_name          → company
          - job_city / job_country → location
          - job_description        → full description text
          - job_highlights         → dict with "Qualifications", "Responsibilities"
          - job_required_skills    → list of skill strings (sometimes present)
          - job_salary_period/min/max → salary info
          - job_posted_at_datetime_utc → ISO 8601 timestamp
          - job_apply_link         → URL to application page
          - job_publisher          → source site name (Indeed, LinkedIn, etc.)

        Args:
            item: A single job result dict from the JSearch API.

        Returns:
            Standard job dict or None if title is missing.
        """
        try:
            title = (item.get("job_title") or "").strip()
            if not title:
                return None

            company  = (item.get("employer_name")  or "Unknown").strip()
            city     = (item.get("job_city")        or "").strip()
            country  = (item.get("job_country")     or "").strip()
            location = f"{city}, {country}".strip(", ") if city or country else ""

            # ── Description: combine body + highlights ─────────────────────────
            description = (item.get("job_description") or "").strip()

            # job_highlights has structured sections: {"Qualifications": [...], ...}
            highlights  = item.get("job_highlights") or {}
            quals       = " ".join(highlights.get("Qualifications", []))
            resps       = " ".join(highlights.get("Responsibilities", []))
            full_text   = f"{description} {quals} {resps}".strip()[:2000]

            # ── Skills: use API-provided list if available, else extract ────────
            api_skills  = item.get("job_required_skills") or []
            desc_skills = extract_skills_from_text(full_text)
            all_skills  = sorted(set(api_skills) | set(desc_skills))

            # ── Stipend ────────────────────────────────────────────────────────
            salary_min    = item.get("job_min_salary")
            salary_max    = item.get("job_max_salary")
            salary_period = item.get("job_salary_period") or "year"
            if salary_min and salary_max:
                stipend_text = f"{salary_min:,.0f} - {salary_max:,.0f} /{salary_period}"
            elif salary_min:
                stipend_text = f"{salary_min:,.0f} /{salary_period}"
            else:
                stipend_text = None

            # ── Date ───────────────────────────────────────────────────────────
            posted_at = item.get("job_posted_at_datetime_utc", "")
            deadline  = posted_at[:10] if posted_at else None

            # ── Source URL & publisher ─────────────────────────────────────────
            source_url  = (item.get("job_apply_link") or "").strip()
            publisher   = (item.get("job_publisher")   or self.SITE_NAME).strip()

            return {
                "title":           title,
                "company":         company,
                "location":        location,
                "stipend_text":    stipend_text,
                "deadline":        deadline,
                "description":     full_text,
                "required_skills": all_skills,
                "source_url":      source_url,
                # Credit the original publisher (Indeed, LinkedIn, etc.) when available
                "source_site":     f"JSearch/{publisher}" if publisher != self.SITE_NAME else self.SITE_NAME,
            }

        except Exception as e:
            logger.warning("[JSearch] Error mapping result: %s", e)
            return None
