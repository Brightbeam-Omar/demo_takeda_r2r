# R2R Intelligence Demo. `make check` is the single pass/fail verdict.
# Each recipe line stops the chain on first failure.

SHELL := /bin/bash
SRC_DIRS := $(shell find packages services tools -type d -name src -not -path '*/node_modules/*' -not -path '*/.venv/*' 2>/dev/null)

.PHONY: help install up down logs fmt test check check-python check-frontend coverage-core leakscan integration stack-test \
        e2e e2e-headed demo-reset pipeline scenario record-agents record-video doctor

help:
	@grep -E '^[a-z0-9-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  make %-14s %s\n", $$1, $$2}'

install: ## Install Python and frontend dependencies
	uv sync
	cd frontend && npm ci

# --- stack -------------------------------------------------------------------------------------
up: ## Start the stack (needs .env: cp .env.example .env)
	@test -f .env || { echo "Missing .env. Run: cp .env.example .env"; exit 1; }
	docker compose up -d --wait

down: ## Stop the stack
	docker compose down

logs: ## Follow stack logs
	docker compose logs -f --tail=100

# --- quality -----------------------------------------------------------------------------------
fmt: ## Auto-fix and format Python code
	uv run ruff check --fix .
	uv run ruff format .

test: ## Run Python and frontend unit tests
	uv run pytest
	cd frontend && npm test -- --run

check-python:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy --strict $(SRC_DIRS)
	uv run pytest

integration: ## Run tests that need Postgres (starts the compose Postgres)
	docker compose up -d --wait postgres
	uv run pytest -m integration

# F03-FR-09: 100% branch coverage on the SLA maths and the air-gap check, independent of what else runs.
coverage-core:
	uv run pytest packages/r2r_core --cov=r2r_core.sla --cov=r2r_core.airgap --cov-branch --cov-report=term-missing --cov-fail-under=100

check-frontend:
	cd frontend && npm run lint
	cd frontend && npm run typecheck
	cd frontend && npm test -- --run

# Scans the git file set, then commit messages on unpushed commits (skipped without an upstream).
# Warns and passes when no denylist is configured, except in CI (see tools/leakscan).
leakscan:
	uv run python -m leakscan
	@if git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then \
		uv run python -m leakscan --commits '@{u}..HEAD'; \
	else \
		echo "leakscan: no upstream branch, skipping commit message scan"; \
	fi

check: check-python coverage-core check-frontend leakscan ## Lint, types, tests, leak scan: one verdict

# --- demo placeholders (implemented by the feature named in each message) --------------------
e2e: ## Demo reset, then Playwright run-of-show
	@echo "e2e: not yet implemented (F14)"

e2e-headed: ## Same as e2e, in a visible browser
	@echo "e2e-headed: not yet implemented (F14)"

demo-reset: ## Wipe state, regenerate seed data, run the pipeline once, sync
	@echo "demo-reset: not yet implemented (F13)"

pipeline: ## Trigger one pipeline run now
	@echo "pipeline: not yet implemented (F07)"

scenario: ## Apply a scripted scenario step: make scenario STEP=<id>
	@echo "scenario (STEP=$(STEP)): not yet implemented (F13)"

record-agents: ## Record LLM replays (needs ANTHROPIC_API_KEY)
	@echo "record-agents: not yet implemented (F12)"

record-video: ## Record the backup demo video
	@echo "record-video: not yet implemented (F14)"

doctor: ## Environment checks
	@echo "doctor: not yet implemented (F14)"
