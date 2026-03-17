FROM python:3.12-slim

WORKDIR /app

# Dependente sistem pentru Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run seteaza PORT automat (default 8080)
ENV PORT=8080
EXPOSE 8080

# 1 worker - Cloud Run scaleza orizontal, nu vertical
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--timeout-keep-alive", "300"]
