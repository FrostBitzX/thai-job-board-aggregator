"""Tests for backend/services/scoring.py"""

import pytest
from backend.models.job import Job, SearchCriteria, ScoreWeights, ScoredJob
from backend.services.scoring import (
    score_job,
    score_and_rank,
    _range_overlap_score,
    _keywords_score,
    _skills_score,
    _salary_score,
    _location_score,
    _experience_score,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# _range_overlap_score
# ---------------------------------------------------------------------------

class TestRangeOverlapScore:
    def test_no_overlap_returns_zero(self):
        assert _range_overlap_score(10, 20, 30, 40) == 0.0

    def test_single_endpoint_shared_returns_half(self):
        assert _range_overlap_score(10, 20, 20, 30) == 0.5
        assert _range_overlap_score(20, 30, 10, 20) == 0.5

    def test_partial_overlap_returns_half(self):
        assert _range_overlap_score(10, 25, 20, 40) == 0.5

    def test_full_containment_job_in_crit_returns_one(self):
        assert _range_overlap_score(25, 35, 20, 40) == 1.0

    def test_full_containment_crit_in_job_returns_one(self):
        assert _range_overlap_score(20, 40, 25, 35) == 1.0

    def test_identical_ranges_returns_one(self):
        assert _range_overlap_score(20, 30, 20, 30) == 1.0

    def test_open_ended_job_max_none(self):
        # job: [30, ∞), crit: [40, 50] — crit fully contained in job
        assert _range_overlap_score(30, None, 40, 50) == 1.0

    def test_open_ended_crit_max_none(self):
        # job: [30, 50], crit: [40, ∞) — partial overlap
        assert _range_overlap_score(30, 50, 40, None) == 0.5

    def test_both_open_ended_returns_one(self):
        # job: [0, ∞), crit: [0, ∞) — identical infinite ranges
        assert _range_overlap_score(0, None, 0, None) == 1.0


# ---------------------------------------------------------------------------
# _keywords_score
# ---------------------------------------------------------------------------

class TestKeywordsScore:
    def test_all_keywords_present_returns_one(self):
        j = _job(title="python developer", abstract="loves django")
        assert _keywords_score(j, "python django") == 1.0

    def test_no_keywords_match_returns_zero(self):
        j = _job(title="accountant")
        assert _keywords_score(j, "python") == 0.0

    def test_partial_match_returns_fraction(self):
        j = _job(title="python developer")
        assert _keywords_score(j, "python java") == 0.5

    def test_case_insensitive(self):
        j = _job(title="Python Developer")
        assert _keywords_score(j, "python") == 1.0

    def test_empty_keywords_returns_one(self):
        j = _job(title="anything")
        assert _keywords_score(j, "") == 1.0

    def test_searches_abstract_and_content(self):
        j = _job(title="developer", abstract="uses python", content="<p>loves django</p>")
        assert _keywords_score(j, "python django") == 1.0

    def test_keyword_counted_once_even_if_repeated(self):
        j = _job(title="python python python")
        # 1 keyword "python" → 1 hit / 1 total = 1.0
        assert _keywords_score(j, "python") == 1.0


# ---------------------------------------------------------------------------
# _skills_score (Jaccard)
# ---------------------------------------------------------------------------

class TestSkillsScore:
    def test_empty_required_returns_one(self):
        assert _skills_score([], ["python"]) == 1.0

    def test_perfect_match_returns_one(self):
        assert _skills_score(["python", "sql"], ["python", "sql"]) == 1.0

    def test_no_match_returns_zero(self):
        assert _skills_score(["python"], ["java"]) == pytest.approx(0.0)

    def test_partial_match_jaccard(self):
        # intersection={python}, union={python,java,sql} → 1/3
        result = _skills_score(["python", "java"], ["python", "sql"])
        assert result == pytest.approx(1 / 3)

    def test_case_insensitive(self):
        assert _skills_score(["Python"], ["python"]) == 1.0

    def test_symmetric(self):
        r = _skills_score(["python", "sql"], ["java", "python"])
        s = _skills_score(["java", "python"], ["python", "sql"])
        assert r == pytest.approx(s)


# ---------------------------------------------------------------------------
# _salary_score
# ---------------------------------------------------------------------------

class TestSalaryScore:
    def test_no_criteria_returns_one(self):
        j = _job(salary_min=30000, salary_max=50000, salary_is_numeric=True)
        assert _salary_score(j, None, None) == 1.0

    def test_job_no_salary_returns_one(self):
        j = _job(salary_is_numeric=False)
        assert _salary_score(j, 30000, 50000) == 1.0

    def test_no_overlap_returns_zero(self):
        j = _job(salary_min=20000, salary_max=25000, salary_is_numeric=True)
        assert _salary_score(j, 30000, 40000) == 0.0

    def test_full_overlap_returns_one(self):
        j = _job(salary_min=25000, salary_max=45000, salary_is_numeric=True)
        assert _salary_score(j, 20000, 50000) == 1.0

    def test_partial_overlap_returns_half(self):
        j = _job(salary_min=20000, salary_max=35000, salary_is_numeric=True)
        assert _salary_score(j, 30000, 50000) == 0.5


# ---------------------------------------------------------------------------
# _location_score
# ---------------------------------------------------------------------------

class TestLocationScore:
    def test_no_criteria_returns_one(self):
        assert _location_score("Bangkok", None) == 1.0

    def test_exact_match_returns_one(self):
        assert _location_score("Bangkok", "Bangkok") == 1.0

    def test_case_insensitive_exact(self):
        assert _location_score("bangkok", "Bangkok") == 1.0

    def test_substring_criteria_in_job_returns_half(self):
        assert _location_score("Bangkok, Thailand", "Bangkok") == 0.5

    def test_substring_job_in_criteria_returns_half(self):
        assert _location_score("Bangkok", "Bangkok, Thailand") == 0.5

    def test_no_match_returns_zero(self):
        assert _location_score("Chiang Mai", "Bangkok") == 0.0

    def test_job_location_none_returns_zero(self):
        assert _location_score(None, "Bangkok") == 0.0


# ---------------------------------------------------------------------------
# _experience_score
# ---------------------------------------------------------------------------

class TestExperienceScore:
    def test_no_criteria_returns_one(self):
        j = _job(experience_min_years=2, experience_max_years=5)
        assert _experience_score(j, None, None) == 1.0

    def test_job_no_experience_returns_one(self):
        j = _job()
        assert _experience_score(j, 2, 5) == 1.0

    def test_full_overlap_returns_one(self):
        j = _job(experience_min_years=2, experience_max_years=4)
        assert _experience_score(j, 1, 5) == 1.0

    def test_no_overlap_returns_zero(self):
        j = _job(experience_min_years=5, experience_max_years=10)
        assert _experience_score(j, 0, 2) == 0.0

    def test_partial_overlap_returns_half(self):
        j = _job(experience_min_years=3, experience_max_years=7)
        assert _experience_score(j, 5, 10) == 0.5


# ---------------------------------------------------------------------------
# score_job — composite
# ---------------------------------------------------------------------------

class TestScoreJob:
    def test_all_unspecified_optional_full_keyword_match_returns_one(self):
        j = _job(title="python developer")
        c = _criteria(keywords="python")
        assert score_job(j, c) == pytest.approx(1.0)

    def test_score_in_bounds(self):
        j = _job(title="accountant", salary_min=10000, salary_max=20000, salary_is_numeric=True)
        c = _criteria(keywords="python", salary_min=50000, salary_max=80000)
        s = score_job(j, c)
        assert 0.0 <= s <= 1.0

    def test_zero_keyword_weight_still_scores(self):
        j = _job(title="python")
        c = _criteria(
            keywords="java",
            score_weights=ScoreWeights(keywords_weight=0.0, skills_weight=1.0,
                                       salary_weight=0.0, location_weight=0.0,
                                       experience_weight=0.0),
        )
        # Only skills weight matters; no required skills → skills score 1.0
        assert score_job(j, c) == pytest.approx(1.0)

    def test_weights_renormalised_proportional_same_result(self):
        j = _job(title="python developer", location="Bangkok",
                 salary_min=30000, salary_max=50000, salary_is_numeric=True)
        c1 = _criteria(keywords="python", location="Bangkok",
                       score_weights=ScoreWeights(keywords_weight=0.30, skills_weight=0.25,
                                                   salary_weight=0.20, location_weight=0.15,
                                                   experience_weight=0.10))
        c2 = _criteria(keywords="python", location="Bangkok",
                       score_weights=ScoreWeights(keywords_weight=3.0, skills_weight=2.5,
                                                   salary_weight=2.0, location_weight=1.5,
                                                   experience_weight=1.0))
        assert score_job(j, c1) == pytest.approx(score_job(j, c2))

    def test_null_salary_no_penalty(self):
        j = _job(title="python developer", salary_is_numeric=False)
        c = _criteria(keywords="python", salary_min=30000, salary_max=50000)
        # Null salary → salary criterion 1.0 → no penalty
        assert score_job(j, c) == pytest.approx(1.0)

    def test_null_experience_no_penalty(self):
        j = _job(title="python developer")  # experience_min/max both None
        c = _criteria(keywords="python", experience_min_years=3, experience_max_years=5)
        assert score_job(j, c) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# score_and_rank
# ---------------------------------------------------------------------------

class TestScoreAndRank:
    def test_empty_list(self):
        assert score_and_rank([], _criteria()) == []

    def test_single_job_rank_one(self):
        result = score_and_rank([_job(id="a", title="python")], _criteria(keywords="python"))
        assert result[0].rank == 1

    def test_descending_order(self):
        jobs = [
            _job(id="a", title="accountant"),     # low score
            _job(id="b", title="python developer"),  # high score
        ]
        result = score_and_rank(jobs, _criteria(keywords="python"))
        assert result[0].job.id == "b"
        assert result[0].score >= result[1].score

    def test_tied_scores_same_rank(self):
        jobs = [
            _job(id="a", title="python developer"),
            _job(id="b", title="python developer"),
        ]
        result = score_and_rank(jobs, _criteria(keywords="python"))
        assert result[0].rank == result[1].rank == 1

    def test_dense_ranking_no_gaps(self):
        # 3 distinct score levels among 4 jobs
        jobs = [
            _job(id="a", title="python developer", skills_mentioned=["python"]),
            _job(id="b", title="python developer", skills_mentioned=["python"]),  # tie with a
            _job(id="c", title="python developer"),   # lower than a/b
            _job(id="d", title="accountant"),          # lowest
        ]
        c = _criteria(keywords="python", required_skills=["python"])
        result = score_and_rank(jobs, c)
        ranks = sorted({sj.rank for sj in result})
        # Dense: ranks must be 1..N where N = number of distinct score levels
        assert ranks == list(range(1, len(ranks) + 1))

    def test_ranks_reflect_score_order(self):
        jobs = [_job(id=str(i), title="python developer" if i < 2 else "accountant")
                for i in range(4)]
        result = score_and_rank(jobs, _criteria(keywords="python"))
        for i in range(len(result) - 1):
            assert result[i].score >= result[i + 1].score
            assert result[i].rank <= result[i + 1].rank
