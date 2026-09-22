"""Integration tests for POST /search and GET /export.

Uses httpx.AsyncClient with ASGITransport so no real network calls are made.
The scraper is patched out via backend.api.search.get_scraper.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

import backend.services.cache as _cache_mod
from backend.models.job import Job
from backend.scrapers.base import BaseScraper, ScraperError

# Build app inline to avoid backend/main.py's bare `from api.search import router`
# which only works when running with backend/ on sys.path (uvicorn mode).
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.search import router
from backend.config import settings

app = FastAPI(title="Thai Job Board Aggregator (test)")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

pytestmark = pytest.mark.anyio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_job(job_id: str = "j1", title: str = "Python Dev") -> Job:
    return Job(
        id=job_id, title=title, company="Acme", location="Bangkok",
        salary_min=50000.0, salary_max=80000.0, currency="THB",
        salary_display="50,000-80,000", salary_is_numeric=True,
        work_arrangement="Onsite", experience_min_years=2.0,
        experience_max_years=5.0, categories=["IT"], skills_mentioned=[],
        abstract="Great job", content=None,
        url="https://th.jobsdb.com/j1",
        listed_at="2024-01-15T08:00:00Z", source="jobsdb", raw=None,
    )


class _MockScraper(BaseScraper):
    source_name = "jobsdb"

    async def search(self, criteria):
        return [_make_job("j1"), _make_job("j2", "Data Analyst")]

    async def get_detail(self, job_id: str) -> Job:
        return _make_job(job_id).model_copy(
            update={"content": "<p>python</p>", "skills_mentioned": ["python"]}
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_cache():
    """Disable Redis and wipe in-memory cache before/after every test."""
    orig = _cache_mod._redis_client
    _cache_mod._redis_client = None
    _cache_mod._memory_cache.clear()
    yield
    _cache_mod._redis_client = orig
    _cache_mod._memory_cache.clear()


@pytest.fixture
def mock_scraper():
    """Patch get_scraper to return _MockScraper() for the duration of a test."""
    with patch("backend.api.search.get_scraper", return_value=_MockScraper()):
        yield


# ---------------------------------------------------------------------------
# POST /search
# ---------------------------------------------------------------------------

async def test_search_cache_miss_returns_results(mock_scraper):
    """Cache miss: scrape → score → response with cached=False."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/search", json={"keywords": "python"})

    assert r.status_code == 200
    body = r.json()
    assert body["cached"] is False
    assert body["total"] == 2
    assert len(body["jobs"]) == 2
    assert body["source"] == "jobsdb"
    assert body["search_id"].startswith("search:v1:")


async def test_search_cache_hit_returns_cached_true(mock_scraper):
    """Second identical request hits cache → cached=True."""
    payload = {"keywords": "python"}
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.post("/search", json=payload)
        r2 = await client.post("/search", json=payload)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["cached"] is False
    assert r2.json()["cached"] is True


async def test_search_unknown_source_returns_400():
    """Unknown source → HTTP 400 with error: unknown_source."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/search", json={"keywords": "python", "source": "notareal"})

    assert r.status_code == 400
    body = r.json()
    assert body["error"] == "unknown_source"
    assert body["retryable"] is False


async def test_search_page_size_over_max_returns_422():
    """page_size > 500 fails Pydantic validation → HTTP 422."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/search", json={"keywords": "python", "page_size": 501})

    assert r.status_code == 422


async def test_search_scraper_exhausted_returns_503_retryable():
    """ScraperError(code='scraper_exhausted') → HTTP 503, retryable=True."""
    scraper = _MockScraper()
    scraper.search = AsyncMock(side_effect=ScraperError(code="scraper_exhausted", message="out"))

    with patch("backend.api.search.get_scraper", return_value=scraper):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post("/search", json={"keywords": "python"})

    assert r.status_code == 503
    body = r.json()
    assert body["error"] == "scraper_exhausted"
    assert body["retryable"] is True


async def test_search_scraper_auth_returns_503_not_retryable():
    """ScraperError(code='scraper_auth') → HTTP 503, retryable=False."""
    scraper = _MockScraper()
    scraper.search = AsyncMock(side_effect=ScraperError(code="scraper_auth", message="blocked"))

    with patch("backend.api.search.get_scraper", return_value=scraper):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post("/search", json={"keywords": "python"})

    assert r.status_code == 503
    body = r.json()
    assert body["error"] == "scraper_auth"
    assert body["retryable"] is False


# ---------------------------------------------------------------------------
# GET /export
# ---------------------------------------------------------------------------

async def _seed_cache(mock_scraper_fixture=None) -> str:
    """Run a search so the cache is populated; return the search_id."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/search", json={"keywords": "python"})
    assert r.status_code == 200
    return r.json()["search_id"]


async def test_export_json_returns_200_with_search_id(mock_scraper):
    """GET /export?format=json → 200, valid JSON containing search_id."""
    search_id = await _seed_cache()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/export", params={"search_id": search_id, "format": "json"})

    assert r.status_code == 200
    data = r.json()
    assert data["search_id"] == search_id


async def test_export_excel_returns_200_xlsx_magic(mock_scraper):
    """GET /export?format=excel → 200, bytes start with PK (xlsx magic bytes)."""
    search_id = await _seed_cache()

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/export", params={"search_id": search_id, "format": "excel"})

    assert r.status_code == 200
    assert r.content[:2] == b"PK"


async def test_export_nonexistent_search_id_returns_410():
    """GET /export with unknown search_id → 410, error: results_expired."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get(
            "/export", params={"search_id": "search:v1:nonexistent", "format": "json"}
        )

    assert r.status_code == 410
    assert r.json()["error"] == "results_expired"
