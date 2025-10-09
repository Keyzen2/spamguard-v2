# Multi-stage build for production
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
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

# ✅ Copy ALL application code (including docs/)
COPY . .

# Make sure scripts are usable
ENV PATH=/root/.local/bin:$PATH

# Expose port
EXPOSE 8000

# Default command (Railway overrides this)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
