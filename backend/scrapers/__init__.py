from __future__ import annotations

from typing import TYPE_CHECKING

from backend.scrapers.base import BaseScraper

if TYPE_CHECKING:
    pass

# Lazy registry: JobsDBScraper is imported at call-time so the factory module
# can be imported before scrapers/jobsdb.py exists (task 5.x).
def _build_registry() -> dict[str, type[BaseScraper]]:
    registry: dict[str, type[BaseScraper]] = {}
    try:
        from backend.scrapers.jobsdb import JobsDBScraper  # noqa: PLC0415
        registry["jobsdb"] = JobsDBScraper
    except ImportError:
        pass  # jobsdb adapter not yet implemented
    return registry


def get_scraper(source: str) -> BaseScraper:
    registry = _build_registry()
    try:
        return registry[source]()
    except KeyError:
        raise ValueError(f"Unknown source: {source!r}")
