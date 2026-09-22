from pydantic import BaseModel, Field

from backend.config import settings


class Job(BaseModel):
    id: str
    title: str
    company: str | None
    location: str | None
    salary_min: float | None
    salary_max: float | None
    currency: str | None
    salary_display: str | None         # raw display text: e.g. "25,000-30,000", "ตามตกลง", "Other"
    salary_is_numeric: bool            # True if salary_min/max are populated with real numbers
    work_arrangement: str | None       # "Onsite" | "Remote" | "Hybrid" | None
    experience_min_years: float | None  # e.g. 0, 2, 5
    experience_max_years: float | None  # null = no upper bound
    categories: list[str]
    skills_mentioned: list[str]
    abstract: str | None
    content: str | None                # Full HTML from get_detail
    url: str
    listed_at: str | None              # ISO 8601 UTC
    source: str                        # e.g. "jobsdb"
    raw: dict | None                   # Original API response (debug only)


class ScoreWeights(BaseModel):
    keywords_weight: float = 0.30
    skills_weight: float   = 0.25
    salary_weight: float   = 0.20
    location_weight: float = 0.15
    experience_weight: float = 0.10


class SearchCriteria(BaseModel):
    keywords: str                              # required
    industry: str | None = None
    required_skills: list[str] = []
    experience_min_years: float | None = None  # lower bound of desired experience range
    experience_max_years: float | None = None  # upper bound; null = no upper bound
    salary_min: float | None = None
    salary_max: float | None = None
    location: str | None = None
    work_arrangement: str | None = None
    company: str | None = None
    page_size: int = Field(
        default=settings.DEFAULT_PAGE_SIZE,
        le=settings.MAX_PAGE_SIZE,
    )
    source: str = "jobsdb"
    score_weights: ScoreWeights = ScoreWeights()


class ScoredJob(BaseModel):
    job: Job
    score: float        # [0.0, 1.0]
    rank: int           # 1-based, dense


class SearchResponse(BaseModel):
    jobs: list[ScoredJob]
    total: int
    source: str
    cached: bool
    search_id: str      # SHA256 cache key


class ErrorResponse(BaseModel):
    error: str          # machine code
    message: str
    retryable: bool
