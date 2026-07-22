.PHONY: help install install-dev test test-watch lint run docker compose clean

# TCP ingress listener is disabled during tests.
export LISTEN_PORT ?= 5050

help:                       ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:                    ## Install runtime dependencies
	pip install -r requirements.txt

install-dev:               ## Install runtime + test dependencies
	pip install -r requirements-dev.txt

test:                       ## Run the full test suite
	LISTEN_PORT=0 pytest

test-watch:                 ## Re-run tests on file changes (needs: pip install pytest-watch)
	LISTEN_PORT=0 ptw

lint:                       ## Byte-compile check (fail fast on syntax errors)
	python -m compileall -q app

run:                        ## Run the app locally on :8000
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker:                     ## Build the Docker image
	docker build -t iot-simulator:latest .

compose:                    ## Run via docker-compose
	docker compose up --build

clean:                      ## Remove caches
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache
