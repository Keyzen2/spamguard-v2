"""
Rutas de Machine Learning - Reentrenamiento
"""
from fastapi import APIRouter, HTTPException, Header, Depends
from typing import Optional
import os

from app.retrain_model import ModelRetrainer

router = APIRouter(prefix="/api/v1/ml", tags=["Machine Learning"])

# Secret key para autorización
ML_SECRET_KEY = os.getenv("ML_SECRET_KEY", "change-me-in-production")


async def verify_ml_secret(x_ml_secret: str = Header(None)):
    """
    Verificar secret key para operaciones ML
    """
    if not x_ml_secret:
        raise HTTPException(
            status_code=401,
            detail="ML Secret Key required in X-ML-Secret header"
        )
    
    if x_ml_secret != ML_SECRET_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid ML Secret Key"
        )
    
    return True


@router.post("/retrain")
async def retrain_model(
    min_samples: int = 100,
    user_id: Optional[str] = None,
    authorized: bool = Depends(verify_ml_secret)
):
    """
    🔄 Reentrenar modelo manualmente
    
    Headers:
        X-ML-Secret: Secret key configurada en Railway
    
    Query params:
        min_samples: Mínimo de ejemplos requeridos (default: 100)
        user_id: Entrenar solo con datos de un usuario (opcional)
    
    Returns:
        Metadata del nuevo modelo entrenado
    """
    try:
        retrainer = ModelRetrainer()
        
        # Ejecutar reentrenamiento
        success = retrainer.run(min_samples=min_samples, user_id=user_id)
        
        if not success:
            raise HTTPException(
                status_code=400,
                detail="Insufficient training data or retraining failed"
            )
        
        # Leer metadata del nuevo modelo
        metadata_path = retrainer.metadata_path
        if metadata_path.exists():
            import json
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
        else:
            metadata = {}
        
        return {
            "success": True,
            "message": "Model retrained successfully",
            "metadata": metadata
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Retraining error: {str(e)}"
        )


@router.get("/model/info")
async def get_model_info(authorized: bool = Depends(verify_ml_secret)):
    """
    📊 Obtener información del modelo actual
    """
    try:
        retrainer = ModelRetrainer()
        metadata_path = retrainer.metadata_path
        
        if not metadata_path.exists():
            return {
                "model_exists": False,
                "message": "No trained model found"
            }
        
        import json
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        return {
            "model_exists": True,
            "metadata": metadata
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error reading model info: {str(e)}"
        )


@router.get("/feedback/stats")
async def get_feedback_stats(authorized: bool = Depends(verify_ml_secret)):
    """
    📈 Estadísticas de feedback disponible para entrenar
    """
    try:
        from app.database import supabase
        
        # Contar feedback no procesado
        response = supabase.table('feedback_queue')\
            .select('id, new_label')\
            .eq('processed', False)\
            .execute()
        
        data = response.data
        
        spam_count = sum(1 for item in data if item.get('new_label') == 'spam')
        ham_count = len(data) - spam_count
        
        return {
            "total_feedback": len(data),
            "spam": spam_count,
            "ham": ham_count,
            "ready_to_train": len(data) >= 100
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting feedback stats: {str(e)}"
        )
