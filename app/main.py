"""
SpamGuard API - Main Application
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import time
import logging
from app.config import settings
from app.core.cache import init_redis
from app.ml.model import MLModelPredictor
from app.api.v1 import api_router

# Logging
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("🚀 Starting SpamGuard API...")
    
    # Initialize Redis
    init_redis()
    
    # Preload ML model
    try:
        MLModelPredictor.get_instance()
        logger.info("✅ ML Model preloaded")
    except Exception as e:
        logger.error(f"❌ Failed to load ML model: {str(e)}")
    
    logger.info("✅ SpamGuard API is ready!")
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down SpamGuard API...")

# Create FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Gzip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "details": exc.errors()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later."
        }
    )

# Health check
@app.get("/health", tags=["Health"])
async def health_check():
    """
    🏥 Health check endpoint
    
    Returns system status and version info
    """
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "model": {
            "loaded": MLModelPredictor._initialized,
            "device": str(MLModelPredictor.get_instance().device) if MLModelPredictor._initialized else "unknown"
        }
    }

# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """
    🏠 API Root
    """
    return {
        "message": "Welcome to SpamGuard API",
        "version": settings.VERSION,
        "docs": "/docs" if settings.DEBUG else "https://docs.spamguard.ai",
        "support": "https://spamguard.ai/support"
    }

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Startup message
@app.on_event("startup")
async def startup_message():
    logger.info("=" * 60)
    logger.info(f"  {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"  Environment: {settings.ENVIRONMENT}")
    logger.info(f"  Debug: {settings.DEBUG}")
    logger.info("=" * 60)
