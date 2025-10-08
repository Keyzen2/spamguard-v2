"""
API Key Authentication (sin Stripe, todo gratis)
"""
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from app.config import settings
import hashlib
import secrets
from typing import Optional

security_scheme = HTTPBearer()

supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_KEY
)

def hash_api_key(api_key: str) -> str:
    """Hash API key para almacenamiento"""
    return hashlib.sha256(api_key.encode()).hexdigest()

def generate_api_key() -> tuple[str, str, str]:
    """
    Generar nueva API key
    
    Returns:
        (full_key, key_hash, key_prefix)
    """
    random_part = secrets.token_urlsafe(32)
    env = "live" if settings.ENVIRONMENT == "production" else "test"
    full_key = f"{settings.API_KEY_PREFIX}_{env}_{random_part}"
    key_hash = hash_api_key(full_key)
    key_prefix = f"{settings.API_KEY_PREFIX}_{env}_"
    
    return full_key, key_hash, key_prefix

async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme)
) -> dict:
    """
    Verificar API key
    
    Returns:
        User data si válida
    
    Raises:
        HTTPException si inválida
    """
    api_key = credentials.credentials
    key_hash = hash_api_key(api_key)
    
    # Buscar en base de datos
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
    
    # Verificar que usuario esté activo
    if not user_data['is_active']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive"
        )
    
    return {
        'user_id': user_data['id'],
        'email': user_data['email'],
        'plan': user_data.get('plan', 'free'),
        'api_key_id': key_data['id'],
        'scopes': key_data.get('scopes', [])
    }

# Función auxiliar para obtener o crear usuario
async def get_or_create_user(email: str, site_url: str = None) -> dict:
    """Obtener usuario existente o crear nuevo"""
    
    # Buscar usuario existente
    response = supabase.table('api_users')\
        .select('*')\
        .eq('email', email)\
        .execute()
    
    if response.data:
        return response.data[0]
    
    # Crear nuevo usuario
    response = supabase.table('api_users').insert({
        'email': email,
        'plan': 'free',
        'is_active': True,
        'email_verified': False,
        'full_name': site_url if site_url else None
    }).execute()
    
    if response.data:
        return response.data[0]
    
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to create user"
    )
