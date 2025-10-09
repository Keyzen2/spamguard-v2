# ------------------------------
# Stage 1: Builder
# ------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .

# Install Python dependencies to user dir
RUN pip install --no-cache-dir --user -r requirements.txt

# ------------------------------
# Stage 2: Runtime
# ------------------------------
FROM python:3.11-slim

WORKDIR /app

# Copy installed dependencies from builder
COPY --from=builder /root/.local /root/.local

# Set PATH so installed packages are found
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY ./app ./app

# Expose port (if needed by your server, e.g. Uvicorn)
EXPOSE 8000

# Set environment variables for runtime (optional fallback values)
# You can remove these if you're using Railway env vars
# ENV SUPABASE_URL=...
# ENV SUPABASE_SERVICE_KEY=...
# ENV DATABASE_URL=...
# ENV SECRET_KEY=...

# Default command (adjust as needed for FastAPI/Uvicorn/Gunicorn/etc.)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

