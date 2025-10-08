"""
Dependencias de autenticación y seguridad
"""
from fastapi import Header, HTTPException, Request, status
from typing import Optional
from datetime import datetime, timedelta
import hmac
import hashlib

from app.database import Database
from app.utils import rate_limiter
from app.config import get_settings

# Cache simple para rate limiting y locks
_rate_limit_cache = {}
_retrain_lock = {"is_running": False, "started_at": None}

def verify_api_key(x_api_key: str = Header(...)) -> str:
    """
    Valida la API key y retorna el site_id (para endpoints normales)
    """
    if not x_api_key or not x_api_key.startswith('sg_'):
        raise HTTPException(
            status_code=401,
            detail="API key inválida o faltante"
        )
    
    site_id = Database.validate_api_key(x_api_key)
    
    if not site_id:
        raise HTTPException(
            status_code=403,
            detail="API key no autorizada"
        )
    
    return site_id


def verify_admin_api_key(x_admin_key: str = Header(..., alias="X-Admin-Key")) -> str:
    """
    Verificar API key de ADMINISTRADOR (para endpoints sensibles como reentrenamiento)
    
    Esta key debe ser diferente a las API keys normales y solo tú debes conocerla.
    Se configura en variables de entorno de Railway.
    """
    settings = get_settings()
    expected_admin_key = settings.admin_api_key
    
    if not expected_admin_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin functionality not configured. Set ADMIN_API_KEY in environment."
        )
    
    # Comparación segura (previene timing attacks)
    if not compare_digest_safe(x_admin_key, expected_admin_key):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin credentials"
        )
    
    return x_admin_key


def compare_digest_safe(a: str, b: str) -> bool:
    """
    Comparación segura de strings (previene timing attacks)
    """
    try:
        return hmac.compare_digest(a.encode(), b.encode())
    except:
        return False


def check_rate_limit(request: Request, x_api_key: str = Header(...)):
    """
    Verifica rate limiting por API key (para endpoints normales)
    """
    client_ip = request.client.host if request.client else "unknown"
    identifier = f"{x_api_key}:{client_ip}"
    
    if not rate_limiter.is_allowed(identifier, max_requests=1000, window_seconds=3600):
        remaining = rate_limiter.get_remaining(identifier, max_requests=1000)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit excedido. Requests restantes: {remaining}",
            headers={"Retry-After": "3600"}
        )
    
    return True


def check_admin_rate_limit(identifier: str, max_requests: int = 1, window_minutes: int = 60):
    """
    Rate limiting estricto para endpoints de admin
    
    Args:
        identifier: Identificador único (e.g., admin_key)
        max_requests: Máximo de requests permitidos
        window_minutes: Ventana de tiempo en minutos
    """
    now = datetime.utcnow()
    
    # Limpiar entradas antiguas
    expired_keys = [
        key for key, data in _rate_limit_cache.items()
        if now - data["first_request"] > timedelta(minutes=window_minutes)
    ]
    for key in expired_keys:
        del _rate_limit_cache[key]
    
    # Verificar límite
    if identifier in _rate_limit_cache:
        data = _rate_limit_cache[identifier]
        
        if data["count"] >= max_requests:
            time_left = window_minutes - (now - data["first_request"]).seconds // 60
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {time_left} minutes."
            )
        
        data["count"] += 1
    else:
        _rate_limit_cache[identifier] = {
            "first_request": now,
            "count": 1
        }


def acquire_retrain_lock() -> bool:
    """
    Intentar adquirir el lock de reentrenamiento.
    Solo un reentrenamiento puede ejecutarse a la vez.
    
    Returns:
        True si se adquirió el lock, False si ya está en ejecución
    """
    if _retrain_lock["is_running"]:
        # Verificar si lleva más de 30 minutos (posible fallo)
        if _retrain_lock["started_at"]:
            elapsed = (datetime.utcnow() - _retrain_lock["started_at"]).seconds
            if elapsed > 1800:  # 30 minutos
                # Liberar lock automáticamente (timeout)
                release_retrain_lock()
            else:
                return False
        else:
            return False
    
    _retrain_lock["is_running"] = True
    _retrain_lock["started_at"] = datetime.utcnow()
    return True


def release_retrain_lock():
    """
    Liberar el lock de reentrenamiento
    """
    _retrain_lock["is_running"] = False
    _retrain_lock["started_at"] = None


def get_retrain_status():
    """
    Obtener estado actual del reentrenamiento
    """
    return _retrain_lock.copy()
