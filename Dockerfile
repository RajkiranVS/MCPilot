# MCPilot — Production Dockerfile
# Multi-stage build for smaller final image

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements-linux.txt .
RUN pip install --no-cache-dir --user -r requirements-linux.txt

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Tesseract OCR — for scanned Indian hospital documents
    tesseract-ocr \
    tesseract-ocr-eng \
    # PDF processing
    libpoppler-cpp-dev \
    poppler-utils \
    # Image processing
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    # Networking
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Download spaCy model
RUN python -m spacy download en_core_web_sm

WORKDIR /app

# Copy application
COPY . .

# Create non-root user
RUN useradd -m -u 1000 mcpilot && chown -R mcpilot:mcpilot /app
USER mcpilot

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV ENVIRONMENT=production

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--timeout-keep-alive", "30"]
