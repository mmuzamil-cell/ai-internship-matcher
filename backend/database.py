"""
database.py — Database connection, ORM models, and dependency injection.

This module is the single source of truth for all database-related setup:
  - SQLAlchemy engine & session factory
  - All ORM table models (Users, Resumes, Internships, Applications, MatchScores)
  - FastAPI dependency `get_db` for injecting DB sessions into route handlers
"""

import os
from datetime import datetime

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker

# Load secrets from .env file (must happen before reading os.getenv)
load_dotenv()

# ─── Engine Setup ─────────────────────────────────────────────────────────────
# pool_pre_ping=True: validates connections before use, handles stale connections
# gracefully without crashing the request.
DATABASE_URL: str = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and fill it in.")

# Detect SQLite vs other databases — SQLite doesn't support pool_size/max_overflow
_is_sqlite = DATABASE_URL.startswith("sqlite")

if _is_sqlite:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # Required for SQLite in FastAPI
        echo=False,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,   # Detect & discard dead connections automatically
        pool_size=10,          # Keep up to 10 connections alive in the pool
        max_overflow=20,       # Allow 20 extra connections under heavy load
        echo=False,            # Set True during development to log all SQL queries
    )

# SessionLocal is a factory that creates new DB sessions.
# autocommit=False → we manage transactions manually (safer for writes).
# autoflush=False  → we control when pending changes are flushed to DB.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ─── Declarative Base ─────────────────────────────────────────────────────────
# All ORM models inherit from Base so SQLAlchemy knows about them.
class Base(DeclarativeBase):
    pass


# ─── ORM Models ───────────────────────────────────────────────────────────────

class User(Base):
    """
    Represents a student account in the system.
    Stores credentials, university affiliation, and timestamps.
    """
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    full_name     = Column(String(150), nullable=False)
    email         = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)       # bcrypt hash, never plaintext
    university    = Column(String(200), nullable=True)
    major         = Column(String(150), nullable=True)
    is_admin      = Column(Boolean, default=False)            # Admin flag for protected routes
    created_at    = Column(DateTime, default=datetime.utcnow)

    # Relationships — lazy="dynamic" defers query until accessed
    resumes      = relationship("Resume", back_populates="owner", cascade="all, delete-orphan")
    applications = relationship("Application", back_populates="student", cascade="all, delete-orphan")
    match_scores = relationship("MatchScore", back_populates="student", cascade="all, delete-orphan")


class Resume(Base):
    """
    Stores uploaded PDF resume metadata and extracted content.
    The actual file lives on disk at `file_path`; this record points to it.
    skills_json is a JSON string like '["python", "sql", "machine learning"]'.
    """
    __tablename__ = "resumes"

    id             = Column(Integer, primary_key=True, index=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename       = Column(String(255), nullable=False)      # Original filename shown to user
    file_path      = Column(String(512), nullable=False)      # Absolute path on server disk
    extracted_text = Column(Text, nullable=True)              # Raw text pulled from PDF
    skills_json    = Column(Text, nullable=True)              # JSON array of detected skills
    uploaded_at    = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="resumes")


class Internship(Base):
    """
    A single internship listing, either scraped automatically or added manually.
    required_skills is a JSON array string matching the format of Resume.skills_json
    so we can compute overlap quickly in the matcher.
    """
    __tablename__ = "internships"

    id              = Column(Integer, primary_key=True, index=True)
    title           = Column(String(255), nullable=False)
    company         = Column(String(200), nullable=False)
    location        = Column(String(150), nullable=True)       # City or "Remote"
    description     = Column(Text, nullable=True)
    required_skills = Column(Text, nullable=True)              # JSON array of skill strings
    stipend         = Column(String(100), nullable=True)       # e.g. "PKR 25,000/month"
    deadline        = Column(DateTime, nullable=True)
    source_url      = Column(String(512), nullable=True)       # Original job posting URL
    source_site     = Column(String(100), nullable=True)       # "LinkedIn", "Rozee.pk", etc.
    scraped_at      = Column(DateTime, default=datetime.utcnow)
    is_active       = Column(Boolean, default=True, index=True)  # False = expired/removed

    applications = relationship("Application", back_populates="internship")
    match_scores = relationship("MatchScore", back_populates="internship")


class Application(Base):
    """
    Tracks a student's application to a specific internship.
    Status transitions: applied → reviewing → accepted | rejected
    """
    __tablename__ = "applications"

    id             = Column(Integer, primary_key=True, index=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
    internship_id  = Column(Integer, ForeignKey("internships.id"), nullable=False)
    status         = Column(String(50), default="applied")    # applied/reviewing/rejected/accepted
    applied_at     = Column(DateTime, default=datetime.utcnow)
    notes          = Column(Text, nullable=True)              # Student's personal notes

    student     = relationship("User", back_populates="applications")
    internship  = relationship("Internship", back_populates="applications")


class MatchScore(Base):
    """
    Cached cosine-similarity score between a student's resume skills
    and an internship's required_skills + description vector.
    Re-computed whenever the student uploads a new resume.
    """
    __tablename__ = "match_scores"

    id             = Column(Integer, primary_key=True, index=True)
    user_id        = Column(Integer, ForeignKey("users.id"), nullable=False)
    internship_id  = Column(Integer, ForeignKey("internships.id"), nullable=False)
    score          = Column(Float, nullable=False)            # 0.0 (no match) → 1.0 (perfect)
    computed_at    = Column(DateTime, default=datetime.utcnow)

    student    = relationship("User", back_populates="match_scores")
    internship = relationship("Internship", back_populates="match_scores")


# ─── FastAPI Dependency ───────────────────────────────────────────────────────

def get_db():
    """
    Yields a SQLAlchemy session for use in a single request, then closes it.

    Usage in route handlers:
        def my_route(db: Session = Depends(get_db)):
            ...

    The try/finally pattern ensures the session is always closed, even if an
    exception is raised mid-request, preventing connection pool exhaustion.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Import ScraperStats so SQLAlchemy includes it in create_all()
# (scraper table lives in same DB as the backend)
try:
    from scraper.db_additions import ScraperStats  # noqa: F401
except ImportError:
    pass  # Scraper not installed — table will be created when scraper runs
