VENV    := .venv/bin
UVICORN := $(VENV)/uvicorn
NPM     := npm --prefix frontend

# Local dev uses SQLite so no Postgres setup is required.
# Tables are auto-created on startup (TRACKSENSE_INIT_DB=1).
export DATABASE_URL       ?= sqlite:///./tracksense.db
export TRACKSENSE_INIT_DB ?= 1

.PHONY: dev backend frontend install seed

## Run backend + frontend together (Ctrl-C stops both)
dev:
	@trap 'kill 0' SIGINT; \
	$(UVICORN) app.server:app --reload --port 8001 & \
	$(NPM) run dev & \
	wait

## Run backend only
backend:
	$(UVICORN) app.server:app --reload --port 8001

## Run frontend only
frontend:
	$(NPM) run dev

## Install all dependencies
install:
	$(VENV)/pip install -r requirements.txt
	$(NPM) install

## Seed the database (skips if already seeded; use seed-force to wipe)
seed:
	$(VENV)/python -m scripts.seed

seed-force:
	$(VENV)/python -m scripts.seed --force