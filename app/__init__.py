"""
SpamGuard API v3.0
Backend API for spam detection and security
"""
import logging
import sys
from pathlib import Path

__version__ = "3.0.0"

# Configurar logging básico
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Logger para la aplicación
logger = logging.getLogger('spamguard')

# Información de inicio
logger.info(f"🚀 SpamGuard API v{__version__} initialized")

# Verificar directorio de modelos
MODELS_DIR = Path('/data/models')
if MODELS_DIR.exists():
    logger.info(f"📦 Models directory found: {MODELS_DIR}")
else:
    logger.warning(f"⚠️ Models directory not found: {MODELS_DIR}")
