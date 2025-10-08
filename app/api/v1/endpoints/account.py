"""
Account management endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from app.core.security import verify_api_key, generate_api_key
from supabase import create_client
from app.config import settings
from datetime import datetime

router = APIRouter()
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

class AccountInfoResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    company_name: Optional[str]
    plan: str
    is_active: bool
    email_verified: bool
    member_since: str
    
class UsageResponse(BaseModel):
    current_period: Dict = Field(..., description="Current month usage")
    plan_limit: int
    percentage_used: float

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
    
    return AccountInfoResponse(
        id=account['id'],
        email=account['email'],
        full_name=account.get('full_name'),
        company_name=account.get('company_name'),
        plan=account['plan'],
        is_active=account['is_active'],
        email_verified=account['email_verified'],
        member_since=account['created_at']
    )

@router.get("/account/usage", response_model=UsageResponse)
async def get_usage(user: dict = Depends(verify_api_key)):
    """
    📈 Get current usage statistics
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
        requests_used = usage['requests_count']
    else:
        requests_used = 0
    
    plan_limit = settings.PLAN_LIMITS.get(user['plan'], 500)
    
    return UsageResponse(
        current_period={
            'year': now.year,
            'month': now.month,
            'requests_used': requests_used,
            'analyze_requests': usage.get('analyze_requests', 0) if response.data else 0
        },
        plan_limit=plan_limit,
        percentage_used=(requests_used / plan_limit * 100) if plan_limit > 0 else 0
    )

# API Keys management
class APIKeyResponse(BaseModel):
    id: str
    name: Optional[str]
    key_prefix: str
    scopes: List[str]
    is_active: bool
    created_at: str
    last_used_at: Optional[str]
    total_requests: int

class CreateAPIKeyRequest(BaseModel):
    name: str = Field(..., max_length=255, description="Descriptive name for this key")
    scopes: Optional[List[str]] = Field(None, description="Permissions for this key")

class CreateAPIKeyResponse(BaseModel):
    api_key: str = Field(..., description="⚠️ Save this! It won't be shown again")
    key_info: APIKeyResponse

@router.get("/account/api-keys", response_model=List[APIKeyResponse])
async def list_api_keys(user: dict = Depends(verify_api_key)):
    """
    🔑 List all your API keys
    """
    response = supabase.table('api_keys')\
        .select('*')\
        .eq('user_id', user['user_id'])\
        .order('created_at', desc=True)\
        .execute()
    
    return [
        APIKeyResponse(
            id=key['id'],
            name=key.get('name'),
            key_prefix=key['key_prefix'],
            scopes=key.get('scopes', []),
            is_active=key['is_active'],
            created_at=key['created_at'],
            last_used_at=key.get('last_used_at'),
            total_requests=key.get('total_requests', 0)
        )
        for key in response.data
    ]

@router.post("/account/api-keys", response_model=CreateAPIKeyResponse, status_code=201)
async def create_api_key(
    request: CreateAPIKeyRequest,
    user: dict = Depends(verify_api_key)
):
    """
    🔑 Create a new API key
    
    ⚠️ **Important**: The full API key is only shown once. Save it securely!
    """
    # Generate new key
    full_key, key_hash, key_prefix = generate_api_key()
    
    # Default scopes
    scopes = request.scopes or ['analyze', 'feedback', 'stats']
    
    # Save to database
    response = supabase.table('api_keys').insert({
        'user_id': user['user_id'],
        'key_hash': key_hash,
        'key_prefix': key_prefix,
        'name': request.name,
        'scopes': scopes,
        'is_active': True
    }).execute()
    
    key_data = response.data[0]
    
    return CreateAPIKeyResponse(
        api_key=full_key,
        key_info=APIKeyResponse(
            id=key_data['id'],
            name=key_data['name'],
            key_prefix=key_data['key_prefix'],
            scopes=key_data['scopes'],
            is_active=key_data['is_active'],
            created_at=key_data['created_at'],
            last_used_at=None,
            total_requests=0
        )
    )

@router.delete("/account/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: str,
    user: dict = Depends(verify_api_key)
):
    """
    🗑️ Revoke an API key
    """
    # Verify ownership
    response = supabase.table('api_keys')\
        .select('user_id')\
        .eq('id', key_id)\
        .execute()
    
    if not response.data or response.data[0]['user_id'] != user['user_id']:
        raise HTTPException(status_code=404, detail="API key not found")
    
    # Soft delete (deactivate)
    supabase.table('api_keys')\
        .update({'is_active': False})\
        .eq('id', key_id)\
        .execute()
    
    return None
