"""
scraper/celery_config.py — Celery + Redis configuration for scheduled scraping.

Celery is a distributed task queue that lets us:
  1. Run scraping tasks asynchronously (non-blocking).
  2. Schedule tasks with Celery Beat (like cron, but Python-native).
  3. Retry failed tasks automatically.
  4. Monitor task status via Flower dashboard.

Architecture:
  - Broker:  Redis (stores task queue)
  - Backend: Redis (stores task results/status)
  - Worker:  celery -A scraper.tasks worker (processes tasks)
  - Scheduler: celery -A scraper.tasks beat (triggers scheduled tasks)

Start commands (run in separate terminals):
  celery -A scraper.tasks worker --loglevel=info --concurrency=2
  celery -A scraper.tasks beat   --loglevel=info
"""

import os
from datetime import timedelta

from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

# ─── Broker & Backend ─────────────────────────────────────────────────────────
# Both use Redis. Using separate DB indices (0 and 1) avoids key collisions.
broker_url      = os.getenv("REDIS_URL", "redis://localhost:6379/0")
result_backend  = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ─── Serialization ────────────────────────────────────────────────────────────
# JSON is safer than pickle (no arbitrary code execution on deserialization)
task_serializer   = "json"
result_serializer = "json"
accept_content    = ["json"]

# ─── Timezone ─────────────────────────────────────────────────────────────────
# Asia/Karachi = PKT (UTC+5). Schedule runs in local Pakistani time.
timezone        = "Asia/Karachi"
enable_utc      = True   # Store timestamps as UTC internally

# ─── Task routing ─────────────────────────────────────────────────────────────
# Route scraping tasks to the 'scraper' queue and cleanup to 'maintenance'.
# This lets you run separate worker pools with different concurrency settings.
task_routes = {
    "scraper.tasks.scrape_*":   {"queue": "scraper"},
    "scraper.tasks.cleanup_*":  {"queue": "maintenance"},
}

# ─── Worker settings ──────────────────────────────────────────────────────────
# prefetch_multiplier=1: Each worker fetches 1 task at a time.
# Prevents one slow scraping task from blocking others in the queue.
worker_prefetch_multiplier = 1
task_acks_late             = True   # Acknowledge task only after completion (safer)

# ─── Task result settings ─────────────────────────────────────────────────────
result_expires  = int(timedelta(days=7).total_seconds())   # Keep results for 7 days

# ─── Retry settings ───────────────────────────────────────────────────────────
# Scraping tasks can fail due to network issues — retry up to 3 times
task_max_retries    = 3
task_default_retry_delay = 300   # 5 minutes between retries

# ─── Beat Schedule ────────────────────────────────────────────────────────────
# Celery Beat runs these tasks automatically on the defined schedule.
# crontab(hour=6, minute=0) = 6:00 AM PKT every day
beat_schedule = {

    # ── Daily scraping run (6:00 AM PKT every day) ────────────────────────────
    "scrape-all-sites-daily": {
        "task":     "scraper.tasks.scrape_all_sites",
        "schedule": crontab(hour=6, minute=0),   # 6:00 AM PKT
        "kwargs": {
            "keywords":  ["software engineer", "data science", "machine learning",
                          "web developer", "business analyst", "ui ux", "devops",
                          "python", "react", "marketing", "finance"],
            "locations": ["Karachi", "Lahore", "Islamabad", "Remote"],
        },
        "options": {"queue": "scraper"},
    },

    # ── Weekly cleanup (Sunday midnight PKT) ──────────────────────────────────
    "cleanup-old-jobs-weekly": {
        "task":     "scraper.tasks.cleanup_old_jobs",
        "schedule": crontab(hour=0, minute=0, day_of_week=0),   # Sunday 00:00 PKT
        "options":  {"queue": "maintenance"},
    },

    # ── API scrapers run more frequently (lower server load) ─────────────────
    "scrape-api-sources-twice-daily": {
        "task":     "scraper.tasks.scrape_api_sources",
        "schedule": crontab(hour="6,18", minute=30),   # 6:30 AM and 6:30 PM PKT
        "kwargs": {
            "keywords":  ["software engineer intern", "data analyst intern",
                          "machine learning intern", "python developer intern"],
            "locations": ["Karachi", "Pakistan", "Remote"],
        },
        "options": {"queue": "scraper"},
    },
}
