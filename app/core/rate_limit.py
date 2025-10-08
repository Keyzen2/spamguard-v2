"""
Rate Limiting per API key and plan
"""
from fastapi import HTTPException, status, Depends
from app.core.security import verify_api_key
from app.config import settings
from supabase import create_client
import redis
from typing import Optional
from datetime import datetime

# Redis client (for fast rate limiting)
redis_client: Optional[redis.Redis] = None

if settings.REDIS_URL:
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

async def check_rate_limit(user = Depends(verify_api_key)):
    """
    Check if user has exceeded rate limit for current month
    """
    if not settings.RATE_LIMIT_ENABLED:
        return user
    
    user_id = user['user_id']
    plan = user['plan']
    
    # Get monthly limit
    limit = settings.PLAN_LIMITS.get(plan, 500)
    
    # Check from database (source of truth)
    now = datetime.now()
    response = supabase.table('monthly_usage')\
        .select('requests_count')\
        .eq('user_id', user_id)\
        .eq('year', now.year)\
        .eq('month', now.month)\
        .execute()
    
    if response.data:
        current_usage = response.data[0]['requests_count']
    else:
        current_usage = 0
    
    # Check if exceeded
    if current_usage >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "limit": limit,
                "current": current_usage,
                "reset_at": f"{now.year}-{now.month + 1 if now.month < 12 else 1}-01T00:00:00Z",
                "upgrade_url": "https://spamguard.ai/pricing"
            }
        )
    
    # Add usage info to user context
    user['usage'] = {
        'current': current_usage,
        'limit': limit,
        'remaining': limit - current_usage,
        'percentage': (current_usage / limit) * 100
    }
    
    return user

async def track_request(user_id: str, api_key_id: str, endpoint: str):
    """Track API request in database"""
    supabase.rpc('track_api_request', {
        'p_user_id': user_id,
        'p_api_key_id': api_key_id,
        'p_endpoint': endpoint
    }).execute()
