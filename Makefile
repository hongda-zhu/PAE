.PHONY: install test run mcp-stdio seed-keys mobsf-up mobsf-down ollama-up ollama-down fmt weasyprint-build demo demo-down

# One-command demo: build the app image, bring up all services, pre-pull the
# LLM model, print the URL. Safe to re-run (idempotent).
demo:
	@if [ ! -f .env ]; then cp .env.demo .env; echo "Created .env from .env.demo"; fi
	docker compose up -d --build
	@echo "Waiting for Ollama to be ready, then pulling qwen2.5:7b (first time ~5 GB)..."
	@for i in $$(seq 1 30); do docker compose exec -T ollama ollama list >/dev/null 2>&1 && break; sleep 2; done
	docker compose exec -T ollama ollama pull qwen2.5:7b
	@echo
	@echo "IKUSA ready: http://localhost:9787"
	@echo "  Docs:    http://localhost:9787  (click 'Documentacion')"
	@echo "  Stop:    make demo-down"

demo-down:
	docker compose down

install:
	uv sync --extra dev

test:
	uv run pytest -v

run:
	uv run uvicorn ikusa.api:app --reload --port 9787

mcp-stdio:
	uv run ikusa-mcp

seed-keys:
	uv run python scripts/seed_demo_keys.py

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
