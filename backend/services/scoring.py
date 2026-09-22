"""Scoring Engine — score_job() and score_and_rank()."""

from __future__ import annotations

import re
from backend.models.job import Job, ScoredJob, SearchCriteria


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _range_overlap_score(
    job_min: float | None,
    job_max: float | None,
    crit_min: float | None,
    crit_max: float | None,
) -> float:
    """
    1.0 — full overlap (one range contains the other, or they share > 1 point)
    0.5 — single endpoint shared, or partial overlap
    0.0 — no overlap

    Open-ended ranges: None on either side means unbounded in that direction.
    """
    # Treat None as ±∞
    j_lo = job_min  if job_min  is not None else float("-inf")
    j_hi = job_max  if job_max  is not None else float("+inf")
    c_lo = crit_min if crit_min is not None else float("-inf")
    c_hi = crit_max if crit_max is not None else float("+inf")

    # No overlap: one range is entirely above the other
    if j_lo > c_hi or c_lo > j_hi:
        return 0.0

    # Exactly one endpoint shared (touching at a single point only)
    if j_lo == c_hi or c_lo == j_hi:
        return 0.5

    # Full containment or real overlap — check for partial (true overlap > 1 point)
    overlap_lo = max(j_lo, c_lo)
    overlap_hi = min(j_hi, c_hi)

    if overlap_lo < overlap_hi:
        # Genuine interval overlap — check full containment
        if (j_lo <= c_lo and j_hi >= c_hi) or (c_lo <= j_lo and c_hi >= j_hi):
            return 1.0
        # Partial overlap
        return 0.5

    # overlap_lo == overlap_hi → single point, not containing
    return 0.5


def _keywords_score(job: Job, keywords: str) -> float:
    kws = [kw.strip().lower() for kw in re.split(r"[,\s]+", keywords) if kw.strip()]
    if not kws:
        return 1.0
    text = " ".join(
        part for part in (job.title, job.abstract, job.content) if part
    ).lower()
    hits = sum(1 for kw in kws if kw in text)
    return hits / len(kws)


def _skills_score(required: list[str], mentioned: list[str]) -> float:
    if not required:
        return 1.0
    r = {s.lower() for s in required}
    m = {s.lower() for s in mentioned}
    union = r | m
    if not union:
        return 1.0
    return len(r & m) / len(union)


def _salary_score(job: Job, crit_min: float | None, crit_max: float | None) -> float:
    # Criteria not specified
    if crit_min is None and crit_max is None:
        return 1.0
    # Job has no numeric salary (null or negotiable)
    if not job.salary_is_numeric or (job.salary_min is None and job.salary_max is None):
        return 1.0
    return _range_overlap_score(job.salary_min, job.salary_max, crit_min, crit_max)


def _location_score(job_location: str | None, crit_location: str | None) -> float:
    if crit_location is None:
        return 1.0
    if job_location is None:
        return 0.0
    jl = job_location.lower()
    cl = crit_location.lower()
    if jl == cl:
        return 1.0
    if cl in jl or jl in cl:
        return 0.5
    return 0.0


def _experience_score(job: Job, crit_min: float | None, crit_max: float | None) -> float:
    # Criteria not specified
    if crit_min is None and crit_max is None:
        return 1.0
    # Job has no experience data
    if job.experience_min_years is None and job.experience_max_years is None:
        return 1.0
    return _range_overlap_score(
        job.experience_min_years, job.experience_max_years,
        crit_min, crit_max,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score_job(job: Job, criteria: SearchCriteria) -> float:
    """Return a score in [0.0, 1.0] for *job* against *criteria*."""
    w = criteria.score_weights
    raw_weights = [
        w.keywords_weight,
        w.skills_weight,
        w.salary_weight,
        w.location_weight,
        w.experience_weight,
    ]
    total_w = sum(raw_weights)
    if total_w == 0:
        return 0.0
    norm = [wi / total_w for wi in raw_weights]

    scores = [
        _keywords_score(job, criteria.keywords),
        _skills_score(criteria.required_skills, job.skills_mentioned),
        _salary_score(job, criteria.salary_min, criteria.salary_max),
        _location_score(job.location, criteria.location),
        _experience_score(job, criteria.experience_min_years, criteria.experience_max_years),
    ]

    result = sum(s * nw for s, nw in zip(scores, norm))
    return max(0.0, min(1.0, result))


def score_and_rank(jobs: list[Job], criteria: SearchCriteria) -> list[ScoredJob]:
    """Score every job, sort descending, assign dense 1-based ranks."""
    scored = [ScoredJob(job=j, score=score_job(j, criteria), rank=0) for j in jobs]
    scored.sort(key=lambda sj: sj.score, reverse=True)

    rank = 1
    for i, sj in enumerate(scored):
        if i > 0 and sj.score < scored[i - 1].score:
            rank += 1
        sj.rank = rank

    return scored


# ---------------------------------------------------------------------------
# Self-check (python backend/services/scoring.py)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    def _job(**kwargs) -> Job:
        defaults = dict(
            id="1", title="", company=None, location=None,
            salary_min=None, salary_max=None, currency=None,
            salary_display=None, salary_is_numeric=False,
            work_arrangement=None, experience_min_years=None,
            experience_max_years=None, categories=[], skills_mentioned=[],
            abstract=None, content=None, url="http://x", listed_at=None,
            source="jobsdb", raw=None,
        )
        defaults.update(kwargs)
        return Job(**defaults)

    def _criteria(**kwargs) -> SearchCriteria:
        defaults = dict(keywords="python")
        defaults.update(kwargs)
        return SearchCriteria(**defaults)

    # 1. Unspecified optional criteria → score must be 1.0 when keyword matches
    j = _job(title="python developer")
    c = _criteria(keywords="python")          # no salary/location/skills/exp
    s = score_job(j, c)
    assert s == 1.0, f"expected 1.0, got {s}"

    # 2. Salary null → salary criterion 1.0 (no penalty)
    j2 = _job(title="python developer", salary_min=None, salary_max=None, salary_is_numeric=False)
    c2 = _criteria(keywords="python", salary_min=30000, salary_max=50000)
    s2 = score_job(j2, c2)
    assert s2 == 1.0, f"salary null should give 1.0, got {s2}"

    # 3. No keyword match → keyword score 0.0, others 1.0 → final = keyword_norm_weight * 0.0 + rest * 1.0
    j3 = _job(title="accountant")
    c3 = _criteria(keywords="python")
    s3 = score_job(j3, c3)
    expected_kw_weight = 0.30
    expected_rest_weight = 1.0 - expected_kw_weight
    expected3 = expected_rest_weight  # 0.70
    assert abs(s3 - expected3) < 1e-9, f"expected ~0.70, got {s3}"

    # 4. Score in [0, 1] for every case
    for score in [s, s2, s3]:
        assert 0.0 <= score <= 1.0, f"score out of range: {score}"

    # 5. Dense ranking with ties
    jobs_list = [
        _job(id="a", title="python", skills_mentioned=["python"]),
        _job(id="b", title="python", skills_mentioned=["python"]),
        _job(id="c", title="java developer"),
        _job(id="d", title="accountant"),
    ]
    c5 = _criteria(keywords="python", required_skills=["python"])
    ranked = score_and_rank(jobs_list, c5)
    # First two have same score → rank 1; third → rank 3; fourth → rank 4
    scores_by_id = {sj.job.id: (sj.score, sj.rank) for sj in ranked}
    assert scores_by_id["a"][1] == 1
    assert scores_by_id["b"][1] == 1
    # Dense ranking: rank values must map 1-to-1 with distinct score groups,
    # ordered so group 1 (highest score) → rank 1, group 2 → rank (size_of_group_1 + 1), etc.
    # e.g. scores [1.0, 1.0, 0.7, 0.3] → ranks [1, 1, 3, 4]
    sorted_scored = sorted(ranked, key=lambda sj: sj.score, reverse=True)
    expected_rank = 1
    for i, sj in enumerate(sorted_scored):
        if i > 0 and sj.score < sorted_scored[i - 1].score:
            expected_rank = i + 1
        assert sj.rank == expected_rank, f"job {sj.job.id}: rank {sj.rank}, expected {expected_rank}"

    # 6. Range overlap cases
    assert _range_overlap_score(20000, 30000, 35000, 50000) == 0.0   # no overlap
    assert _range_overlap_score(20000, 35000, 35000, 50000) == 0.5   # single endpoint
    assert _range_overlap_score(20000, 40000, 30000, 50000) == 0.5   # partial
    assert _range_overlap_score(25000, 45000, 20000, 50000) == 1.0   # fully contained

    print("All self-checks passed.")
