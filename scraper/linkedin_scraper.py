"""
scraper/sites/linkedin_scraper.py — Scrape LinkedIn Jobs public search.

Strategy:
  - LinkedIn's job search page is publicly accessible (no login required)
    at: https://www.linkedin.com/jobs/search/
  - Use Selenium for the listing page (JavaScript-rendered job cards).
  - Use requests + BeautifulSoup for individual job detail pages
    (faster than navigating with Selenium, and LinkedIn allows direct fetches).

Rate Limiting:
  LinkedIn aggressively rate-limits scrapers. Mitigations:
  - Max 50 jobs per run
  - Exponential backoff on 429 responses: 30s → 60s → 120s
  - 3-7 second random delay between job detail fetches
  - Random User-Agent rotation per request

CSS selectors for LinkedIn's public jobs page (as of 2024):
  May need updating if LinkedIn changes its layout.
"""

import logging
import time
from typing import Optional
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from scraper.base_scraper import BaseScraper
from scraper.utils.driver_manager import random_delay, safe_find_all, scroll_to_bottom
from scraper.utils.proxy_rotator import ProxyRotator

logger = logging.getLogger(__name__)

# ─── Selectors (LinkedIn public jobs page) ─────────────────────────────────────
SEL_JOB_CARD       = "div.base-card"
SEL_TITLE          = "h3.base-search-card__title"
SEL_COMPANY        = "h4.base-search-card__subtitle a"
SEL_LOCATION       = "span.job-search-card__location"
SEL_DATE           = "time.job-search-card__listdate"
SEL_LINK           = "a.base-card__full-link"

MAX_JOBS_PER_RUN   = 50    # Hard cap to avoid triggering LinkedIn's rate limit
BASE_SEARCH_URL    = "https://www.linkedin.com/jobs/search/"
BACKOFF_DELAYS     = [30, 60, 120]   # Seconds to wait on consecutive 429s


class LinkedInScraper(BaseScraper):
    """
    Scraper for LinkedIn Jobs public search — no authentication required.
    Uses Selenium for the listings page and requests for job detail pages.
    """

    SITE_NAME = "LinkedIn"

    def setup(self) -> None:
        """Initialize proxy rotator for requests-based detail fetches."""
        self.proxy_rotator = ProxyRotator()

    def _build_search_url(self, keyword: str, location: str, start: int = 0) -> str:
        """
        Build LinkedIn job search URL.

        LinkedIn uses `start` for pagination (25 results per page):
          start=0  → page 1
          start=25 → page 2
        """
        return (
            f"{BASE_SEARCH_URL}"
            f"?keywords={quote_plus('internship ' + keyword)}"
            f"&location={quote_plus(location)}"
            f"&f_E=1"        # Entry level experience filter
            f"&f_JT=I"       # Internship job type filter
            f"&start={start}"
        )

    def search(self, keyword: str, location: str) -> list[dict]:
        """
        Load LinkedIn job search results and extract job cards.

        We only paginate if we haven't hit MAX_JOBS_PER_RUN yet.
        For each card, we fetch the full job description via HTTP GET
        (faster than navigating Selenium to each URL).

        Returns:
            List of raw job dicts.
        """
        all_jobs = []
        driver   = self._get_driver()
        start    = 0

        while len(all_jobs) < MAX_JOBS_PER_RUN:
            url = self._build_search_url(keyword, location, start)
            logger.info("[LinkedIn] Loading: %s", url)
            driver.get(url)
            random_delay(3.0, 5.0)

            # LinkedIn shows a sign-in wall for some requests — detect it
            if "authwall" in driver.current_url or "login" in driver.current_url:
                logger.warning("[LinkedIn] Auth wall detected — using public search fallback.")
                break

            # Scroll to load lazy-rendered job cards (LinkedIn uses infinite scroll)
            scroll_to_bottom(driver, pauses=3, pause_sec=2.0)

            cards = safe_find_all(driver, SEL_JOB_CARD, timeout=10)
            if not cards:
                logger.info("[LinkedIn] No cards found at start=%d — stopping.", start)
                break

            logger.info("[LinkedIn] Found %d cards at start=%d", len(cards), start)

            for card in cards:
                if len(all_jobs) >= MAX_JOBS_PER_RUN:
                    break

                job = self.extract_job_data(card)
                if job and job.get("source_url"):
                    # Fetch full description using requests (faster, less suspicious)
                    desc, skills = self._fetch_job_detail(job["source_url"])
                    job["description"]     = desc or ""
                    job["required_skills"] = skills
                    all_jobs.append(job)
                    random_delay(3.0, 7.0)   # Polite delay between detail fetches

            # LinkedIn loads 25 jobs per page
            start += 25
            random_delay(4.0, 8.0)

            # Stop if we've seen all available results
            if len(cards) < 25:
                break

        logger.info("[LinkedIn] Total jobs extracted: %d", len(all_jobs))
        return all_jobs

    def extract_job_data(self, card) -> Optional[dict]:
        """
        Parse a single LinkedIn job card (div.base-card) into a raw job dict.

        LinkedIn's public search cards show: title, company, location, time posted, link.
        The full description is fetched separately in _fetch_job_detail().

        Returns:
            Raw job dict or None if extraction fails.
        """
        try:
            # ── Title ──────────────────────────────────────────────────────────
            title_el = card.find_element(By.CSS_SELECTOR, SEL_TITLE)
            title    = title_el.text.strip()

            # ── Company ────────────────────────────────────────────────────────
            try:
                company = card.find_element(By.CSS_SELECTOR, SEL_COMPANY).text.strip()
            except NoSuchElementException:
                company = "Unknown"

            # ── Location ───────────────────────────────────────────────────────
            try:
                location = card.find_element(By.CSS_SELECTOR, SEL_LOCATION).text.strip()
            except NoSuchElementException:
                location = ""

            # ── Date posted ────────────────────────────────────────────────────
            date_posted = None
            try:
                date_el     = card.find_element(By.CSS_SELECTOR, SEL_DATE)
                date_posted = date_el.get_attribute("datetime") or date_el.text.strip()
            except NoSuchElementException:
                pass

            # ── Job URL ─────────────────────────────────────────────────────────
            source_url = ""
            try:
                link_el    = card.find_element(By.CSS_SELECTOR, SEL_LINK)
                source_url = link_el.get_attribute("href") or ""
                # Strip LinkedIn tracking parameters — keep only the /view/ path
                if "linkedin.com/jobs/view/" in source_url:
                    source_url = source_url.split("?")[0]
            except NoSuchElementException:
                pass

            if not title:
                return None

            return {
                "title":           title,
                "company":         company,
                "location":        location,
                "deadline":        date_posted,
                "stipend_text":    None,         # LinkedIn rarely shows salary publicly
                "description":     "",           # Filled by _fetch_job_detail()
                "required_skills": [],
                "source_url":      source_url,
                "source_site":     self.SITE_NAME,
            }

        except Exception as e:
            logger.debug("[LinkedIn] Card extraction error: %s", e)
            return None

    def _fetch_job_detail(self, job_url: str) -> tuple[Optional[str], list[str]]:
        """
        Fetch a job's full description from its detail page using requests + BS4.

        Why not Selenium?
          Fetching 50 full pages via Selenium would take 5-10 minutes and
          generate obvious browser traffic. HTTP GET via requests is ~10x
          faster and looks more like normal API traffic.

        LinkedIn job detail page structure (public):
          - div.description__text → full job description
          - ul.job-criteria__list → skills/requirements section (sometimes)

        Args:
            job_url: Full LinkedIn job URL (e.g. linkedin.com/jobs/view/12345)

        Returns:
            Tuple of (description_text, skills_list).
            Both may be empty/None if the page couldn't be fetched.
        """
        response = self.proxy_rotator.make_request(job_url, timeout=15, retries=3)
        if not response:
            return None, []

        soup = BeautifulSoup(response.text, "html.parser")

        # ── Description ────────────────────────────────────────────────────────
        desc_el = soup.select_one("div.description__text")
        if not desc_el:
            # Fallback selector for LinkedIn's alternate layout
            desc_el = soup.select_one("div.show-more-less-html__markup")
        description = desc_el.get_text(separator=" ").strip()[:2000] if desc_el else ""

        # ── Skills section (LinkedIn sometimes shows explicit skill tags) ───────
        skills_text = ""
        skills_section = soup.select("li.job-criteria__item")
        for item in skills_section:
            header = item.select_one("h3")
            if header and "skill" in header.text.lower():
                skills_text += " " + item.get_text(separator=" ")

        # Extract canonical skills from both description + skills section
        from scraper.utils.data_cleaner import extract_skills_from_text
        skills = extract_skills_from_text(description + " " + skills_text)

        return description, skills
