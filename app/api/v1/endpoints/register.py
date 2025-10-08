"""
Register endpoint - Crear usuario y API key
"""
from fastapi import APIRouter, HTTPException, status
from app.db.schemas import RegisterRequest, RegisterResponse
from app.core.security import generate_api_key, get_or_create_user
from supabase import create_client
from app.config import settings
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register_user(request: RegisterRequest):
    """
    🔑 Register new user and get API key
    
    Create a free account and receive your API key instantly.
    No credit card required!
    """
    try:
        # 1. Crear o obtener usuario
        user = await get_or_create_user(
            email=request.email,
            site_url=request.site_url
        )
        
        user_id = user['id']
        
        # 2. Verificar si ya tiene API key activa
        existing_keys = supabase.table('api_keys')\
            .select('*')\
            .eq('user_id', user_id)\
            .eq('is_active', True)\
            .execute()
        
        if existing_keys.data and len(existing_keys.data) > 0:
            # Ya tiene API key, retornar error amigable
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "Account already exists",
                    "message": "This email already has an active API key. Check your email or contact support.",
                    "support_email": "support@spamguard.ai"
                }
            )
        
        # 3. Generar nueva API key
        full_key, key_hash, key_prefix = generate_api_key()
        
        # 4. Guardar en base de datos
        api_key_data = supabase.table('api_keys').insert({
            'user_id': user_id,
            'key_hash': key_hash,
            'key_prefix': key_prefix,
            'name': request.name or request.site_url or 'Default Key',
            'scopes': ['analyze', 'feedback', 'stats'],
            'rate_limit_tier': 'free',
            'is_active': True
        }).execute()
        
        if not api_key_data.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create API key"
            )
        
        logger.info(f"New user registered: {request.email}")
        
        return RegisterResponse(
            success=True,
            message="Account created successfully! Save your API key securely.",
            api_key=full_key,
            user_id=user_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during registration. Please try again."
        )
