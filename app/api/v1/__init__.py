"""
API v1 Router
"""
from fastapi import APIRouter
from app.api.v1.endpoints import analyze, feedback, stats, account

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(analyze.router, prefix="/analyze", tags=["Analysis"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
api_router.include_router(stats.router, prefix="/stats", tags=["Statistics"])
api_router.include_router(account.router, prefix="/account", tags=["Account"])
