from __future__ import annotations

import asyncio
import json
import logging
import re
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

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


SKILLS_VOCAB: list[str] = [
    "python", "javascript", "typescript", "java", "go", "rust",
    "c++", "c#", "sql", "nosql", "react", "vue", "angular",
    "node.js", "fastapi", "django", "flask", "spring",
    "docker", "kubernetes", "aws", "gcp", "azure", "terraform", "git",
    "ci/cd", "agile", "scrum", "jira", "figma", "excel",
    "powerbi", "tableau", "data analysis", "machine learning",
    "deep learning", "communication", "leadership", "project management",
]


_BOUNDARY = r"(?<!\w){term}(?!\w)"


def extract_skills(html_content: str, vocab: list[str] = SKILLS_VOCAB) -> list[str]:
    """Return a sorted, deduplicated list of skill terms found in *html_content*.

    HTML is stripped via BeautifulSoup; matching is case-insensitive whole-word.
    """
    text = BeautifulSoup(html_content, "html.parser").get_text().lower()
    matched = {
        term
        for term in vocab
        if re.search(_BOUNDARY.format(term=re.escape(term)), text)
    }
    return sorted(matched)


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


def _map_jsonld_job(entry: dict) -> Job:
    """Map a JSON-LD JobPosting entry → Job (Req 3.4).

    All absent fields map to None/empty as required.
    """
    hiring_org = entry.get("hiringOrganization") or {}
    job_location = entry.get("jobLocation") or {}
    address = job_location.get("address") or {}
    base_salary = entry.get("baseSalary") or {}
    salary_value = base_salary.get("value") or {}

    salary_min: float | None = salary_value.get("minValue")
    salary_max: float | None = salary_value.get("maxValue")
    salary_is_numeric = salary_min is not None and salary_max is not None

    if salary_is_numeric:
        salary_display = f"{salary_min:g}-{salary_max:g}"
    else:
        salary_display = "Other"

    content: str | None = entry.get("description") or None
    url: str = entry.get("url") or ""
    if url.startswith("/"):
        url = _BASE_URL + url

    return Job(
        id=entry.get("identifier", {}).get("value") or url or "",
        title=entry.get("title") or "",
        company=hiring_org.get("name"),
        location=address.get("addressLocality"),
        salary_min=salary_min,
        salary_max=salary_max,
        currency=salary_value.get("currency"),
        salary_display=salary_display,
        salary_is_numeric=salary_is_numeric,
        work_arrangement=None,
        experience_min_years=None,
        experience_max_years=None,
        categories=[],
        skills_mentioned=extract_skills(content) if content else [],
        abstract=None,
        content=content,
        url=url,
        listed_at=entry.get("datePosted"),
        source="jobsdb",
        raw=None,
    )


class JobsDBScraper(BaseScraper):
    source_name = "jobsdb"

    async def search(self, criteria: SearchCriteria) -> list[Job]:
        jobs: list[Job] = []
        page_num = 1

        try:
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

        except (_AuthError, ScraperError):
            logger.info("GraphQL path failed; switching to Playwright fallback")
            return await self._playwright_search(criteria)

        return jobs[: criteria.page_size]

    async def _playwright_search(self, criteria: SearchCriteria) -> list[Job]:
        """Playwright fallback: scrape JSON-LD JobPosting blocks from th.jobsdb.com.

        Requirements 3.1–3.7.
        """
        from playwright.async_api import async_playwright, TimeoutError as PwTimeout

        kw_slug = re.sub(r"\s+", "-", criteria.keywords.strip().lower())
        jobs: list[Job] = []
        page_num = 1

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()

                while len(jobs) < criteria.page_size:
                    page_param = f"?page={page_num}" if page_num > 1 else ""
                    url = f"{_BASE_URL}/th/{kw_slug}-jobs{page_param}"
                    last_exc: Exception | None = None

                    for attempt in range(3):
                        try:
                            await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                            # Wait up to 30 s for the JSON-LD script tag (Req 3.2)
                            await page.wait_for_selector(
                                'script[type="application/ld+json"]', timeout=30_000
                            )
                            last_exc = None
                            break
                        except PwTimeout as exc:
                            last_exc = exc
                            logger.warning(
                                "Playwright timeout page=%d attempt=%d: %s",
                                page_num, attempt + 1, exc,
                            )
                            await asyncio.sleep(_RETRY_BASE_DELAY * (2**attempt))
                        except Exception as exc:
                            last_exc = exc
                            logger.warning(
                                "Playwright nav error page=%d attempt=%d: %s",
                                page_num, attempt + 1, exc,
                            )
                            await asyncio.sleep(_RETRY_BASE_DELAY * (2**attempt))

                    if last_exc is not None:
                        raise ScraperError(code="scraper_auth") from last_exc

                    # Extract all JSON-LD blocks and keep @type == JobPosting (Req 3.3)
                    handles = await page.query_selector_all('script[type="application/ld+json"]')
                    page_jobs: list[Job] = []
                    for handle in handles:
                        try:
                            raw_text = await handle.inner_text()
                            block = json.loads(raw_text)
                        except Exception:
                            continue

                        # block may be a list or a single object
                        entries = block if isinstance(block, list) else [block]
                        for entry in entries:
                            if entry.get("@type") != "JobPosting":
                                continue
                            page_jobs.append(_map_jsonld_job(entry))

                    if not page_jobs:
                        break  # No more results (Req 3.6)

                    jobs.extend(page_jobs)
                    page_num += 1

            finally:
                await browser.close()

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
            categories=[], skills_mentioned=extract_skills(content) if content else [],
            abstract=None, content=content,
            url="", listed_at=None,
            source="jobsdb", raw=None,
        )
