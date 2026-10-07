# R2R Intelligence Demo. `make check` is the single pass/fail verdict.
# Each recipe line stops the chain on first failure.

SHELL := /bin/bash
SRC_DIRS := $(shell find packages services tools -type d -name src -not -path '*/node_modules/*' -not -path '*/.venv/*' 2>/dev/null)

.PHONY: help install up down logs fmt test contract-json check check-python check-frontend coverage-core leakscan integration stack-test \
        e2e e2e-headed demo-reset seed pipeline scenario record-agents record-video doctor

help:
	@grep -E '^[a-z0-9-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  make %-14s %s\n", $$1, $$2}'

install: ## Install Python and frontend dependencies
	uv sync
	cd frontend && npm ci
	cd tests/e2e && npm ci && npx playwright install chromium

# --- stack -------------------------------------------------------------------------------------
up: ## Start the stack (needs .env: cp .env.example .env)
	@test -f .env || { echo "Missing .env. Run: cp .env.example .env"; exit 1; }
	docker compose up -d --build --wait

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

STACK_PROJECT := r2r_stacktest

# Runs on its own compose project (own network, containers and Postgres volume) and other host ports, then
# removes all of it, so the demo stack can keep running untouched.
stack-test: ## Start an isolated copy of the stack, run the acceptance tests against it, tear it down
	@test -f .env || cp .env.example .env
	@export COMPOSE_PROJECT_NAME=$(STACK_PROJECT) POSTGRES_HOST_PORT=15432 SCENARIO_HOST_PORT=18100 \
		ERP_HOST_PORT=18101 LIMS_HOST_PORT=18102 QMS_HOST_PORT=18103 AGENTS_HOST_PORT=18200 DAGSTER_HOST_PORT=13001 APP_API_HOST_PORT=18000 FRONTEND_HOST_PORT=15173 FRONTEND_WEB_HOST_PORT=18080 \
		LAKEHOUSE_HOST_DIR=$(CURDIR)/.stacktest-lakehouse; \
	trap 'docker compose -p $(STACK_PROJECT) down -v --remove-orphans' EXIT; \
	docker compose -p $(STACK_PROJECT) up -d --build --wait && uv run pytest -m stack tests/stack

# F03-FR-09: 100% branch coverage on the SLA maths and the air-gap check, independent of what else runs.
coverage-core:
	uv run pytest packages/r2r_core --cov=r2r_core.sla --cov=r2r_core.airgap --cov=r2r_core.reports --cov-branch --cov-report=term-missing --cov-fail-under=100

check-frontend:
	cd frontend && npm run lint
	cd frontend && npm run typecheck
	cd frontend && npm test -- --run
	@if [ -d tests/e2e/node_modules ]; then cd tests/e2e && npx tsc --noEmit; fi

# Scans the git file set, then commit messages on unpushed commits (skipped without an upstream).
# Warns and passes when no denylist is configured, except in CI (see tools/leakscan).
# F14-AC-04: artifacts/ is gitignored, so the git file set misses it; it is scanned explicitly when it exists
# (the legacy workbook, the e2e reports, the video's folder).
leakscan:
	uv run python -m leakscan
	@if [ -d artifacts ]; then uv run python -m leakscan artifacts; fi
	@if git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then \
		uv run python -m leakscan --commits '@{u}..HEAD'; \
	else \
		echo "leakscan: no upstream branch, skipping commit message scan"; \
	fi

# F21-FR-06: regenerate the Schema Reference's contract file (the check in `make check` fails when it is stale).
contract-json: ## Regenerate specs/contract.json from the published schemas and the specs
	uv run python tools/contract_schema.py

check: check-python coverage-core check-frontend leakscan ## Lint, types, tests, leak scan: one verdict

# --- demo placeholders (implemented by the feature named in each message) --------------------
# F14-FR-02, OQ-162: demo reset, then the run-of-show (acts 2, 3, 5, 6, which need the untouched demo-start state),
# then a second reset and every other spec. HTML reports go to artifacts/e2e/run-of-show and artifacts/e2e/specs.
# `make e2e-headed` is the same in a visible browser. Runs against the built frontend on 8080 (FRONTEND_URL overrides).
define PLAYWRIGHT
@set -a; [ ! -f .env ] || . ./.env; set +a; cd tests/e2e && \
	E2E_REPORT_DIR=../../artifacts/e2e/run-of-show npx playwright test --project=run-of-show $(1)
$(MAKE) demo-reset
@set -a; [ ! -f .env ] || . ./.env; set +a; cd tests/e2e && \
	E2E_REPORT_DIR=../../artifacts/e2e/specs npx playwright test --project=specs $(1)
endef

e2e: demo-reset ## Demo reset, then the run-of-show and the other Playwright specs against the running stack
	$(call PLAYWRIGHT,)

e2e-headed: demo-reset ## Same as e2e, in a visible browser
	$(call PLAYWRIGHT,--headed)

# F13-FR-05: clears the app tables, regenerates the source data with the profile seed, runs the pipeline and
# waits for the sync. Needs the stack up (`make up`). Takes under three minutes.
# F14-FR-08, OQ-153: a stale or empty recordings mount in the agents container would make the air-gap agent miss
# every replay key in front of an audience, so the reset recreates that container first when the mount is empty.
demo-reset: ## Wipe state, regenerate seed data, run the pipeline once, sync
	@test -f .env || { echo "Missing .env. Run: cp .env.example .env"; exit 1; }
	@seen=$$(docker compose exec -T agents sh -c 'ls /recordings/air_gap 2>/dev/null | wc -l' 2>/dev/null | tr -d ' \r'); \
		if [ "$${seen:-0}" = "0" ]; then \
			if ls services/agents/recordings/air_gap/*.json >/dev/null 2>&1; then \
				echo "demo-reset: the agents container sees no recordings (stale mount); recreating it"; \
				docker compose up -d --force-recreate --wait agents || exit 1; \
			else echo "demo-reset: WARNING no recordings in services/agents/recordings/air_gap; run make record-agents"; fi; \
		fi
	@set -a; . ./.env; set +a; \
		SCENARIO_URL=http://localhost:$${SCENARIO_HOST_PORT:-8100} uv run python -m scenario.cli reset

# Runs datagen from the host against the published Postgres port (the containers use POSTGRES_PORT=5432 on the
# compose network; the host sees POSTGRES_HOST_PORT), then runs the pipeline so the app mirror picks the data up.
seed: ## Regenerate site_a source data (profile seed) against the running stack, then run the pipeline
	@test -f .env || { echo "Missing .env. Run: cp .env.example .env"; exit 1; }
	@set -a; . ./.env; set +a; \
		POSTGRES_HOST=localhost POSTGRES_PORT=$${POSTGRES_HOST_PORT:-5432} \
		uv run python -m datagen generate --profile site_a
	$(MAKE) pipeline

# Runs the Dagster job through the scenario service and waits; a failed run fails the target (F07-FR-06).
pipeline: ## Trigger one pipeline run now and wait for it
	@test -f .env || { echo "Missing .env. Run: cp .env.example .env"; exit 1; }
	@set -a; . ./.env; set +a; \
		curl -sS --fail-with-body -X POST -H "X-Scenario-Token: $$SCENARIO_TOKEN" \
		"http://localhost:$${SCENARIO_HOST_PORT:-8100}/pipeline/run?wait=true" && echo

# F13-FR-04: prints each progress line; exits non-zero when the step is refused or fails. `make scenario STEP=list`
# shows the steps and whether their preconditions hold.
scenario: ## Apply a scripted scenario step: make scenario STEP=<id>  (STEP=list shows them)
	@test -n "$(STEP)" || { echo "usage: make scenario STEP=<id>   (make scenario STEP=list shows the steps)"; exit 1; }
	@test -f .env || { echo "Missing .env. Run: cp .env.example .env"; exit 1; }
	@set -a; . ./.env; set +a; export SCENARIO_URL=http://localhost:$${SCENARIO_HOST_PORT:-8100}; \
		if [ "$(STEP)" = "list" ]; then uv run python -m scenario.cli list; \
		else uv run python -m scenario.cli run "$(STEP)"; fi

# Runs the air-gap agent live for the four demo-start air gaps and writes the recordings the replay provider
# answers from (services/agents/recordings). Needs the stack in the demo-start state (`make demo-reset`) and ANTHROPIC_API_KEY in .env; nothing is written to the database. The key is read from the
# environment by the process and is never printed.
record-agents: ## Record LLM replays for the demo-start state (needs ANTHROPIC_API_KEY)
	@test -f .env || { echo "Missing .env. Run: cp .env.example .env"; exit 1; }
	@set -a; . ./.env; set +a; \
		test -n "$$ANTHROPIC_API_KEY" || { echo "record-agents: ANTHROPIC_API_KEY is empty in .env"; exit 1; }; \
		CLOCK_SOURCE=http SCENARIO_URL=http://localhost:$${SCENARIO_HOST_PORT:-8100} \
		APP_API_URL=http://localhost:$${APP_API_HOST_PORT:-8000} ERP_URL=http://localhost:$${ERP_HOST_PORT:-8101} \
		LIMS_URL=http://localhost:$${LIMS_HOST_PORT:-8102} QMS_URL=http://localhost:$${QMS_HOST_PORT:-8103} \
		uv run python -m agents.record

# F14-FR-07, OQ-157, OQ-164: demo reset, then the run-of-show once at presenter pace (1.5 s after each beat), 1440x900,
# no voice-over. Writes artifacts/video/run-of-show.webm, and an .mp4 next to it when ffmpeg is installed.
record-video: demo-reset ## Record the backup demo video (artifacts/video/)
	@set -a; [ ! -f .env ] || . ./.env; set +a; cd tests/e2e && \
		RECORD_VIDEO=1 PACE=presenter E2E_REPORT_DIR=../../artifacts/e2e/video npx playwright test --project=run-of-show
	@if command -v ffmpeg >/dev/null 2>&1; then \
		ffmpeg -y -loglevel error -i artifacts/video/run-of-show.webm -c:v libx264 -pix_fmt yuv420p artifacts/video/run-of-show.mp4 \
		&& echo "record-video: wrote artifacts/video/run-of-show.mp4"; \
	else echo "record-video: ffmpeg not installed, so no .mp4 (brew install ffmpeg)"; fi
	@cd tests/e2e && node video-size.mjs ../../artifacts/video/run-of-show.webm

# F14-FR-05: `make doctor` before `make up` checks the machine (Docker, memory, ports, .env, denylist); after it,
# the stack too (health, the recordings mount, replay keys). `make doctor EXPECT_UP=1` fails when it is not running.
doctor: ## Environment checks, each with its fix
	@uv run python -m doctor $(if $(EXPECT_UP),--expect-up)
