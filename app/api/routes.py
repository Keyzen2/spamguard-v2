from fastapi import APIRouter, Depends, HTTPException, Request, Header, BackgroundTasks
from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
import logging
import os
from pathlib import Path

from app.api.dependencies import (
    verify_api_key, 
    check_rate_limit,
    verify_admin_api_key,
    check_admin_rate_limit,
    acquire_retrain_lock,
    release_retrain_lock,
    get_retrain_status
)
from app.database import Database, supabase
from app.features import extract_features
from app.utils import sanitize_input, calculate_spam_score_explanation
from app.ml_model import spam_detector
from app.config import get_settings

router = APIRouter(prefix="/api/v1", tags=["spam-detection"])
logger = logging.getLogger(__name__)

# === MODELOS PYDANTIC ===

class CommentInput(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    author: str = Field(..., min_length=1, max_length=255)
    author_email: Optional[EmailStr] = None
    author_url: Optional[str] = Field(None, max_length=500)
    author_ip: str
    post_id: int
    user_agent: Optional[str] = None
    referer: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "content": "Great article! Thanks for sharing this information.",
                "author": "John Doe",
                "author_email": "john@example.com",
                "author_url": "https://johndoe.com",
                "author_ip": "192.168.1.1",
                "post_id": 123,
                "user_agent": "Mozilla/5.0...",
                "referer": "https://google.com"
            }
        }

class PredictionResponse(BaseModel):
    is_spam: bool
    confidence: float = Field(..., ge=0, le=1)
    spam_score: float = Field(..., ge=0, le=100)
    reasons: List[str]
    comment_id: str
    explanation: dict
    
class FeedbackInput(BaseModel):
    comment_id: str
    is_spam: bool
    
class StatsResponse(BaseModel):
    total_analyzed: int
    total_spam_blocked: int
    total_ham_approved: int
    accuracy: Optional[float]
    spam_block_rate: float
    last_retrain: Optional[str]

class ApiKeyResponse(BaseModel):
    site_id: str
    api_key: str
    created_at: str
    message: str

# === ENDPOINTS PÚBLICOS ===

@router.post("/analyze", response_model=PredictionResponse)
async def analyze_comment(
    comment: CommentInput,
    request: Request,
    site_id: str = Depends(verify_api_key),
    _: bool = Depends(check_rate_limit)
):
    """
    **Analiza un comentario y predice si es spam**
    """
    try:
        # Sanitizar inputs
        comment_data = {
            'content': sanitize_input(comment.content),
            'author': sanitize_input(comment.author),
            'author_email': comment.author_email,
            'author_url': comment.author_url,
            'author_ip': comment.author_ip,
            'post_id': comment.post_id,
            'user_agent': comment.user_agent,
            'referer': comment.referer
        }
        
        # 1. Extraer características
        features = extract_features(comment_data)
        
        # 2. Predicción con modelo ML
        prediction = spam_detector.predict(features)
        
        # 3. Generar explicación detallada
        explanation = calculate_spam_score_explanation(
            features,
            prediction['is_spam'],
            prediction['confidence']
        )
        
        # 4. Guardar análisis en base de datos
        comment_id = Database.save_comment_analysis(
            site_id=site_id,
            comment_data=comment_data,
            features=features,
            prediction=prediction
        )
        
        return PredictionResponse(
            is_spam=prediction['is_spam'],
            confidence=prediction['confidence'],
            spam_score=prediction['score'],
            reasons=prediction['reasons'],
            comment_id=comment_id,
            explanation=explanation
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando comentario: {str(e)}"
        )


@router.post("/feedback")
async def submit_feedback(
    feedback: FeedbackInput,
    site_id: str = Depends(verify_api_key),
    _: bool = Depends(check_rate_limit)
):
    """
    **Envía feedback sobre la clasificación de un comentario**
    """
    try:
        # Obtener el comentario original
        result = supabase.table('comments_analyzed')\
            .select('predicted_label')\
            .eq('id', feedback.comment_id)\
            .eq('site_id', site_id)\
            .execute()
        
        if not result.data:
            raise HTTPException(
                status_code=404,
                detail="Comentario no encontrado"
            )
        
        old_label = result.data[0]['predicted_label']
        new_label = 'spam' if feedback.is_spam else 'ham'
        
        # Guardar feedback
        Database.save_feedback(
            comment_id=feedback.comment_id,
            site_id=site_id,
            correct_label=new_label,
            old_label=old_label
        )
        
        # Verificar si es momento de reentrenar
        should_retrain = Database.check_retrain_needed(site_id)
        
        response = {
            "status": "success",
            "message": "Feedback recibido correctamente",
            "queued_for_training": should_retrain
        }
        
        if should_retrain:
            response["message"] += ". El modelo será reentrenado próximamente."
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error guardando feedback: {str(e)}"
        )


@router.post("/register-site", response_model=ApiKeyResponse)
async def register_new_site(
    site_url: str,
    admin_email: EmailStr,
):
    """
    **Registra un nuevo sitio y genera API key**
    """
    try:
        import hashlib
        site_id = hashlib.sha256(site_url.encode()).hexdigest()[:16]
        
        existing = supabase.table('site_stats')\
            .select('api_key, created_at')\
            .eq('site_id', site_id)\
            .execute()
        
        if existing.data:
            return ApiKeyResponse(
                site_id=site_id,
                api_key=existing.data[0]['api_key'],
                created_at=existing.data[0].get('created_at', datetime.utcnow().isoformat()),
                message="Este sitio ya está registrado. Aquí está tu API key."
            )
        
        # Crear nuevo registro
        api_key = Database.generate_api_key()
        
        new_site = {
            'site_id': site_id,
            'api_key': api_key,
            'total_analyzed': 0,
            'total_spam_blocked': 0,
            'total_ham_approved': 0,
            'created_at': datetime.utcnow().isoformat()
        }
        
        supabase.table('site_stats').insert(new_site).execute()
        
        return ApiKeyResponse(
            site_id=site_id,
            api_key=api_key,
            created_at=new_site['created_at'],
            message="Sitio registrado exitosamente. Guarda tu API key de forma segura."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error registrando sitio: {str(e)}"
        )


@router.get("/check-site")
async def check_existing_site(site_url: str):
    """
    Verifica si un sitio ya está registrado
    """
    try:
        import hashlib
        site_id = hashlib.sha256(site_url.encode()).hexdigest()[:16]
        
        result = supabase.table('site_stats')\
            .select('api_key')\
            .eq('site_id', site_id)\
            .execute()
        
        if result.data:
            return {
                "exists": True,
                "api_key": result.data[0]['api_key'],
                "message": "Sitio ya registrado"
            }
        
        return {
            "exists": False,
            "message": "Sitio no encontrado"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=StatsResponse)
async def get_statistics(
    site_id: str = Depends(verify_api_key)
):
    """
    **Obtiene estadísticas del sitio**
    """
    try:
        stats = Database.get_site_statistics(site_id)
        
        if not stats:
            return StatsResponse(
                total_analyzed=0,
                total_spam_blocked=0,
                total_ham_approved=0,
                accuracy=None,
                spam_block_rate=0.0,
                last_retrain=None
            )
        
        return StatsResponse(**stats)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo estadísticas: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    **Health check del servicio**
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "model_status": "trained" if spam_detector.is_trained else "baseline",
        "version": "1.0.0"
    }


# === ENDPOINTS DE ADMIN (PROTEGIDOS) ===

@router.post("/admin/retrain-model")
async def retrain_model_endpoint(
    background_tasks: BackgroundTasks,
    admin_key: str = Depends(verify_admin_api_key)
):
    """
    🔒 ENDPOINT PROTEGIDO - Solo para administradores
    
    Reentrenar el modelo ML con datos actualizados.
    Requiere X-Admin-Key en los headers.
    
    Security:
    - Requiere admin API key
    - Rate limit: 1 request por hora
    - Solo un reentrenamiento a la vez
    """
    
    # 1. Verificar rate limit (1 request por hora)
    check_admin_rate_limit(
        identifier=f"retrain_{admin_key[:8]}", 
        max_requests=1, 
        window_minutes=60
    )
    
    # 2. Verificar que no haya otro reentrenamiento en curso
    if not acquire_retrain_lock():
        raise HTTPException(
            status_code=409,
            detail="Model retraining already in progress. Check /admin/retrain-status"
        )
    
    try:
        # 3. Ejecutar reentrenamiento en background
        background_tasks.add_task(run_retrain_background)
        
        return {
            "success": True,
            "message": "Model retraining started in background",
            "estimated_time": "5-15 minutes",
            "check_status_at": "/api/v1/admin/retrain-status"
        }
        
    except Exception as e:
        release_retrain_lock()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start retraining: {str(e)}"
        )

@router.get("/admin/retrain-status", tags=["admin"])
async def get_retrain_status_endpoint(
    admin_key: str = Depends(verify_admin_api_key)
):
    """
    🔒 Verificar estado del reentrenamiento
    """
    status = get_retrain_status()
    
    if status["is_running"]:
        elapsed = (datetime.utcnow() - status["started_at"]).seconds
        return {
            "status": "running",
            "started_at": status["started_at"].isoformat(),
            "elapsed_seconds": elapsed,
            "estimated_remaining": max(0, 900 - elapsed)
        }
    else:
        # Leer metadata del último entrenamiento
        # CORREGIDO: Buscar en volumen persistente
        volume_path = os.getenv('RAILWAY_VOLUME_MOUNT_PATH')
        
        if volume_path:
            metadata_path = Path(volume_path) / 'models' / 'model_metadata.json'
        else:
            metadata_path = Path('models') / 'model_metadata.json'
        
        try:
            if metadata_path.exists():
                import json
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                return {
                    "status": "idle",
                    "last_training": metadata.get('trained_at'),
                    "last_accuracy": metadata.get('metrics', {}).get('test_accuracy'),
                    "training_samples": metadata.get('training_samples'),
                    "storage_location": str(metadata_path)
                }
            else:
                return {
                    "status": "idle",
                    "last_training": None,
                    "message": f"No training metadata found at {metadata_path}"
                }
        except Exception as e:
            return {
                "status": "idle",
                "last_training": None,
                "error": str(e),
                "metadata_path": str(metadata_path)
            }


async def run_retrain_background():
    """
    Función que ejecuta el reentrenamiento en background
    """
    import subprocess
    
    try:
        logger.info("🚀 Starting model retraining...")
        
        # Ejecutar script de reentrenamiento
        result = subprocess.run(
            ['python', 'app/retrain_model.py'],
            capture_output=True,
            text=True,
            timeout=1800  # 30 minutos máximo
        )
        
        if result.returncode == 0:
            logger.info("✅ Model retrained successfully")
            
            # Recargar modelo en memoria
            spam_detector.load_model('models/spam_model.pkl')
            
        else:
            logger.error(f"❌ Retraining failed: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        logger.error("❌ Retraining timeout (>30 min)")
    except Exception as e:
        logger.error(f"❌ Retraining error: {str(e)}")
    finally:
        release_retrain_lock()
