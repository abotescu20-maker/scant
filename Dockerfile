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
    libpango1.0-dev \
    libcairo2 \
    libcairo2-dev \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    fonts-liberation \
    fonts-dejavu-core \
    fontconfig \
    chromium \
    chromium-driver \
    && fc-cache -fv \
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
COPY template_builder.html .
COPY .chainlit/ ./.chainlit/

# Copy public assets (custom CSS, logo, etc.)
COPY public/ ./public/

# Clean up any stale Python cache that slipped through
RUN find /app -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Ensure output directory exists
RUN mkdir -p mcp-server/output

# Copy startup script
COPY startup.sh .
RUN chmod +x startup.sh

# Force UTF-8 everywhere — prevents encoding issues with Romanian text
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONIOENCODING=utf-8

# Cloud Run uses PORT env variable (default 8080)
ENV PORT=8080
ENV PYTHONPATH=/app:/app/mcp-server

# startup.sh: re-seeds demo data on fresh deploys, then starts uvicorn
CMD ["/app/startup.sh"]
# cache-bust: 1776000122
