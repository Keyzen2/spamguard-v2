from pydantic_settings import BaseSettings
from typing import List, Optional
import json

class Settings(BaseSettings):
    # Project
    PROJECT_NAME: str = "SpamGuard API"
    VERSION: str = "3.0.0"
    ENVIRONMENT: str = "production"
    
    # API Keys
    API_KEY_PREFIX: str = "sg"
    
    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    
    # Database
    DATABASE_URL: str
    
    # Security
    SECRET_KEY: str
    
    # CORS
    CORS_ORIGINS: List[str] = ["*"]
    
    # Redis (OPCIONAL)
    REDIS_URL: Optional[str] = None
    
    # ML Model
    MODEL_PATH: str = "ml/models/spam_model_v1"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from string or list"""
        if isinstance(self.CORS_ORIGINS, str):
            try:
                return json.loads(self.CORS_ORIGINS)
            except:
                return [origin.strip() for origin in self.CORS_ORIGINS.split(',') if origin.strip()]
        return self.CORS_ORIGINS
    
    class Config:
        env_file = ".env"
        case_sensitive = True

def get_settings() -> Settings:
    return Settings()

settings = get_settings()
