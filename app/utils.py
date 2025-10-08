from typing import Dict, Optional
import hashlib
import re
from datetime import datetime, timedelta

def hash_string(text: str, length: int = 8) -> str:
    """Genera un hash corto de un string para privacidad"""
    return hashlib.md5(text.encode()).hexdigest()[:length]

def is_valid_email(email: str) -> bool:
    """Valida formato de email"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def is_valid_url(url: str) -> bool:
    """Valida formato de URL"""
    pattern = r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return bool(re.match(pattern, url))

def sanitize_input(text: str, max_length: int = 10000) -> str:
    """Sanitiza input del usuario"""
    if not text:
        return ""
    
    # Limitar longitud
    text = text[:max_length]
    
    # Remover caracteres nulos
    text = text.replace('\x00', '')
    
    return text.strip()

def calculate_spam_score_explanation(features: Dict, is_spam: bool, confidence: float) -> Dict:
    """Genera una explicación detallada del score de spam"""
    
    explanation = {
        'verdict': 'SPAM' if is_spam else 'LEGÍTIMO',
        'confidence_percentage': round(confidence * 100, 2),
        'risk_level': 'high' if confidence > 0.8 else 'medium' if confidence > 0.5 else 'low',
        'signals': []
    }
    
    # Señales positivas (spam)
    if features.get('spam_keyword_count', 0) > 0:
        explanation['signals'].append({
            'type': 'negative',
            'description': f"Contiene {features['spam_keyword_count']} palabras típicas de spam",
            'impact': 'high'
        })
    
    if features.get('url_count', 0) > 3:
        explanation['signals'].append({
            'type': 'negative',
            'description': f"Exceso de enlaces ({features['url_count']})",
            'impact': 'high'
        })
    
    if features.get('has_suspicious_tld', 0):
        explanation['signals'].append({
            'type': 'negative',
            'description': "Dominios con extensiones sospechosas",
            'impact': 'medium'
        })
    
    if features.get('email_domain_suspicious', 0):
        explanation['signals'].append({
            'type': 'negative',
            'description': "Email de servicio temporal",
            'impact': 'medium'
        })
    
    if features.get('is_bot', 0):
        explanation['signals'].append({
            'type': 'negative',
            'description': "User-agent identificado como bot",
            'impact': 'high'
        })
    
    if features.get('uppercase_ratio', 0) > 0.5:
        explanation['signals'].append({
            'type': 'negative',
            'description': f"Exceso de mayúsculas ({round(features['uppercase_ratio']*100)}%)",
            'impact': 'low'
        })
    
    # Señales negativas (legítimo)
    if features.get('text_length', 0) > 100 and features.get('url_count', 0) == 0:
        explanation['signals'].append({
            'type': 'positive',
            'description': "Comentario sustancial sin enlaces promocionales",
            'impact': 'medium'
        })
    
    if not features.get('spam_keyword_count', 0) and features.get('word_count', 0) > 10:
        explanation['signals'].append({
            'type': 'positive',
            'description': "Contenido natural sin palabras spam",
            'impact': 'medium'
        })
    
    return explanation

def format_datetime(dt: datetime) -> str:
    """Formatea datetime a string ISO"""
    return dt.isoformat()

def parse_datetime(dt_string: str) -> Optional[datetime]:
    """Parsea string ISO a datetime"""
    try:
        return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
    except:
        return None

def get_time_ago(dt: datetime) -> str:
    """Retorna tiempo transcurrido en formato legible"""
    now = datetime.utcnow()
    diff = now - dt
    
    if diff.days > 365:
        years = diff.days // 365
        return f"hace {years} año{'s' if years > 1 else ''}"
    elif diff.days > 30:
        months = diff.days // 30
        return f"hace {months} mes{'es' if months > 1 else ''}"
    elif diff.days > 0:
        return f"hace {diff.days} día{'s' if diff.days > 1 else ''}"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"hace {hours} hora{'s' if hours > 1 else ''}"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"hace {minutes} minuto{'s' if minutes > 1 else ''}"
    else:
        return "hace unos segundos"

class RateLimiter:
    """Rate limiter simple en memoria"""
    
    def __init__(self):
        self.requests = {}
    
    def is_allowed(self, identifier: str, max_requests: int = 100, window_seconds: int = 3600) -> bool:
        """
        Verifica si una request está permitida
        
        Args:
            identifier: IP, API key, etc.
            max_requests: Máximo de requests en la ventana
            window_seconds: Ventana de tiempo en segundos
        """
        now = datetime.utcnow()
        
        if identifier not in self.requests:
            self.requests[identifier] = []
        
        # Limpiar requests antiguas
        cutoff = now - timedelta(seconds=window_seconds)
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if req_time > cutoff
        ]
        
        # Verificar límite
        if len(self.requests[identifier]) >= max_requests:
            return False
        
        # Agregar nueva request
        self.requests[identifier].append(now)
        return True
    
    def get_remaining(self, identifier: str, max_requests: int = 100) -> int:
        """Retorna requests restantes"""
        if identifier not in self.requests:
            return max_requests
        return max(0, max_requests - len(self.requests[identifier]))

# Instancia global del rate limiter
rate_limiter = RateLimiter()
