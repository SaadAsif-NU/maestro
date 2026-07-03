.PHONY: help dev test cov lint typecheck fmt serve clean
help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'
dev:  ## Install with dev dependencies
	pip install -e ".[dev]"
test:  ## Run the test suite
	pytest
cov:  ## Tests with coverage
	pytest --cov=maestro --cov-report=term-missing --cov-report=xml
lint:  ## Lint with ruff
	ruff check maestro tests
typecheck:  ## Type-check with mypy
	mypy
fmt:  ## Auto-format
	ruff check --fix maestro tests && ruff format maestro tests
serve:  ## Run the studio (http://localhost:8000)
	uvicorn maestro.server.app:app --host 0.0.0.0 --port 8000
clean:  ## Remove caches
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage coverage.xml
	find . -type d -name __pycache__ -exec rm -rf {} +
