# R2R Intelligence Demo. `make check` is the single pass/fail verdict.
# Each recipe line stops the chain on first failure.

SHELL := /bin/bash
SRC_DIRS := $(shell find packages services tools -type d -name src -not -path '*/node_modules/*' -not -path '*/.venv/*' 2>/dev/null)

.PHONY: install fmt check check-python check-frontend leakscan

install:
	uv sync
	cd frontend && npm ci

fmt:
	uv run ruff check --fix .
	uv run ruff format .

check-python:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy --strict $(SRC_DIRS)
	uv run pytest

check-frontend:
	cd frontend && npm run lint
	cd frontend && npm run typecheck
	cd frontend && npm test -- --run

# No-op until F02 (leak scanner) lands.
leakscan:
	@echo "leakscan: not yet implemented (F02)"

check: check-python check-frontend leakscan
