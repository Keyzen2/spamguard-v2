"""
Cache system (Redis opcional, sino usa memoria)
"""
import redis
import json
from typing import Optional, Any
from app.config import settings
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# Redis client (puede ser None)
redis_client: Optional[redis.Redis] = None

def init_redis():
    """Inicializar Redis (opcional)"""
    global redis_client
    
    if not settings.REDIS_URL:
        logger.info("⚠️ Redis not configured. Using in-memory cache only.")
        return
    
    try:
        redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5
        )
        redis_client.ping()
        logger.info("✅ Redis connected")
    except Exception as e:
        logger.warning(f"⚠️ Redis connection failed: {str(e)}. Using in-memory cache.")
        redis_client = None

# In-memory cache alternativo (si no hay Redis)
_memory_cache = {}

async def cache_get(key: str) -> Optional[dict]:
    """Obtener desde cache"""
    
    # Intentar Redis primero
    if redis_client:
        try:
            value = redis_client.get(key)
            if value:
                return json.loads(value)
        except Exception as e:
            logger.error(f"Redis get error: {str(e)}")
    
    # Fallback a memoria
    return _memory_cache.get(key)

async def cache_set(key: str, value: Any, ttl: int = 300):
    """Guardar en cache"""
    
    # Intentar Redis primero
    if redis_client:
        try:
            redis_client.setex(key, ttl, json.dumps(value))
            return
        except Exception as e:
            logger.error(f"Redis set error: {str(e)}")
    
    # Fallback a memoria (sin TTL real por ahora)
    _memory_cache[key] = value

async def cache_delete(key: str):
    """Eliminar de cache"""
    if redis_client:
        try:
            redis_client.delete(key)
        except:
            pass
    
    _memory_cache.pop(key, None)
