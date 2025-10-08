"""
Feedback endpoint
"""
from fastapi import APIRouter, Depends, BackgroundTasks
from app.db.schemas import FeedbackRequest, FeedbackResponse
from app.core.security import verify_api_key
from app.db.crud import save_feedback
from datetime import datetime
import uuid

router = APIRouter()

@router.post("/feedback", response_model=FeedbackResponse, status_code=201)
async def submit_feedback(
    request: FeedbackRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(verify_api_key)
):
    """
    📝 Submit feedback to improve the model
    
    Help us improve by reporting:
    - False positives (spam marked as legitimate)
    - False negatives (legitimate marked as spam)
    
    Your feedback helps train better models for everyone!
    """
    feedback_id = f"fb_{uuid.uuid4().hex[:12]}"
    
    feedback_data = {
        'id': feedback_id,
        'user_id': user['user_id'],
        'site_id': None,  # v3.0: no usamos site_id
        'old_label': request.predicted_category,
        'new_label': request.correct_category,
        'processed': False,
        'created_at': datetime.now().isoformat()
    }
    
    # Guardar en background
    background_tasks.add_task(save_feedback, feedback_data)
    
    return FeedbackResponse(
        success=True,
        message="Thank you! Your feedback will help improve our model.",
        feedback_id=feedback_id
    )
