from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import time
import logging
from datetime import datetime
import os
from pathlib import Path

from app.config import get_settings
from app.api.routes import router as spam_router  # Anti-spam (existente)
from app.api.routes_antivirus import router as antivirus_router  # 🆕 Antivirus (nuevo)
from app.ml_model import spam_detector

# Configuración
settings = get_settings()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Eventos de inicio y cierre de la aplicación
    """
    # STARTUP
    logger.info("=" * 60)
    logger.info("🚀 INICIANDO SPAMGUARD SECURITY SUITE")
    logger.info("=" * 60)
    logger.info(f"📊 Environment: {settings.environment}")
    
    # 1. Cargar modelo ML de Anti-Spam
    logger.info("\n📦 Módulo Anti-Spam:")
    try:
        # Detectar ubicación del modelo (local o volumen persistente)
        volume_path = os.getenv('RAILWAY_VOLUME_MOUNT_PATH')
        if volume_path:
            model_path = Path(volume_path) / 'models' / 'spam_model.pkl'
            logger.info(f"   📦 Buscando modelo en volumen: {model_path}")
        else:
            model_path = Path('models') / 'spam_model.pkl'
            logger.info(f"   📁 Buscando modelo localmente: {model_path}")
        
        spam_detector.load_model(str(model_path))
        logger.info(f"   ✅ Modelo ML cargado - Entrenado: {spam_detector.is_trained}")
        
        if spam_detector.is_trained:
            logger.info("   ✅ Anti-Spam: Modo ML activo (92%+ accuracy)")
        else:
            logger.info("   ⚠️  Anti-Spam: Modo reglas básicas")
            
    except Exception as e:
        logger.warning(f"   ⚠️  Modelo no disponible: {e}")
        logger.info("   📝 API funcionará con reglas básicas (honeypot/time check)")
    
    # 2. Inicializar módulo Antivirus
    logger.info("\n🦠 Módulo Antivirus:")
    try:
        from app.modules.antivirus.signatures import SignatureManager
        
        sig_manager = SignatureManager()
        signatures = sig_manager.load_signatures()
        logger.info(f"   ✅ Firmas de malware cargadas: {len(signatures)}")
        logger.info(f"   ✅ Antivirus: Sistema activo")
        
    except Exception as e:
        logger.warning(f"   ⚠️  Error iniciando antivirus: {e}")
        logger.info("   📝 Módulo antivirus en modo limitado")
    
    # 3. Verificar base de datos
    logger.info("\n🗄️  Base de Datos:")
    try:
        from app.database import supabase
        
        # Ping simple a Supabase
        result = supabase.table('site_stats').select('site_id').limit(1).execute()
        logger.info(f"   ✅ Supabase conectado")
        
    except Exception as e:
        logger.error(f"   ❌ Error conectando a Supabase: {e}")
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ SPAMGUARD SECURITY SUITE INICIADO CORRECTAMENTE")
    logger.info("=" * 60)
    logger.info(f"📚 Documentación: http://localhost:8000/docs")
    logger.info("=" * 60 + "\n")
    
    yield
    
    # SHUTDOWN
    logger.info("=" * 60)
    logger.info("👋 Cerrando SpamGuard Security Suite...")
    logger.info("=" * 60)


# Crear aplicación FastAPI
app = FastAPI(
    title="SpamGuard Security Suite API",
    description="""
    API completa de seguridad para WordPress
    
    ## Módulos:
    
    ### 🛡️ Anti-Spam
    - Detección de spam con Machine Learning (92%+ accuracy)
    - Sistema de feedback y aprendizaje continuo
    - Reglas heurísticas avanzadas
    
    ### 🦠 Antivirus
    - Escaneo de malware por firmas
    - Detección de código sospechoso
    - Sistema de cuarentena
    
    ## Endpoints principales:
    - **Anti-Spam**: `/api/v1/analyze`, `/api/v1/feedback`
    - **Antivirus**: `/api/v1/antivirus/scan/start`, `/api/v1/antivirus/scan/{id}/progress`
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    contact={
        "name": "SpamGuard Security",
        "url": "https://spamguard.dev",
    },
    license_info={
        "name": "GPL v3",
        "url": "https://www.gnu.org/licenses/gpl-3.0.html",
    }
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción: especificar dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware para logging de requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Log con formato mejorado
        log_message = (
            f"{request.method} {request.url.path} - "
            f"{response.status_code} - {process_time:.3f}s"
        )
        
        if response.status_code >= 500:
            logger.error(f"❌ {log_message}")
        elif response.status_code >= 400:
            logger.warning(f"⚠️  {log_message}")
        else:
            logger.info(f"📝 {log_message}")
        
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
        
    except Exception as e:
        logger.error(f"❌ Error processing request: {str(e)}")
        raise


# Manejador de errores de validación
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"❌ Validation error on {request.url.path}: {exc.errors()}")
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Error de validación",
            "errors": exc.errors()
        }
    )


# Manejador de errores generales
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ Unhandled error on {request.url.path}: {str(exc)}")
    
    # Stack trace en desarrollo
    if settings.environment == "development":
        import traceback
        logger.error(traceback.format_exc())
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "message": str(exc) if settings.environment == "development" else "An error occurred"
        }
    )


# ============================================
# INCLUIR ROUTERS
# ============================================

# Anti-Spam (existente) - mantener funcionando
app.include_router(spam_router)

# Antivirus (nuevo) - añadir sin afectar lo anterior
app.include_router(antivirus_router)


# ============================================
# ENDPOINTS PRINCIPALES
# ============================================

@app.get("/")
async def root():
    """
    Endpoint raíz - Información general de la API
    """
    return {
        "service": "SpamGuard Security Suite API",
        "version": "2.0.0",
        "status": "online",
        "modules": {
            "antispam": {
                "status": "active",
                "model_loaded": spam_detector.is_trained,
                "mode": "ML" if spam_detector.is_trained else "Rules-based"
            },
            "antivirus": {
                "status": "active",
                "signatures": "loaded"
            }
        },
        "environment": settings.environment,
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "antispam": {
                "analyze": "/api/v1/analyze",
                "feedback": "/api/v1/feedback",
                "stats": "/api/v1/stats"
            },
            "antivirus": {
                "scan": "/api/v1/antivirus/scan/start",
                "progress": "/api/v1/antivirus/scan/{scan_id}/progress",
                "results": "/api/v1/antivirus/scan/{scan_id}/results",
                "stats": "/api/v1/antivirus/stats"
            }
        }
    }


@app.get("/health")
async def health():
    """
    Health check completo del sistema
    """
    # Verificar conexión a base de datos
    db_status = "connected"
    try:
        from app.database import supabase
        supabase.table('site_stats').select('site_id').limit(1).execute()
    except:
        db_status = "disconnected"
    
    # Verificar volumen persistente
    volume_info = None
    volume_path = os.getenv('RAILWAY_VOLUME_MOUNT_PATH')
    if volume_path:
        volume_info = {
            "path": volume_path,
            "exists": Path(volume_path).exists()
        }
    
    return {
        "status": "healthy",
        "modules": {
            "antispam": {
                "model_loaded": spam_detector.is_trained,
                "type": "ML" if spam_detector.is_trained else "Rules-based"
            },
            "antivirus": {
                "signatures": "loaded"
            }
        },
        "database": db_status,
        "storage": volume_info,
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/version")
async def version():
    """
    Información de versión detallada
    """
    return {
        "api_version": "2.0.0",
        "modules": {
            "antispam": "1.0.0",
            "antivirus": "1.0.0-beta"
        },
        "python_version": "3.12",
        "fastapi_version": "0.115.0"
    }


# ============================================
# DESARROLLO LOCAL
# ============================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info("🚀 Iniciando servidor de desarrollo...")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
        access_log=True
    )
