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

class RegisterSiteRequest(BaseModel):
    site_url: str = Field(..., description="URL del sitio WordPress")
    admin_email: EmailStr = Field(..., description="Email del administrador")
    
    class Config:
        json_schema_extra = {
            "example": {
                "site_url": "https://example.com",
                "admin_email": "admin@example.com"
            }
        }

class ApiKeyResponse(BaseModel):
    site_id: str
    api_key: str
    created_at: str
    message: str

# === ENDPOINT RAÍZ DE LA API (Para validación del plugin) ===

@router.get("/")
async def api_info():
    """
    **Información de la API - Endpoint de validación**
    
    Este endpoint es usado por el plugin de WordPress para verificar
    que la API está funcionando correctamente.
    """
    return {
        "name": "SpamGuard API",
        "version": "3.0.0",
        "status": "operational",
        "message": "✅ API funcionando correctamente",
        "endpoints": {
            "health": "/api/v1/health",
            "register": "/api/v1/register-site",
            "analyze": "/api/v1/analyze",
            "feedback": "/api/v1/feedback",
            "stats": "/api/v1/stats",
            "docs": "/docs"
        },
        "model": {
            "status": "trained" if spam_detector.is_trained else "baseline",
            "version": "2.0"
        },
        "documentation": "https://docs.spamguard.app"
    }


@router.get("/health")
async def health_check():
    """
    **Health check del servicio**
    
    Verifica que todos los componentes estén funcionando:
    - API operativa
    - Modelo ML cargado
    - Base de datos conectada
    """
    try:
        # Test de conexión a base de datos
        db_healthy = True
        try:
            supabase.table('site_stats').select('count').limit(1).execute()
        except:
            db_healthy = False
        
        model_status = "trained" if spam_detector.is_trained else "baseline"
        
        return {
            "status": "healthy" if db_healthy else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "components": {
                "api": "operational",
                "model": model_status,
                "database": "connected" if db_healthy else "error"
            },
            "version": "3.0.0",
            "model_accuracy": "92.82%" if spam_detector.is_trained else "N/A"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


# === ENDPOINTS PÚBLICOS ===

@router.post("/register-site", response_model=ApiKeyResponse)
async def register_new_site(request: RegisterSiteRequest):
    """
    **Registra un nuevo sitio WordPress y genera API key**
    
    Este endpoint es llamado automáticamente por el plugin de WordPress
    cuando se activa por primera vez.
    
    Returns:
        - site_id: Identificador único del sitio
        - api_key: Clave de API para autenticación
        - created_at: Fecha de creación
        - message: Mensaje informativo
    """
    try:
        import hashlib
        
        # Generar site_id único basado en la URL
        site_id = hashlib.sha256(request.site_url.encode()).hexdigest()[:16]
        
        # Verificar si el sitio ya está registrado
        existing = supabase.table('site_stats')\
            .select('api_key, created_at')\
            .eq('site_id', site_id)\
            .execute()
        
        if existing.data:
            logger.info(f"🔑 Sitio existente solicitando API key: {request.site_url}")
            return ApiKeyResponse(
                site_id=site_id,
                api_key=existing.data[0]['api_key'],
                created_at=existing.data[0].get('created_at', datetime.utcnow().isoformat()),
                message="✅ Este sitio ya está registrado. Aquí está tu API key."
            )
        
        # Crear nuevo registro
        api_key = Database.generate_api_key()
        
        new_site = {
            'site_id': site_id,
            'api_key': api_key,
            'site_url': request.site_url,
            'admin_email': request.admin_email,
            'total_analyzed': 0,
            'total_spam_blocked': 0,
            'total_ham_approved': 0,
            'created_at': datetime.utcnow().isoformat(),
            'last_seen': datetime.utcnow().isoformat()
        }
        
        supabase.table('site_stats').insert(new_site).execute()
        
        logger.info(f"✅ Nuevo sitio registrado: {request.site_url} (ID: {site_id})")
        
        return ApiKeyResponse(
            site_id=site_id,
            api_key=api_key,
            created_at=new_site['created_at'],
            message="✅ Sitio registrado exitosamente. Guarda tu API key de forma segura."
        )
        
    except Exception as e:
        logger.error(f"❌ Error registrando sitio: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error registrando sitio: {str(e)}"
        )


@router.get("/register-site")
async def register_site_info():
    """
    **Información sobre cómo registrar un sitio**
    
    Este endpoint GET proporciona instrucciones cuando alguien
    intenta acceder al endpoint de registro incorrectamente.
    """
    return {
        "message": "⚠️ Usa POST para registrar un nuevo sitio",
        "endpoint": "/api/v1/register-site",
        "method": "POST",
        "required_fields": {
            "site_url": "URL del sitio WordPress",
            "admin_email": "Email del administrador"
        },
        "example": {
            "site_url": "https://example.com",
            "admin_email": "admin@example.com"
        },
        "response": {
            "site_id": "string",
            "api_key": "string",
            "created_at": "ISO 8601 datetime",
            "message": "string"
        }
    }


@router.get("/check-site")
async def check_existing_site(site_url: str):
    """
    **Verifica si un sitio ya está registrado**
    
    Útil para verificar la existencia de un sitio antes de registrarlo.
    
    Query Parameters:
        site_url: URL del sitio a verificar
    """
    try:
        import hashlib
        site_id = hashlib.sha256(site_url.encode()).hexdigest()[:16]
        
        result = supabase.table('site_stats')\
            .select('api_key, created_at')\
            .eq('site_id', site_id)\
            .execute()
        
        if result.data:
            return {
                "exists": True,
                "site_id": site_id,
                "registered_at": result.data[0].get('created_at'),
                "message": "✅ Sitio ya registrado"
            }
        
        return {
            "exists": False,
            "message": "❌ Sitio no encontrado. Usa POST /register-site para registrarlo."
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze", response_model=PredictionResponse)
async def analyze_comment(
    comment: CommentInput,
    request: Request,
    site_id: str = Depends(verify_api_key),
    _: bool = Depends(check_rate_limit)
):
    """
    **Analiza un comentario y predice si es spam**
    
    Este es el endpoint principal usado por el plugin de WordPress
    para analizar comentarios en tiempo real.
    
    Requiere:
        - X-API-Key header con la API key del sitio
        - Datos del comentario en el body
    
    Returns:
        - is_spam: Boolean indicando si es spam
        - confidence: Nivel de confianza (0-1)
        - spam_score: Puntuación de spam (0-100)
        - reasons: Lista de razones de la clasificación
        - comment_id: ID del análisis guardado
        - explanation: Detalles técnicos del análisis
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
        
        # 5. Actualizar estadísticas del sitio
        Database.update_site_stats(site_id, prediction['is_spam'])
        
        logger.info(
            f"📊 Análisis completado - Site: {site_id}, "
            f"Spam: {prediction['is_spam']}, "
            f"Confidence: {prediction['confidence']:.2f}"
        )
        
        return PredictionResponse(
            is_spam=prediction['is_spam'],
            confidence=prediction['confidence'],
            spam_score=prediction['score'],
            reasons=prediction['reasons'],
            comment_id=comment_id,
            explanation=explanation
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error analizando comentario: {str(e)}")
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
    
    Permite al administrador corregir errores del modelo.
    El feedback se usa para mejorar el modelo con reentrenamiento.
    
    Requiere:
        - X-API-Key header
        - comment_id: ID del comentario analizado
        - is_spam: Clasificación correcta (true/false)
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
            "message": "✅ Feedback recibido correctamente",
            "queued_for_training": should_retrain
        }
        
        if should_retrain:
            response["message"] += ". El modelo será reentrenado próximamente."
            logger.info(f"🔄 Reentrenamiento programado para site: {site_id}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error guardando feedback: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error guardando feedback: {str(e)}"
        )


@router.get("/stats", response_model=StatsResponse)
async def get_statistics(
    site_id: str = Depends(verify_api_key)
):
    """
    **Obtiene estadísticas del sitio**
    
    Retorna métricas de uso y precisión del modelo para el sitio.
    
    Requiere:
        - X-API-Key header
    
    Returns:
        - total_analyzed: Comentarios totales analizados
        - total_spam_blocked: Spam bloqueado
        - total_ham_approved: Comentarios legítimos aprobados
        - accuracy: Precisión del modelo (si hay feedback)
        - spam_block_rate: Tasa de bloqueo de spam
        - last_retrain: Fecha del último reentrenamiento
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
        logger.error(f"❌ Error obteniendo estadísticas: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo estadísticas: {str(e)}"
        )


# === ENDPOINTS DE ADMIN (PROTEGIDOS) ===

@router.post("/admin/retrain-model")
async def retrain_model_endpoint(
    background_tasks: BackgroundTasks,
    admin_key: str = Depends(verify_admin_api_key)
):
    """
    🔒 **ENDPOINT PROTEGIDO - Solo para administradores**
    
    Reentrenar el modelo ML con datos actualizados.
    
    Requiere:
        - X-Admin-Key header
    
    Security:
        - Requiere admin API key
        - Rate limit: 1 request por hora
        - Solo un reentrenamiento a la vez
    
    Returns:
        Confirmación de que el reentrenamiento ha iniciado
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
        
        logger.info("🚀 Reentrenamiento iniciado")
        
        return {
            "success": True,
            "message": "✅ Model retraining started in background",
            "estimated_time": "5-15 minutes",
            "check_status_at": "/api/v1/admin/retrain-status"
        }
        
    except Exception as e:
        release_retrain_lock()
        logger.error(f"❌ Error iniciando reentrenamiento: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start retraining: {str(e)}"
        )


@router.get("/admin/retrain-status", tags=["admin"])
async def get_retrain_status_endpoint(
    admin_key: str = Depends(verify_admin_api_key)
):
    """
    🔒 **Verificar estado del reentrenamiento**
    
    Requiere:
        - X-Admin-Key header
    
    Returns:
        Estado actual del proceso de reentrenamiento
    """
    status = get_retrain_status()
    
    if status["is_running"]:
        elapsed = (datetime.utcnow() - status["started_at"]).seconds
        return {
            "status": "running",
            "started_at": status["started_at"].isoformat(),
            "elapsed_seconds": elapsed,
            "estimated_remaining": max(0, 900 - elapsed),
            "message": "🔄 Reentrenamiento en progreso..."
        }
    else:
        # Leer metadata del último entrenamiento
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
                    "model_version": metadata.get('version'),
                    "storage_location": str(metadata_path),
                    "message": "✅ No hay reentrenamiento en progreso"
                }
            else:
                return {
                    "status": "idle",
                    "last_training": None,
                    "message": f"⚠️ No training metadata found at {metadata_path}"
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
        logger.info("🚀 Starting model retraining in background...")
        
        # Ejecutar script de reentrenamiento
        result = subprocess.run(
            ['python', 'app/retrain_model.py'],
            capture_output=True,
            text=True,
            timeout=1800  # 30 minutos máximo
        )
        
        if result.returncode == 0:
            logger.info("✅ Model retrained successfully")
            logger.info(f"Output: {result.stdout}")
            
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
        logger.info("🔓 Retrain lock released")


# === ENDPOINTS ADICIONALES ÚTILES ===

@router.get("/test")
async def test_endpoint():
    """
    **Endpoint de prueba simple**
    
    Útil para verificar que la API responde correctamente
    sin necesidad de autenticación.
    """
    return {
        "message": "✅ API funcionando correctamente",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "3.0.0"
    }


@router.get("/ping")
async def ping():
    """
    **Ping simple**
    
    Respuesta mínima para health checks externos
    """
    return {"status": "ok"}
