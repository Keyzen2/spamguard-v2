"""
Stats endpoint: Get usage statistics
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from app.core.security import verify_api_key
from supabase import create_client
from app.config import settings
from datetime import datetime, timedelta

router = APIRouter()
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

class StatsResponse(BaseModel):
    period: str
    total_requests: int
    spam_detected: int
    ham_detected: int
    phishing_detected: int
    ai_generated_detected: int
    fraud_detected: int
    accuracy_rate: Optional[float] = None
    
    # By day (for charts)
    daily_breakdown: Optional[List[Dict]] = None

@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    period: str = Query('30d', regex='^(7d|30d|90d|1y|all)$'),
    include_daily: bool = Query(False, description="Include daily breakdown"),
    user: dict = Depends(verify_api_key)
):
    """
    📊 Get your usage statistics
    
    ## Periods
    - **7d**: Last 7 days
    - **30d**: Last 30 days (default)
    - **90d**: Last 90 days
    - **1y**: Last year
    - **all**: All time
    """
    user_id = user['user_id']
    
    # Calculate date range
    now = datetime.now()
    if period == '7d':
        start_date = now - timedelta(days=7)
    elif period == '30d':
        start_date = now - timedelta(days=30)
    elif period == '90d':
        start_date = now - timedelta(days=90)
    elif period == '1y':
        start_date = now - timedelta(days=365)
    else:  # all
        start_date = datetime(2020, 1, 1)
    
    # Query requests
    response = supabase.table('api_requests')\
        .select('prediction, created_at')\
        .eq('user_id', user_id)\
        .gte('created_at', start_date.isoformat())\
        .execute()
    
    requests = response.data
    
    # Calculate stats
    total_requests = len(requests)
    spam_count = sum(1 for r in requests if r['prediction'].get('category') == 'spam')
    ham_count = sum(1 for r in requests if r['prediction'].get('category') == 'ham')
    phishing_count = sum(1 for r in requests if r['prediction'].get('category') == 'phishing')
    ai_gen_count = sum(1 for r in requests if r['prediction'].get('category') == 'ai_generated')
    fraud_count = sum(1 for r in requests if r['prediction'].get('category') == 'fraud')
    
    # Daily breakdown (if requested)
    daily_breakdown = None
    if include_daily:
        daily_breakdown = _calculate_daily_breakdown(requests, start_date, now)
    
    return StatsResponse(
        period=period,
        total_requests=total_requests,
        spam_detected=spam_count,
        ham_detected=ham_count,
        phishing_detected=phishing_count,
        ai_generated_detected=ai_gen_count,
        fraud_detected=fraud_count,
        daily_breakdown=daily_breakdown
    )

def _calculate_daily_breakdown(requests: List, start_date: datetime, end_date: datetime) -> List[Dict]:
    """Calculate daily breakdown for charts"""
    from collections import defaultdict
    
    daily = defaultdict(lambda: {'spam': 0, 'ham': 0, 'phishing': 0, 'ai_generated': 0, 'fraud': 0})
    
    for req in requests:
        date = datetime.fromisoformat(req['created_at']).date()
        category = req['prediction'].get('category', 'unknown')
        if category in daily[date]:
            daily[date][category] += 1
    
    # Fill missing dates
    result = []
    current = start_date.date()
    while current <= end_date.date():
        result.append({
            'date': current.isoformat(),
            **daily[current]
        })
        current += timedelta(days=1)
    
    return result
