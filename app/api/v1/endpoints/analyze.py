"""
Analyze endpoint - Main spam detection
"""
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Request
from app.db.schemas import AnalyzeRequest, AnalyzeResponse
from app.core.security import verify_api_key
from app.core.rate_limit import check_rate_limit, track_request
from app.core.cache import cache_get, cache_set
from app.ml.model import MLPredictor
from app.db.crud import log_api_request
import time
import hashlib
import json
import uuid

router = APIRouter()

@router.post("/analyze", response_model=AnalyzeResponse, status_code=200)
async def analyze_text(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
    user: dict = Depends(check_rate_limit)
):
    """
    🤖 Analyze text for spam detection
    
    Detects:
    - Commercial spam
    - Phishing attempts
    - Suspicious content
    
    ## Rate Limits (v3.0 Hybrid - FREE)
    - 1,000 requests/month per account
    - Soft limit (no blocking, just warnings)
    
    ## Response Time
    - Average: 50-100ms
    - P95: < 200ms
    """
    start_time = time.time()
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    
    # 1. Check cache
    cache_key = _generate_cache_key(request.text, request.context)
    cached_result = await cache_get(cache_key)
    
    if cached_result:
        cached_result['request_id'] = request_id
        cached_result['cached'] = True
        cached_result['usage'] = user['usage']
        
        # Track en background
        background_tasks.add_task(
            track_request,
            user['user_id'],
            user['api_key_id'],
            '/analyze'
        )
        
        return AnalyzeResponse(**cached_result)
    
    # 2. Predict con ML
    try:
        predictor = MLPredictor.get_instance()
        prediction = await predictor.predict(
            text=request.text,
            context=request.context
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error processing request"
        )
    
    # 3. Calcular tiempo
    processing_time = int((time.time() - start_time) * 1000)
    
    # 4. Build response
    response_data = {
        'is_spam': prediction['category'] != 'ham',
        'category': prediction['category'],
        'confidence': prediction['confidence'],
        'risk_level': prediction['risk_level'],
        'scores': prediction['scores'],
        'processing_time_ms': processing_time,
        'flags': prediction.get('flags', []),
        'request_id': request_id,
        'cached': False,
        'usage': user['usage']  # v3.0 hybrid: mostrar uso
    }
    
    # 5. Cache result
    background_tasks.add_task(
        cache_set,
        cache_key,
        response_data,
        300  # 5 minutos
    )
    
    # 6. Track request
    background_tasks.add_task(
        track_request,
        user['user_id'],
        user['api_key_id'],
        '/analyze'
    )
    
    # 7. Log detallado
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
        request_id=request_id,
        ip_address=http_request.client.host if http_request.client else None,
        user_agent=http_request.headers.get('user-agent')
    )
    
    return AnalyzeResponse(**response_data)

def _generate_cache_key(text: str, context: dict = None) -> str:
    """Generar cache key único"""
    data = {
        'text': text[:500],
        'context': context or {}
    }
    return f"analyze:{hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()}"
