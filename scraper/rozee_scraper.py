"""
scraper/sites/rozee_scraper.py — Scrape internship listings from Rozee.pk.

Strategy:
  - Rozee.pk is Pakistan's largest job board and is mostly server-rendered HTML,
    making BeautifulSoup4 sufficient (no Selenium needed for basic listings).
  - Search URL returns paginated HTML with job cards.
  - Filter only internship/trainee positions by checking experience level.
  - Handle Urdu text by ensuring UTF-8 encoding throughout.

Rozee.pk Terms of Service note:
  Use reasonable request rates (5-10 second delays) and identify
  the scraper honestly if challenged. Prefer their RSS feed or API
  if one becomes available.
"""

import logging
import time
from typing import Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from scraper.base_scraper import BaseScraper
from scraper.utils.data_cleaner import extract_skills_from_text
from scraper.utils.driver_manager import random_delay
from scraper.utils.proxy_rotator import ProxyRotator

logger = logging.getLogger(__name__)

# ─── Rozee.pk search URL template ─────────────────────────────────────────────
BASE_SEARCH_URL = "https://www.rozee.pk/job/jsearch/q/{query}/fpn/{page}"
JOB_DETAIL_BASE = "https://www.rozee.pk"

# Keywords that indicate internship/trainee positions in the experience field
INTERNSHIP_KEYWORDS = {
    "internship", "intern", "trainee", "graduate trainee",
    "management trainee", "student", "fresher", "entry level",
}


class RozeeScraper(BaseScraper):
    """
    BeautifulSoup-based scraper for Rozee.pk — no Selenium required.
    Uses the proxy rotator for HTTP requests with proper Pakistani locale headers.
    """

    SITE_NAME = "Rozee.pk"

    def setup(self) -> None:
        """Initialize proxy rotator for all HTTP requests."""
        self.proxy_rotator = ProxyRotator()

    def _build_url(self, query: str, page: int = 1) -> str:
        """
        Build a Rozee.pk search URL for the given query and page number.

        Rozee uses path-based pagination: /fpn/1, /fpn/2, etc.
        """
        safe_query = quote_plus(query)
        return BASE_SEARCH_URL.format(query=safe_query, page=page)

    def _get_page(self, url: str) -> Optional[BeautifulSoup]:
        """
        Fetch a Rozee.pk page and parse it into a BeautifulSoup object.

        Rozee serves UTF-8 HTML — we explicitly set encoding to handle
        any Urdu text that appears in company names or job descriptions.

        Returns:
            BeautifulSoup object or None if the request failed.
        """
        response = self.proxy_rotator.make_request(url, timeout=20, retries=3)
        if not response:
            return None

        # Explicitly set encoding to UTF-8 to handle Urdu/Arabic characters correctly
        response.encoding = "utf-8"
        return BeautifulSoup(response.text, "html.parser")

    def search(self, keyword: str, location: str) -> list[dict]:
        """
        Search Rozee.pk for internship listings matching keyword and location.

        Rozee doesn't support location filtering in the URL the same way Indeed does,
        so we append the city to the search query and filter by location in the results.

        Process:
          1. Build search URL with keyword + location + "internship" combined.
          2. Fetch and parse each page of results (up to 5 pages).
          3. Filter results to only include internship/trainee level positions.
          4. For each valid card, fetch the detail page for the full description.

        Returns:
            List of raw job dicts for internship-level positions only.
        """
        all_jobs  = []
        # Combine keyword + location + "internship" for better relevance
        query     = f"internship {keyword} {location}".strip()
        max_pages = 5

        for page_num in range(1, max_pages + 1):
            url  = self._build_url(query, page_num)
            logger.info("[Rozee.pk] Page %d: %s", page_num, url)

            soup = self._get_page(url)
            if not soup:
                logger.warning("[Rozee.pk] Failed to fetch page %d", page_num)
                break

            # Rozee job cards are inside div.job-listing or similar wrappers
            # Try multiple selectors as Rozee sometimes updates its markup
            cards = (
                soup.select("div.job-listing") or
                soup.select("div.fjl") or              # Alternate listing class
                soup.select("li.job-item") or
                soup.select("div[class*='job']")        # Broad fallback
            )

            if not cards:
                logger.info("[Rozee.pk] No job cards found on page %d — stopping.", page_num)
                break

            logger.info("[Rozee.pk] Found %d cards on page %d", len(cards), page_num)

            for card in cards:
                job = self.extract_job_data(card)
                if job is None:
                    continue

                # ── Filter: only internship/trainee positions ──────────────────
                exp_text = (job.get("_experience_level") or "").lower()
                title_lower = job["title"].lower()
                is_internship = (
                    any(kw in exp_text for kw in INTERNSHIP_KEYWORDS) or
                    any(kw in title_lower for kw in INTERNSHIP_KEYWORDS)
                )
                if not is_internship:
                    logger.debug("[Rozee.pk] Skipping non-internship: %s", job["title"])
                    continue

                # ── Fetch detail page for full description ─────────────────────
                if job.get("source_url"):
                    detail_url = job["source_url"]
                    if not detail_url.startswith("http"):
                        detail_url = JOB_DETAIL_BASE + detail_url

                    desc, skills = self._fetch_detail_page(detail_url)
                    job["description"]     = desc or job.get("description", "")
                    job["required_skills"] = skills

                all_jobs.append(job)
                random_delay(3.0, 6.0)   # Respectful delay between detail page fetches

            # Stop if we got fewer results than a full page (last page)
            if len(cards) < 10:
                logger.info("[Rozee.pk] Partial page — reached end of results.")
                break

            random_delay(4.0, 7.0)   # Delay between search result pages

        logger.info("[Rozee.pk] Total internship jobs found: %d", len(all_jobs))
        return all_jobs

    def extract_job_data(self, card) -> Optional[dict]:
        """
        Parse a single Rozee.pk job card (BeautifulSoup Tag) into a raw job dict.

        Rozee's card structure contains:
          - Job title (linked to detail page)
          - Company name
          - City / location
          - Salary range (optional)
          - Experience level (used for filtering)
          - Application deadline (optional)

        Handles Urdu text by reading the string directly as UTF-8 without re-encoding.

        Args:
            card: BeautifulSoup Tag representing one job listing card.

        Returns:
            Raw job dict or None if title/company are missing.
        """
        try:
            # ── Title and URL ──────────────────────────────────────────────────
            title_tag  = card.select_one("a.job-title") or card.select_one("h2 a") or card.select_one("a.title")
            if not title_tag:
                return None

            # Ensure title is properly decoded as UTF-8 (handles Urdu company names)
            title      = title_tag.get_text(strip=True).encode("utf-8", errors="replace").decode("utf-8")
            source_url = title_tag.get("href", "")
            if source_url and not source_url.startswith("http"):
                source_url = JOB_DETAIL_BASE + source_url

            # ── Company name ───────────────────────────────────────────────────
            company_tag = (
                card.select_one("span.company-name") or
                card.select_one("a.company") or
                card.select_one("div.company")
            )
            company = company_tag.get_text(strip=True) if company_tag else "Unknown"
            # Handle Urdu company names
            company = company.encode("utf-8", errors="replace").decode("utf-8")

            # ── Location / city ────────────────────────────────────────────────
            location_tag = (
                card.select_one("span.city") or
                card.select_one("div.location") or
                card.select_one("span.location")
            )
            location = location_tag.get_text(strip=True) if location_tag else ""

            # ── Salary / stipend ───────────────────────────────────────────────
            salary_tag = card.select_one("span.salary") or card.select_one("div.salary")
            stipend_text = salary_tag.get_text(strip=True) if salary_tag else None

            # ── Experience level (used for filtering, not stored directly) ──────
            exp_tag = (
                card.select_one("span.exp") or
                card.select_one("span.experience") or
                card.select_one("div.experience")
            )
            exp_level = exp_tag.get_text(strip=True).lower() if exp_tag else ""

            # ── Deadline ───────────────────────────────────────────────────────
            deadline_tag = card.select_one("span.deadline") or card.select_one("div.deadline")
            deadline = deadline_tag.get_text(strip=True) if deadline_tag else None

            if not title or title.strip() == "":
                return None

            return {
                "title":              title,
                "company":            company,
                "location":           location,
                "stipend_text":       stipend_text,
                "deadline":           deadline,
                "description":        "",    # Filled by _fetch_detail_page()
                "required_skills":    [],
                "source_url":         source_url,
                "source_site":        self.SITE_NAME,
                "_experience_level":  exp_level,  # Used for internship filter, not saved to DB
            }

        except Exception as e:
            logger.warning("[Rozee.pk] Card extraction error: %s", e)
            return None

    def _fetch_detail_page(self, url: str) -> tuple[Optional[str], list[str]]:
        """
        Fetch a Rozee.pk job detail page and extract the full description + skills.

        The detail page contains a rich description with requirements, responsibilities,
        and sometimes an explicit skills section. We parse all of this for skill detection.

        Args:
            url: Full URL to the job detail page.

        Returns:
            Tuple of (description_text, extracted_skills_list).
        """
        response = self.proxy_rotator.make_request(url, timeout=20, retries=2)
        if not response:
            return None, []

        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")

        # Try multiple selector patterns for Rozee's description container
        desc_el = (
            soup.select_one("div.job-description") or
            soup.select_one("div#job-description") or
            soup.select_one("div.description") or
            soup.select_one("section.job-desc")
        )

        description = ""
        if desc_el:
            description = desc_el.get_text(separator=" ", strip=True)[:2000]

        # Extract skills from the full description text
        skills = extract_skills_from_text(description)

        return description, skills
