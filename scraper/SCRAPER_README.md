# AI Internship Matcher — Web Scraping Pipeline

Automated pipeline that collects internship listings from 7 sources daily
and saves them to the shared PostgreSQL database used by the FastAPI backend.

---

## Architecture Overview

```
                      ┌──────────────────────────────────────┐
                      │         Celery Beat Scheduler         │
                      │   (triggers tasks on cron schedule)   │
                      └─────────────────┬────────────────────┘
                                        │
                                        ▼
┌──────────────┐    task queue    ┌──────────────┐    results    ┌──────────┐
│    Redis     │ ◄──────────────► │ Celery Worker│ ─────────────►│  Redis   │
│  (broker)    │                  │  (2 workers) │               │ (backend)│
└──────────────┘                  └──────┬───────┘               └──────────┘
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                     ▼
             ┌────────────┐      ┌────────────┐       ┌────────────┐
             │   Indeed   │      │  LinkedIn  │       │  Rozee.pk  │
             │  Scraper   │      │  Scraper   │       │  Scraper   │
             └─────┬──────┘      └─────┬──────┘       └─────┬──────┘
                   │                   │                     │
                   └───────────────────┼─────────────────────┘
                                       │
                                       ▼
                    ┌──────────────────────────────────┐
                    │        Data Cleaner              │
                    │  normalize → skills → truncate   │
                    └──────────────┬───────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────────┐
                    │        Deduplicator              │
                    │  Redis cache → PostgreSQL check  │
                    └──────────────┬───────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────────────┐
                    │       PostgreSQL Database        │
                    │    internships + scraper_stats   │
                    └──────────────────────────────────┘
```

---

## Sources Scraped

| Source       | Method          | Daily Limit | Anti-Bot Risk |
|--------------|-----------------|-------------|---------------|
| Rozee.pk     | BS4/requests    | ~200 jobs   | Low           |
| Internshala  | BS4/requests    | ~150 jobs   | Low           |
| Adzuna API   | REST API        | 250/month   | None          |
| JSearch API  | REST API        | 200/month   | None          |
| LinkedIn     | Selenium        | 50 jobs     | Medium        |
| Indeed       | Selenium        | ~100 jobs   | High          |
| Glassdoor    | Selenium        | ~50 jobs    | Very High     |

---

## Installation

### Prerequisites
- Python 3.11+
- Google Chrome (for Selenium scrapers)
- Redis server
- PostgreSQL (shared with FastAPI backend)

### 1. Install dependencies
```bash
pip install -r scraper_requirements.txt
python -m spacy download en_core_web_sm
```

### 2. Configure environment variables
Add these to your existing `.env` file:
```bash
# Redis (required)
REDIS_URL=redis://localhost:6379/0

# Adzuna API (free — register at https://developer.adzuna.com)
ADZUNA_APP_ID=your_app_id_here
ADZUNA_APP_KEY=your_app_key_here

# JSearch via RapidAPI (free tier — register at https://rapidapi.com)
RAPIDAPI_KEY=your_rapidapi_key_here

# Optional: proxy list for IP rotation (host:port, comma-separated)
PROXY_LIST=proxy1.example.com:8080,proxy2.example.com:8080

# Flower monitoring credentials (optional)
FLOWER_USER=admin
FLOWER_PASSWORD=your_secure_password
```

### 3. Add ScraperStats model to database.py
Copy the `ScraperStats` class from `scraper/db_additions.py` into your
`database.py` file, then restart the FastAPI app to auto-create the table.

---

## Running Scrapers Manually

### Scrape all sites (sequential, ~60-90 min)
```bash
python run_scraper.py
```

### Scrape a specific site
```bash
python run_scraper.py --site rozee
python run_scraper.py --site linkedin
python run_scraper.py --site indeed
python run_scraper.py --site internshala
python run_scraper.py --site glassdoor
python run_scraper.py --site adzuna
python run_scraper.py --site jsearch
python run_scraper.py --site api          # Both API scrapers
```

### Dry run (preview without saving)
```bash
python run_scraper.py --site rozee --dry-run
python run_scraper.py --dry-run           # All sites, no DB writes
```

### Custom keywords and locations
```bash
python run_scraper.py --site indeed \
    --keywords "python developer,data scientist,ml engineer" \
    --locations "Karachi,Lahore,Remote"
```

### Debug mode (show browser window + verbose logs)
```bash
python run_scraper.py --site linkedin --verbose --no-headless
```

---

## Starting Celery Workers (Automated Scheduling)

Run each command in a separate terminal:

### Terminal 1: Start Redis (if not already running)
```bash
# Using Docker
docker run -d -p 6379:6379 redis:alpine

# Or install Redis natively
sudo apt install redis-server && redis-server
```

### Terminal 2: Start Celery worker
```bash
celery -A scraper.tasks worker \
    --loglevel=info \
    --concurrency=2 \
    --queues=scraper,maintenance \
    --hostname=worker@%h
```

### Terminal 3: Start Celery Beat scheduler
```bash
celery -A scraper.tasks beat --loglevel=info
```

### Terminal 4: Monitor tasks (optional)
```bash
celery -A scraper.tasks flower --port=5555
# Open http://localhost:5555 in browser
```

---

## Celery Beat Schedule

| Task                      | Schedule                  | Description                    |
|---------------------------|---------------------------|--------------------------------|
| `scrape_all_sites`        | Daily at 6:00 AM PKT      | Full scrape of all 7 sources   |
| `scrape_api_sources`      | 6:30 AM + 6:30 PM PKT     | Adzuna + JSearch APIs only     |
| `cleanup_old_jobs`        | Sunday at 00:00 PKT       | Deactivate 60+ day old listings|

---

## Docker Deployment

### Build and start all services
```bash
cp .env.example .env     # Fill in SECRET_KEY and API keys
docker compose up -d
```

### Check service status
```bash
docker compose ps
docker compose logs -f worker    # Follow scraper worker logs
docker compose logs -f beat      # Follow scheduler logs
```

### Run a manual scrape inside Docker
```bash
docker compose exec worker python run_scraper.py --site rozee --dry-run
```

### Stop everything
```bash
docker compose down
docker compose down -v    # Also delete database and Redis data
```

---

## Checking Logs

Logs are written to `logs/scraper_YYYY-MM-DD.log` with timestamps.

```bash
# Follow today's log in real time
tail -f logs/scraper_$(date +%Y-%m-%d).log

# Search for errors
grep "ERROR" logs/scraper_2024-05-01.log

# Count jobs saved per site
grep "INSERTED" logs/scraper_2024-05-01.log | awk '{print $NF}' | sort | uniq -c
```

### Query scraper stats from PostgreSQL
```sql
-- Jobs found per site in the last 7 days
SELECT site_name,
       SUM(jobs_found) AS total_found,
       SUM(jobs_saved) AS total_saved,
       SUM(errors)     AS total_errors,
       COUNT(*)        AS run_count
FROM scraper_stats
WHERE run_at > NOW() - INTERVAL '7 days'
GROUP BY site_name
ORDER BY total_saved DESC;

-- Recent run history
SELECT site_name, jobs_found, jobs_saved, errors, run_at
FROM scraper_stats
ORDER BY run_at DESC
LIMIT 20;
```

---

## Troubleshooting

### Chrome not found
```bash
# Install Google Chrome
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list
sudo apt update && sudo apt install -y google-chrome-stable
```

### Redis connection refused
```bash
# Start Redis
docker run -d -p 6379:6379 --name redis redis:alpine
# or: sudo systemctl start redis
```

### Selectors broken (site changed layout)
Job sites update their HTML structure periodically. When a scraper returns 0 results:
1. Run with `--no-headless` to see the browser
2. Open DevTools (F12) and inspect the new element structure
3. Update the `SEL_*` constants at the top of the affected scraper file

### CAPTCHA blocks (Indeed/Glassdoor)
- Add real proxies to `PROXY_LIST` in `.env`
- Reduce scraping frequency (increase delays in `driver_manager.py`)
- Consider using Adzuna/JSearch APIs as fallback (no CAPTCHA risk)

---

## File Reference

```
scraper/
├── base_scraper.py           Abstract base: clean → dedup → save pipeline
├── celery_config.py          Celery + Redis config, Beat schedule
├── tasks.py                  Celery task definitions
├── db_additions.py           ScraperStats model (add to database.py)
│
├── sites/
│   ├── indeed_scraper.py     Selenium + JS panel click for descriptions
│   ├── linkedin_scraper.py   Selenium listings + requests detail pages
│   ├── rozee_scraper.py      BS4 only — Pakistan-specific, UTF-8 aware
│   ├── internshala_scraper.py BS4 only — India/remote internships
│   └── glassdoor_scraper.py  Selenium with Cloudflare bypass
│
├── api_scrapers/
│   ├── adzuna_scraper.py     Free REST API — no browser needed
│   └── jsearch_scraper.py    RapidAPI aggregator — 7+ sources in one call
│
└── utils/
    ├── driver_manager.py     Chrome setup: anti-detection, random UA, delays
    ├── proxy_rotator.py      IP/UA rotation, exponential backoff, requests helper
    ├── data_cleaner.py       Normalize location/stipend/date, skill extraction
    └── deduplicator.py       Redis + PostgreSQL two-tier dedup, expiry

run_scraper.py                CLI entry point — site selection, dry-run, progress bar
Dockerfile.scraper            Container with Chrome + Python + all deps
docker-compose.yml            Full stack: DB + Redis + API + Worker + Beat + Flower
scraper_requirements.txt      Python dependencies for the scraper
```
