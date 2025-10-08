"""
Redis Cache for API responses
"""
import redis
import json
from typing import Optional, Any
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Redis client
redis_client: Optional[redis.Redis] = None

def init_redis():
    """Initialize Redis connection"""
    global redis_client
    
    if not settings.REDIS_URL:
        logger.warning("⚠️ Redis URL not configured. Cache disabled.")
        return
    
    try:
        redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        
        # Test connection
        redis_client.ping()
        logger.info("✅ Redis connected")
        
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {str(e)}")
        redis_client = None

async def cache_get(key: str) -> Optional[dict]:
    """
    Get value from cache
    
    Args:
        key: Cache key
    
    Returns:
        Cached value or None
    """
    if not redis_client:
        return None
    
    try:
        value = redis_client.get(key)
        if value:
            return json.loads(value)
        return None
    except Exception as e:
        logger.error(f"Cache get error: {str(e)}")
        return None

async def cache_set(key: str, value: Any, ttl: int = 300):
    """
    Set value in cache
    
    Args:
        key: Cache key
        value: Value to cache (must be JSON serializable)
        ttl: Time to live in seconds (default 5 minutes)
    """
    if not redis_client:
        return
    
    try:
        redis_client.setex(
            key,
            ttl,
            json.dumps(value)
        )
    except Exception as e:
        logger.error(f"Cache set error: {str(e)}")

async def cache_delete(key: str):
    """Delete key from cache"""
    if not redis_client:
        return
    
    try:
        redis_client.delete(key)
    except Exception as e:
        logger.error(f"Cache delete error: {str(e)}")

async def cache_clear_pattern(pattern: str):
    """Clear all keys matching pattern"""
    if not redis_client:
        return
    
    try:
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
    except Exception as e:
        logger.error(f"Cache clear error: {str(e)}")

# Rate limiting with Redis
async def rate_limit_check(key: str, limit: int, window: int = 60) -> tuple[bool, int]:
    """
    Check rate limit using Redis
    
    Args:
        key: Rate limit key (e.g., "ratelimit:user_123")
        limit: Max requests allowed
        window: Time window in seconds
    
    Returns:
        (is_allowed, current_count)
    """
    if not redis_client:
        return True, 0
    
    try:
        current = redis_client.get(key)
        
        if current is None:
            # First request
            redis_client.setex(key, window, 1)
            return True, 1
        
        current_count = int(current)
        
        if current_count >= limit:
            return False, current_count
        
        # Increment
        redis_client.incr(key)
        return True, current_count + 1
        
    except Exception as e:
        logger.error(f"Rate limit check error: {str(e)}")
        return True, 0  # Fail open
