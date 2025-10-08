"""
SpamGuard API v3.0 Hybrid - Configuration
Sin billing, todo gratis por ahora
"""
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    
    # API Info
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "SpamGuard API v3.0 Hybrid"
    VERSION: str = "3.0.0"
    DESCRIPTION: str = "ML-powered spam detection API (Free tier)"
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # Security
    SECRET_KEY: str
    API_KEY_PREFIX: str = "sg"
    
    # Database (Supabase)
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    DATABASE_URL: str
    
    # Redis Cache (opcional por ahora)
    REDIS_URL: str = None
    CACHE_TTL: int = 300  # 5 minutos
    
    # ML Model
    MODEL_PATH: str = "ml/models/spam_model_v1"
    MODEL_DEVICE: str = "cpu"
    
    # Rate Limiting (soft - no bloquea, solo avisa)
    RATE_LIMIT_ENABLED: bool = True
    MONTHLY_REQUEST_LIMIT: int = 1000  # Por usuario
    
    # CORS
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:8000",
        "*"  # Permitir todos por ahora (FREE)
    ]
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
