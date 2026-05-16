"""
scraper/db_additions.py — ScraperStats SQLAlchemy model.

INSTRUCTIONS: This model must be imported into your backend's database.py
so SQLAlchemy includes it in Base.metadata.create_all().

Add this line at the bottom of backend/database.py:
    from scraper.db_additions import ScraperStats  # noqa: F401

Or simply copy the ScraperStats class directly into database.py.
"""

from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text

# BUG FIX: Import Base from database.py so the table is registered with SQLAlchemy
# When used standalone (e.g. in scraper workers), import Base from the backend
try:
    from database import Base
except ImportError:
    # Fallback for when scraper runs in its own process
    from sqlalchemy.orm import DeclarativeBase
    class Base(DeclarativeBase):
        pass


class ScraperStats(Base):
    """
    Tracks statistics for each scraper run.
    One row inserted per scraper per run() call.
    """
    __tablename__ = "scraper_stats"

    id         = Column(Integer, primary_key=True, index=True)
    site_name  = Column(String(100), nullable=False, index=True)
    jobs_found = Column(Integer, default=0)
    jobs_saved = Column(Integer, default=0)
    errors     = Column(Integer, default=0)
    run_at     = Column(DateTime, default=datetime.utcnow, index=True)
    notes      = Column(Text, nullable=True)

    def __repr__(self):
        return (
            f"<ScraperStats site={self.site_name} "
            f"found={self.jobs_found} saved={self.jobs_saved} "
            f"errors={self.errors} at={self.run_at}>"
        )
