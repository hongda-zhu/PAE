.PHONY: install test run mobsf-up mobsf-down ollama-up ollama-down fmt weasyprint-build

install:
	uv sync --extra dev

test:
	uv run pytest -v

run:
	uv run uvicorn ikusa.api:app --reload --port 9000

mobsf-up:
	docker compose up -d mobsf

mobsf-down:
	docker compose down

ollama-up:
	docker compose up -d ollama

ollama-down:
	docker compose stop ollama

fmt:
	uv run ruff format src tests
	uv run ruff check --fix src tests

weasyprint-build:
	docker build --network=host -t ikusa-weasyprint:latest -f docker/weasyprint/Dockerfile docker/weasyprint
