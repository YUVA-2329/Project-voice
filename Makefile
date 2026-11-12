# PROJECT VOICE — developer entry points. `make help` lists them.
# Everything here is a thin wrapper; the real commands are documented in docs/LOCAL_DEVELOPMENT.md.

SHELL := /bin/bash
.DEFAULT_GOAL := help

VENV        ?= .venv
PY          := $(abspath $(VENV))/bin/python
PIP         := $(abspath $(VENV))/bin/pip
BACKEND     := backend
COMPOSE     ?= docker compose
COMPOSE_PROD:= $(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml
MODELS_DIR  ?= $(abspath models)
API_PORT    ?= 8000

# Environment every local backend process needs (overridable: make api PV_LOG_JSON=true).
export PV_ENV              ?= development
export PV_MODELS_DIR       ?= $(MODELS_DIR)
export PV_STORAGE_LOCAL_DIR?= $(abspath storage)
export PV_TMP_DIR          ?= $(abspath tmp)
export PV_LOG_JSON         ?= false

.PHONY: help venv dev-up dev-down dev-logs migrate api worker frontend start stop \
        test test-unit test-model e2e e2e-ws e2e-browser lint fmt typecheck backup restore \
        download-models logs prod-up prod-down build psql

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# ----------------------------------------------------------------------------- local (no Docker)
venv: ## Create .venv and install the backend with dev + engine extras
	test -d $(VENV) || python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	cd $(BACKEND) && $(PIP) install -e ".[dev,engine]"

migrate: ## Apply database migrations (alembic upgrade head)
	cd $(BACKEND) && $(PY) -m alembic upgrade head

api: ## Run the API with reload on :$(API_PORT)
	cd $(BACKEND) && $(PY) -m uvicorn app.main:app --reload --port $(API_PORT)

worker: ## Run the RQ worker (queues voice,generation)
	cd $(BACKEND) && $(PY) -m app.jobs.worker

frontend: ## Run the Next.js dev server on :3000 (proxies /api to the local API)
	cd frontend && API_INTERNAL_URL=http://localhost:$(API_PORT) pnpm dev

start: ## Start postgres/redis if down, migrate, launch api + worker + frontend in the background (.run/)
	scripts/start-local.sh

stop: ## Stop the processes started by `make start`
	scripts/stop-local.sh

download-models: ## Download ZipVoice, Whisper and Silero weights into $(MODELS_DIR)
	$(PY) scripts/download-models.py --models-dir $(MODELS_DIR)

# ----------------------------------------------------------------------------- quality
test: ## Backend test suite (unit + integration + engine + audio; model tests skip without weights)
	cd $(BACKEND) && $(PY) -m pytest -q

test-unit: ## Fast tests only (no model inference)
	cd $(BACKEND) && $(PY) -m pytest -q -m "not model"

test-model: ## Real-inference tests (ZipVoice / Whisper / VAD; needs weights, ~2-3 min on CPU)
	cd $(BACKEND) && $(PY) -m pytest -q tests/model -m model

e2e: ## Full HTTP workflow against the running stack (scripts/e2e_api.py → evidence/)
	$(PY) scripts/e2e_api.py --base http://localhost:$(API_PORT) --skip-restart

e2e-ws: ## Conversation WebSocket turn against the running stack (scripts/e2e_ws.py → evidence/)
	$(PY) scripts/e2e_ws.py --base http://localhost:$(API_PORT)

e2e-browser: ## 22-step acceptance workflow in Chromium with a fake microphone (needs frontend on :3000)
	node scripts/e2e_browser.mjs --base http://localhost:3000

lint: ## ruff check + ruff format --check + frontend eslint (when installed)
	cd $(BACKEND) && $(PY) -m ruff check app tests alembic
	cd $(BACKEND) && $(PY) -m ruff format --check app tests
	@if [ -d frontend/node_modules ]; then cd frontend && pnpm lint; else echo "frontend deps not installed; skipping eslint"; fi

fmt: ## ruff format + ruff --fix
	cd $(BACKEND) && $(PY) -m ruff format app tests && $(PY) -m ruff check --fix app tests

typecheck: ## mypy (backend) + tsc (frontend when installed)
	cd $(BACKEND) && $(PY) -m mypy app --ignore-missing-imports
	@if [ -d frontend/node_modules ]; then cd frontend && pnpm typecheck; fi

# ----------------------------------------------------------------------------- docker
dev-up: ## docker compose up (dev stack: postgres, redis, api, worker, frontend, caddy on :80)
	$(COMPOSE) up -d --build

dev-down: ## docker compose down (volumes kept; add -v manually to wipe data)
	$(COMPOSE) down

build: ## Build all images without starting
	$(COMPOSE) build

logs: ## Follow logs of the compose stack (SERVICE=api to filter)
	$(COMPOSE) logs -f --tail=200 $(SERVICE)

prod-up: ## Production stack (docker-compose.prod.yml); add PROFILES="--profile s3" for MinIO
	$(COMPOSE_PROD) $(PROFILES) up -d --build

prod-down: ## Stop the production stack
	$(COMPOSE_PROD) down

psql: ## psql into the compose Postgres
	$(COMPOSE) exec postgres psql -U $${POSTGRES_USER:-projectvoice} -d $${POSTGRES_DB:-projectvoice}

# ----------------------------------------------------------------------------- data
backup: ## pg_dump + storage tarball → backups/<timestamp> (RETENTION=7)
	infra/scripts/backup.sh

restore: ## Restore SNAPSHOT=backups/<timestamp> (destructive; requires --yes which this target passes)
	@test -n "$(SNAPSHOT)" || (echo "usage: make restore SNAPSHOT=backups/<timestamp>"; exit 1)
	infra/scripts/restore.sh $(SNAPSHOT) --yes --verify
