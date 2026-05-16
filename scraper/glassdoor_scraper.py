"""
scraper/sites/glassdoor_scraper.py — Scrape internship listings from Glassdoor.

Glassdoor is heavily protected by bot-detection (Cloudflare + custom JS
fingerprinting). We use undetected-chromedriver with extended delays and
session warming to pass these checks.

Approach:
  1. Load Glassdoor homepage first (warms up cookies/JS fingerprint).
  2. Navigate to job search with internship filter.
  3. Handle the sign-in modal (close it without logging in).
  4. Extract job cards from the search results.
  5. For each card, read the description from the right-side panel.

Important: Glassdoor's UI changes frequently. If selectors break, check
the current HTML at glassdoor.com/Job/jobs.htm and update the SEL_* constants.
"""

import logging
import time
from typing import Optional
from urllib.parse import quote_plus

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from scraper.base_scraper import BaseScraper
from scraper.utils.data_cleaner import extract_skills_from_text
from scraper.utils.driver_manager import random_delay, safe_find, safe_find_all, scroll_to_bottom

logger = logging.getLogger(__name__)

# ─── Selectors — update when Glassdoor changes its layout ─────────────────────
SEL_JOB_LIST       = "ul.JobsList_jobsList__lqjTr li"   # Job list items
SEL_JOB_CARD       = "div.JobCard_jobCardContainer__arK7V"
SEL_TITLE          = "a.JobCard_seoLink__WdqHZ"
SEL_COMPANY        = "span.EmployerProfile_compactEmployerName__9MGcV"
SEL_LOCATION       = "div.JobCard_location__Ds1fM"
SEL_SALARY         = "div.JobCard_salaryEstimate___m9eB"
SEL_DESCRIPTION    = "div.JobDetails_jobDescription__uW_fK"
SEL_CLOSE_MODAL    = "button.CloseButton"               # Sign-in modal close btn
SEL_NEXT_PAGE      = "button[data-test='pagination-next']"

BASE_URL   = "https://www.glassdoor.com"
SEARCH_URL = "https://www.glassdoor.com/Job/jobs.htm"
MAX_PAGES  = 3   # Glassdoor is aggressive — keep page count low


class GlassdoorScraper(BaseScraper):
    """
    Selenium-based scraper for Glassdoor internship listings.
    Handles Cloudflare bot protection via undetected-chromedriver session warming.
    """

    SITE_NAME = "Glassdoor"

    def setup(self) -> None:
        """Warm up the browser session on Glassdoor's homepage to pass bot checks."""
        driver = self._get_driver()
        logger.info("[Glassdoor] Warming up session on homepage…")
        driver.get(BASE_URL)
        # Wait for Cloudflare challenge to resolve (usually takes 2-4 seconds)
        random_delay(4.0, 7.0)
        # Accept cookies if prompted
        self._try_accept_cookies(driver)

    def _try_accept_cookies(self, driver) -> None:
        """Click cookie consent button if it appears (common on EU-adjacent CDNs)."""
        selectors = [
            "button#onetrust-accept-btn-handler",
            "button[data-testid='accept-cookies']",
            "button.cookie-consent-button",
        ]
        for sel in selectors:
            btn = safe_find(driver, sel, timeout=3)
            if btn:
                try:
                    btn.click()
                    logger.debug("[Glassdoor] Accepted cookie consent.")
                    time.sleep(1)
                    return
                except Exception:
                    pass

    def _close_signin_modal(self, driver) -> None:
        """
        Dismiss Glassdoor's sign-in modal which appears after a few seconds.

        Glassdoor aggressively prompts visitors to sign in. The modal blocks
        interaction with job cards if not dismissed. We try multiple close
        strategies in order of reliability.
        """
        strategies = [
            # Strategy 1: Click the explicit close (X) button
            lambda: safe_find(driver, SEL_CLOSE_MODAL, timeout=4),
            # Strategy 2: Press Escape key
            lambda: driver.find_element(By.TAG_NAME, "body").send_keys("\ue00c"),
            # Strategy 3: Click outside the modal (overlay)
            lambda: safe_find(driver, "div.modal-overlay", timeout=3),
        ]

        for i, strategy in enumerate(strategies):
            try:
                element = strategy()
                if element and hasattr(element, "click"):
                    element.click()
                    logger.debug("[Glassdoor] Modal closed (strategy %d).", i + 1)
                    time.sleep(1)
                    return
            except Exception:
                continue

        logger.debug("[Glassdoor] Sign-in modal not found or already dismissed.")

    def _build_search_url(self, keyword: str, location: str, page: int = 1) -> str:
        """
        Build Glassdoor job search URL with internship filter.

        Glassdoor job type codes:
          jobType=internship → filter for internships only
          sc.keyword         → search keyword
          locT=C             → city-level location filter
        """
        return (
            f"{SEARCH_URL}"
            f"?sc.keyword={quote_plus('internship ' + keyword)}"
            f"&locKeyword={quote_plus(location)}"
            f"&jobType=internship"
            f"&fromAge=30"     # Posted within last 30 days
            f"&p={page}"
        )

    def search(self, keyword: str, location: str) -> list[dict]:
        """
        Navigate Glassdoor search results and extract job listings.

        Process:
          1. Load search URL (browser already warmed up in setup()).
          2. Close sign-in modal.
          3. Scroll to load dynamic job cards.
          4. Extract all visible cards.
          5. Paginate up to MAX_PAGES.

        Returns:
            List of raw job dicts.
        """
        all_jobs = []
        driver   = self._get_driver()

        for page in range(1, MAX_PAGES + 1):
            url = self._build_search_url(keyword, location, page)
            logger.info("[Glassdoor] Page %d: %s", page, url)
            driver.get(url)
            random_delay(4.0, 7.0)

            # Glassdoor shows sign-in modal on almost every page load
            self._close_signin_modal(driver)
            random_delay(1.0, 2.0)

            # Check for Cloudflare challenge page
            if "just a moment" in driver.page_source.lower() or "checking your browser" in driver.page_source.lower():
                logger.warning("[Glassdoor] Cloudflare challenge on page %d — waiting 10s…", page)
                time.sleep(10)
                self._close_signin_modal(driver)

            # Scroll to load lazy-rendered job cards
            scroll_to_bottom(driver, pauses=3, pause_sec=2.0)
            self._close_signin_modal(driver)   # Modal may reappear after scroll

            # Try primary selector, fall back to generic li items
            cards = safe_find_all(driver, SEL_JOB_LIST, timeout=10)
            if not cards:
                cards = safe_find_all(driver, "li.react-job-listing", timeout=5)
            if not cards:
                logger.info("[Glassdoor] No job cards on page %d — stopping.", page)
                break

            logger.info("[Glassdoor] Found %d cards on page %d", len(cards), page)

            for card in cards:
                job = self.extract_job_data(card)
                if job:
                    # Get full description from right panel by clicking card
                    desc = self._get_description_from_panel(card)
                    if desc:
                        job["description"]     = desc
                        job["required_skills"] = extract_skills_from_text(desc)
                    all_jobs.append(job)
                    random_delay(2.0, 4.0)
                    self._close_signin_modal(driver)   # Appears randomly mid-browse

            # Check for and click Next page button
            next_btn = safe_find(driver, SEL_NEXT_PAGE, timeout=5)
            if not next_btn:
                logger.info("[Glassdoor] No next page button — done.")
                break

            try:
                driver.execute_script("arguments[0].click();", next_btn)
                random_delay(3.0, 5.0)
            except Exception as e:
                logger.warning("[Glassdoor] Could not click next page: %s", e)
                break

        logger.info("[Glassdoor] Total jobs extracted: %d", len(all_jobs))
        return all_jobs

    def extract_job_data(self, card) -> Optional[dict]:
        """
        Extract structured data from a single Glassdoor job card element.

        Glassdoor cards show title, company, location, and estimated salary.
        Full description is in the right-side panel (loaded by clicking the card).

        Args:
            card: Selenium WebElement for a single job listing item.

        Returns:
            Raw job dict or None if critical fields are missing.
        """
        try:
            # ── Title & URL ────────────────────────────────────────────────────
            link_el = card.find_element(By.CSS_SELECTOR, SEL_TITLE)
            title   = link_el.text.strip()
            url     = link_el.get_attribute("href") or ""
            # Strip Glassdoor tracking params — keep only the /job-listing/ path
            if "/job-listing/" in url:
                url = url.split("?")[0]

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

            # ── Salary (Glassdoor shows estimated salary ranges) ───────────────
            try:
                salary = card.find_element(By.CSS_SELECTOR, SEL_SALARY).text.strip()
            except NoSuchElementException:
                salary = None

            if not title:
                return None

            return {
                "title":           title,
                "company":         company,
                "location":        location,
                "stipend_text":    salary,
                "deadline":        None,   # Glassdoor doesn't show application deadlines
                "description":     "",
                "required_skills": [],
                "source_url":      url,
                "source_site":     self.SITE_NAME,
            }

        except Exception as e:
            logger.debug("[Glassdoor] Card extraction error: %s", e)
            return None

    def _get_description_from_panel(self, card) -> Optional[str]:
        """
        Click a job card to load the description in Glassdoor's right-side panel,
        then return the description text.

        Glassdoor loads job details into a persistent right panel without full page
        navigation, similar to Indeed's UI. We click the card title link and wait
        for the description div to update.

        Returns:
            Description text string or None if panel didn't load.
        """
        driver = self._get_driver()
        try:
            link = card.find_element(By.CSS_SELECTOR, SEL_TITLE)
            driver.execute_script("arguments[0].click();", link)
            random_delay(2.0, 3.5)

            # Close modal if it appeared after click
            self._close_signin_modal(driver)

            desc_el = safe_find(driver, SEL_DESCRIPTION, timeout=8)
            if desc_el:
                return desc_el.text.strip()[:2000]

        except (ElementClickInterceptedException, NoSuchElementException, Exception) as e:
            logger.debug("[Glassdoor] Description panel error: %s", e)

        return None
