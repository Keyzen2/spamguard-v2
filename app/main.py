"""
SpamGuard API v3.0 Hybrid - Main Application
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
from app.ml.model import MLPredictor
from app.api.v1 import api_router

# Logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    logger.info("=" * 60)
    logger.info(f"🚀 Starting {settings.PROJECT_NAME}")
    logger.info(f"   Version: {settings.VERSION}")
    logger.info(f"   Environment: {settings.ENVIRONMENT}")
    logger.info("=" * 60)
    
    # Initialize cache (Redis optional)
    try:
        from app.core.cache import init_redis
        init_redis()
    except Exception as e:
        logger.warning(f"⚠️  Cache initialization warning: {e}")
        logger.info("   Using in-memory cache as fallback")
    
    # Preload ML model
    try:
        MLPredictor.get_instance()
        logger.info("✅ ML Model ready")
    except Exception as e:
        logger.error(f"❌ Failed to load ML model: {str(e)}")
        logger.warning("⚠️  Will use rule-based fallback")
    
    logger.info("✅ SpamGuard API is ready!")
    logger.info("=" * 60)
    
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
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Registration",
            "description": "Register and get your free API key"
        },
        {
            "name": "Analysis",
            "description": "Spam detection endpoints"
        },
        {
            "name": "Feedback",
            "description": "Submit feedback to improve the model"
        },
        {
            "name": "Statistics",
            "description": "Get your usage statistics"
        },
        {
            "name": "Account",
            "description": "Manage your account"
        }
    ]
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
    response.headers["X-Process-Time"] = f"{process_time:.3f}"
    response.headers["X-SpamGuard-Version"] = settings.VERSION
    return response

# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "Validation Error",
            "message": "The request contains invalid data",
            "details": exc.errors()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later.",
            "support": "support@spamguard.ai"
        }
    )

# Health check
@app.get("/health", tags=["Health"])
async def health_check():
    """
    🏥 Health check endpoint
    
    Returns system status and version info
    """
    ml_status = "loaded" if MLPredictor._initialized else "not_loaded"
    
    # Check cache status
    try:
        from app.core.cache import redis_client
        cache_status = "redis" if redis_client else "memory"
    except:
        cache_status = "memory"
    
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "model_status": ml_status,
        "cache_status": cache_status,
        "api_docs": "/docs" if settings.DEBUG else "https://docs.spamguard.ai"
    }

# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """
    🏠 API Root
    
    Welcome to SpamGuard API v3.0 Hybrid!
    """
    return {
        "message": "Welcome to SpamGuard API v3.0 Hybrid",
        "version": settings.VERSION,
        "description": "Free spam detection API powered by machine learning",
        "features": [
            "Spam detection",
            "Phishing detection",
            "1,000 free requests/month",
            "No credit card required"
        ],
        "docs": "/docs" if settings.DEBUG else "https://docs.spamguard.ai",
        "register": f"{settings.API_V1_STR}/register",
        "support": "support@spamguard.ai"
    }

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Custom 404 handler
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "error": "Not Found",
            "message": f"The endpoint {request.url.path} does not exist",
            "available_endpoints": {
                "docs": "/docs" if settings.DEBUG else "https://docs.spamguard.ai",
                "register": f"{settings.API_V1_STR}/register",
                "analyze": f"{settings.API_V1_STR}/analyze"
            }
        }
    )
