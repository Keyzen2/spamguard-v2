"""
SpamGuard API v3.0 - Main Application
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

# ✅ Intentar importar ML router (puede no existir)
try:
    from app.api.routes_ml import router as ml_router
    ML_ROUTER_AVAILABLE = True
except ImportError:
    ML_ROUTER_AVAILABLE = False
    logging.warning("⚠️ routes_ml.py not found - ML endpoints disabled")

# ========================================
# CONFIGURACIÓN
# ========================================
settings = get_settings()

# Logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ========================================
# LIFESPAN EVENTS
# ========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión de eventos de inicio y cierre"""
    # STARTUP
    logger.info("=" * 60)
    logger.info("🚀 Starting SpamGuard API")
    logger.info(f"Version: {settings.VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info("=" * 60)
    
    # Cargar modelo ML
    try:
        logger.info("🤖 Loading ML Model...")
        detector = get_detector()
        logger.info(f"✅ ML Model ready - {detector.get_model_info()}")
    except Exception as e:
        logger.error(f"❌ Failed to load ML model: {str(e)}")
        logger.warning("⚠️ Will use rule-based fallback")
    
    logger.info("✅ SpamGuard API is ready!")
    logger.info("=" * 60)
    
    yield
    
    # SHUTDOWN
    logger.info("👋 Shutting down SpamGuard API...")

# ========================================
# CREATE APP
# ========================================

app = FastAPI(
    title="SpamGuard API",
    description="🛡️ Intelligent Spam Detection & Security",
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# ========================================
# MIDDLEWARE
# ========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.add_middleware(GZipMiddleware, minimum_size=1000)

@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add timing headers"""
    start_time = time.time()
    
    import uuid
    request_id = str(uuid.uuid4())
    
    logger.info(f"📥 {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.3f}"
    response.headers["X-Request-ID"] = request_id
    
    logger.info(f"📤 {request.method} {request.url.path} [{response.status_code}] [{process_time:.3f}s]")
    
    return response

# ========================================
# EXCEPTION HANDLERS
# ========================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "details": exc.errors()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ Error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc)
        }
    )

# ========================================
# ROOT ENDPOINTS
# ========================================

@app.get("/")
async def root():
    """API Root"""
    return {
        "message": "🛡️ SpamGuard API v3.0",
        "status": "operational",
        "version": settings.VERSION,
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "api": "/api/v1"
        }
    }

@app.get("/health")
async def health():
    """Health check"""
    try:
        from app.database import supabase
        db_status = "connected"
        try:
            supabase.table('site_stats').select('count').limit(1).execute()
        except:
            db_status = "error"
        
        return {
            "status": "healthy" if db_status == "connected" else "degraded",
            "version": settings.VERSION,
            "database": db_status
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@app.get("/ping")
async def ping():
    """Ping"""
    return {"status": "ok"}

# ========================================
# DOCUMENTACIÓN HTML
# ========================================

@app.get("/docs/retrain.html", response_class=HTMLResponse, include_in_schema=False)
async def retrain_docs():
    """Página de reentrenamiento ML"""
    html_file = Path(__file__).parent / "docs" / "retrain.html"
    
    if not html_file.exists():
        logger.warning(f"⚠️ HTML file not found: {html_file}")
        return HTMLResponse(
            content="<h1>404 - Documentation not found</h1><p>File: " + str(html_file) + "</p>",
            status_code=404
        )
    
    return FileResponse(html_file)

# ========================================
# INCLUIR ROUTERS
# ========================================

app.include_router(spam_router)

if ML_ROUTER_AVAILABLE:
    app.include_router(ml_router)
    logger.info("✅ ML router registered")
else:
    logger.warning("⚠️ ML router not available")

# ========================================
# MAIN
# ========================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
