"""Unit tests for JobsDBScraper.search() — mocks httpx.AsyncClient.post."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.models.job import SearchCriteria
from backend.scrapers.jobsdb import JobsDBScraper

pytestmark = pytest.mark.anyio


def _make_job_dict(job_id: str, title: str, **overrides) -> dict:
    base = {
        "id": job_id,
        "title": title,
        "abstract": f"Abstract for {title}",
        "advertiser": {"name": "Acme Corp"},
        "categories": [{"label": "IT / Computer"}],
        "location": {"displayName": {"text": "Bangkok"}},
        "cjs": {
            "salary": {
                "hideSalary": False,
                "minimum": 50000.0,
                "maximum": 80000.0,
                "currency": "THB",
                "displayValue": "50,000-80,000",
            }
        },
        "listedAt": {"dateTimeUtc": "2024-01-15T08:00:00Z"},
        "url": "/software-engineer-jobs/job-123",
        "workArrangements": [{"label": [{"lang": "en", "text": "Hybrid"}]}],
    }
    base.update(overrides)
    return base


def _make_response(jobs: list[dict], result_count: int | None = None) -> MagicMock:
    """Build a mock httpx Response returning a GraphQL payload."""
    rc = result_count if result_count is not None else len(jobs)
    payload = {
        "data": {
            "jobSearchV7": {
                "results": {
                    "jobs": jobs,
                    "pagination": {"page": 1, "pageSize": 30, "resultCount": rc},
                }
            }
        }
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


async def test_search_maps_two_jobs_correctly():
    """Happy path: 2 jobs returned, fields mapped correctly."""
    jobs_raw = [
        _make_job_dict("j1", "Software Engineer"),
        _make_job_dict("j2", "Data Analyst", advertiser={"name": "Beta Ltd"}),
    ]
    mock_resp = _make_response(jobs_raw)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        criteria = SearchCriteria(keywords="software engineer", page_size=10)
        scraper = JobsDBScraper()
        results = await scraper.search(criteria)

    assert len(results) == 2

    j1 = results[0]
    assert j1.id == "j1"
    assert j1.title == "Software Engineer"
    assert j1.company == "Acme Corp"
    assert j1.location == "Bangkok"
    assert j1.salary_min == 50000.0
    assert j1.salary_max == 80000.0
    assert j1.currency == "THB"
    assert j1.salary_display == "50,000-80,000"
    assert j1.salary_is_numeric is True
    assert j1.work_arrangement == "Hybrid"
    assert j1.categories == ["IT / Computer"]
    assert j1.abstract == "Abstract for Software Engineer"
    assert j1.url == "https://th.jobsdb.com/software-engineer-jobs/job-123"
    assert j1.listed_at == "2024-01-15T08:00:00Z"
    assert j1.source == "jobsdb"
    assert j1.experience_min_years is None
    assert j1.experience_max_years is None
    assert j1.skills_mentioned == []
    assert j1.content is None

    j2 = results[1]
    assert j2.company == "Beta Ltd"


async def test_search_stops_at_result_count():
    """Pagination stops when cumulative jobs >= resultCount, not just page empty."""
    # 2 jobs on page 1, resultCount=2 → should not fetch page 2
    jobs_raw = [
        _make_job_dict("j1", "Dev A"),
        _make_job_dict("j2", "Dev B"),
    ]
    mock_resp = _make_response(jobs_raw, result_count=2)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        criteria = SearchCriteria(keywords="dev", page_size=100)
        results = await JobsDBScraper().search(criteria)

    assert len(results) == 2
    # Only one POST call (page 1), because resultCount was reached
    assert mock_client.post.call_count == 1


async def test_url_relative_gets_base_prepended():
    """Relative URLs are prefixed with https://th.jobsdb.com."""
    jobs_raw = [_make_job_dict("j1", "Dev", url="/some/path")]
    mock_resp = _make_response(jobs_raw)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        results = await JobsDBScraper().search(SearchCriteria(keywords="dev"))

    assert results[0].url == "https://th.jobsdb.com/some/path"


async def test_salary_hidden_shows_other():
    """hideSalary=True with no displayValue → salary_display == 'Other'."""
    raw_salary = {
        "hideSalary": True,
        "minimum": None,
        "maximum": None,
        "currency": None,
        "displayValue": "",
    }
    jobs_raw = [_make_job_dict("j1", "Dev", cjs={"salary": raw_salary})]
    mock_resp = _make_response(jobs_raw)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        results = await JobsDBScraper().search(SearchCriteria(keywords="dev"))

    j = results[0]
    assert j.salary_display == "Other"
    assert j.salary_is_numeric is False
    assert j.salary_min is None
    assert j.salary_max is None


async def test_search_trims_to_page_size():
    """Result list is trimmed to criteria.page_size."""
    jobs_raw = [_make_job_dict(f"j{i}", f"Dev {i}") for i in range(5)]
    mock_resp = _make_response(jobs_raw, result_count=5)

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        criteria = SearchCriteria(keywords="dev", page_size=3)
        results = await JobsDBScraper().search(criteria)

    assert len(results) == 3


# ---------------------------------------------------------------------------
# Tests for get_detail() and _parse_experience  (task 5.2)
# ---------------------------------------------------------------------------

from backend.scrapers.jobsdb import _parse_experience


def _make_detail_response(
    content: str | None = None,
    content2_content: str | None = None,
    work_type: str | None = None,
) -> MagicMock:
    job_node: dict = {}
    if content is not None:
        job_node["content"] = content
    if content2_content is not None:
        job_node["content2"] = {"content": content2_content}

    payload = {
        "data": {
            "jobDetails": {
                "job": job_node,
                "seoInfo": {"workType": work_type},
            }
        }
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = payload
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# --- _parse_experience unit tests ---

@pytest.mark.parametrize("text,expected", [
    (None,                  (None, None)),
    ("",                    (None, None)),
    ("Graduate",            (None, None)),
    ("No experience",       (0.0,  0.0)),
    ("No Experience Required", (0.0, 0.0)),
    ("2 years experience",  (2.0,  None)),
    ("2+ years",            (2.0,  None)),
    ("5 years",             (5.0,  None)),
    ("2-5 years",           (2.0,  5.0)),
    ("2 - 5 years",         (2.0,  5.0)),
    ("3–7 years",           (3.0,  7.0)),
])
def test_parse_experience(text, expected):
    assert _parse_experience(text) == expected


# --- get_detail() unit tests ---

async def test_get_detail_maps_content_and_experience():
    """Happy path: content and experience extracted correctly."""
    mock_resp = _make_detail_response(
        content="<p>Job description here</p>",
        work_type="2-5 years",
    )

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        job = await JobsDBScraper().get_detail("job-123")

    assert job.id == "job-123"
    assert job.content == "<p>Job description here</p>"
    assert job.experience_min_years == 2.0
    assert job.experience_max_years == 5.0


async def test_get_detail_prefers_content2():
    """content2.content takes priority over plain content."""
    mock_resp = _make_detail_response(
        content="plain content",
        content2_content="<p>richer content</p>",
        work_type=None,
    )

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        job = await JobsDBScraper().get_detail("job-456")

    assert job.content == "<p>richer content</p>"
    assert job.experience_min_years is None
    assert job.experience_max_years is None


async def test_get_detail_retry_exhaustion_returns_shell():
    """On retry exhaustion get_detail() returns a shell Job (not raises)."""
    from backend.scrapers.base import ScraperError as SE

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        # Always return 503 → exhausts retries → ScraperError
        mock_resp = MagicMock()
        mock_resp.status_code = 503
        mock_resp.request = MagicMock()
        mock_resp.response = mock_resp
        mock_client.post = AsyncMock(return_value=mock_resp)
        mock_client_cls.return_value = mock_client

        with patch("asyncio.sleep", new_callable=AsyncMock):
            job = await JobsDBScraper().get_detail("job-fail")

    assert job.id == "job-fail"
    assert job.content is None
    assert job.skills_mentioned == []
    assert job.experience_min_years is None
