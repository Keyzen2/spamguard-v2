"""
Stats endpoint
"""
from fastapi import APIRouter, Depends, Query
from app.db.schemas import StatsResponse
from app.core.security import verify_api_key
from app.db.crud import get_user_stats

router = APIRouter()

@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    period: int = Query(30, ge=1, le=365, description="Days to analyze"),
    user: dict = Depends(verify_api_key)
):
    """
    📊 Get your usage statistics
    
    Returns detailed stats for the specified period.
    
    ## Periods
    - Default: 30 days
    - Min: 1 day
    - Max: 365 days
    """
    stats = await get_user_stats(user['user_id'], period)
    
    return StatsResponse(
        period_days=period,
        total_requests=stats['total_requests'],
        spam_detected=stats['spam_detected'],
        ham_detected=stats['ham_detected'],
        phishing_detected=stats['phishing_detected']
    )
