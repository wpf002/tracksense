VENV    := .venv/bin
UVICORN := $(VENV)/uvicorn
NPM     := npm --prefix frontend

.PHONY: dev backend frontend install

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