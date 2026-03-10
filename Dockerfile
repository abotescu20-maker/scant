# Insurance Broker AI — Docker image for GCP Cloud Run
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies:
#   - weasyprint needs pango/cairo/fonts
#   - chromium-driver needs a full set of libs
#   - We install Chromium from Debian repos (more reliable than playwright install on slim)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    fonts-liberation \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tell Playwright to use the system Chromium instead of downloading its own
# This avoids the 300MB download and uses the already-installed binary
ENV PLAYWRIGHT_BROWSERS_PATH=/usr/bin
ENV PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium

# Copy MCP server (tools + DB)
COPY mcp-server/ ./mcp-server/

# Copy admin panel + shared modules
COPY admin/ ./admin/
COPY shared/ ./shared/

# Copy scripts
COPY scripts/ ./scripts/

# Copy Chainlit app and config
COPY app.py .
COPY main.py .
COPY cu_state.py .
COPY chainlit.md .
COPY CLAUDE.md .
COPY .chainlit/ ./.chainlit/

# Ensure output directory exists
RUN mkdir -p mcp-server/output

# Cloud Run uses PORT env variable (default 8080)
ENV PORT=8080
ENV PYTHONPATH=/app:/app/mcp-server

# Run via uvicorn main:app — FastAPI handles /cu/* + /admin/* routes,
# then mounts Chainlit at /. This allows custom REST endpoints to work.
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT}
