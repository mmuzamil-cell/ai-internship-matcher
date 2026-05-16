"""
scraper/utils/data_cleaner.py — Normalize and clean raw scraped job data.

Raw data from different job sites uses inconsistent formats:
  - Locations: "Karachi, Sindh, Pakistan" vs "KHI" vs "Remote (Pakistan)"
  - Dates: "2 days ago" vs "Dec 31" vs "2024-12-31T00:00:00Z"
  - Stipends: "PKR 15,000/month" vs "15k" vs "Competitive"
  - Descriptions: Full HTML vs plain text with escape characters

This module normalizes all of the above into a consistent format
that maps directly to the Internship ORM model fields.
"""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ─── Master Skills List (80+ skills) ──────────────────────────────────────────
# Same canonical structure as utils/skill_extractor.py in the FastAPI backend.
# Maintained separately so the scraper can run independently.
MASTER_SKILLS: dict[str, list[str]] = {
    # Programming Languages
    "python":       ["python", "python3", "py"],
    "javascript":   ["javascript", "js", "es6", "es2022"],
    "typescript":   ["typescript", "ts"],
    "java":         ["java", "java 17", "java 11"],
    "c++":          ["c++", "cpp", "c plus plus"],
    "c#":           ["c#", "csharp", "dotnet", ".net"],
    "go":           ["golang", "go lang"],
    "rust":         ["rust", "rustlang"],
    "swift":        ["swift", "swiftui"],
    "kotlin":       ["kotlin"],
    "php":          ["php", "php8"],
    "ruby":         ["ruby", "ror", "rails"],
    "r":            ["r programming", "rstudio", "tidyverse"],
    "matlab":       ["matlab", "simulink"],
    "scala":        ["scala", "spark scala"],
    "dart":         ["dart", "flutter"],
    "perl":         ["perl"],
    "shell":        ["bash", "shell", "shell scripting", "zsh"],
    # Web Frameworks
    "react":        ["react", "reactjs", "react.js"],
    "next.js":      ["nextjs", "next.js", "next js"],
    "vue":          ["vuejs", "vue.js", "nuxt"],
    "angular":      ["angular", "angularjs"],
    "fastapi":      ["fastapi"],
    "django":       ["django", "drf", "django rest"],
    "flask":        ["flask"],
    "express":      ["express", "expressjs"],
    "spring boot":  ["spring boot", "spring", "spring mvc"],
    "laravel":      ["laravel"],
    "node.js":      ["nodejs", "node.js", "node js"],
    "asp.net":      ["asp.net", "aspnet", "blazor"],
    # Databases
    "sql":          ["sql", "mysql", "mariadb", "tsql", "plsql"],
    "postgresql":   ["postgresql", "postgres", "psql"],
    "mongodb":      ["mongodb", "mongo", "mongoose"],
    "redis":        ["redis", "elasticache"],
    "sqlite":       ["sqlite"],
    "elasticsearch":["elasticsearch", "elastic", "opensearch"],
    "firebase":     ["firebase", "firestore", "realtime database"],
    "cassandra":    ["cassandra", "dynamodb", "nosql"],
    "oracle":       ["oracle db", "oracle database"],
    # Cloud & DevOps
    "aws":          ["aws", "amazon web services", "ec2", "s3", "lambda"],
    "azure":        ["azure", "microsoft azure", "azure devops"],
    "google cloud": ["gcp", "google cloud", "bigquery", "cloud run"],
    "docker":       ["docker", "dockerfile", "container"],
    "kubernetes":   ["kubernetes", "k8s", "helm", "eks", "aks"],
    "ci/cd":        ["ci/cd", "cicd", "jenkins", "github actions", "gitlab ci", "circleci"],
    "git":          ["git", "github", "gitlab", "bitbucket", "version control"],
    "linux":        ["linux", "unix", "ubuntu", "centos", "debian"],
    "terraform":    ["terraform", "iac", "infrastructure as code", "pulumi"],
    "ansible":      ["ansible", "puppet", "chef"],
    # AI / ML / Data
    "machine learning": ["machine learning", "ml", "supervised learning", "classification"],
    "deep learning":    ["deep learning", "neural network", "cnn", "rnn", "lstm", "transformer"],
    "tensorflow":       ["tensorflow", "tf", "keras"],
    "pytorch":          ["pytorch", "torch"],
    "scikit-learn":     ["scikit-learn", "sklearn", "scikit learn"],
    "pandas":           ["pandas", "dataframe"],
    "numpy":            ["numpy", "np"],
    "data analysis":    ["data analysis", "data analytics", "statistical analysis", "eda"],
    "nlp":              ["nlp", "natural language processing", "bert", "gpt", "llm", "spacy", "nltk"],
    "computer vision":  ["computer vision", "opencv", "yolo", "image classification"],
    "tableau":          ["tableau", "data visualization"],
    "power bi":         ["power bi", "powerbi", "dax"],
    "spark":            ["apache spark", "pyspark", "databricks"],
    "hadoop":           ["hadoop", "hive", "hdfs", "mapreduce"],
    # Business / Other Tech
    "rest api":         ["rest api", "restful", "api", "openapi", "swagger"],
    "graphql":          ["graphql", "apollo"],
    "agile":            ["agile", "scrum", "kanban", "jira", "sprint"],
    "ui/ux":            ["ui/ux", "figma", "sketch", "adobe xd", "wireframe", "prototype"],
    "testing":          ["testing", "pytest", "jest", "selenium", "cypress", "unit test", "tdd"],
    "data structures":  ["data structures", "algorithms", "dsa", "leetcode", "competitive programming"],
    "oop":              ["object oriented", "oop", "design patterns", "solid principles"],
    "microservices":    ["microservices", "service mesh", "istio", "grpc"],
    "blockchain":       ["blockchain", "ethereum", "solidity", "web3", "smart contract"],
    "cybersecurity":    ["cybersecurity", "penetration testing", "ethical hacking", "siem", "soc"],
    "excel":            ["excel", "vba", "spreadsheet", "google sheets"],
    "sap":              ["sap", "erp", "sap s/4hana"],
    "salesforce":       ["salesforce", "crm", "apex", "soql"],
}

# Flat alias → canonical lookup for O(1) matching
_ALIAS_MAP: dict[str, str] = {}
for canonical, aliases in MASTER_SKILLS.items():
    _ALIAS_MAP[canonical] = canonical
    for alias in aliases:
        _ALIAS_MAP[alias.lower()] = canonical

# ─── Location normalization ───────────────────────────────────────────────────
PAKISTAN_CITIES = {
    "karachi", "lahore", "islamabad", "rawalpindi", "faisalabad",
    "multan", "peshawar", "quetta", "sialkot", "gujranwala",
    "hyderabad", "abbottabad", "bahawalpur", "sargodha", "sukkur",
}
REMOTE_KEYWORDS = {"remote", "work from home", "wfh", "distributed", "anywhere", "globally"}


def normalize_location(raw_location: Optional[str]) -> dict:
    """
    Normalize a raw location string into a structured dict.

    Examples:
      "Karachi, Sindh, Pakistan" → {city: "Karachi", country: "Pakistan", is_remote: False}
      "Remote (PKT)"             → {city: None,      country: None,       is_remote: True}
      "KHI"                      → {city: "Karachi", country: "Pakistan", is_remote: False}

    Returns:
        dict with keys: city (str|None), country (str|None), is_remote (bool)
    """
    if not raw_location:
        return {"city": None, "country": None, "is_remote": False}

    loc_lower = raw_location.lower().strip()

    # Check for remote keywords first
    is_remote = any(kw in loc_lower for kw in REMOTE_KEYWORDS)

    # Try to extract a Pakistani city
    city = None
    for pk_city in PAKISTAN_CITIES:
        if pk_city in loc_lower:
            city = pk_city.title()
            break

    # Abbreviation mapping for common Pakistani city codes
    abbrev_map = {"khi": "Karachi", "lhr": "Lahore", "isb": "Islamabad", "rwp": "Rawalpindi"}
    if not city:
        for abbrev, full_name in abbrev_map.items():
            if abbrev in loc_lower.split():
                city = full_name
                break

    # Determine country
    country = None
    if city or "pakistan" in loc_lower or "pk" in loc_lower.split(",")[-1].strip().split():
        country = "Pakistan"
    elif any(kw in loc_lower for kw in ["india", "in"]):
        country = "India"
    elif any(kw in loc_lower for kw in ["usa", "united states", "us"]):
        country = "United States"

    # Compose display string: use raw if we couldn't parse it
    display = city or (raw_location.strip() if not is_remote else "Remote")

    return {
        "city":      city,
        "country":   country,
        "is_remote": is_remote,
        "display":   display,
    }


def parse_stipend(raw_stipend: Optional[str]) -> dict:
    """
    Extract structured stipend data from a free-text string.

    Examples:
      "PKR 15,000 - 25,000/month" → {amount: 15000, max: 25000, currency: "PKR", period: "monthly"}
      "Rs. 20k per month"         → {amount: 20000, currency: "PKR", period: "monthly"}
      "Unpaid"                    → {amount: 0,     currency: None,  period: None}
      "Competitive"               → {amount: None,  currency: None,  period: None}

    Returns:
        dict with keys: amount (int|None), max (int|None), currency (str|None), period (str|None)
    """
    result = {"amount": None, "max": None, "currency": None, "period": None, "raw": raw_stipend}

    if not raw_stipend:
        return result

    text = raw_stipend.strip()
    text_lower = text.lower()

    # Check for unpaid/volunteer explicitly
    if any(kw in text_lower for kw in ["unpaid", "volunteer", "no stipend"]):
        result["amount"] = 0
        return result

    # Currency detection
    if any(kw in text_lower for kw in ["pkr", "rs.", "rs ", "rupee", "₨"]):
        result["currency"] = "PKR"
    elif any(kw in text_lower for kw in ["usd", "$", "dollar"]):
        result["currency"] = "USD"
    elif any(kw in text_lower for kw in ["inr", "₹", "indian rupee"]):
        result["currency"] = "INR"

    # Period detection
    if any(kw in text_lower for kw in ["month", "/mo", "monthly", "pm"]):
        result["period"] = "monthly"
    elif any(kw in text_lower for kw in ["week", "/wk", "weekly"]):
        result["period"] = "weekly"
    elif any(kw in text_lower for kw in ["hour", "/hr", "hourly"]):
        result["period"] = "hourly"

    # Amount extraction: find numeric values (handles "15,000", "15k", "15K")
    amounts = []
    # First try explicit numbers with commas
    for match in re.finditer(r"[\d,]+(?:\.\d+)?", text.replace(",", "")):
        try:
            amounts.append(int(float(match.group())))
        except ValueError:
            pass

    # Handle "k" suffix (15k → 15000)
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*k", text_lower):
        try:
            amounts.append(int(float(match.group(1)) * 1000))
        except ValueError:
            pass

    if amounts:
        amounts.sort()
        result["amount"] = amounts[0]   # Min amount
        if len(amounts) > 1:
            result["max"] = amounts[-1]  # Max amount (for ranges)

    return result


def parse_deadline(raw_date: Optional[str]) -> Optional[str]:
    """
    Convert various date formats to an ISO 8601 date string.

    Handles:
      - "3 days ago" → today - 3 days (for posted dates, not deadlines)
      - "Dec 31"     → current year + Dec 31 → "2024-12-31"
      - "2024-12-31" → "2024-12-31" (already ISO)
      - "31/12/2024" → "2024-12-31"

    Returns:
        ISO date string "YYYY-MM-DD" or None if parsing fails.
    """
    if not raw_date:
        return None

    text = raw_date.strip().lower()
    now  = datetime.utcnow()

    # ── Relative dates ──────────────────────────────────────────────────────
    m = re.match(r"(\d+)\s+(day|week|month|hour)s?\s+ago", text)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        if unit == "hour":
            dt = now - timedelta(hours=n)
        elif unit == "day":
            dt = now - timedelta(days=n)
        elif unit == "week":
            dt = now - timedelta(weeks=n)
        elif unit == "month":
            dt = now - timedelta(days=n * 30)
        return dt.strftime("%Y-%m-%d")

    if "today" in text or "just now" in text:
        return now.strftime("%Y-%m-%d")
    if "yesterday" in text:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")

    # ── Absolute date formats ──────────────────────────────────────────────
    formats = [
        "%Y-%m-%d",          # 2024-12-31
        "%d/%m/%Y",          # 31/12/2024
        "%m/%d/%Y",          # 12/31/2024
        "%B %d, %Y",         # December 31, 2024
        "%b %d, %Y",         # Dec 31, 2024
        "%B %d",             # December 31 (assume current year)
        "%b %d",             # Dec 31
        "%d %B %Y",          # 31 December 2024
        "%Y-%m-%dT%H:%M:%SZ",# ISO 8601 with time
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(raw_date.strip(), fmt)
            if dt.year == 1900:   # strptime default year for partial dates
                dt = dt.replace(year=now.year)
                if dt < now:      # If parsed date is in past, assume next year
                    dt = dt.replace(year=now.year + 1)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    logger.debug("Could not parse date: '%s'", raw_date)
    return None


def strip_html(html_text: Optional[str]) -> str:
    """
    Remove HTML tags from text and normalize whitespace.
    Uses BeautifulSoup for robust HTML parsing.
    """
    if not html_text:
        return ""
    soup = BeautifulSoup(html_text, "html.parser")
    text = soup.get_text(separator=" ")
    # Collapse multiple spaces/newlines into single space
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_skills_from_text(text: str) -> list[str]:
    """
    Scan a job description for known skills using n-gram matching.

    Strategy: normalize text → slide 1/2/3-gram window → look up in alias map.
    Returns a sorted, deduplicated list of canonical skill names.
    """
    if not text:
        return []

    # Normalize: lowercase, strip non-skill punctuation
    normalized = text.lower()
    normalized = re.sub(r"[^\w\s\+\#\/\.\-]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)

    tokens = normalized.split()
    found:  set[str] = set()

    for i in range(len(tokens)):
        for size in (1, 2, 3):
            if i + size > len(tokens):
                break
            gram = " ".join(tokens[i : i + size])
            canonical = _ALIAS_MAP.get(gram)
            if canonical:
                found.add(canonical)

    return sorted(found)


def clean_job(raw: dict) -> Optional[dict]:
    """
    Transform a raw scraped job dict into the normalized format
    expected by the Internship ORM model.

    Args:
        raw: Dict with keys from individual scrapers (inconsistent format).

    Returns:
        Normalized dict ready for database insertion, or None if the job
        is missing critical required fields (title or company).
    """
    # ── Required fields check ─────────────────────────────────────────────────
    title   = (raw.get("title") or "").strip()
    company = (raw.get("company") or "").strip()
    if not title or not company:
        logger.debug("Skipping job with missing title or company: %s", raw.get("source_url"))
        return None

    # ── Description cleanup ───────────────────────────────────────────────────
    desc_raw  = raw.get("description") or ""
    desc_text = strip_html(desc_raw)[:2000]  # Truncate to 2000 chars

    # ── Skill extraction from description ─────────────────────────────────────
    # Combine explicit required_skills (if scraper found them) with desc-extracted skills
    explicit_skills = raw.get("required_skills") or []
    desc_skills     = extract_skills_from_text(desc_text)
    all_skills      = sorted(set(explicit_skills) | set(desc_skills))

    # ── Location normalization ─────────────────────────────────────────────────
    location_data = normalize_location(raw.get("location"))

    # ── Stipend parsing ────────────────────────────────────────────────────────
    stipend_data = parse_stipend(raw.get("stipend_text") or raw.get("salary"))

    # ── Deadline parsing ───────────────────────────────────────────────────────
    deadline_str = parse_deadline(raw.get("deadline") or raw.get("date_posted"))

    return {
        "title":           title,
        "company":         company,
        "location":        location_data.get("display") or location_data.get("city") or "Unknown",
        "is_remote":       location_data["is_remote"],
        "description":     desc_text,
        "required_skills": json.dumps(all_skills),   # JSON array for DB storage
        "stipend":         stipend_data.get("raw"),   # Keep original text for display
        "deadline":        deadline_str,
        "source_url":      (raw.get("source_url") or "").strip(),
        "source_site":     (raw.get("source_site") or "Unknown").strip(),
        "scraped_at":      datetime.utcnow().isoformat(),
        # Extra structured fields (for analytics, not stored in main table)
        "_city":           location_data.get("city"),
        "_stipend_amount": stipend_data.get("amount"),
        "_stipend_currency": stipend_data.get("currency"),
        "_skills_count":   len(all_skills),
    }
