from __future__ import annotations

import asyncio
import re

import httpx

from backend.config import settings
from backend.models.job import Job, SearchCriteria
from backend.scrapers.base import BaseScraper, ScraperError

_BASE_URL = "https://th.jobsdb.com"
_GRAPHQL_URL = f"{_BASE_URL}/graphql"

_HEADERS = {
    "content-type": "application/json",
    "seek-request-brand": "jobsdb",
    "seek-request-country": "TH",
    "origin": _BASE_URL,
    "accept": "application/graphql-response+json,application/json;q=0.9",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

_QUERY = """
query JobSearchV7($params: JobSearchV7QueryInput!, $locale: Locale!, $zone: Zone!, $country: JobSearchV7Country!, $timezone: Timezone!) {
  jobSearchV7(params: $params) {
    results {
      jobs {
        id
        title
        abstract
        advertiser { name }
        categories { label(locale: $locale) }
        location { displayName { text } }
        cjs {
          salary {
            hideSalary
            minimum
            maximum
            currency
            displayValue
          }
        }
        listedAt { dateTimeUtc }
        url
        workArrangements {
          label { lang text }
        }
      }
      pagination { page pageSize resultCount }
    }
  }
}
""".strip()

_DETAIL_QUERY = """
query jobDetails($jobId: ID!, $zone: Zone!, $locale: Locale!, $countryCode: CountryCodeIso2!, $timezone: Timezone!) {
  jobDetails(id: $jobId, tracking: {channel: "WEB"}) {
    job {
      content(platform: WEB)
      content2(zone: $zone) { content }
    }
    seoInfo {
      workType
    }
  }
}
""".strip()

_PAGE_SIZE = 30
_MAX_RETRIES = settings.MAX_RETRIES
_RETRY_BASE_DELAY = settings.RETRY_BASE_DELAY
_RETRYABLE_STATUS = {429, 503}
_AUTH_FAIL_STATUS = {401, 403}


class _AuthError(Exception):
    """Sentinel raised on HTTP 401/403 to trigger Playwright fallback."""


def _build_variables(criteria: SearchCriteria, page_num: int) -> dict:
    return {
        "params": {
            "searchIntent": {
                "country": "TH",
                "locale": "en-TH",
                "text": criteria.keywords,
                "sort": "score",
            },
            "searchContext": {
                "brand": "jobsdb",
                "channel": "web",
            },
            "responseConfig": {
                "results": ["jobs"],
                "representations": ["uiV1"],
                "page": page_num,
                "pageSize": _PAGE_SIZE,
            },
        },
        "locale": "en-TH",
        "zone": "asia-3",
        "timezone": "Asia/Bangkok",
        "country": "TH",
    }


def _map_job(raw: dict) -> Job:
    salary = (raw.get("cjs") or {}).get("salary") or {}
    salary_min = salary.get("minimum")
    salary_max = salary.get("maximum")
    salary_is_numeric = salary_min is not None and salary_max is not None

    display_val = salary.get("displayValue") or ""
    if display_val:
        salary_display = display_val
    elif salary.get("hideSalary") or not salary_is_numeric:
        salary_display = "Other"
    else:
        salary_display = None

    # work_arrangement: first label where lang == "en"
    work_arrangement = None
    for wa in raw.get("workArrangements") or []:
        for lbl in wa.get("label") or []:
            if lbl.get("lang") == "en":
                work_arrangement = lbl.get("text")
                break
        if work_arrangement is not None:
            break

    location_obj = raw.get("location") or {}
    display_name = location_obj.get("displayName") or {}
    location = display_name.get("text")

    categories = [c["label"] for c in (raw.get("categories") or []) if c.get("label")]

    url: str = raw.get("url") or ""
    if url.startswith("/"):
        url = _BASE_URL + url

    listed_at = (raw.get("listedAt") or {}).get("dateTimeUtc")
    advertiser = raw.get("advertiser") or {}

    return Job(
        id=raw["id"],
        title=raw.get("title") or "",
        company=advertiser.get("name"),
        location=location,
        salary_min=salary_min,
        salary_max=salary_max,
        currency=salary.get("currency"),
        salary_display=salary_display,
        salary_is_numeric=salary_is_numeric,
        work_arrangement=work_arrangement,
        experience_min_years=None,
        experience_max_years=None,
        categories=categories,
        skills_mentioned=[],
        abstract=raw.get("abstract"),
        content=None,
        url=url,
        listed_at=listed_at,
        source="jobsdb",
        raw=raw,
    )


async def _post_with_retry(client: httpx.AsyncClient, payload: dict) -> dict:
    """POST to GraphQL endpoint with exponential backoff. Returns parsed JSON."""
    last_exc: Exception | None = None

    for attempt in range(_MAX_RETRIES):
        try:
            resp = await client.post(_GRAPHQL_URL, json=payload, headers=_HEADERS)
        except (httpx.NetworkError, httpx.TimeoutException) as exc:
            last_exc = exc
            await asyncio.sleep(_RETRY_BASE_DELAY * (2**attempt))
            continue

        if resp.status_code in _AUTH_FAIL_STATUS:
            raise _AuthError(f"HTTP {resp.status_code}")

        if resp.status_code in _RETRYABLE_STATUS:
            last_exc = httpx.HTTPStatusError(
                f"HTTP {resp.status_code}", request=resp.request, response=resp
            )
            await asyncio.sleep(_RETRY_BASE_DELAY * (2**attempt))
            continue

        resp.raise_for_status()
        return resp.json()

    raise ScraperError(code="scraper_exhausted") from last_exc


def _parse_experience(work_type: str | None) -> tuple[float | None, float | None]:
    """Parse seoInfo.workType text into (min_years, max_years).

    Examples:
      "2 years experience" → (2.0, None)
      "2-5 years"          → (2.0, 5.0)
      "No experience"      → (0.0, 0.0)
      anything else        → (None, None)
    """
    if not work_type:
        return None, None

    text = work_type.strip().lower()

    if "no experience" in text:
        return 0.0, 0.0

    # "2-5 years" or "2 - 5 years"
    range_match = re.search(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)\s*year", text)
    if range_match:
        return float(range_match.group(1)), float(range_match.group(2))

    # "2 years" / "2+ years" / "at least 2 years"
    single_match = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*year", text)
    if single_match:
        return float(single_match.group(1)), None

    return None, None


class JobsDBScraper(BaseScraper):
    source_name = "jobsdb"

    async def search(self, criteria: SearchCriteria) -> list[Job]:
        jobs: list[Job] = []
        page_num = 1

        async with httpx.AsyncClient() as client:
            while True:
                payload = {
                    "operationName": "JobSearchV7",
                    "variables": _build_variables(criteria, page_num),
                    "query": _QUERY,
                }
                data = await _post_with_retry(client, payload)

                results = (
                    data.get("data", {})
                    .get("jobSearchV7", {})
                    .get("results", {})
                )
                page_jobs: list[dict] = results.get("jobs") or []
                pagination: dict = results.get("pagination") or {}
                result_count: int = pagination.get("resultCount", 0)

                if not page_jobs:
                    break

                jobs.extend(_map_job(j) for j in page_jobs)

                if len(jobs) >= criteria.page_size:
                    break
                if len(jobs) >= result_count:
                    break

                page_num += 1

        return jobs[: criteria.page_size]

    async def get_detail(self, job_id: str) -> Job:
        """Fetch detail for a single job and return a Job carrying content + experience.

        The caller (task 7.1) merges these fields back onto the listing-level Job.
        On retry exhaustion, returns a shell Job so the caller can retain listing
        fields and set skills_mentioned=[] rather than failing the whole search.
        """
        payload = {
            "operationName": "jobDetails",
            "variables": {
                "jobId": job_id,
                "zone": "asia-3",
                "locale": "en-TH",
                "countryCode": "TH",
                "timezone": "Asia/Bangkok",
            },
            "query": _DETAIL_QUERY,
        }

        async with httpx.AsyncClient() as client:
            try:
                data = await _post_with_retry(client, payload)
            except ScraperError:
                # Exhausted retries: return a shell so caller falls back gracefully
                return Job(
                    id=job_id, title="", company=None, location=None,
                    salary_min=None, salary_max=None, currency=None,
                    salary_display=None, salary_is_numeric=False,
                    work_arrangement=None, experience_min_years=None,
                    experience_max_years=None, categories=[], skills_mentioned=[],
                    abstract=None, content=None, url="", listed_at=None,
                    source="jobsdb", raw=None,
                )

        detail = (data.get("data") or {}).get("jobDetails") or {}
        job_node = detail.get("job") or {}
        seo_info = detail.get("seoInfo") or {}

        # content2 (click-to-reveal path) takes priority over plain content
        content2 = job_node.get("content2") or {}
        content: str | None = content2.get("content") or job_node.get("content")

        exp_min, exp_max = _parse_experience(seo_info.get("workType"))

        return Job(
            id=job_id, title="", company=None, location=None,
            salary_min=None, salary_max=None, currency=None,
            salary_display=None, salary_is_numeric=False,
            work_arrangement=None,
            experience_min_years=exp_min,
            experience_max_years=exp_max,
            categories=[], skills_mentioned=[],
            abstract=None, content=content,
            url="", listed_at=None,
            source="jobsdb", raw=None,
        )
