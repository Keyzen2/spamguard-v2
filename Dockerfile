FROM python:3.11-slim

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Test imports during build
RUN python -c "from app.main import app; print('SUCCESS: app.main imports OK')" || \
    (echo "ERROR: Import failed!" && exit 1)

# Expose port (Railway usa $PORT dinámico)
EXPOSE 8000

# Start command - Railway sobreescribe esto con railway.json
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
