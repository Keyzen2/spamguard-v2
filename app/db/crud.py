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
    """Log API request to database"""
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
    """Save user feedback"""
    try:
        supabase.table('feedback_queue').insert(feedback_data).execute()
    except Exception as e:
        logger.error(f"Error saving feedback: {str(e)}")

async def get_user_by_api_key(api_key_hash: str) -> Optional[Dict]:
    """Get user by API key hash"""
    try:
        response = supabase.table('api_keys')\
            .select('*, api_users(*)')\
            .eq('key_hash', api_key_hash)\
            .eq('is_active', True)\
            .execute()
        
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error getting user: {str(e)}")
        return None

async def get_monthly_usage(user_id: str, year: int, month: int) -> int:
    """Get user's monthly usage"""
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

async def create_user(email: str, password_hash: str, plan: str = 'free') -> Optional[Dict]:
    """Create new user"""
    try:
        response = supabase.table('api_users').insert({
            'email': email,
            'password_hash': password_hash,
            'plan': plan,
            'is_active': True,
            'email_verified': False,
            'created_at': datetime.now().isoformat()
        }).execute()
        
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        return None

async def update_user_plan(user_id: str, plan: str, stripe_subscription_id: Optional[str] = None):
    """Update user's plan"""
    try:
        data = {'plan': plan}
        if stripe_subscription_id:
            data['stripe_subscription_id'] = stripe_subscription_id
        
        supabase.table('api_users')\
            .update(data)\
            .eq('id', user_id)\
            .execute()
    except Exception as e:
        logger.error(f"Error updating plan: {str(e)}")

async def get_webhooks_for_user(user_id: str, event_type: str) -> List[Dict]:
    """Get active webhooks for user and event type"""
    try:
        response = supabase.table('webhooks')\
            .select('*')\
            .eq('user_id', user_id)\
            .eq('is_active', True)\
            .contains('events', [event_type])\
            .execute()
        
        return response.data
    except Exception as e:
        logger.error(f"Error getting webhooks: {str(e)}")
        return []

async def trigger_webhooks(user_id: str, event_type: str, payload: Dict):
    """Trigger webhooks for an event"""
    webhooks = await get_webhooks_for_user(user_id, event_type)
    
    for webhook in webhooks:
        try:
            import httpx
            import hmac
            import hashlib
            
            # Sign payload
            signature = hmac.new(
                webhook['secret'].encode() if webhook.get('secret') else b'',
                json.dumps(payload).encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Send webhook
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    webhook['url'],
                    json=payload,
                    headers={
                        'X-SpamGuard-Signature': signature,
                        'X-SpamGuard-Event': event_type
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    # Update success count
                    supabase.table('webhooks')\
                        .update({
                            'last_triggered_at': datetime.now().isoformat(),
                            'success_count': webhook['success_count'] + 1
                        })\
                        .eq('id', webhook['id'])\
                        .execute()
                else:
                    # Update failure count
                    supabase.table('webhooks')\
                        .update({
                            'failure_count': webhook['failure_count'] + 1
                        })\
                        .eq('id', webhook['id'])\
                        .execute()
                    
        except Exception as e:
            logger.error(f"Error triggering webhook {webhook['id']}: {str(e)}")
