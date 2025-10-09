"""
SpamGuard API v3.0 - Main Application
Unified spam detection and malware scanning API
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
from pathlib import Path
import time
import logging
from datetime import datetime

from app.config import get_settings
from app.ml_model import get_detector

# ========================================
# IMPORTAR ROUTERS
# ========================================
from app.api.routes import router as spam_router
from app.api.routes_ml import router as ml_router

# ========================================
# CONFIGURACIÓN
# ========================================
settings = get_settings()

# Logging configuration
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ========================================
# LIFESPAN EVENTS
# ========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gestión de eventos de inicio y cierre de la aplicación
    """
    # ============ STARTUP ============
    logger.info("=" * 60)
    logger.info("🚀 Starting SpamGuard API")
    logger.info(f"Version: {settings.VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info("=" * 60)
    
    # Cargar modelo ML
    try:
        logger.info("🤖 Loading ML Model...")
        detector = get_detector()
        logger.info(f"✅ ML Model ready - Type: {detector.get_model_info()['model_type']}")
    except Exception as e:
        logger.error(f"❌ Failed to load ML model: {str(e)}")
        logger.warning("⚠️ Will use rule-based fallback")
    
    logger.info("✅ SpamGuard API is ready!")
    logger.info("=" * 60)
    
    yield
    
    # ============ SHUTDOWN ============
    logger.info("👋 Shutting down SpamGuard API...")
    logger.info("=" * 60)

# ========================================
# CREATE FASTAPI APP
# ========================================

app = FastAPI(
    title="SpamGuard API",
    description="""
    🛡️ **SpamGuard API v3.0** - Intelligent Spam Detection & Malware Scanning
    
    ## Features
    
    * 🤖 **Machine Learning powered** spam detection
    * 🦠 **Malware scanning** for WordPress files
    * 📊 **Real-time statistics** and analytics
    * 🔄 **Continuous learning** from feedback
    * 🚀 **Fast & reliable** - 99.9% uptime
    
    ## Free Tier
    
    * 1,000 requests/month
    * No credit card required
    * Full feature access
    
    ## Getting Started
    
    1. Register your site: `POST /api/v1/register-site`
    2. Get your API key
    3. Start analyzing: `POST /api/v1/analyze`
    
    ## Support
    
    * 📧 Email: support@spamguard.app
    * 📖 Docs: https://docs.spamguard.app
    * 🐛 Issues: https://github.com/spamguard/api/issues
    """,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    contact={
        "name": "SpamGuard Support",
        "email": "support@spamguard.app",
        "url": "https://spamguard.app"
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    }
)

# ========================================
# MIDDLEWARE
# ========================================

# CORS - Permitir peticiones desde WordPress
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especifica los dominios
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-API-Key",
        "X-ML-Secret",
        "X-Requested-With"
    ],
    expose_headers=[
        "X-Process-Time",
        "X-SpamGuard-Version",
        "X-Rate-Limit-Remaining"
    ]
)

# Gzip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Añade headers y timing a todas las respuestas"""
    start_time = time.time()
    
    import uuid
    request_id = str(uuid.uuid4())
    
    logger.info(f"📥 {request.method} {request.url.path} [ID: {request_id[:8]}]")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    
    response.headers["X-Process-Time"] = f"{process_time:.3f}"
    response.headers["X-SpamGuard-Version"] = settings.VERSION
    response.headers["X-Request-ID"] = request_id
    
    logger.info(
        f"📤 {request.method} {request.url.path} "
        f"[{response.status_code}] [{process_time:.3f}s]"
    )
    
    return response

# ========================================
# EXCEPTION HANDLERS
# ========================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning(f"❌ Validation error on {request.url.path}: {exc.errors()}")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "message": "Los datos enviados no son válidos",
            "details": exc.errors(),
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ Unhandled exception on {request.url.path}: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "Ha ocurrido un error inesperado",
            "support": "support@spamguard.app",
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# ========================================
# ROOT ENDPOINTS
# ========================================

@app.get("/", tags=["Root"])
async def root():
    """🏠 API Root"""
    return {
        "message": "🛡️ Bienvenido a SpamGuard API v3.0",
        "tagline": "Protección inteligente contra spam con Machine Learning",
        "version": settings.VERSION,
        "status": "operational",
        "features": [
            "🤖 Detección de spam con ML (92%+ accuracy)",
            "📊 Estadísticas en tiempo real",
            "🔄 Aprendizaje continuo",
            "🚀 API rápida y confiable"
        ],
        "links": {
            "documentation": "/docs",
            "health": "/health",
            "api_info": "/api/v1",
            "ml_retrain": "/docs/retrain.html"
        }
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """🏥 Health Check"""
    try:
        detector = get_detector()
        model_info = detector.get_model_info()
        
        db_status = "connected"
        try:
            from app.database import supabase
            supabase.table('site_stats').select('count').limit(1).execute()
        except Exception as e:
            db_status = "error"
            logger.error(f"Database health check failed: {e}")
        
        is_healthy = db_status == "connected"
        
        return {
            "status": "healthy" if is_healthy else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "version": settings.VERSION,
            "environment": settings.ENVIRONMENT,
            "components": {
                "api": "operational",
                "database": db_status,
                "model": model_info
            }
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }

@app.get("/ping", tags=["Health"])
async def ping():
    """🏓 Ping"""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat()
    }

# ========================================
# DOCUMENTACIÓN HTML
# ========================================

@app.get("/docs/retrain.html", response_class=HTMLResponse, include_in_schema=False)
async def retrain_docs():
    """📄 Página de reentrenamiento ML"""
    html_file = Path(__file__).parent / "docs" / "retrain.html"
    
    if not html_file.exists():
        return HTMLResponse(
            content="<h1>404 - Documentation not found</h1>",
            status_code=404
        )
    
    return FileResponse(html_file)

# ========================================
# INCLUIR ROUTERS
# ========================================

app.include_router(spam_router)    # /api/v1/*
app.include_router(ml_router)      # /api/v1/ml/*

# ========================================
# MAIN (para desarrollo local)
# ========================================

if __name__ == "__main__":
    import uvicorn
    
    logger.info("🚀 Starting SpamGuard API in development mode...")
    logger.info("📖 API Docs: http://localhost:8000/docs")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
