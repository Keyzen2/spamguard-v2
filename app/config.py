"""
Configuration settings for SpamGuard API
"""
from pydantic_settings import BaseSettings
from typing import List, Optional
import os


class Settings(BaseSettings):
    # Project
    PROJECT_NAME: str = "SpamGuard API"
    VERSION: str = "3.0.0"
    DESCRIPTION: str = "Free spam detection API powered by machine learning"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # API
    API_V1_STR: str = "/api/v1"
    
    # API Keys
    API_KEY_PREFIX: str = "sg"
    
    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    
    # Database
    DATABASE_URL: str = ""
    
    # Security
    SECRET_KEY: str
    ADMIN_API_KEY: str = ""  # ← MAYÚSCULAS con default vacío
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    
    # Redis (OPCIONAL)
    REDIS_URL: Optional[str] = None
    
    # ML Model
    MODEL_PATH: str = "ml/models/spam_model_v1"
    
    class Config:
        env_file = ".env"
        case_sensitive = False  # ← CAMBIAR A False para mayor compatibilidad


def get_settings() -> Settings:
    return Settings()


settings = get_settings()
