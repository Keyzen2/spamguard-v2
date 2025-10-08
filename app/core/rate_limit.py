"""
Soft Rate Limiting (no bloquea, solo avisa)
"""
from fastapi import Depends
from app.core.security import verify_api_key
from app.config import settings
from supabase import create_client
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

async def check_rate_limit(user = Depends(verify_api_key)):
    """
    Verificar rate limit (soft - no bloquea en v3.0 hybrid)
    """
    if not settings.RATE_LIMIT_ENABLED:
        user['usage'] = {'current': 0, 'limit': 999999, 'remaining': 999999}
        return user
    
    user_id = user['user_id']
    now = datetime.now()
    
    # Obtener uso del mes actual
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
    
    limit = settings.MONTHLY_REQUEST_LIMIT
    
    # En v3.0 hybrid, no bloqueamos, solo informamos
    user['usage'] = {
        'current': current_usage,
        'limit': limit,
        'remaining': max(0, limit - current_usage),
        'percentage': (current_usage / limit * 100) if limit > 0 else 0,
        'exceeded': current_usage >= limit
    }
    
    # Log si excede (pero no bloquea)
    if current_usage >= limit:
        logger.warning(f"User {user_id} exceeded rate limit: {current_usage}/{limit}")
    
    return user

async def track_request(user_id: str, api_key_id: str, endpoint: str):
    """Trackear request en base de datos"""
    try:
        supabase.rpc('track_api_request', {
            'p_user_id': user_id,
            'p_api_key_id': api_key_id,
            'p_endpoint': endpoint
        }).execute()
    except Exception as e:
        logger.error(f"Error tracking request: {str(e)}")
