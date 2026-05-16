"""
run_scraper.py — Manual CLI trigger for the scraping pipeline.

Usage examples:
  # Scrape all sites with defaults
  python run_scraper.py

  # Scrape a specific site
  python run_scraper.py --site indeed
  python run_scraper.py --site linkedin
  python run_scraper.py --site rozee
  python run_scraper.py --site internshala
  python run_scraper.py --site glassdoor
  python run_scraper.py --site adzuna
  python run_scraper.py --site jsearch
  python run_scraper.py --site api     # Both Adzuna + JSearch

  # Dry run — print what would be saved without writing to DB
  python run_scraper.py --site indeed --dry-run

  # Custom keywords and locations
  python run_scraper.py --site rozee --keywords "python,data science" --locations "Karachi,Lahore"

  # Verbose logging
  python run_scraper.py --site linkedin --verbose
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import redis
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from tqdm import tqdm

load_dotenv()

# ─── Logging Setup ────────────────────────────────────────────────────────────
# Write logs to both console and dated log file in logs/
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
log_filename = LOG_DIR / f"scraper_{datetime.now().strftime('%Y-%m-%d')}.log"


def setup_logging(verbose: bool = False) -> None:
    """
    Configure logging to write to both the console and a dated log file.

    Verbose mode (--verbose) sets level to DEBUG, showing every selector
    attempt, delay, and HTTP request. Default shows INFO and above.
    """
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level   = level,
        format  = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
        datefmt = "%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_filename, encoding="utf-8"),
        ],
    )
    # Suppress noisy third-party loggers
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("undetected_chromedriver").setLevel(logging.WARNING)


logger = logging.getLogger(__name__)

# ─── Available scrapers registry ──────────────────────────────────────────────
# Maps CLI --site argument to (ScraperClass, import_path)
# Add new scrapers here to make them available via CLI automatically.
SITE_REGISTRY = {
    "indeed":      ("scraper.sites.indeed_scraper",      "IndeedScraper"),
    "linkedin":    ("scraper.sites.linkedin_scraper",    "LinkedInScraper"),
    "rozee":       ("scraper.sites.rozee_scraper",       "RozeeScraper"),
    "internshala": ("scraper.sites.internshala_scraper", "IntershalaScraper"),
    "glassdoor":   ("scraper.sites.glassdoor_scraper",   "GlassdoorScraper"),
    "adzuna":      ("scraper.api_scrapers.adzuna_scraper",  "AdzunaScraper"),
    "jsearch":     ("scraper.api_scrapers.jsearch_scraper", "JSearchScraper"),
}

ALL_SITES = list(SITE_REGISTRY.keys())

# Default search configuration (override with --keywords and --locations flags)
DEFAULT_KEYWORDS = [
    "software engineer", "data science", "machine learning",
    "web developer", "python developer", "react developer",
    "business analyst", "ui ux", "devops", "cybersecurity",
]
DEFAULT_LOCATIONS = ["Karachi", "Lahore", "Islamabad", "Remote"]


def get_db_session():
    """
    Create a SQLAlchemy session connected to the FastAPI backend's PostgreSQL DB.
    Reads DATABASE_URL from .env (same database the FastAPI app uses).
    """
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        logger.error("DATABASE_URL not set in .env file.")
        sys.exit(1)
    engine  = create_engine(db_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    return Session()


def get_redis_client() -> redis.Redis:
    """Connect to Redis for deduplication cache."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()   # Verify connection immediately
        return client
    except redis.exceptions.ConnectionError:
        logger.error(
            "Cannot connect to Redis at %s. "
            "Start Redis with: docker run -d -p 6379:6379 redis:alpine",
            redis_url,
        )
        sys.exit(1)


def load_scraper_class(site_name: str):
    """
    Dynamically import and return the scraper class for the given site name.
    This avoids importing all scrapers at startup (saves memory for Selenium drivers).
    """
    import importlib

    module_path, class_name = SITE_REGISTRY[site_name]
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def run_single_site(
    site_name:  str,
    keywords:   list[str],
    locations:  list[str],
    db_session,
    redis_client,
    dry_run:    bool,
    headless:   bool,
) -> dict:
    """
    Instantiate and run a single site scraper with a progress bar.

    Args:
        site_name:    One of the SITE_REGISTRY keys.
        keywords:     List of search keywords.
        locations:    List of target locations.
        db_session:   Active SQLAlchemy session.
        redis_client: Active Redis client.
        dry_run:      If True, don't write to DB.
        headless:     If True, run Chrome without a GUI.

    Returns:
        Stats dict from the scraper run.
    """
    ScraperClass = load_scraper_class(site_name)

    total_searches = len(keywords) * len(locations)
    print(f"\n{'='*60}")
    print(f"  Site:      {site_name.upper()}")
    print(f"  Keywords:  {', '.join(keywords)}")
    print(f"  Locations: {', '.join(locations)}")
    print(f"  Searches:  {total_searches}")
    print(f"  Dry Run:   {'YES — nothing will be saved' if dry_run else 'No'}")
    print(f"  Log file:  {log_filename}")
    print(f"{'='*60}\n")

    # Create progress bar for search combinations
    progress = tqdm(
        total       = total_searches,
        desc        = f"Scraping {site_name}",
        unit        = "search",
        bar_format  = "{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
        colour      = "green",
    )

    scraper = ScraperClass(
        db_session   = db_session,
        redis_client = redis_client,
        headless     = headless,
        dry_run      = dry_run,
    )

    stats = scraper.run(
        keywords      = keywords,
        locations     = locations,
        progress_bar  = progress,
    )

    progress.close()
    return stats


def run_all_sites(
    keywords:    list[str],
    locations:   list[str],
    db_session,
    redis_client,
    dry_run:     bool,
    headless:    bool,
) -> dict:
    """
    Run all scrapers sequentially with aggregate progress tracking.
    Sites are ordered by anti-bot difficulty (easiest first).
    """
    site_order = ["rozee", "internshala", "adzuna", "jsearch", "linkedin", "indeed", "glassdoor"]
    all_stats  = {}
    combined   = {"jobs_found": 0, "jobs_saved": 0, "jobs_updated": 0,
                  "jobs_skipped": 0, "errors": 0}

    print(f"\n{'='*60}")
    print(f"  SCRAPING ALL {len(site_order)} SITES")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    for site in site_order:
        try:
            stats = run_single_site(
                site_name    = site,
                keywords     = keywords,
                locations    = locations,
                db_session   = db_session,
                redis_client = redis_client,
                dry_run      = dry_run,
                headless     = headless,
            )
            all_stats[site] = stats
            for k in combined:
                combined[k] += stats.get(k, 0)

        except Exception as e:
            logger.error("Site '%s' failed: %s", site, e)
            all_stats[site] = {"error": str(e)}
            combined["errors"] += 1

    return {"combined": combined, "by_site": all_stats}


def print_summary(stats: dict, site: str, elapsed_sec: float) -> None:
    """Print a formatted summary table after the scrape run completes."""
    if "combined" in stats:
        # Multiple sites
        s = stats["combined"]
        by_site = stats.get("by_site", {})
    else:
        s = stats
        by_site = {site: stats}

    print(f"\n{'='*60}")
    print(f"  SCRAPE COMPLETE — {elapsed_sec:.0f} seconds")
    print(f"{'='*60}")
    print(f"  Jobs Found:   {s.get('jobs_found',  0):>6}")
    print(f"  Jobs Saved:   {s.get('jobs_saved',  0):>6}")
    print(f"  Jobs Updated: {s.get('jobs_updated',0):>6}")
    print(f"  Jobs Skipped: {s.get('jobs_skipped',0):>6}")
    print(f"  Errors:       {s.get('errors',      0):>6}")

    if len(by_site) > 1:
        print(f"\n  Per-site breakdown:")
        for site_name, site_stats in by_site.items():
            if "error" in site_stats:
                print(f"    {site_name:15} ERROR: {site_stats['error'][:40]}")
            else:
                print(f"    {site_name:15} saved={site_stats.get('jobs_saved',0):3}  "
                      f"found={site_stats.get('jobs_found',0):3}  "
                      f"errors={site_stats.get('errors',0):2}")

    print(f"\n  Full log: {log_filename}")
    print(f"{'='*60}\n")


# ─── CLI Argument Parser ───────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AI Internship Matcher — Manual Scraper Trigger",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_scraper.py                              # Scrape all sites
  python run_scraper.py --site indeed               # Indeed only
  python run_scraper.py --site rozee --dry-run      # Preview without saving
  python run_scraper.py --site api                  # Adzuna + JSearch APIs
  python run_scraper.py --keywords "python,django"  # Custom keywords
  python run_scraper.py --verbose                   # Debug logging
        """,
    )
    parser.add_argument(
        "--site",
        choices  = ALL_SITES + ["all", "api"],
        default  = "all",
        help     = "Which site to scrape. 'all' runs every scraper. 'api' runs Adzuna+JSearch.",
    )
    parser.add_argument(
        "--keywords",
        default  = None,
        help     = "Comma-separated list of job keywords (default: built-in list of 10).",
    )
    parser.add_argument(
        "--locations",
        default  = None,
        help     = "Comma-separated list of locations (default: Karachi, Lahore, Islamabad, Remote).",
    )
    parser.add_argument(
        "--dry-run",
        action   = "store_true",
        help     = "Parse and print jobs without saving to database.",
    )
    parser.add_argument(
        "--no-headless",
        action   = "store_true",
        help     = "Show the browser window (useful for debugging selectors).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action   = "store_true",
        help     = "Enable DEBUG-level logging (very detailed output).",
    )
    return parser


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main():
    parser = build_parser()
    args   = parser.parse_args()

    setup_logging(verbose=args.verbose)

    # Parse keywords and locations from CLI or use defaults
    keywords  = [k.strip() for k in args.keywords.split(",")]  if args.keywords  else DEFAULT_KEYWORDS
    locations = [l.strip() for l in args.locations.split(",")] if args.locations else DEFAULT_LOCATIONS

    headless  = not args.no_headless
    dry_run   = args.dry_run

    if dry_run:
        logger.info("DRY RUN MODE — no data will be written to the database.")

    # Connect to database and Redis
    db_session   = get_db_session()
    redis_client = get_redis_client()

    start_time = datetime.now()

    try:
        # ── Dispatch based on --site argument ─────────────────────────────────
        if args.site == "all":
            stats = run_all_sites(keywords, locations, db_session, redis_client, dry_run, headless)

        elif args.site == "api":
            # Run both API scrapers together
            stats = {"combined": {"jobs_found":0,"jobs_saved":0,"jobs_updated":0,"jobs_skipped":0,"errors":0}, "by_site": {}}
            for api_site in ["adzuna", "jsearch"]:
                s = run_single_site(api_site, keywords, locations, db_session, redis_client, dry_run, headless)
                stats["by_site"][api_site] = s
                for k in stats["combined"]:
                    stats["combined"][k] += s.get(k, 0)

        else:
            # Single specific site
            stats = run_single_site(
                site_name    = args.site,
                keywords     = keywords,
                locations    = locations,
                db_session   = db_session,
                redis_client = redis_client,
                dry_run      = dry_run,
                headless     = headless,
            )

        elapsed = (datetime.now() - start_time).total_seconds()
        print_summary(stats, args.site, elapsed)

    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user (Ctrl+C).")
        logger.info("Scraping interrupted by user.")
        sys.exit(0)

    except Exception as e:
        logger.exception("Fatal error in run_scraper: %s", e)
        sys.exit(1)

    finally:
        db_session.close()


if __name__ == "__main__":
    main()
