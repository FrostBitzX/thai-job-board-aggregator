from pydantic_settings import BaseSettings, SettingsConfigDict

# --- Default values (fallback when not set in .env) ---
_REDIS_URL             = "redis://localhost:6379"
_CACHE_TTL_SECONDS     = 7200
_DEFAULT_PAGE_SIZE     = 100
_MAX_PAGE_SIZE         = 500
_MAX_RETRIES           = 3
_RETRY_BASE_DELAY      = 1.0
_DETAIL_BATCH_SIZE     = 10
_BACKEND_CORS_ORIGINS  = ["http://localhost:5173"]
# ------------------------------------------------------


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    REDIS_URL:             str       = _REDIS_URL
    CACHE_TTL_SECONDS:     int       = _CACHE_TTL_SECONDS
    DEFAULT_PAGE_SIZE:     int       = _DEFAULT_PAGE_SIZE
    MAX_PAGE_SIZE:         int       = _MAX_PAGE_SIZE
    MAX_RETRIES:           int       = _MAX_RETRIES
    RETRY_BASE_DELAY:      float     = _RETRY_BASE_DELAY
    DETAIL_BATCH_SIZE:     int       = _DETAIL_BATCH_SIZE
    BACKEND_CORS_ORIGINS:  list[str] = _BACKEND_CORS_ORIGINS


settings = Settings()
