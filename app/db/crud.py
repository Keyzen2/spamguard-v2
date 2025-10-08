"""
Database CRUD operations
"""
from supabase import create_client
from app.config import settings
from typing import Dict, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

async def log_api_request(
    user_id: str,
    api_key_id: str,
    endpoint: str,
    method: str,
    text_length: int,
    context: Optional[Dict],
    prediction: Dict,
    processing_time_ms: int,
    request_id: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    status_code: int = 200,
    error_message: Optional[str] = None
):
    """Log API request en base de datos"""
    try:
        supabase.table('api_requests').insert({
            'user_id': user_id,
            'api_key_id': api_key_id,
            'endpoint': endpoint,
            'method': method,
            'text_length': text_length,
            'context': context,
            'prediction': prediction,
            'processing_time_ms': processing_time_ms,
            'ip_address': ip_address,
            'user_agent': user_agent,
            'status_code': status_code,
            'error_message': error_message,
            'created_at': datetime.now().isoformat()
        }).execute()
    except Exception as e:
        logger.error(f"Error logging request: {str(e)}")

async def save_feedback(feedback_data: Dict):
    """Guardar feedback del usuario"""
    try:
        supabase.table('feedback_queue').insert(feedback_data).execute()
        logger.info(f"Feedback saved: {feedback_data.get('id')}")
    except Exception as e:
        logger.error(f"Error saving feedback: {str(e)}")

async def get_monthly_usage(user_id: str, year: int, month: int) -> int:
    """Obtener uso mensual del usuario"""
    try:
        response = supabase.table('monthly_usage')\
            .select('requests_count')\
            .eq('user_id', user_id)\
            .eq('year', year)\
            .eq('month', month)\
            .execute()
        
        if response.data:
            return response.data[0]['requests_count']
        return 0
    except Exception as e:
        logger.error(f"Error getting usage: {str(e)}")
        return 0

async def get_user_stats(user_id: str, period_days: int = 30) -> Dict:
    """Obtener estadísticas del usuario"""
    try:
        from datetime import timedelta
        start_date = datetime.now() - timedelta(days=period_days)
        
        response = supabase.table('api_requests')\
            .select('prediction')\
            .eq('user_id', user_id)\
            .gte('created_at', start_date.isoformat())\
            .execute()
        
        requests = response.data
        
        total = len(requests)
        spam_count = sum(1 for r in requests if r['prediction'].get('category') == 'spam')
        ham_count = sum(1 for r in requests if r['prediction'].get('category') == 'ham')
        phishing_count = sum(1 for r in requests if r['prediction'].get('category') == 'phishing')
        
        return {
            'total_requests': total,
            'spam_detected': spam_count,
            'ham_detected': ham_count,
            'phishing_detected': phishing_count,
            'period_days': period_days
        }
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        return {
            'total_requests': 0,
            'spam_detected': 0,
            'ham_detected': 0,
            'phishing_detected': 0,
            'period_days': period_days
        }
