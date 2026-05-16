"""
main.py — FastAPI application entry point.

Responsibilities:
  - Create and configure the FastAPI app instance
  - Set up CORS middleware (allow the React/Next.js frontend to call the API)
  - Register all routers (auth, resume, jobs, applications, matching)
  - Apply slowapi rate limiting on the login endpoint
  - On startup: auto-create all database tables if they don't exist

Run with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load environment variables FIRST — before any module that reads env vars at import time
load_dotenv()

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from database import Base, engine

# ─── Logging Setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level    = logging.INFO,
    format   = "%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt  = "%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─── Rate Limiter ─────────────────────────────────────────────────────────────
# Uses the client's IP address as the rate limit key.
# Limits are applied per-route using the @limiter.limit() decorator.
limiter = Limiter(key_func=get_remote_address)


# ─── Lifespan (Startup / Shutdown) ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs once at server startup (before yielding) and once at shutdown (after).

    On startup:
      - Create all SQLAlchemy tables that don't exist yet.
        This is safe to run on every restart (checkfirst=True is the default).
      - Ensure the uploads directory exists.

    On shutdown:
      - Nothing to clean up for now (connection pool closes automatically).
    """
    # Create tables from ORM models
    logger.info("Creating database tables (if not exist)…")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ready.")

    # Ensure upload directory exists
    upload_dir = os.getenv("UPLOAD_DIR", "uploads/resumes")
    os.makedirs(upload_dir, exist_ok=True)
    logger.info("Upload directory ready: %s", upload_dir)

    yield  # Server is now running and accepting requests

    logger.info("Shutting down AI Internship Matcher API.")


# ─── FastAPI App Instance ──────────────────────────────────────────────────────
app = FastAPI(
    title       = "AI Internship Matcher API",
    description = (
        "Backend for the AI-Powered Internship Matcher final year project.\n\n"
        "Upload your resume, let the AI match you with relevant internships, "
        "and identify skill gaps with learning recommendations."
    ),
    version     = "1.0.0",
    docs_url    = "/docs",      # Swagger UI
    redoc_url   = "/redoc",     # ReDoc (alternative docs)
    lifespan    = lifespan,
)

# Attach rate limiter state to the app so slowapi middleware can access it
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ─── CORS Middleware ───────────────────────────────────────────────────────────
# Reads allowed origins from environment variable (comma-separated).
# In development: http://localhost:3000 (React), http://localhost:5173 (Vite).
# In production: set to your actual frontend domain.
raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173")
allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins     = allowed_origins,
    allow_credentials = True,               # Required for cookies / Authorization header
    allow_methods     = ["*"],              # Allow GET, POST, PUT, DELETE, OPTIONS
    allow_headers     = ["*"],              # Allow Authorization, Content-Type, etc.
)


# ─── Error Response Standardization ───────────────────────────────────────────
# FastAPI's default validation errors are verbose. This handler wraps them
# in our consistent {detail, code} format for the frontend to parse easily.
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "The requested resource was not found.", "code": "NOT_FOUND"},
    )


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    logger.error("Unhandled server error: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected server error occurred.", "code": "INTERNAL_ERROR"},
    )


# ─── Router Registration ───────────────────────────────────────────────────────
# Import routers AFTER app creation to avoid circular imports.
from routes.auth     import router as auth_router
from routes.resume   import router as resume_router
from routes.jobs     import apps_router, jobs_router
from routes.matching import router as match_router
from routes.scraper  import router as scraper_router

# Apply rate limit to the login route (5 requests per minute per IP)
# The login function has a Request parameter so slowapi can extract the client IP
LOGIN_RATE_LIMIT = os.getenv("LOGIN_RATE_LIMIT", "100/minute")  # Relaxed for dev
from routes.auth import login as login_fn
login_fn = limiter.limit(LOGIN_RATE_LIMIT)(login_fn)

app.include_router(auth_router)
app.include_router(resume_router)
app.include_router(jobs_router)
app.include_router(apps_router)
app.include_router(match_router)
app.include_router(scraper_router)


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"], summary="Health check")
def health_check():
    """
    Simple liveness probe endpoint.
    Returns 200 OK if the server is running.
    Useful for Docker health checks and load balancer probes.
    """
    return {"status": "ok", "service": "AI Internship Matcher API", "version": "1.0.0"}


# ─── Root Redirect ─────────────────────────────────────────────────────────────
@app.get("/", tags=["System"], include_in_schema=False)
def root():
    """Redirect root to API docs for convenience."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/docs")
