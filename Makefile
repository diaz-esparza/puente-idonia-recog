.PHONY: version demo up check test lint format typecheck

DOCKER := $(shell command -v docker 2>/dev/null)
YAML_FILES := $(shell git ls-files '*.yaml' | paste -sd ' ' || true)


version:
	uv run puente version

up:
	docker compose up -d --build --remove-orphans

demo: up
	docker compose exec -it puente bash -c "uv run puente demo"

format:
	uv run ruff check --fix --silent --exit-zero
	uv run ruff format src tests
	uv run pyproject-fmt pyproject.toml -n || true
	uv run yamlfix $(YAML_FILES)

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
	uv run yamlfix --check $(YAML_FILES)

typecheck:
	uv run pyright src tests

test:
	uv run pytest tests -sv
