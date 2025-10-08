"""
Feedback endpoint: Improve model with user corrections
"""
from fastapi import APIRouter, Depends, BackgroundTasks, status
from pydantic import BaseModel, Field
from typing import Optional
from app.core.security import verify_api_key
from app.db.crud import save_feedback
from datetime import datetime

router = APIRouter()

class FeedbackRequest(BaseModel):
    request_id: Optional[str] = Field(None, description="Original request ID (if available)")
    text: str = Field(..., min_length=1, max_length=50000)
    predicted_category: str = Field(..., description="What we predicted")
    correct_category: str = Field(..., description="What it actually is")
    confidence: Optional[float] = Field(None, ge=0, le=1)
    notes: Optional[str] = Field(None, max_length=1000, description="Additional notes")
    
    class Config:
        schema_extra = {
            "example": {
                "request_id": "req_abc123",
                "text": "This is a legitimate message",
                "predicted_category": "spam",
                "correct_category": "ham",
                "notes": "False positive - this was from a real customer"
            }
        }

class FeedbackResponse(BaseModel):
    success: bool
    message: str
    feedback_id: str

@router.post("/feedback", response_model=FeedbackResponse, status_code=201)
async def submit_feedback(
    request: FeedbackRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(verify_api_key)
):
    """
    📝 Submit feedback to improve the model
    
    Help us improve by reporting false positives/negatives.
    Your feedback is used to retrain the model periodically.
    
    ## Categories
    - ham
    - spam
    - phishing
    - ai_generated
    - fraud
    """
    import uuid
    
    feedback_id = f"fb_{uuid.uuid4().hex[:12]}"
    
    # Save feedback
    feedback_data = {
        'id': feedback_id,
        'user_id': user['user_id'],
        'request_id': request.request_id,
        'text': request.text,
        'predicted_category': request.predicted_category,
        'correct_category': request.correct_category,
        'confidence': request.confidence,
        'notes': request.notes,
        'created_at': datetime.now().isoformat()
    }
    
    background_tasks.add_task(save_feedback, feedback_data)
    
    return FeedbackResponse(
        success=True,
        message="Thank you for your feedback! It will help improve our model.",
        feedback_id=feedback_id
    )
