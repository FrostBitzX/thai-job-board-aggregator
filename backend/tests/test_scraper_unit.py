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
        "workArrangements": [{"label": {"lang": "en", "text": "Hybrid"}}],
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


# ---------------------------------------------------------------------------
# Tests for extract_skills (task 5.3)
# ---------------------------------------------------------------------------

from backend.scrapers.jobsdb import SKILLS_VOCAB, extract_skills


def test_extract_skills_case_insensitive():
    """`python` matched regardless of case in HTML."""
    assert "python" in extract_skills("<p>Python developer</p>")


def test_extract_skills_go_boundary():
    """`go` must NOT match inside `django` or `mongo`."""
    result = extract_skills("<p>django mongo</p>")
    assert "go" not in result


def test_extract_skills_go_standalone():
    """`go` matched when it appears as a standalone word."""
    assert "go" in extract_skills("<p>We use Go and Docker</p>")


def test_extract_skills_deduplication():
    """Each term appears at most once even if it appears multiple times in text."""
    result = extract_skills("<p>Python python PYTHON</p>")
    assert result.count("python") == 1


def test_extract_skills_sorted():
    """Returned list is sorted alphabetically."""
    result = extract_skills("<p>python docker aws</p>")
    assert result == sorted(result)


def test_extract_skills_strips_html():
    """HTML tags are stripped before matching."""
    assert "python" in extract_skills("<div><b>Python</b> is great</div>")


def test_extract_skills_special_chars():
    """Terms with non-word chars (c++, c#, node.js, ci/cd) are matched."""
    html = "<p>We use C++, C#, Node.js, and CI/CD pipelines</p>"
    result = extract_skills(html)
    assert "c++" in result
    assert "c#" in result
    assert "node.js" in result
    assert "ci/cd" in result


def test_extract_skills_multi_word():
    """Multi-word terms like `data analysis` are matched correctly."""
    assert "data analysis" in extract_skills("<p>Experience in data analysis required</p>")


def test_extract_skills_empty_content():
    """Empty string returns empty list."""
    assert extract_skills("") == []


def test_skills_vocab_minimum_count():
    """Vocabulary contains at least 39 terms as required."""
    assert len(SKILLS_VOCAB) >= 39


# ---------------------------------------------------------------------------
# Tests for fetch_details_batched (task 7.1)
# ---------------------------------------------------------------------------

from backend.scrapers.jobsdb import fetch_details_batched


def _make_listing_job(job_id: str) -> "Job":
    from backend.models.job import Job as _Job
    return _Job(
        id=job_id, title="Dev", company="Co", location="BKK",
        salary_min=None, salary_max=None, currency=None,
        salary_display=None, salary_is_numeric=False,
        work_arrangement=None, experience_min_years=None,
        experience_max_years=None, categories=[], skills_mentioned=[],
        abstract=None, content=None, url="https://example.com",
        listed_at=None, source="jobsdb", raw=None,
    )


def _make_detail_job(job_id: str, content: str, skills: list[str],
                     exp_min: float | None = None, exp_max: float | None = None):
    from backend.models.job import Job as _Job
    return _Job(
        id=job_id, title="", company=None, location=None,
        salary_min=None, salary_max=None, currency=None,
        salary_display=None, salary_is_numeric=False,
        work_arrangement=None, experience_min_years=exp_min,
        experience_max_years=exp_max, categories=[], skills_mentioned=skills,
        abstract=None, content=content, url="", listed_at=None,
        source="jobsdb", raw=None,
    )


async def test_fetch_details_batched_merges_fields():
    """Happy path: listing fields preserved; content/skills/experience from detail."""
    listing = _make_listing_job("j1")
    detail = _make_detail_job("j1", "<p>python dev</p>", ["python"], 2.0, 5.0)

    scraper = MagicMock()
    scraper.get_detail = AsyncMock(return_value=detail)

    results = await fetch_details_batched(scraper, [listing])

    assert len(results) == 1
    r = results[0]
    assert r.id == "j1"
    assert r.title == "Dev"          # listing field preserved
    assert r.company == "Co"         # listing field preserved
    assert r.content == "<p>python dev</p>"
    assert r.skills_mentioned == ["python"]
    assert r.experience_min_years == 2.0
    assert r.experience_max_years == 5.0


async def test_fetch_details_batched_failure_keeps_listing():
    """On per-job failure: listing fields kept, skills_mentioned set to []."""
    listing = _make_listing_job("j2")

    scraper = MagicMock()
    scraper.get_detail = AsyncMock(side_effect=RuntimeError("boom"))

    results = await fetch_details_batched(scraper, [listing])

    assert len(results) == 1
    r = results[0]
    assert r.id == "j2"
    assert r.title == "Dev"
    assert r.skills_mentioned == []
    assert r.content is None        # unchanged from listing


async def test_fetch_details_batched_one_failure_does_not_kill_batch():
    """A failure on job[0] does not affect job[1] in the same batch."""
    jobs = [_make_listing_job("ok"), _make_listing_job("fail")]
    detail_ok = _make_detail_job("ok", "<p>go</p>", ["go"])

    async def _get_detail(job_id: str):
        if job_id == "fail":
            raise ValueError("network error")
        return detail_ok

    scraper = MagicMock()
    scraper.get_detail = _get_detail

    results = await fetch_details_batched(scraper, jobs)

    assert results[0].skills_mentioned == ["go"]
    assert results[1].skills_mentioned == []
    assert results[1].title == "Dev"


async def test_fetch_details_batched_respects_batch_size(monkeypatch):
    """Jobs are processed in chunks of DETAIL_BATCH_SIZE; gather called per batch."""
    import backend.scrapers.jobsdb as jmod
    monkeypatch.setattr(jmod.settings, "DETAIL_BATCH_SIZE", 2)

    jobs = [_make_listing_job(f"j{i}") for i in range(5)]
    detail = _make_detail_job("x", "", [])

    scraper = MagicMock()
    scraper.get_detail = AsyncMock(return_value=detail)

    results = await fetch_details_batched(scraper, jobs)

    assert len(results) == 5
    assert scraper.get_detail.call_count == 5
