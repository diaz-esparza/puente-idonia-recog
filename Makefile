.PHONY: demo up check test lint format typecheck

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

check: lint typecheck test

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests
	uv run pyproject-fmt pyproject.toml --check

typecheck:
	uv run pyright src tests

test:
	uv run pytest tests -sv
