"""
Main endpoint: Analyze text for spam, phishing, AI-generated content
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List
from app.core.security import verify_api_key, check_scope
from app.core.rate_limit import check_rate_limit, track_request
from app.ml.model import MLModelPredictor
from app.core.cache import cache_get, cache_set
from app.db.crud import log_api_request
import time
import hashlib
import json

router = APIRouter()

class AnalyzeRequest(BaseModel):
    text: str = Field(
        ..., 
        min_length=1, 
        max_length=50000,
        description="Text content to analyze"
    )
    context: Optional[Dict] = Field(
        None,
        description="Additional context (email, IP, user_agent, etc.)"
    )
    metadata: Optional[Dict] = Field(
        None,
        description="Custom metadata for your records"
    )
    options: Optional[Dict] = Field(
        None,
        description="Analysis options"
    )
    
    @validator('text')
    def text_not_empty(cls, v):
        if not v or v.strip() == '':
            raise ValueError('Text cannot be empty')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "text": "Congratulations! You've won $1,000,000! Click here to claim your prize now!",
                "context": {
                    "email": "user@example.com",
                    "ip": "192.168.1.100",
                    "user_agent": "Mozilla/5.0...",
                    "referer": "https://example.com"
                },
                "metadata": {
                    "form_id": "contact-form-1",
                    "post_id": 123
                },
                "options": {
                    "return_explanation": True,
                    "language": "en"
                }
            }
        }

class AnalyzeResponse(BaseModel):
    # Main result
    is_spam: bool = Field(..., description="True if spam detected")
    category: str = Field(..., description="Category: ham, spam, phishing, ai_generated, fraud")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score (0-1)")
    risk_level: str = Field(..., description="Risk level: low, medium, high, critical")
    
    # Detailed scores
    scores: Dict[str, float] = Field(..., description="Score for each category")
    
    # Performance
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    
    # Optional
    explanation: Optional[Dict] = Field(None, description="Explanation of prediction (if requested)")
    language_detected: Optional[str] = Field(None, description="Detected language code")
    flags: Optional[List[str]] = Field(None, description="Specific flags triggered")
    
    # Meta
    request_id: str = Field(..., description="Unique request ID")
    cached: bool = Field(False, description="Whether result was cached")
    
    class Config:
        schema_extra = {
            "example": {
                "is_spam": True,
                "category": "spam",
                "confidence": 0.95,
                "risk_level": "high",
                "scores": {
                    "ham": 0.02,
                    "spam": 0.95,
                    "phishing": 0.01,
                    "ai_generated": 0.01,
                    "fraud": 0.01
                },
                "processing_time_ms": 145,
                "flags": ["excessive_capitalization", "urgency_words", "money_references"],
                "request_id": "req_abc123",
                "cached": False
            }
        }

@router.post("/analyze", response_model=AnalyzeResponse, status_code=200)
async def analyze_text(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(check_rate_limit)
):
    """
    🤖 Analyze text for spam, phishing, AI-generated content, and fraud
    
    ## Rate Limits
    - **Free**: 500 requests/month
    - **Pro**: 10,000 requests/month  
    - **Business**: 100,000 requests/month
    - **Enterprise**: Unlimited
    
    ## Response Time
    - **Average**: 100-150ms
    - **P95**: < 250ms
    
    ## Categories
    - **ham**: Legitimate content
    - **spam**: Commercial spam
    - **phishing**: Phishing attempt
    - **ai_generated**: AI-generated content
    - **fraud**: Fraud/scam
    
    ## Risk Levels
    - **low**: Safe, no action needed
    - **medium**: Suspicious, review recommended
    - **high**: Likely malicious, block recommended
    - **critical**: Definite threat, immediate action required
    """
    import uuid
    
    start_time = time.time()
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    
    # Check cache (if enabled)
    cache_key = _generate_cache_key(request.text, request.context)
    cached_result = await cache_get(cache_key)
    
    if cached_result:
        cached_result['request_id'] = request_id
        cached_result['cached'] = True
        
        # Track request in background
        background_tasks.add_task(
            track_request,
            user['user_id'],
            user['api_key_id'],
            '/analyze'
        )
        
        return cached_result
    
    # Load ML model (singleton, loaded once)
    predictor = MLModelPredictor.get_instance()
    
    # Get options
    options = request.options or {}
    return_explanation = options.get('return_explanation', False)
    language = options.get('language', None)
    
    # Predict
    try:
        prediction = await predictor.predict(
            text=request.text,
            context=request.context,
            language=language,
            return_explanation=return_explanation
        )
    except Exception as e:
        # Log error
        print(f"ML Prediction error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing request. Please try again."
        )
    
    # Calculate processing time
    processing_time = int((time.time() - start_time) * 1000)
    
    # Build response
    response = AnalyzeResponse(
        is_spam=prediction['category'] != 'ham',
        category=prediction['category'],
        confidence=prediction['confidence'],
        risk_level=prediction['risk_level'],
        scores=prediction['scores'],
        processing_time_ms=processing_time,
        explanation=prediction.get('explanation'),
        language_detected=prediction.get('language'),
        flags=prediction.get('flags', []),
        request_id=request_id,
        cached=False
    )
    
    # Cache result (5 minutes)
    background_tasks.add_task(
        cache_set,
        cache_key,
        response.dict(exclude={'request_id', 'cached'}),
        ttl=300
    )
    
    # Track request
    background_tasks.add_task(
        track_request,
        user['user_id'],
        user['api_key_id'],
        '/analyze'
    )
    
    # Log detailed request
    background_tasks.add_task(
        log_api_request,
        user_id=user['user_id'],
        api_key_id=user['api_key_id'],
        endpoint='/api/v1/analyze',
        method='POST',
        text_length=len(request.text),
        context=request.context,
        prediction=prediction,
        processing_time_ms=processing_time,
        request_id=request_id
    )
    
    return response

def _generate_cache_key(text: str, context: Optional[Dict] = None) -> str:
    """Generate cache key from text and context"""
    data = {
        'text': text[:500],  # First 500 chars
        'context': context or {}
    }
    return f"analyze:{hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()}"


# Batch endpoint (analyze multiple texts at once)
class BatchAnalyzeRequest(BaseModel):
    items: List[AnalyzeRequest] = Field(..., max_items=100, description="Up to 100 items")
    
    @validator('items')
    def validate_items(cls, v):
        if len(v) > 100:
            raise ValueError('Maximum 100 items per batch')
        return v

class BatchAnalyzeResponse(BaseModel):
    results: List[AnalyzeResponse]
    total_items: int
    processing_time_ms: int

@router.post("/analyze/batch", response_model=BatchAnalyzeResponse)
async def analyze_batch(
    request: BatchAnalyzeRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(check_rate_limit)
):
    """
    🚀 Analyze multiple texts in a single request (up to 100)
    
    More efficient than individual requests.
    Each item counts as 1 request towards your limit.
    """
    start_time = time.time()
    
    results = []
    predictor = MLModelPredictor.get_instance()
    
    for item in request.items:
        # Analyze each item
        prediction = await predictor.predict(
            text=item.text,
            context=item.context
        )
        
        results.append(AnalyzeResponse(
            is_spam=prediction['category'] != 'ham',
            category=prediction['category'],
            confidence=prediction['confidence'],
            risk_level=prediction['risk_level'],
            scores=prediction['scores'],
            processing_time_ms=0,  # Individual time not tracked in batch
            request_id=f"req_batch_{len(results)}",
            cached=False
        ))
    
    processing_time = int((time.time() - start_time) * 1000)
    
    # Track all requests
    for _ in request.items:
        background_tasks.add_task(
            track_request,
            user['user_id'],
            user['api_key_id'],
            '/analyze/batch'
        )
    
    return BatchAnalyzeResponse(
        results=results,
        total_items=len(results),
        processing_time_ms=processing_time
    )
