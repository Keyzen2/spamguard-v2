"""
Cache system (Redis opcional, fallback a memoria)
"""
import json
from typing import Optional, Any, Dict
from app.config import settings
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Intentar importar redis (opcional)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("⚠️  Redis library not installed. Using in-memory cache only.")

# Redis client (puede ser None)
redis_client: Optional[Any] = None

def init_redis():
    """Inicializar Redis (opcional)"""
    global redis_client
    
    if not REDIS_AVAILABLE:
        logger.info("⚠️  Redis not available. Using in-memory cache only.")
        return
    
    if not settings.REDIS_URL:
        logger.info("⚠️  Redis not configured (REDIS_URL not set). Using in-memory cache only.")
        return
    
    try:
        redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5
        )
        redis_client.ping()
        logger.info("✅ Redis connected successfully")
    except Exception as e:
        logger.warning(f"⚠️  Redis connection failed: {str(e)}. Using in-memory cache.")
        redis_client = None

# In-memory cache alternativo (si no hay Redis)
class MemoryCache:
    """Simple in-memory cache con TTL"""
    def __init__(self):
        self._cache: Dict[str, tuple[Any, datetime]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Obtener valor si no ha expirado"""
        if key in self._cache:
            value, expiry = self._cache[key]
            if datetime.now() < expiry:
                return value
            else:
                # Expiró, eliminar
                del self._cache[key]
        return None
    
    def set(self, key: str, value: Any, ttl: int = 300):
        """Guardar con TTL en segundos"""
        expiry = datetime.now() + timedelta(seconds=ttl)
        self._cache[key] = (value, expiry)
    
    def delete(self, key: str):
        """Eliminar entrada"""
        self._cache.pop(key, None)
    
    def clear(self):
        """Limpiar todo el cache"""
        self._cache.clear()
    
    def cleanup(self):
        """Limpiar entradas expiradas"""
        now = datetime.now()
        expired_keys = [
            key for key, (_, expiry) in self._cache.items() 
            if now >= expiry
        ]
        for key in expired_keys:
            del self._cache[key]

_memory_cache = MemoryCache()

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
    
    # Fallback a memoria con TTL
    _memory_cache.set(key, value, ttl)

async def cache_delete(key: str):
    """Eliminar de cache"""
    if redis_client:
        try:
            redis_client.delete(key)
        except:
            pass
    
    _memory_cache.delete(key)

async def cache_clear():
    """Limpiar todo el cache"""
    if redis_client:
        try:
            redis_client.flushdb()
        except:
            pass
    
    _memory_cache.clear()

def cleanup_expired_cache():
    """Limpiar entradas expiradas del cache en memoria"""
    _memory_cache.cleanup()
