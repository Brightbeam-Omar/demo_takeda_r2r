# R2R Intelligence Demo. `make check` is the single pass/fail verdict.
# Each recipe line stops the chain on first failure.

SHELL := /bin/bash
SRC_DIRS := $(shell find packages services tools -type d -name src -not -path '*/node_modules/*' -not -path '*/.venv/*' 2>/dev/null)

.PHONY: fmt check check-python

fmt:
	uv run ruff check --fix .
	uv run ruff format .

check-python:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy --strict $(SRC_DIRS)
	uv run pytest

check: check-python
