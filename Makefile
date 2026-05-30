ROOT_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
SERVICE_DIR := $(ROOT_DIR)/service
WEB_UI_DIR := $(ROOT_DIR)/web_ui

export PROTON_AI_TOOLS_FILE ?= $(ROOT_DIR)/data/tools/tools.json
export PROTON_AI_DATASET_DIR ?= $(ROOT_DIR)/data/train/routing
export PROTON_AI_ROUTER_LOG_FILE ?= $(ROOT_DIR)/data/logs/router.jsonl
export PROTON_AI_SERVICE_URL ?= http://127.0.0.1:8000

.PHONY: help run-service run-ui-backend run-web-ui run-dev

help:
	@printf "Available targets:\n"
	@printf "  make run-service     # FastAPI model service on 8000\n"
	@printf "  make run-ui-backend  # FastAPI BFF on 8100\n"
	@printf "  make run-web-ui      # Vite frontend on 8501\n"
	@printf "  make run-dev         # all three services together\n"

run-service:
	cd "$(SERVICE_DIR)" && uvicorn main:app --reload --port 8000

run-ui-backend:
	cd "$(ROOT_DIR)" && uvicorn web_backend.app:app --reload --port 8100

run-web-ui:
	cd "$(WEB_UI_DIR)" && npm run dev

run-dev:
	@set -e; \
	trap 'kill 0' INT TERM EXIT; \
	( cd "$(SERVICE_DIR)" && exec uvicorn main:app --reload --port 8000 ) & \
	( cd "$(ROOT_DIR)" && exec uvicorn web_backend.app:app --reload --port 8100 ) & \
	( cd "$(WEB_UI_DIR)" && exec npm run dev ) & \
	wait
