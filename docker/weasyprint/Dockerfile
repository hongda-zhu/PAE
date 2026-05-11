# Slim WeasyPrint runtime: just enough to convert HTML to PDF.
# Pinning to a specific WeasyPrint version avoids surprise CSS rendering changes.
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    fonts-noto-color-emoji \
 && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir weasyprint==65.1

WORKDIR /work
ENTRYPOINT ["weasyprint"]
