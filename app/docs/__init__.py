"""
Documentation Routes
Serve static HTML docs
"""
from fastapi import APIRouter
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter(prefix="/docs", tags=["Documentation"])

# Directorio de documentación
DOCS_DIR = Path(__file__).parent


@router.get("/retrain.html", include_in_schema=False)
async def retrain_page():
    """
    📄 Página de reentrenamiento manual del modelo ML
    
    Permite a los administradores reentrenar el modelo Naive Bayes
    con los datos de feedback acumulados.
    """
    html_path = DOCS_DIR / "retrain.html"
    
    if not html_path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Documentation not found")
    
    return FileResponse(html_path, media_type="text/html")


@router.get("/", include_in_schema=False)
async def docs_index():
    """
    📚 Índice de documentación
    """
    return {
        "message": "SpamGuard API Documentation",
        "version": "3.0.0",
        "available_docs": [
            {
                "title": "ML Retraining",
                "description": "Manual model retraining interface",
                "url": "/docs/retrain.html"
            }
        ]
    }
