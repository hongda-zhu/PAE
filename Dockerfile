# Base image python 3.11 slim
FROM python:3.11-slim

# Install system libraries needed by WeasyPrint directly inside the container
# This allows generating PDFs without needing Docker-in-Docker or mounting the docker socket
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    fonts-noto-color-emoji \
 && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PORT=9787 \
    SCAN_STORAGE=/app/data/scans

WORKDIR /app

# Install uv for fast dependency resolution and install the project
RUN pip install --no-cache-dir uv

# Copy dependencies manifest
COPY pyproject.toml uv.lock ./

# Install project dependencies
RUN uv pip install --system --no-cache -r pyproject.toml

# Copy source code
COPY src/ ./src/
COPY data/ ./data/

# Install the project packages
RUN uv pip install --system --no-cache -e .

EXPOSE 9787

# Command to run the FastAPI application
CMD ["uvicorn", "ikusa.api:app", "--host", "0.0.0.0", "--port", "9787"]
