# IKUSA Compliance Scanner - app image.
# Self-contained: bundles the FastAPI service and WeasyPrint (no external
# Docker call for PDF rendering). MobSF and Ollama remain separate services
# in docker-compose.yml.

FROM python:3.11-slim

# System libraries WeasyPrint needs at runtime, plus curl for the healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    fonts-noto-color-emoji \
    curl \
 && rm -rf /var/lib/apt/lists/*

# uv: fast Python package manager + virtualenv tool.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first (better layer caching).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Application code + bundled data.
COPY src ./src
COPY data ./data
COPY scripts ./scripts

# Install the project itself into the venv.
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    SCAN_STORAGE=/var/lib/ikusa/scans

RUN mkdir -p "${SCAN_STORAGE}"

EXPOSE 9787

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=5 \
  CMD curl -fs http://localhost:9787/ || exit 1

CMD ["uvicorn", "ikusa.api:app", "--host", "0.0.0.0", "--port", "9787"]
