import copy
import hashlib
import json
import logging

import redis
import redis.exceptions
from cachetools import TTLCache

from backend.config import settings
from backend.models.job import SearchCriteria

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Backend initialisation (import time)
# ---------------------------------------------------------------------------
_redis_client: redis.Redis | None = None
_memory_cache: TTLCache = TTLCache(maxsize=256, ttl=settings.CACHE_TTL_SECONDS)

try:
    _redis_client = redis.from_url(
        settings.REDIS_URL,
        socket_connect_timeout=2,
        socket_timeout=2,
        decode_responses=True,
    )
    _redis_client.ping()
    logger.info("Cache backend: redis")
except redis.exceptions.RedisError:
    logger.warning("Cache backend: in-memory (Redis unavailable at startup)", exc_info=True)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def cache_key(criteria: SearchCriteria) -> str:
    """Deterministic cache key: search:v1:<sha256 of sorted JSON>."""
    payload = criteria.model_dump(mode="json")
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"search:v1:{digest}"


def cache_get(key: str) -> dict | None:
    if _redis_client is not None:
        try:
            value = _redis_client.get(key)
            if value is None:
                return None
            return json.loads(value)
        except redis.exceptions.RedisError:
            logger.warning("Cache read failed (Redis), falling back to memory", exc_info=True)
        except json.JSONDecodeError:
            logger.warning("Cache read failed (corrupt JSON in Redis), treating as miss")
            return None
    # memory fallback
    hit = _memory_cache.get(key)
    return copy.deepcopy(hit) if hit is not None else None


def cache_set(key: str, value: dict, ttl: int) -> None:
    if _redis_client is not None:
        try:
            _redis_client.set(key, json.dumps(value), ex=ttl)
            return
        except (redis.exceptions.RedisError, TypeError, ValueError):
            logger.warning("Cache write failed (Redis), falling back to memory", exc_info=True)
    # memory fallback
    _memory_cache[key] = copy.deepcopy(value)
