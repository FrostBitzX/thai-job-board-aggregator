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
