#!/bin/bash
set -e

# Obtener el puerto de Railway o usar 8000 por defecto
PORT=${PORT:-8000}

echo "🚀 Starting uvicorn on port $PORT"

# Ejecutar uvicorn
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --workers 2
