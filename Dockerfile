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

# Copy startup script
COPY start.sh .

# Make startup script executable
RUN chmod +x start.sh

# Make sure scripts are usable
ENV PATH=/root/.local/bin:$PATH

# Expose port
EXPOSE 8000

# Use startup script as CMD
CMD ["./start.sh"]
