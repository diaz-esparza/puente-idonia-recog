.PHONY: demo up check test lint format typecheck

DOCKER := $(shell command -v docker 2>/dev/null)

version:
	uv run puente version

demo:
	uv run puente demo

up:
	uv run puente serve

format:
	uv run ruff check --fix --silent --exit-zero
	uv run ruff format src tests
	uv run pyproject-fmt pyproject.toml -n || true
	uv run yamlfix docker-compose.yml

check: lint typecheck test

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run pyproject-fmt pyproject.toml --check
	@if [ -n "$(DOCKER)" ]; then \
		$(DOCKER) build --check -f Dockerfile .; \
		$(DOCKER) compose config -q; \
	else \
		echo "Skipping docker build --check (docker not available)"; \
		echo "Skipping docker compose config (docker not available)"; \
	fi
	uv run yamlfix --check docker-compose.yml

typecheck:
	uv run pyright src tests

test:
	uv run pytest tests -sv
