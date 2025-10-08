"""
Text preprocessing para ML
"""
import re
import html
from typing import Optional

def preprocess_text(text: str, aggressive: bool = False) -> str:
    """
    Preprocesar texto para ML
    
    Args:
        text: Texto raw
        aggressive: Si True, hace limpieza más agresiva
    
    Returns:
        Texto limpio
    """
    # 1. Decode HTML entities
    text = html.unescape(text)
    
    # 2. Lowercase
    text = text.lower()
    
    # 3. Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # 4. Remove zero-width characters
    text = re.sub(r'[\u200B-\u200D\uFEFF]', '', text)
    
    if aggressive:
        # 5. Normalize URLs
        text = re.sub(r'https?://[^\s]+', '[URL]', text)
        
        # 6. Normalize emails
        text = re.sub(r'\S+@\S+', '[EMAIL]', text)
        
        # 7. Normalize phone numbers
        text = re.sub(r'\+?\d[\d\s\-\(\)]{7,}\d', '[PHONE]', text)
        
        # 8. Remove excessive punctuation
        text = re.sub(r'([!?.]){2,}', r'\1', text)
        
        # 9. Remove numbers
        text = re.sub(r'\d+', '[NUM]', text)
    
    # 10. Strip
    text = text.strip()
    
    return text

def tokenize_simple(text: str) -> list:
    """Tokenización simple por espacios"""
    return text.split()

def remove_stopwords(tokens: list, language: str = 'en') -> list:
    """
    Remover stopwords
    
    Args:
        tokens: Lista de tokens
        language: Idioma (en, es)
    
    Returns:
        Tokens sin stopwords
    """
    stopwords = {
        'en': {
            'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'can', 'a', 'an', 'and',
            'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'as', 'this', 'that', 'these', 'those'
        },
        'es': {
            'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
            'y', 'o', 'pero', 'de', 'del', 'en', 'a', 'al', 'por',
            'para', 'con', 'sin', 'sobre', 'es', 'son', 'está', 'están',
            'ser', 'estar', 'tener', 'hacer', 'poder', 'este', 'esta',
            'estos', 'estas', 'ese', 'esa', 'esos', 'esas'
        }
    }
    
    stops = stopwords.get(language, stopwords['en'])
    return [token for token in tokens if token.lower() not in stops]
