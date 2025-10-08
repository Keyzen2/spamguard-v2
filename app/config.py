"""
Configuration settings for SpamGuard API
"""
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache

class Settings(BaseSettings):
    
    # API Info
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "SpamGuard API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "Spam, Phishing & AI-Generated Content Detection API"
    
    # Environment
    ENVIRONMENT: str = "development"  # development, staging, production
    DEBUG: bool = False
    
    # Security
    SECRET_KEY: str
    API_KEY_PREFIX: str = "sg"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Database
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    DATABASE_URL: str
    
    # Redis Cache
    REDIS_URL: Optional[str] = None
    CACHE_TTL: int = 300  # 5 minutes
    
    # ML Model
    MODEL_PATH: str = "ml/models/distilbert_spam_v1"
    MODEL_DEVICE: str = "cpu"  # cpu or cuda
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    
    # Plans & Limits
    PLAN_LIMITS: dict = {
        "free": 500,
        "pro": 10000,
        "business": 100000,
        "enterprise": 999999999
    }
    
    # Stripe (Billing)
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_PRICES: dict = {
        "pro": "price_xxx",  # Configurar en Stripe
        "business": "price_yyy"
    }
    
    # CORS
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://spamguard.ai",
        "https://app.spamguard.ai"
    ]
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    # Monitoring
    SENTRY_DSN: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
