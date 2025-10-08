from supabase import create_client, Client
from app.config import get_settings
from typing import Optional, Dict, List
from datetime import datetime
import uuid

settings = get_settings()

# Cliente Supabase
supabase: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_key
)

class Database:
    """Clase para manejar todas las operaciones de base de datos"""
    
    @staticmethod
    def save_comment_analysis(  # ← SIN async
        site_id: str,
        comment_data: Dict,
        features: Dict,
        prediction: Dict
    ) -> str:
        """Guarda el análisis de un comentario"""
        
        comment_id = str(uuid.uuid4())
        
        data = {
            'id': comment_id,
            'site_id': site_id,
            'comment_content': comment_data.get('content'),
            'comment_author': comment_data.get('author'),
            'comment_author_email': comment_data.get('author_email'),
            'comment_author_ip': comment_data.get('author_ip'),
            'comment_author_url': comment_data.get('author_url'),
            'post_id': comment_data.get('post_id'),
            'features': features,
            'predicted_label': 'spam' if prediction['is_spam'] else 'ham',
            'prediction_confidence': prediction['confidence'],
            'user_agent': comment_data.get('user_agent'),
            'referer': comment_data.get('referer'),
            'created_at': datetime.utcnow().isoformat()
        }
        
        supabase.table('comments_analyzed').insert(data).execute()  # ← SIN await
        
        # Actualizar estadísticas
        Database.update_site_stats(site_id, prediction['is_spam'])  # ← SIN await
        
        return comment_id
    
    @staticmethod
    def update_site_stats(site_id: str, is_spam: bool):  # ← SIN async
        """Actualiza las estadísticas del sitio"""
        
        # Obtener stats actuales
        result = supabase.table('site_stats').select('*').eq('site_id', site_id).execute()
        
        if result.data:
            stats = result.data[0]
            update_data = {
                'total_analyzed': stats['total_analyzed'] + 1,
            }
            
            if is_spam:
                update_data['total_spam_blocked'] = stats['total_spam_blocked'] + 1
            else:
                update_data['total_ham_approved'] = stats['total_ham_approved'] + 1
            
            supabase.table('site_stats').update(update_data).eq('site_id', site_id).execute()
        else:
            # Crear nuevo registro
            new_stats = {
                'site_id': site_id,
                'total_analyzed': 1,
                'total_spam_blocked': 1 if is_spam else 0,
                'total_ham_approved': 0 if is_spam else 1,
                'api_key': Database.generate_api_key(),
                'created_at': datetime.utcnow().isoformat()
            }
            supabase.table('site_stats').insert(new_stats).execute()
    
    @staticmethod
    def validate_api_key(api_key: str) -> Optional[str]:  # ← SIN async
        """Valida una API key y retorna el site_id"""
        result = supabase.table('site_stats').select('site_id').eq('api_key', api_key).execute()
        
        if result.data:
            return result.data[0]['site_id']
        return None
    
    @staticmethod
    def save_feedback(comment_id: str, site_id: str, correct_label: str, old_label: str):  # ← SIN async
        """Guarda feedback del usuario"""
        
        feedback_data = {
            'comment_id': comment_id,
            'site_id': site_id,
            'old_label': old_label,
            'new_label': correct_label,
            'processed': False,
            'created_at': datetime.utcnow().isoformat()
        }
        
        supabase.table('feedback_queue').insert(feedback_data).execute()
        
        # Actualizar el comentario original
        supabase.table('comments_analyzed').update({
            'actual_label': correct_label
        }).eq('id', comment_id).execute()
    
    @staticmethod
    def get_site_statistics(site_id: str) -> Dict:  # ← SIN async
        """Obtiene estadísticas del sitio"""
        result = supabase.table('site_stats').select('*').eq('site_id', site_id).execute()
        
        if result.data:
            stats = result.data[0]
            
            total_analyzed = stats['total_analyzed']
            if total_analyzed > 0:
                feedback_result = supabase.table('comments_analyzed')\
                    .select('predicted_label, actual_label')\
                    .eq('site_id', site_id)\
                    .not_.is_('actual_label', 'null')\
                    .execute()
                
                if feedback_result.data:
                    correct = sum(
                        1 for item in feedback_result.data 
                        if item['predicted_label'] == item['actual_label']
                    )
                    accuracy = correct / len(feedback_result.data)
                else:
                    accuracy = None
            else:
                accuracy = None
            
            return {
                'total_analyzed': total_analyzed,
                'total_spam_blocked': stats['total_spam_blocked'],
                'total_ham_approved': stats['total_ham_approved'],
                'accuracy': accuracy,
                'last_retrain': stats.get('last_retrain'),
                'spam_block_rate': stats['total_spam_blocked'] / max(total_analyzed, 1)
            }
        
        return None
    
    @staticmethod
    def get_training_data(site_id: str, limit: int = 1000) -> List[Dict]:  # ← SIN async
        """Obtiene datos para reentrenamiento"""
        result = supabase.table('comments_analyzed')\
            .select('features, actual_label')\
            .eq('site_id', site_id)\
            .not_.is_('actual_label', 'null')\
            .limit(limit)\
            .execute()
        
        return result.data if result.data else []
    
    @staticmethod
    def generate_api_key() -> str:
        """Genera una nueva API key"""
        import secrets
        return f"sg_{secrets.token_urlsafe(32)}"
    
    @staticmethod
    def check_retrain_needed(site_id: str) -> bool:  # ← SIN async
        """Verifica si es necesario reentrenar el modelo"""
        result = supabase.table('feedback_queue')\
            .select('id', count='exact')\
            .eq('site_id', site_id)\
            .eq('processed', False)\
            .execute()
        
        pending_count = result.count if result.count else 0
        return pending_count >= settings.retrain_threshold
