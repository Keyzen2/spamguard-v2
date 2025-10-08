"""
Pydantic schemas para validación
"""
from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, Dict, List
from datetime import datetime

# ============================================
# ANALYZE ENDPOINT
# ============================================

class AnalyzeRequest(BaseModel):
    text: str = Field(
        ..., 
        min_length=1, 
        max_length=50000,
        description="Text to analyze"
    )
    context: Optional[Dict] = Field(
        None,
        description="Additional context (email, IP, etc.)"
    )
    metadata: Optional[Dict] = Field(
        None,
        description="Custom metadata"
    )
    
    @validator('text')
    def text_not_empty(cls, v):
        if not v or v.strip() == '':
            raise ValueError('Text cannot be empty')
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "text": "Buy cheap Viagra now! Click here!!!",
                "context": {
                    "email": "user@example.com",
                    "ip": "192.168.1.1"
                }
            }
        }

class AnalyzeResponse(BaseModel):
    is_spam: bool
    category: str
    confidence: float = Field(..., ge=0, le=1)
    risk_level: str
    scores: Dict[str, float]
    processing_time_ms: int
    flags: Optional[List[str]] = None
    request_id: str
    cached: bool = False
    
    # Usage info (v3.0 hybrid)
    usage: Optional[Dict] = None
    
    class Config:
        schema_extra = {
            "example": {
                "is_spam": True,
                "category": "spam",
                "confidence": 0.95,
                "risk_level": "high",
                "scores": {
                    "ham": 0.05,
                    "spam": 0.95,
                    "phishing": 0.0
                },
                "processing_time_ms": 145,
                "flags": ["excessive_caps", "urgency_words"],
                "request_id": "req_abc123",
                "cached": False,
                "usage": {
                    "current": 50,
                    "limit": 1000,
                    "remaining": 950
                }
            }
        }

# ============================================
# FEEDBACK ENDPOINT
# ============================================

class FeedbackRequest(BaseModel):
    request_id: Optional[str] = None
    text: str = Field(..., min_length=1, max_length=50000)
    predicted_category: str
    correct_category: str
    notes: Optional[str] = Field(None, max_length=1000)
    
    class Config:
        schema_extra = {
            "example": {
                "request_id": "req_abc123",
                "text": "This is a legitimate message",
                "predicted_category": "spam",
                "correct_category": "ham",
                "notes": "False positive"
            }
        }

class FeedbackResponse(BaseModel):
    success: bool
    message: str
    feedback_id: str

# ============================================
# STATS ENDPOINT
# ============================================

class StatsResponse(BaseModel):
    period_days: int
    total_requests: int
    spam_detected: int
    ham_detected: int
    phishing_detected: int
    daily_breakdown: Optional[List[Dict]] = None

# ============================================
# ACCOUNT ENDPOINT
# ============================================

class AccountInfoResponse(BaseModel):
    id: str
    email: str
    plan: str
    is_active: bool
    created_at: str
    usage: Dict

class UsageResponse(BaseModel):
    current_month: Dict
    limit: int
    percentage_used: float

# ============================================
# REGISTER ENDPOINT
# ============================================

class RegisterRequest(BaseModel):
    email: EmailStr
    site_url: Optional[str] = None
    name: Optional[str] = None
    
    class Config:
        schema_extra = {
            "example": {
                "email": "admin@example.com",
                "site_url": "https://example.com",
                "name": "My WordPress Site"
            }
        }

class RegisterResponse(BaseModel):
    success: bool
    message: str
    api_key: str
    user_id: str
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "message": "Account created successfully",
                "api_key": "sg_test_xxxxxxxxxxxxxxxx",
                "user_id": "uuid-here"
            }
        }
