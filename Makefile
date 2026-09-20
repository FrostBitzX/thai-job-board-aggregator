PYTHON  = .venv/Scripts/python
PYTEST  = $(PYTHON) -m pytest
UVICORN = $(PYTHON) -m uvicorn

# --- Setup ------------------------------------------------------------------

.PHONY: install
install:  ## install dependencies + playwright chromium
	uv sync
	$(PYTHON) -m playwright install chromium --with-deps

# --- Tests ------------------------------------------------------------------

.PHONY: test-backend
test-backend:  ## run all backend tests
	$(PYTEST) backend/tests/ -v

.PHONY: test-frontend
test-frontend:  ## run all frontend tests (vitest)
	cd frontend && pnpm run test -- --run

.PHONY: test-scraper
test-scraper:  ## run scraper tests only
	$(PYTEST) backend/tests/test_scraper_unit.py -v

.PHONY: test-cache
test-cache:  ## run cache tests only
	$(PYTEST) backend/tests/test_cache.py -v

.PHONY: test-scoring
test-scoring:  ## run scoring tests only
	$(PYTEST) backend/tests/test_scoring.py -v

.PHONY: test-exporters
test-exporters:  ## run exporter tests only
	$(PYTEST) backend/tests/test_exporters.py -v

.PHONY: test-api
test-api:  ## run API integration tests only
	$(PYTEST) backend/tests/test_api_integration.py -v

# --- Dev --------------------------------------------------------------------

.PHONY: dev
dev:  ## start backend dev server -- run in a separate terminal
	$(UVICORN) backend.main:app --reload

# --- Help -------------------------------------------------------------------

.PHONY: help
help:  ## show all targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
