"""
Security: Authentication & Authorization
"""
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from app.config import settings
import hashlib
import secrets
from typing import Optional

security_scheme = HTTPBearer()

# Supabase client
supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_KEY
)

def hash_api_key(api_key: str) -> str:
    """Hash API key for storage"""
    return hashlib.sha256(api_key.encode()).hexdigest()

def generate_api_key() -> tuple[str, str, str]:
    """
    Generate new API key
    
    Returns:
        (full_key, key_hash, key_prefix)
    """
    # Generate random key
    random_part = secrets.token_urlsafe(32)
    
    # Format: sg_live_xxxxxxxxxxxxx or sg_test_xxxxxxxxxxxxx
    env = "live" if settings.ENVIRONMENT == "production" else "test"
    full_key = f"{settings.API_KEY_PREFIX}_{env}_{random_part}"
    
    # Hash for storage
    key_hash = hash_api_key(full_key)
    
    # Prefix for display (sg_live_ or sg_test_)
    key_prefix = f"{settings.API_KEY_PREFIX}_{env}_"
    
    return full_key, key_hash, key_prefix

async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme)
) -> dict:
    """
    Verify API key from Authorization header
    
    Returns:
        User data if valid
    
    Raises:
        HTTPException if invalid
    """
    api_key = credentials.credentials
    
    # Hash the provided key
    key_hash = hash_api_key(api_key)
    
    # Look up in database
    response = supabase.table('api_keys')\
        .select('*, api_users(*)')\
        .eq('key_hash', key_hash)\
        .eq('is_active', True)\
        .execute()
    
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    key_data = response.data[0]
    user_data = key_data['api_users']
    
    # Check if user is active
    if not user_data['is_active']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    
    # Check if key is expired
    if key_data.get('expires_at'):
        from datetime import datetime
        expires_at = datetime.fromisoformat(key_data['expires_at'])
        if datetime.now() > expires_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key has expired"
            )
    
    return {
        'user_id': user_data['id'],
        'email': user_data['email'],
        'plan': user_data['plan'],
        'api_key_id': key_data['id'],
        'scopes': key_data.get('scopes', [])
    }

def check_scope(required_scope: str):
    """Dependency to check if API key has required scope"""
    async def scope_checker(user = Security(verify_api_key)):
        if required_scope not in user.get('scopes', []):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required scope: {required_scope}"
            )
        return user
    return scope_checker
