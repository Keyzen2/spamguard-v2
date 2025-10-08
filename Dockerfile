# Multi-stage build for production

# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /root/.local /root/.local

# Copy application code
COPY ./app ./app

# Make sure scripts are usable
ENV PATH=/root/.local/bin:$PATH

# Expose port
EXPOSE 8000

# CRITICAL: Use shell form to allow variable expansion
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2
