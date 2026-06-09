.PHONY: version demo up check test lint format typecheck

DOCKER := $(shell command -v docker 2>/dev/null)
YAML_FILES := $(shell git ls-files '*.yaml' | paste -sd ' ' || true)


version:
	uv run puente version

up:
	docker compose up -d --build --remove-orphans
	@ID=$$(docker compose ps -q grafana 2>/dev/null); \
	if [ -n "$$ID" ]; then \
		IP=$$(docker inspect $$ID --format '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}' | awk '{print $$1}'); \
		echo; \
		echo "  Grafana -> http://$$IP:3000"; \
		echo; \
	fi

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
	uv run pytest tests -v
