"""
scraper/sites/indeed_scraper.py — Scrape internship listings from Indeed.com.

Strategy:
  - Use Selenium (undetected-chromedriver) because Indeed's job cards
    are dynamically rendered and protected by Cloudflare bot checks.
  - Navigate to search URL, scroll to load lazy-loaded cards, paginate.
  - Click each card to reveal the full description in the right panel.
  - Extract skills from the description using the data_cleaner skill detector.

Anti-blocking measures:
  - Random delays between every action (2-5 seconds)
  - Session cookie acceptance to pass cookie walls
  - Rotate User-Agent on each new driver session
  - Max 5 pages per search to avoid triggering rate limits
  - Handle CAPTCHA gracefully (log and skip, don't crash)

Note: Indeed's HTML structure changes frequently. Selectors are kept in
      constants at the top of the file for easy updates when the site changes.
"""

import logging
import time
from typing import Optional
from urllib.parse import quote_plus

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from scraper.base_scraper import BaseScraper
from scraper.utils.driver_manager import random_delay, safe_find, safe_find_all, scroll_to_bottom

logger = logging.getLogger(__name__)

# ─── CSS Selectors (update these when Indeed changes its layout) ───────────────
SEL_JOB_CARD      = "div.job_seen_beacon"          # Individual job listing card
SEL_JOB_TITLE     = "h2.jobTitle span[title]"      # Job title text
SEL_COMPANY       = "span[data-testid='company-name']"
SEL_LOCATION      = "div[data-testid='text-location']"
SEL_SALARY        = "div[data-testid='attribute_snippet_testid']"
SEL_DATE_POSTED   = "span[data-testid='myJobsStateDate']"
SEL_DESCRIPTION   = "div#jobDescriptionText"        # Full description panel
SEL_NEXT_BUTTON   = "a[data-testid='pagination-page-next']"
SEL_COOKIE_ACCEPT = "button#onetrust-accept-btn-handler"  # Cookie consent

MAX_PAGES  = 5    # Scrape at most 5 pages per search to stay safe
BASE_URL   = "https://www.indeed.com/jobs"


class IndeedScraper(BaseScraper):
    """Selenium-based scraper for Indeed.com internship listings."""

    SITE_NAME = "Indeed"

    def setup(self) -> None:
        """Initialize driver on setup (Indeed always requires Selenium)."""
        self._driver = self._get_driver()

    def _accept_cookies(self) -> None:
        """
        Click the cookie consent banner if it appears.
        Indeed shows this on first visit from certain regions.
        Failing to accept it can block interaction with the page.
        """
        try:
            btn = WebDriverWait(self._driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, SEL_COOKIE_ACCEPT))
            )
            btn.click()
            logger.debug("Accepted Indeed cookie consent.")
            time.sleep(1)
        except TimeoutException:
            pass  # No cookie banner — that's fine

    def _build_url(self, keyword: str, location: str, start: int = 0) -> str:
        """
        Build the Indeed search URL for a keyword + location + page offset.

        Indeed uses `start` parameter for pagination (10 per page):
          start=0  → page 1
          start=10 → page 2
          start=20 → page 3
        """
        query = f"internship {keyword}"
        return (
            f"{BASE_URL}"
            f"?q={quote_plus(query)}"
            f"&l={quote_plus(location)}"
            f"&start={start}"
            f"&fromage=30"  # Posted within last 30 days
        )

    def search(self, keyword: str, location: str) -> list[dict]:
        """
        Navigate Indeed search results and extract all job cards across pages.

        Process:
          1. Load search URL.
          2. Accept cookie consent if shown.
          3. Scroll to load lazy-loaded cards.
          4. Extract all job cards on current page.
          5. Click "Next" to paginate (max MAX_PAGES pages).

        Returns:
            List of raw job dicts (uncleaned) from all pages.
        """
        all_jobs = []
        driver   = self._get_driver()

        for page in range(MAX_PAGES):
            start = page * 10
            url   = self._build_url(keyword, location, start)

            logger.info("[Indeed] Page %d: %s", page + 1, url)
            driver.get(url)
            random_delay(3.0, 5.0)

            # Accept cookie consent on first page only
            if page == 0:
                self._accept_cookies()

            # Check for CAPTCHA — Indeed shows a "Let us know you're not a robot" page
            if "captcha" in driver.current_url.lower() or "robot" in driver.page_source.lower():
                logger.warning("[Indeed] CAPTCHA detected on page %d — stopping pagination.", page + 1)
                break

            # Scroll to trigger lazy-loaded job cards
            scroll_to_bottom(driver, pauses=3, pause_sec=1.5)

            # Extract all job cards on this page
            cards = safe_find_all(driver, SEL_JOB_CARD, timeout=10)
            if not cards:
                logger.info("[Indeed] No job cards found on page %d — stopping.", page + 1)
                break

            logger.info("[Indeed] Found %d cards on page %d", len(cards), page + 1)

            for card in cards:
                job = self.extract_job_data(card)
                if job:
                    # Fetch full description by clicking the card
                    desc = self._get_full_description(card)
                    if desc:
                        job["description"] = desc
                    all_jobs.append(job)
                    random_delay(1.0, 2.5)  # Delay between card clicks

            # Try to click "Next" button; if absent, we've reached the last page
            next_btn = safe_find(driver, SEL_NEXT_BUTTON, timeout=5)
            if not next_btn:
                logger.info("[Indeed] No 'Next' button — reached last page.")
                break

            random_delay(2.0, 4.0)

        logger.info("[Indeed] Total jobs extracted: %d", len(all_jobs))
        return all_jobs

    def extract_job_data(self, card) -> Optional[dict]:
        """
        Parse a single Indeed job card element into a raw job dict.

        Indeed renders each card as a <div class="job_seen_beacon">.
        We extract visible fields from the card without clicking
        (clicking loads the description in the right panel — done separately).

        Args:
            card: Selenium WebElement for a single job card.

        Returns:
            Raw job dict or None if critical fields are missing.
        """
        try:
            # ── Job title ──────────────────────────────────────────────────────
            title_el = card.find_element(By.CSS_SELECTOR, SEL_JOB_TITLE)
            title    = title_el.get_attribute("title") or title_el.text
            title    = title.strip()

            # ── Company name ───────────────────────────────────────────────────
            try:
                company = card.find_element(By.CSS_SELECTOR, SEL_COMPANY).text.strip()
            except NoSuchElementException:
                company = "Unknown"

            # ── Location ───────────────────────────────────────────────────────
            try:
                location = card.find_element(By.CSS_SELECTOR, SEL_LOCATION).text.strip()
            except NoSuchElementException:
                location = ""

            # ── Salary / stipend ───────────────────────────────────────────────
            stipend_text = None
            try:
                stipend_text = card.find_element(By.CSS_SELECTOR, SEL_SALARY).text.strip()
            except NoSuchElementException:
                pass

            # ── Date posted ────────────────────────────────────────────────────
            date_posted = None
            try:
                date_el     = card.find_element(By.CSS_SELECTOR, SEL_DATE_POSTED)
                date_posted = date_el.text.strip()
            except NoSuchElementException:
                pass

            # ── Job URL ─────────────────────────────────────────────────────────
            source_url = ""
            try:
                link_el    = card.find_element(By.CSS_SELECTOR, "h2.jobTitle a")
                source_url = link_el.get_attribute("href") or ""
                # Indeed URLs contain tracking params — strip to canonical form
                if "indeed.com" in source_url and "jk=" in source_url:
                    jk = source_url.split("jk=")[1].split("&")[0]
                    source_url = f"https://www.indeed.com/viewjob?jk={jk}"
            except NoSuchElementException:
                pass

            if not title:
                return None

            return {
                "title":           title,
                "company":         company,
                "location":        location,
                "stipend_text":    stipend_text,
                "deadline":        date_posted,   # "posted N days ago" — cleaner parses this
                "description":     "",            # Populated by _get_full_description()
                "required_skills": [],
                "source_url":      source_url,
                "source_site":     self.SITE_NAME,
            }

        except StaleElementReferenceException:
            # Card element became stale (page re-rendered) — safe to skip
            logger.debug("[Indeed] Stale card element — skipping.")
            return None
        except Exception as e:
            logger.warning("[Indeed] Error extracting card: %s", e)
            return None

    def _get_full_description(self, card) -> Optional[str]:
        """
        Click a job card to load its full description in Indeed's right panel,
        then extract and return the description text.

        Indeed's UI: clicking a card loads a detail pane on the right side
        without navigating away. This avoids navigating to a new page per job,
        which is much faster and generates less suspicious traffic.

        Returns:
            Description text string, or None if the panel didn't load.
        """
        driver = self._get_driver()
        try:
            # Click the card title link to open the detail panel
            link = card.find_element(By.CSS_SELECTOR, "h2.jobTitle a")
            driver.execute_script("arguments[0].click();", link)  # JS click avoids intercept
            random_delay(1.5, 3.0)

            # Wait for description panel to appear
            desc_el = safe_find(driver, SEL_DESCRIPTION, timeout=8)
            if desc_el:
                return desc_el.text.strip()

        except (ElementClickInterceptedException, NoSuchElementException, Exception) as e:
            logger.debug("[Indeed] Could not load description panel: %s", e)

        return None
