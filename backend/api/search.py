"""POST /search endpoint — orchestrates scrape → score → cache pipeline."""

from __future__ import annotations

import asyncio
import logging
from typing import Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from backend.config import settings
from backend.exporters.excel_exporter import export_excel
from backend.exporters.json_exporter import export_json
from backend.models.job import ErrorResponse, Job, SearchCriteria, SearchResponse
from backend.scrapers import get_scraper
from backend.scrapers.base import ScraperError
from backend.services.cache import cache_get, cache_key, cache_set
from backend.services.scoring import score_and_rank

logger = logging.getLogger(__name__)
router = APIRouter()


async def _fetch_details(scraper, jobs: list[Job]) -> list[Job]:
    """Fetch job details in batches of DETAIL_BATCH_SIZE, merging results back."""
    results: list[Job] = []
    for i in range(0, len(jobs), settings.DETAIL_BATCH_SIZE):
        batch = jobs[i : i + settings.DETAIL_BATCH_SIZE]
        fetched = await asyncio.gather(
            *[scraper.get_detail(job.id) for job in batch],
            return_exceptions=True,
        )
        for job, detail in zip(batch, fetched):
            if isinstance(detail, Exception):
                logger.warning("get_detail failed for job %s: %s", job.id, detail)
                results.append(job)  # keep listing-level data; skills_mentioned stays []
            else:
                results.append(detail)
    return results


@router.post("/search", response_model=SearchResponse)
async def search(criteria: SearchCriteria) -> SearchResponse | JSONResponse:
    key = cache_key(criteria)

    # --- Cache hit ---
    cached = cache_get(key)
    if cached is not None:
        return SearchResponse(**{**cached, "cached": True})

    # --- Cache miss: scrape → detail → score ---
    try:
        scraper = get_scraper(criteria.source)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                error="unknown_source",
                message=f"No adapter registered for source {criteria.source!r}.",
                retryable=False,
            ).model_dump(),
        )

    try:
        jobs = await scraper.search(criteria)
        jobs = await _fetch_details(scraper, jobs)
        scored = score_and_rank(jobs, criteria)
    except ScraperError as exc:
        retryable = exc.code == "scraper_exhausted"
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(
                error=exc.code,
                message=str(exc),
                retryable=retryable,
            ).model_dump(),
        )
    except Exception:
        logger.exception("Unhandled error during search for criteria: %s", criteria)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_error",
                message="An unexpected error occurred. Please try again later.",
                retryable=False,
            ).model_dump(),
        )

    response = SearchResponse(
        jobs=scored,
        total=len(scored),
        source=criteria.source,
        cached=False,
        search_id=key,
    )
    cache_set(key, response.model_dump(mode="json"), settings.CACHE_TTL_SECONDS)
    return response


@router.get("/export", response_model=None)
async def export(search_id: str, format: Literal["json", "excel"]) -> StreamingResponse | JSONResponse:
    data = cache_get(search_id)
    if data is None:
        return JSONResponse(
            status_code=410,
            content=ErrorResponse(
                error="results_expired",
                message="Search results have expired. Please run your search again.",
                retryable=False,
            ).model_dump(),
        )

    try:
        scored_jobs = SearchResponse(**data).jobs
        if format == "json":
            content = export_json(scored_jobs, search_id)
            return StreamingResponse(
                iter([content]),
                media_type="application/json",
                headers={"Content-Disposition": "attachment; filename=\"results.json\""},
            )
        else:
            content = export_excel(scored_jobs)
            return StreamingResponse(
                iter([content]),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": "attachment; filename=\"results.xlsx\""},
            )
    except Exception:
        logger.exception("Export failed for search_id=%s format=%s", search_id, format)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_error",
                message="Export failed due to an internal error.",
                retryable=False,
            ).model_dump(),
        )
