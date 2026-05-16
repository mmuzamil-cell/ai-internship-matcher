"""
scraper/utils/driver_manager.py — Selenium WebDriver factory with anti-detection measures.

Why undetected-chromedriver?
  Standard Selenium is trivially fingerprinted by Cloudflare, Distil Networks,
  and other bot-detection systems via navigator.webdriver=true, automation flags
  in the Chrome DevTools Protocol, and known chromedriver process signatures.
  undetected-chromedriver patches these at the binary level.

Usage:
    driver = create_driver(headless=True)
    element = safe_find(driver, "div.job-card", timeout=10)
    driver.quit()
"""

import logging
import random
import time
from typing import Optional

import undetected_chromedriver as uc
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

# ─── Real-browser User-Agent pool ─────────────────────────────────────────────
# These are real Chrome UA strings sampled from browsing telemetry.
# Rotating them makes each session look like a different user.
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.6312.86 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 OPR/109.0.0.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 11.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
]


def random_delay(min_sec: float = 2.0, max_sec: float = 5.0) -> None:
    """
    Sleep for a random duration within [min_sec, max_sec].

    Why random? Fixed delays (time.sleep(2)) are a clear bot signal —
    real users have variable interaction timing. Randomized delays mimic
    natural browsing rhythm and make session timing analysis ineffective.
    """
    delay = random.uniform(min_sec, max_sec)
    logger.debug("Sleeping %.2fs (anti-bot delay)", delay)
    time.sleep(delay)


def create_driver(headless: bool = True, proxy: Optional[str] = None) -> uc.Chrome:
    """
    Create a Selenium WebDriver instance hardened against bot detection.

    Args:
        headless: Run Chrome without a visible window (True for production).
                  Set False for local debugging to see the browser.
        proxy:    Optional HTTP proxy string "host:port" for IP rotation.

    Returns:
        A configured undetected_chromedriver.Chrome instance.

    Detection countermeasures applied:
      1. undetected-chromedriver patches navigator.webdriver = false
      2. excludeSwitches removes automation fingerprints from DevTools
      3. Random User-Agent from real-browser pool
      4. Window size 1920×1080 matches common desktop resolution
      5. Disabled images & CSS for faster loading (optional, disabled here
         to avoid layout fingerprints)
      6. Language and timezone spoofing
    """
    options = uc.ChromeOptions()

    # ── Headless mode ──────────────────────────────────────────────────────────
    if headless:
        # --headless=new is the modern headless flag (Chrome 112+).
        # The old --headless flag is detectable; the new one is not.
        options.add_argument("--headless=new")

    # ── Anti-detection flags ───────────────────────────────────────────────────
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")        # Prevent /dev/shm OOM in Docker
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-infobars")
    options.add_argument("--window-size=1920,1080")         # Standard desktop resolution
    options.add_argument("--start-maximized")
    options.add_argument("--lang=en-US,en;q=0.9")          # Appear as English browser
    options.add_argument("--disable-extensions")

    # ── Random User-Agent ──────────────────────────────────────────────────────
    user_agent = random.choice(USER_AGENTS)
    options.add_argument(f"--user-agent={user_agent}")
    logger.debug("Using User-Agent: %s", user_agent[:60])

    # ── Proxy ─────────────────────────────────────────────────────────────────
    if proxy:
        options.add_argument(f"--proxy-server={proxy}")
        logger.info("Using proxy: %s", proxy)

    # ── Experimental options (remove automation signatures) ───────────────────
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option("useAutomationExtension", False)

    # ── Create the patched driver ──────────────────────────────────────────────
    driver = uc.Chrome(options=options, use_subprocess=True)

    # ── JavaScript patches (applied after launch) ─────────────────────────────
    # Override navigator.webdriver at the JS level for any site that checks it
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                window.chrome = { runtime: {} };
            """
        },
    )

    logger.info("Chrome WebDriver created (headless=%s)", headless)
    return driver


def safe_find(driver, css_selector: str, timeout: int = 10):
    """
    Wait for and return the first matching element, or None on timeout.

    Using explicit waits instead of time.sleep() is more reliable —
    the driver returns as soon as the element appears rather than always
    waiting the full sleep duration.

    Args:
        driver:       The Selenium WebDriver instance.
        css_selector: CSS selector string (e.g. "div.job-card h2 a").
        timeout:      Max seconds to wait before returning None.

    Returns:
        WebElement if found, None if timeout or error.
    """
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
        )
        return element
    except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e:
        logger.debug("safe_find: '%s' not found within %ds — %s", css_selector, timeout, type(e).__name__)
        return None


def safe_find_all(driver, css_selector: str, timeout: int = 10) -> list:
    """
    Wait for and return all matching elements, or [] on timeout.
    Same as safe_find but returns a list for iterating job cards.
    """
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, css_selector))
        )
        return driver.find_elements(By.CSS_SELECTOR, css_selector)
    except (TimeoutException, NoSuchElementException) as e:
        logger.debug("safe_find_all: '%s' not found — %s", css_selector, type(e).__name__)
        return []


def scroll_to_bottom(driver, pauses: int = 3, pause_sec: float = 2.0) -> None:
    """
    Scroll the page to load lazy-loaded job cards.

    Many job boards (Indeed, LinkedIn) use infinite scroll or lazy loading —
    cards only render when scrolled into view. We scroll in increments,
    pausing each time to let the page fetch and render more results.

    Args:
        driver:    WebDriver instance.
        pauses:    Number of scroll increments.
        pause_sec: Seconds to wait after each scroll.
    """
    last_height = driver.execute_script("return document.body.scrollHeight")
    for i in range(pauses):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(pause_sec + random.uniform(0.5, 1.5))  # Random jitter
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            logger.debug("Scroll %d/%d: page height stable, no more content", i + 1, pauses)
            break
        last_height = new_height
        logger.debug("Scroll %d/%d: height %d → %d", i + 1, pauses, last_height, new_height)
