"""
scraper/utils/proxy_rotator.py — User-agent and proxy rotation utilities.

In production you'd subscribe to a proxy service (Bright Data, Oxylabs, etc.)
and load proxies from their API. Here we provide the framework for loading
from a local list or environment variable, with round-robin + health checking.

Usage:
    rotator = ProxyRotator()
    proxy   = rotator.get_proxy()          # Returns "http://host:port" or None
    rotator.mark_failed(proxy)             # Remove bad proxy from pool
    ua      = rotator.get_user_agent()     # Random UA string
"""

import logging
import os
import random
from collections import deque
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ─── User-Agent pool (also in driver_manager, kept here for requests-based scrapers)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
]


class ProxyRotator:
    """
    Manages a rotating pool of HTTP proxies with health tracking.

    Proxies are loaded from:
      1. PROXY_LIST env var (comma-separated "host:port" strings)
      2. proxies.txt file in the project root (one proxy per line)
      3. Falls back to no-proxy mode if neither is configured

    Failed proxies are removed from the active pool to avoid wasting
    requests on dead endpoints. Pool is reset when all proxies are exhausted.
    """

    def __init__(self):
        self._pool: deque[str] = deque()
        self._failed: set[str] = set()
        self._load_proxies()

    def _load_proxies(self) -> None:
        """Load proxies from environment variable or proxies.txt file."""
        proxies: list[str] = []

        # Try environment variable first (useful in Docker / CI)
        env_proxies = os.getenv("PROXY_LIST", "")
        if env_proxies:
            proxies = [p.strip() for p in env_proxies.split(",") if p.strip()]
            logger.info("Loaded %d proxies from PROXY_LIST env var", len(proxies))

        # Fall back to proxies.txt file
        elif os.path.exists("proxies.txt"):
            with open("proxies.txt") as f:
                proxies = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            logger.info("Loaded %d proxies from proxies.txt", len(proxies))

        else:
            logger.warning(
                "No proxies configured. Running without proxy rotation. "
                "For production, set PROXY_LIST env var or create proxies.txt."
            )

        # Shuffle to avoid all workers starting with the same proxy
        random.shuffle(proxies)
        self._pool = deque(proxies)

    def get_proxy(self) -> Optional[str]:
        """
        Return the next available proxy in round-robin order.
        Returns None if no proxies are configured (direct connection).
        Reloads the pool if it's been exhausted.
        """
        if not self._pool:
            if self._failed:
                # All proxies failed — reset and try again
                logger.warning("All proxies exhausted, resetting pool.")
                self._load_proxies()
                self._failed.clear()
            return None  # No proxies configured

        proxy = self._pool[0]
        self._pool.rotate(-1)  # Move to back of queue (round-robin)
        return f"http://{proxy}" if not proxy.startswith("http") else proxy

    def mark_failed(self, proxy: Optional[str]) -> None:
        """
        Remove a proxy from the pool after a failure (connection error, 403, etc.).
        This prevents repeated use of a blocked or dead proxy.
        """
        if proxy and proxy in self._pool:
            self._pool.remove(proxy)
            self._failed.add(proxy)
            logger.warning("Proxy marked as failed and removed: %s (pool size: %d)", proxy, len(self._pool))

    def get_user_agent(self) -> str:
        """Return a random User-Agent string from the pool."""
        return random.choice(USER_AGENTS)

    def get_headers(self) -> dict:
        """
        Return a complete set of HTTP headers that mimic a real browser.
        Used by requests-based scrapers (LinkedIn, Rozee, Internshala).
        """
        return {
            "User-Agent":      self.get_user_agent(),
            "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT":             "1",                  # Do Not Track (looks like real user)
            "Connection":      "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest":  "document",
            "Sec-Fetch-Mode":  "navigate",
            "Sec-Fetch-Site":  "none",
            "Cache-Control":   "max-age=0",
        }

    def make_request(
        self,
        url: str,
        timeout: int = 15,
        retries: int = 3,
        backoff_base: float = 2.0,
    ) -> Optional[requests.Response]:
        """
        Make an HTTP GET request with proxy rotation and exponential backoff.

        Handles:
          - Proxy failures: rotates to next proxy on connection error
          - Rate limiting (429): waits exponentially before retry
          - Timeouts: retries with fresh proxy

        Args:
            url:          Target URL.
            timeout:      Per-request timeout in seconds.
            retries:      Max retry attempts.
            backoff_base: Base seconds for exponential backoff (2^attempt * base).

        Returns:
            Response object on success, None after all retries fail.
        """
        import time

        proxy = self.get_proxy()

        for attempt in range(retries):
            try:
                proxies_dict = {"http": proxy, "https": proxy} if proxy else None
                response = requests.get(
                    url,
                    headers=self.get_headers(),
                    proxies=proxies_dict,
                    timeout=timeout,
                )

                if response.status_code == 429:
                    # Rate limited — exponential backoff
                    wait_sec = (backoff_base ** (attempt + 1)) * 15  # 30s, 60s, 120s
                    logger.warning("Rate limited (429) on %s. Waiting %.0fs…", url, wait_sec)
                    time.sleep(wait_sec)
                    proxy = self.get_proxy()  # Rotate proxy on rate limit too
                    continue

                if response.status_code == 403:
                    logger.warning("Blocked (403) on %s with proxy %s", url, proxy)
                    self.mark_failed(proxy)
                    proxy = self.get_proxy()
                    continue

                response.raise_for_status()
                return response

            except requests.exceptions.ProxyError:
                logger.warning("Proxy error with %s (attempt %d/%d)", proxy, attempt + 1, retries)
                self.mark_failed(proxy)
                proxy = self.get_proxy()

            except requests.exceptions.Timeout:
                logger.warning("Timeout on %s (attempt %d/%d)", url, attempt + 1, retries)
                wait = backoff_base ** attempt
                time.sleep(wait)

            except requests.exceptions.RequestException as e:
                logger.error("Request error on %s: %s", url, e)
                break

        logger.error("All %d attempts failed for %s", retries, url)
        return None
