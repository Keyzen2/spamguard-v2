import re
from typing import Dict
from urllib.parse import urlparse
import hashlib
from datetime import datetime

class FeatureExtractor:
    """Extrae características relevantes de un comentario"""
    
    SPAM_KEYWORDS = [
        'viagra', 'cialis', 'pharmacy', 'casino', 'poker', 'lottery',
        'loan', 'mortgage', 'credit', 'earn money', 'work from home',
        'click here', 'buy now', 'limited offer', 'act now', 'call now',
        'free money', 'weight loss', 'bitcoin', 'crypto', 'investment',
        'million dollars', 'prince', 'inheritance', 'beneficiary',
        'congratulations', 'winner', 'prizes', 'gift card'
    ]
    
    SUSPICIOUS_DOMAINS = [
        'tempmail.com', 'guerrillamail.com', '10minutemail.com',
        'mailinator.com', 'throwaway.email', 'temp-mail.org',
        'sharklasers.com', 'guerrillamail.info'
    ]
    
    def __init__(self):
        self.suspicious_tlds = ['.ru', '.cn', '.tk', '.ml', '.ga', '.cf', '.gq']
    
    def extract(self, comment_data: Dict) -> Dict:
        """Extrae todas las características"""
        
        content = comment_data.get('content', '')
        author = comment_data.get('author', '')
        author_email = comment_data.get('author_email', '')
        author_url = comment_data.get('author_url', '')
        author_ip = comment_data.get('author_ip', '')
        user_agent = comment_data.get('user_agent', '')
        
        features = {}
        content_lower = content.lower()
        
        # === TEXTO ===
        features['text_length'] = len(content)
        words = content.split()
        features['word_count'] = len(words)
        features['avg_word_length'] = sum(len(w) for w in words) / max(len(words), 1)
        
        # URLs
        urls = re.findall(
            r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
            content
        )
        features['url_count'] = len(urls)
        features['has_url'] = len(urls) > 0
        features['url_to_text_ratio'] = len(''.join(urls)) / max(len(content), 1)
        
        if urls:
            domains = [urlparse(url).netloc for url in urls]
            features['unique_domains'] = len(set(domains))
            features['has_suspicious_tld'] = any(
                any(domain.endswith(tld) for tld in self.suspicious_tlds)
                for domain in domains
            )
        else:
            features['unique_domains'] = 0
            features['has_suspicious_tld'] = 0
        
        # Palabras spam
        spam_count = sum(1 for kw in self.SPAM_KEYWORDS if kw in content_lower)
        features['spam_keyword_count'] = spam_count
        features['spam_keyword_density'] = spam_count / max(len(words), 1)
        
        # Caracteres
        features['special_char_ratio'] = len(re.findall(r'[^a-zA-Z0-9\s]', content)) / max(len(content), 1)
        features['uppercase_ratio'] = sum(1 for c in content if c.isupper()) / max(len(content), 1)
        features['digit_ratio'] = sum(1 for c in content if c.isdigit()) / max(len(content), 1)
        features['exclamation_count'] = content.count('!')
        features['question_count'] = content.count('?')
        features['has_html'] = bool(re.search(r'<[^>]+>', content))
        
        # Palabras repetidas
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        features['max_word_repetition'] = max(word_freq.values()) if word_freq else 0
        
        # === AUTOR ===
        features['author_length'] = len(author)
        features['author_has_numbers'] = bool(re.search(r'\d', author))
        features['author_all_caps'] = author.isupper() if author else False
        features['author_is_short'] = len(author) < 3
        
        # Email
        if author_email:
            email_parts = author_email.split('@')
            if len(email_parts) == 2:
                email_domain = email_parts[1]
                features['email_domain_suspicious'] = email_domain in self.SUSPICIOUS_DOMAINS
                features['email_has_numbers'] = bool(re.search(r'\d', email_parts[0]))
                features['email_length'] = len(author_email)
            else:
                features['email_domain_suspicious'] = True
                features['email_has_numbers'] = False
                features['email_length'] = 0
        else:
            features['email_domain_suspicious'] = False
            features['email_has_numbers'] = False
            features['email_length'] = 0
        
        # URL del autor
        if author_url:
            features['has_author_url'] = 1
            try:
                author_domain = urlparse(author_url).netloc
                features['author_url_suspicious'] = any(
                    author_domain.endswith(tld) for tld in self.suspicious_tlds
                )
            except:
                features['author_url_suspicious'] = True
        else:
            features['has_author_url'] = 0
            features['author_url_suspicious'] = False
        
        # === COMPORTAMIENTO ===
        hour = datetime.now().hour
        features['hour_of_day'] = hour
        features['is_night_time'] = 1 if (hour < 6 or hour > 23) else 0
        features['is_weekend'] = 1 if datetime.now().weekday() >= 5 else 0
        
        # User agent
        if user_agent:
            features['has_user_agent'] = 1
            features['is_bot'] = 1 if re.search(r'bot|crawler|spider|scraper', user_agent.lower()) else 0
        else:
            features['has_user_agent'] = 0
            features['is_bot'] = 0
        
        # Convertir booleanos a int para el modelo
        for key, value in features.items():
            if isinstance(value, bool):
                features[key] = 1 if value else 0
        
        return features

def extract_features(comment_data: Dict) -> Dict:
    """Función helper para extraer características"""
    extractor = FeatureExtractor()
    return extractor.extract(comment_data)
