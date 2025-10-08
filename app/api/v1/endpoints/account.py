"""
Account endpoint (sin billing)
"""
from fastapi import APIRouter, Depends, HTTPException
from app.db.schemas import AccountInfoResponse, UsageResponse
from app.core.security import verify_api_key
from supabase import create_client
from app.config import settings
from datetime import datetime

router = APIRouter()
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

@router.get("/account", response_model=AccountInfoResponse)
async def get_account_info(user: dict = Depends(verify_api_key)):
    """
    👤 Get your account information
    """
    response = supabase.table('api_users')\
        .select('*')\
        .eq('id', user['user_id'])\
        .execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Account not found")
    
    account = response.data[0]
    
    # Obtener uso actual
    now = datetime.now()
    usage_response = supabase.table('monthly_usage')\
        .select('requests_count')\
        .eq('user_id', user['user_id'])\
        .eq('year', now.year)\
        .eq('month', now.month)\
        .execute()
    
    current_usage = usage_response.data[0]['requests_count'] if usage_response.data else 0
    limit = settings.MONTHLY_REQUEST_LIMIT
    
    return AccountInfoResponse(
        id=account['id'],
        email=account['email'],
        plan=account.get('plan', 'free'),
        is_active=account['is_active'],
        created_at=account['created_at'],
        usage={
            'current': current_usage,
            'limit': limit,
            'remaining': max(0, limit - current_usage),
            'percentage': (current_usage / limit * 100) if limit > 0 else 0
        }
    )

@router.get("/account/usage", response_model=UsageResponse)
async def get_usage(user: dict = Depends(verify_api_key)):
    """
    📈 Get detailed usage information
    """
    now = datetime.now()
    
    response = supabase.table('monthly_usage')\
        .select('*')\
        .eq('user_id', user['user_id'])\
        .eq('year', now.year)\
        .eq('month', now.month)\
        .execute()
    
    if response.data:
        usage = response.data[0]
        current_usage = usage['requests_count']
    else:
        current_usage = 0
    
    limit = settings.MONTHLY_REQUEST_LIMIT
    
    return UsageResponse(
        current_month={
            'year': now.year,
            'month': now.month,
            'requests': current_usage
        },
        limit=limit,
        percentage_used=(current_usage / limit * 100) if limit > 0 else 0
    )
