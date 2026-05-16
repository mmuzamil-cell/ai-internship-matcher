"""
scraper/sites/internshala_scraper.py — Scrape listings from Internshala.com.

Internshala is India's largest internship platform and also lists remote
internships that are open to Pakistani students. It is server-rendered
with some AJAX for pagination, making a hybrid BS4 + requests approach ideal.

Internshala structure:
  - Listing page: https://internshala.com/internships/keywords-{keyword}/
  - Each card shows: title, company, location, duration, stipend, posted date
  - Detail page has full description and required skills section

Key difference from other scrapers:
  - Internshala uses "duration" (e.g. "3 Months") instead of deadline.
  - Stipend is often shown as "₹ 5,000 /month" or "Unpaid" or "Performance-based".
  - Remote internships are explicitly tagged as "Work From Home".
"""

import logging
from typing import Optional
from urllib.parse import quote

from bs4 import BeautifulSoup

from scraper.base_scraper import BaseScraper
from scraper.utils.data_cleaner import extract_skills_from_text
from scraper.utils.driver_manager import random_delay
from scraper.utils.proxy_rotator import ProxyRotator

logger = logging.getLogger(__name__)

BASE_URL        = "https://internshala.com"
SEARCH_TEMPLATE = "https://internshala.com/internships/keywords-{keyword}/"
MAX_PAGES       = 5


class IntershalaScraper(BaseScraper):
    """
    Requests + BeautifulSoup scraper for Internshala.com.
    No Selenium required — Internshala is mostly server-rendered.
    """

    SITE_NAME = "Internshala"

    def setup(self) -> None:
        self.proxy_rotator = ProxyRotator()

    def _build_url(self, keyword: str, page: int = 1) -> str:
        """
        Build Internshala search URL.
        Internshala paginates via a `page-{n}` path segment.
        e.g. /internships/keywords-python/page-2/
        """
        safe_kw = quote(keyword.replace(" ", "-"))
        if page == 1:
            return f"{BASE_URL}/internships/keywords-{safe_kw}/"
        return f"{BASE_URL}/internships/keywords-{safe_kw}/page-{page}/"

    def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch a page and return a BeautifulSoup object, or None on failure."""
        resp = self.proxy_rotator.make_request(url, timeout=20, retries=3)
        if not resp:
            return None
        resp.encoding = "utf-8"
        return BeautifulSoup(resp.text, "html.parser")

    def search(self, keyword: str, location: str) -> list[dict]:
        """
        Search Internshala for internships matching the keyword.

        Note: Internshala's URL-based search is keyword-only.
        We use the `location` argument to post-filter results
        (keep remote/WFH jobs and jobs in the specified city).

        Returns:
            List of raw job dicts for matching internships.
        """
        all_jobs     = []
        loc_lower    = location.lower()
        is_remote_req = "remote" in loc_lower or "wfh" in loc_lower

        for page in range(1, MAX_PAGES + 1):
            url  = self._build_url(keyword, page)
            logger.info("[Internshala] Page %d: %s", page, url)

            soup = self._get_soup(url)
            if not soup:
                break

            # Internshala job cards are in div.individual_internship
            cards = soup.select("div.individual_internship")
            if not cards:
                logger.info("[Internshala] No cards on page %d — stopping.", page)
                break

            logger.info("[Internshala] Found %d cards on page %d", len(cards), page)

            for card in cards:
                job = self.extract_job_data(card)
                if not job:
                    continue

                # ── Location filter: keep remote jobs or matching city ──────────
                job_loc  = job.get("location", "").lower()
                is_wfh   = "work from home" in job_loc or "wfh" in job_loc or "remote" in job_loc
                city_match = loc_lower in job_loc or is_wfh

                if not is_remote_req and not city_match and not is_wfh:
                    continue   # Skip jobs in unrelated cities

                # ── Fetch detail page for full description ─────────────────────
                if job.get("source_url"):
                    detail_url = job["source_url"]
                    if not detail_url.startswith("http"):
                        detail_url = BASE_URL + detail_url
                    desc, skills = self._fetch_detail(detail_url)
                    job["description"]     = desc or ""
                    job["required_skills"] = skills

                all_jobs.append(job)
                random_delay(2.0, 5.0)

            if len(cards) < 10:
                break   # Last page

            random_delay(3.0, 6.0)

        logger.info("[Internshala] Total found: %d", len(all_jobs))
        return all_jobs

    def extract_job_data(self, card) -> Optional[dict]:
        """
        Parse a single Internshala job card (div.individual_internship).

        Card contains:
          - h3.job-internship-name → title + link to detail page
          - a.link_display_flex    → company name
          - div.location_link      → city or "Work From Home"
          - div.stipend            → stipend string
          - div.internship_other_details_container → duration, start date, openings

        Returns:
            Raw job dict or None if required fields are missing.
        """
        try:
            # ── Title & URL ────────────────────────────────────────────────────
            title_el = card.select_one("h3.job-internship-name a") or card.select_one("h3 a")
            if not title_el:
                return None
            title      = title_el.get_text(strip=True)
            source_url = title_el.get("href", "")
            if source_url and not source_url.startswith("http"):
                source_url = BASE_URL + source_url

            # ── Company ────────────────────────────────────────────────────────
            company_el = (
                card.select_one("a.link_display_flex") or
                card.select_one("p.company-name") or
                card.select_one("div.company-name a")
            )
            company = company_el.get_text(strip=True) if company_el else "Unknown"

            # ── Location ───────────────────────────────────────────────────────
            loc_el   = card.select_one("a.location_link") or card.select_one("div.location_link")
            location = loc_el.get_text(strip=True) if loc_el else ""

            # ── Stipend ────────────────────────────────────────────────────────
            # Internshala shows "₹ 5,000 /month", "Unpaid", "Performance-based"
            stipend_el   = card.select_one("span.stipend") or card.select_one("div.stipend")
            stipend_text = stipend_el.get_text(strip=True) if stipend_el else None

            # ── Posted date (Internshala shows "Posted X days ago") ────────────
            posted_el  = card.select_one("div.status-inactive") or card.select_one("span.posted")
            date_text  = posted_el.get_text(strip=True) if posted_el else None

            if not title:
                return None

            return {
                "title":           title,
                "company":         company,
                "location":        location,
                "stipend_text":    stipend_text,
                "deadline":        date_text,
                "description":     "",
                "required_skills": [],
                "source_url":      source_url,
                "source_site":     self.SITE_NAME,
            }

        except Exception as e:
            logger.warning("[Internshala] Card error: %s", e)
            return None

    def _fetch_detail(self, url: str) -> tuple[Optional[str], list[str]]:
        """
        Fetch Internshala job detail page to get full description and skills.

        Internshala detail pages have:
          - div#about_the_internship → full description
          - div#about_the_company    → company info (skip)
          - div.other_detail_item    → additional requirements

        Returns:
            (description_text, skills_list)
        """
        resp = self.proxy_rotator.make_request(url, timeout=20, retries=2)
        if not resp:
            return None, []

        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")

        desc_el = (
            soup.select_one("div#about_the_internship") or
            soup.select_one("div.internship-detail-cover") or
            soup.select_one("section.about_internship")
        )
        description = ""
        if desc_el:
            description = desc_el.get_text(separator=" ", strip=True)[:2000]

        # Also check skills section if explicitly listed
        skills_el = soup.select_one("div#skills_required") or soup.select_one("div.round_tabs_container")
        skills_text = skills_el.get_text(separator=" ") if skills_el else ""

        skills = extract_skills_from_text(description + " " + skills_text)
        return description, skills
