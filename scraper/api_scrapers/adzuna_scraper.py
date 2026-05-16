"""
scraper/api_scrapers/adzuna_scraper.py — Fetch internships via the Adzuna Jobs API.

Adzuna offers a free tier API with 250 requests/month (no credit card required).
This is the most reliable scraping method since it uses an official API — no
anti-bot measures, no parsing fragility, and structured JSON responses.

Free API registration: https://developer.adzuna.com/

Environment variables required:
  ADZUNA_APP_ID  → Your Adzuna application ID
  ADZUNA_APP_KEY → Your Adzuna API key

API endpoint: https://api.adzuna.com/v1/api/jobs/{country}/search/{page}

Adzuna covers Pakistan (country code: "pk") and India ("in") which are most
relevant for Pakistani students seeking local or regional internships.
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

ADZUNA_BASE_URL  = "https://api.adzuna.com/v1/api/jobs"
RESULTS_PER_PAGE = 50    # Adzuna max per page
MAX_PAGES        = 3     # 3 pages × 50 = up to 150 results per search


class AdzunaScraper(BaseScraper):
    """
    API-based scraper for Adzuna Jobs.
    No browser needed — pure HTTP requests to the Adzuna REST API.
    Inherits from BaseScraper for clean/dedup/save pipeline.
    """

    SITE_NAME = "Adzuna"

    def setup(self) -> None:
        """Load API credentials from environment variables."""
        self.app_id  = os.getenv("ADZUNA_APP_ID",  "")
        self.app_key = os.getenv("ADZUNA_APP_KEY", "")

        if not self.app_id or not self.app_key:
            logger.warning(
                "[Adzuna] ADZUNA_APP_ID or ADZUNA_APP_KEY not set. "
                "Register free at https://developer.adzuna.com/"
            )

    def _api_request(self, country: str, page: int, what: str, where: str) -> Optional[dict]:
        """
        Make a single paginated request to the Adzuna API.

        Args:
            country: ISO 2-letter country code ("pk" for Pakistan, "in" for India).
            page:    Page number (1-based).
            what:    Job keyword query (e.g. "python internship").
            where:   Location query (e.g. "karachi").

        Returns:
            Parsed JSON response dict, or None on error.
        """
        if not self.app_id or not self.app_key:
            logger.error("[Adzuna] Cannot make request — missing API credentials.")
            return None

        url    = f"{ADZUNA_BASE_URL}/{country}/search/{page}"
        params = {
            "app_id":          self.app_id,
            "app_key":         self.app_key,
            "what":            what,
            "where":           where,
            "results_per_page": RESULTS_PER_PAGE,
            "content-type":    "application/json",
            "sort_by":         "date",      # Most recent first
            "max_days_old":    30,          # Posted within last 30 days
        }

        try:
            response = requests.get(url, params=params, timeout=20)

            # Adzuna returns 401 for invalid credentials — give a clear error
            if response.status_code == 401:
                logger.error("[Adzuna] Authentication failed. Check ADZUNA_APP_ID and ADZUNA_APP_KEY.")
                return None

            # Handle rate limiting (free tier: ~250 requests/month)
            if response.status_code == 429:
                logger.warning("[Adzuna] Rate limit hit — waiting 60 seconds.")
                time.sleep(60)
                return None

            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error("[Adzuna] API request failed: %s", e)
            return None
        except ValueError as e:
            logger.error("[Adzuna] JSON parse error: %s", e)
            return None

    def search(self, keyword: str, location: str) -> list[dict]:
        """
        Query the Adzuna API for internships matching keyword + location.

        We query both Pakistan ("pk") and India ("in") to maximize coverage,
        since many Pakistani students also apply to Indian remote roles.

        For each API result, we map Adzuna's field names to our standard format.

        Returns:
            List of raw job dicts in the standard BaseScraper format.
        """
        all_jobs = []
        # Search Pakistan first, then India for remote roles
        countries = [
            ("pk", location),       # Pakistan listings
            ("in", "remote"),       # Indian remote listings accessible to all
        ]

        for country_code, search_where in countries:
            logger.info("[Adzuna] Searching '%s' in '%s' (%s)", keyword, search_where, country_code)

            for page in range(1, MAX_PAGES + 1):
                data = self._api_request(
                    country = country_code,
                    page    = page,
                    what    = f"internship {keyword}",
                    where   = search_where,
                )

                if not data:
                    break

                results = data.get("results", [])
                if not results:
                    logger.info("[Adzuna] No results on page %d for %s/%s", page, country_code, search_where)
                    break

                logger.info("[Adzuna] Page %d: got %d results", page, len(results))

                for item in results:
                    job = self.extract_job_data(item)
                    if job:
                        all_jobs.append(job)

                # Stop early if fewer results than a full page (last page)
                if len(results) < RESULTS_PER_PAGE:
                    break

                time.sleep(1.0)   # Small delay between API pages to be polite

        logger.info("[Adzuna] Total jobs fetched: %d", len(all_jobs))
        return all_jobs

    def extract_job_data(self, item: dict) -> Optional[dict]:
        """
        Map an Adzuna API result object to the standard job dict format.

        Adzuna API response fields (relevant ones):
          - title           → job title
          - company.display_name → company name
          - location.display_name → location string
          - description     → HTML or plain text description
          - salary_min/max  → estimated salary range
          - redirect_url    → URL to the original job posting
          - created         → ISO 8601 creation timestamp

        Args:
            item: A single result dict from the Adzuna API "results" array.

        Returns:
            Standard job dict or None if title is missing.
        """
        try:
            title = (item.get("title") or "").strip()
            if not title:
                return None

            company  = item.get("company", {}).get("display_name", "Unknown").strip()
            location = item.get("location", {}).get("display_name", "").strip()

            # ── Stipend: build from salary_min/max if available ────────────────
            salary_min = item.get("salary_min")
            salary_max = item.get("salary_max")
            if salary_min and salary_max:
                stipend_text = f"{salary_min:,.0f} - {salary_max:,.0f} /year"
            elif salary_min:
                stipend_text = f"{salary_min:,.0f} /year"
            else:
                stipend_text = None

            # ── Description: Adzuna truncates to ~200 chars in search results ──
            # We store what we have; the full description is on the redirect URL
            description = (item.get("description") or "").strip()[:2000]

            # ── Skills from description ────────────────────────────────────────
            skills = extract_skills_from_text(description)

            # ── Date posted ────────────────────────────────────────────────────
            # Adzuna returns ISO 8601: "2024-05-01T10:30:00Z"
            created = item.get("created", "")
            deadline = created[:10] if created else None   # Take "YYYY-MM-DD" portion

            return {
                "title":           title,
                "company":         company,
                "location":        location,
                "stipend_text":    stipend_text,
                "deadline":        deadline,
                "description":     description,
                "required_skills": skills,
                "source_url":      item.get("redirect_url", "").strip(),
                "source_site":     self.SITE_NAME,
            }

        except Exception as e:
            logger.warning("[Adzuna] Error mapping result: %s", e)
            return None
