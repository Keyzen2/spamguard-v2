from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_key: str
    supabase_service_key: str
    
    # API
    api_version: str = "v1"
    environment: str = "production"
    debug: bool = False
    
    # ML
    ml_model_path: str = "models/"
    retrain_threshold: int = 100
    min_samples_for_retrain: int = 50
    
    # Redis
    redis_url: Optional[str] = None
    
    # Admin (para endpoints sensibles)
    admin_secret: str = "tu_clave_super_secreta_aqui_123456"
    
    # Admin API Key (NUEVA - para reentrenamiento)
    admin_api_key: str = ""  # Se configura en Railway como variable de entorno
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": 'utf-8',
        "case_sensitive": False,
        "protected_namespaces": ('settings_',)
    }

@lru_cache()
def get_settings():
    return Settings()
