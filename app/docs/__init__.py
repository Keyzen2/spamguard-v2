"""
Documentación estática
"""
from fastapi import APIRouter
from fastapi.responses import FileResponse
from pathlib import Path

router = APIRouter(prefix="/docs", tags=["Documentation"])

DOCS_DIR = Path(__file__).parent


@router.get("/retrain.html", include_in_schema=False)
async def retrain_docs():
    """
    Página de reentrenamiento manual
    """
    html_path = DOCS_DIR / "retrain.html"
    return FileResponse(html_path, media_type="text/html")
