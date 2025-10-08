"""
API v1 Router
"""
from fastapi import APIRouter
from app.api.v1.endpoints import register, analyze, feedback, stats, account

api_router = APIRouter()

# Include all routers
api_router.include_router(register.router, tags=["Registration"])
api_router.include_router(analyze.router, tags=["Analysis"])
api_router.include_router(feedback.router, tags=["Feedback"])
api_router.include_router(stats.router, tags=["Statistics"])
api_router.include_router(account.router, tags=["Account"])
