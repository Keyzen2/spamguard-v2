from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from app.core.security import verify_api_key, get_current_user
from app.core.rate_limit import check_rate_limit
from app.ml.model import MLModelPredictor
from app.db.crud import log_request, update_usage
from pydantic import BaseModel, Field
from typing import Optional, Dict, List

router = APIRouter()

class AnalyzeRequest(BaseModel):
    text: str = Field(..., max_length=50000, description="Text to analyze")
    context: Optional[Dict] = Field(None, description="Additional context")
    metadata: Optional[Dict] = Field(None, description="Custom metadata")
    
    # Opciones
    return_explanation: bool = Field(False, description="Return SHAP explanation")
    language: Optional[str] = Field(None, description="Language code (auto-detect if null)")
    
    class Config:
        schema_extra = {
            "example": {
                "text": "Buy cheap Viagra now! Click here!!!",
                "context": {
                    "email": "user@example.com",
                    "ip": "192.168.1.1",
                    "user_agent": "Mozilla/5.0..."
                }
            }
        }

class AnalyzeResponse(BaseModel):
    is_spam: bool
    category: str  # ham, spam, phishing, ai_generated, fraud
    confidence: float
    scores: Dict[str, float]  # Score por cada categoría
    processing_time_ms: int
    
    # Opcional
    explanation: Optional[Dict] = None
    language_detected: Optional[str] = None
    risk_level: str  # low, medium, high, critical

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_text(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    user = Depends(get_current_user),
    rate_limit = Depends(check_rate_limit)
):
    """
    🤖 Analyze text for spam, phishing, AI-generated content, and fraud
    
    **Rate Limits:**
    - Free tier: 500 requests/month
    - Pro tier: 10,000 requests/month
    - Enterprise: Unlimited
    
    **Response Time:** < 200ms (p95)
    """
    import time
    start_time = time.time()
    
    # Load ML model (cached)
    predictor = MLModelPredictor()
    
    # Predict
    prediction = await predictor.predict(
        text=request.text,
        context=request.context,
        return_explanation=request.return_explanation
    )
    
    processing_time = int((time.time() - start_time) * 1000)
    
    # Log request asíncrono
    background_tasks.add_task(
        log_request,
        user_id=user.id,
        text=request.text,
        prediction=prediction,
        processing_time=processing_time
    )
    
    # Update usage counter
    background_tasks.add_task(update_usage, user.id)
    
    return AnalyzeResponse(
        is_spam=prediction['category'] != 'ham',
        category=prediction['category'],
        confidence=prediction['confidence'],
        scores=prediction['scores'],
        processing_time_ms=processing_time,
        explanation=prediction.get('explanation'),
        language_detected=prediction.get('language'),
        risk_level=prediction['risk_level']
    )
