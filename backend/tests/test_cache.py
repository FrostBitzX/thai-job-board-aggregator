"""Tests for backend/services/cache.py"""

import pytest


def _make_criteria(**overrides):
    from backend.models.job import SearchCriteria
    defaults = {"keywords": "python developer", "location": "Bangkok"}
    defaults.update(overrides)
    return SearchCriteria(**defaults)


class TestCacheKey:
    def test_same_criteria_same_key(self):
        from backend.services.cache import cache_key
        c = _make_criteria()
        assert cache_key(c) == cache_key(c)

    def test_equal_criteria_same_key(self):
        from backend.services.cache import cache_key
        c1 = _make_criteria(keywords="data engineer", salary_min=50000.0)
        c2 = _make_criteria(keywords="data engineer", salary_min=50000.0)
        assert cache_key(c1) == cache_key(c2)

    def test_different_keywords_different_key(self):
        from backend.services.cache import cache_key
        c1 = _make_criteria(keywords="python")
        c2 = _make_criteria(keywords="java")
        assert cache_key(c1) != cache_key(c2)

    def test_key_has_expected_prefix(self):
        from backend.services.cache import cache_key
        k = cache_key(_make_criteria())
        assert k.startswith("search:v1:")

    def test_key_is_deterministic_across_calls(self):
        from backend.services.cache import cache_key
        c = _make_criteria(keywords="vue developer", page_size=200)
        keys = {cache_key(c) for _ in range(10)}
        assert len(keys) == 1


class TestMemoryCacheRoundtrip:
    def setup_method(self):
        import backend.services.cache as cm
        self._module = cm
        self._orig_redis = cm._redis_client
        cm._redis_client = None
        cm._memory_cache.clear()

    def teardown_method(self):
        self._module._redis_client = self._orig_redis
        self._module._memory_cache.clear()

    def test_miss_returns_none(self):
        from backend.services.cache import cache_get
        assert cache_get("nonexistent-key-xyz") is None

    def test_set_then_get_returns_value(self):
        from backend.services.cache import cache_get, cache_set
        data = {"jobs": [{"id": "1", "title": "Dev"}], "total": 1}
        cache_set("test-key", data, ttl=60)
        result = cache_get("test-key")
        assert result == data

    def test_get_returns_copy_not_reference(self):
        from backend.services.cache import cache_get, cache_set
        data = {"value": [1, 2, 3]}
        cache_set("copy-key", data, ttl=60)
        result = cache_get("copy-key")
        result["value"].append(99)
        assert cache_get("copy-key") == {"value": [1, 2, 3]}

    def test_overwrite_replaces_value(self):
        from backend.services.cache import cache_get, cache_set
        cache_set("ow-key", {"v": 1}, ttl=60)
        cache_set("ow-key", {"v": 2}, ttl=60)
        assert cache_get("ow-key") == {"v": 2}

    def test_different_keys_independent(self):
        from backend.services.cache import cache_get, cache_set
        cache_set("k1", {"a": 1}, ttl=60)
        cache_set("k2", {"b": 2}, ttl=60)
        assert cache_get("k1") == {"a": 1}
        assert cache_get("k2") == {"b": 2}
