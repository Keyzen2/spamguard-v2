"""
API Dependencies - MEJORADO
"""
from fastapi import Header, HTTPException, Depends
import logging

from app.database import supabase

logger = logging.getLogger(__name__)

async def verify_api_key(x_api_key: str = Header(...)) -> str:
    """
    Verificar API key y retornar site_id
    """
    try:
        # Buscar en base de datos
        result = supabase.table('site_stats')\
            .select('site_id')\
            .eq('api_key', x_api_key)\
            .execute()
        
        if not result.data:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )
        
        return result.data[0]['site_id']
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying API key: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error verifying API key"
        )

def get_spam_detector():
    """
    ✅ NUEVO: Dependency para obtener el detector ML
    """
    from app.main import spam_detector
    
    if spam_detector is None:
        raise HTTPException(
            status_code=503,
            detail="ML detector not initialized"
        )
    
    return spam_detector
