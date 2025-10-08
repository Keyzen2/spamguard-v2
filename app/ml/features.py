"""
Feature extraction para spam detection
"""
import re
from typing import Dict, Optional
from urllib.parse import urlparse

def extract_features(text: str, context: Optional[Dict] = None) -> Dict:
    """
    Extraer features rule-based del texto
    
    Returns:
        Dict con features numéricas y booleanas
    """
    features = {}
    
    # ============================================
    # TEXT STATISTICS
    # ============================================
    features['length'] = len(text)
    features['word_count'] = len(text.split())
    features['avg_word_length'] = sum(len(word) for word in text.split()) / max(len(text.split()), 1)
    
    # ============================================
    # CAPITALIZATION
    # ============================================
    caps_count = sum(1 for c in text if c.isupper())
    features['excessive_caps_ratio'] = caps_count / len(text) if len(text) > 0 else 0
    features['all_caps_words'] = sum(1 for word in text.split() if word.isupper() and len(word) > 1)
    
    # ============================================
    # PUNCTUATION
    # ============================================
    features['exclamation_count'] = text.count('!')
    features['question_count'] = text.count('?')
    features['multiple_exclamation'] = len(re.findall(r'!{2,}', text))
    features['multiple_question'] = len(re.findall(r'\?{2,}', text))
    
    # ============================================
    # SPAM KEYWORDS
    # ============================================
    spam_keywords = [
        'viagra', 'cialis', 'casino', 'lottery', 'winner', 'congratulations',
        'click here', 'click now', 'buy now', 'order now', 'limited time',
        'act now', 'free money', 'no cost', 'risk free', 'credit card',
        'weight loss', 'lose weight', 'diet pill', 'forex', 'bitcoin',
        'crypto', 'investment', 'earn money', 'work from home', 'income',
        'million dollars', 'inheritance', 'prince', 'nigeria'
    ]
    
    text_lower = text.lower()
    features['spam_keyword_count'] = sum(
        1 for keyword in spam_keywords if keyword in text_lower
    )
    features['has_spam_keywords'] = features['spam_keyword_count'] > 0
    
    # ============================================
    # URGENCY WORDS
    # ============================================
    urgency_words = [
        'urgent', 'immediate', 'immediately', 'now', 'today', 'hurry',
        'limited', 'expires', 'expiring', 'act fast', 'don\'t miss',
        'last chance', 'final notice', 'limited time', 'only today',
        'expires today', 'act immediately', 'respond now'
    ]
    
    features['urgency_word_count'] = sum(
        1 for word in urgency_words if word in text_lower
    )
    features['has_urgency_words'] = features['urgency_word_count'] > 0
    
    # ============================================
    # MONEY WORDS
    # ============================================
    money_words = [
        'money', 'cash', 'dollar', 'euro', 'pound', 'prize', 'win', 'won',
        'million', 'thousand', 'free', 'bonus', 'reward', 'payment',
        'credit', 'bank', 'account', 'transfer', '$', '€', '£', '¥'
    ]
    
    features['money_word_count'] = sum(
        1 for word in money_words if word in text_lower
    )
    features['has_money_words'] = features['money_word_count'] > 0
    
    # ============================================
    # LINKS & URLs
    # ============================================
    urls = re.findall(r'https?://[^\s]+', text)
    features['link_count'] = len(urls)
    features['suspicious_link_count'] = sum(1 for url in urls if _is_suspicious_url(url))
    features['has_phishing_url'] = any(_is_phishing_url(url) for url in urls)
    features['shortened_url_count'] = sum(1 for url in urls if _is_shortened_url(url))
    
    # ============================================
    # EMAIL PATTERNS
    # ============================================
    emails = re.findall(r'\S+@\S+', text)
    features['email_count'] = len(emails)
    features['suspicious_email'] = any(_is_suspicious_email(email) for email in emails)
    
    # ============================================
    # PHONE NUMBERS
    # ============================================
    phones = re.findall(r'\+?\d[\d\s\-\(\)]{7,}\d', text)
    features['phone_count'] = len(phones)
    
    # ============================================
    # HTML/SCRIPT TAGS
    # ============================================
    features['has_html_tags'] = bool(re.search(r'<[^>]+>', text))
    features['has_script_tags'] = bool(re.search(r'<script', text, re.IGNORECASE))
    
    # ============================================
    # SPECIAL CHARACTERS
    # ============================================
    special_chars = sum(1 for c in text if not c.isalnum() and not c.isspace())
    features['special_char_ratio'] = special_chars / len(text) if len(text) > 0 else 0
    
    # ============================================
    # REPETITION
    # ============================================
    words = text_lower.split()
    if words:
        unique_words = set(words)
        features['word_repetition_ratio'] = 1 - (len(unique_words) / len(words))
    else:
        features['word_repetition_ratio'] = 0
    
    # ============================================
    # CONTEXT FEATURES
    # ============================================
    if context:
        features['has_email_context'] = bool(context.get('email'))
        features['has_ip_context'] = bool(context.get('ip'))
        
        # Check IP reputation (placeholder)
        # features['suspicious_ip'] = _check_ip_reputation(context.get('ip'))
    else:
        features['has_email_context'] = False
        features['has_ip_context'] = False
    
    # ============================================
    # LANGUAGE DETECTION (simple)
    # ============================================
    features['language'] = _detect_language(text)
    
    return features

# ============================================
# HELPER FUNCTIONS
# ============================================

def _is_suspicious_url(url: str) -> bool:
    """Verificar si URL es sospechosa"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # URLs acortadas
        if _is_shortened_url(url):
            return True
        
        # IP addresses en lugar de dominios
        if re.match(r'\d+\.\d+\.\d+\.\d+', domain):
            return True
        
        # TLDs sospechosos
        suspicious_tlds = ['.tk', '.ml', '.ga', '.cf', '.xyz', '.top', '.club']
        if any(domain.endswith(tld) for tld in suspicious_tlds):
            return True
        
        # Muchos subdominios
        if domain.count('.') > 3:
            return True
        
        return False
    except:
        return True

def _is_shortened_url(url: str) -> bool:
    """Verificar si es URL acortada"""
    short_domains = [
        'bit.ly', 'tinyurl.com', 't.co', 'goo.gl', 'ow.ly',
        'is.gd', 'buff.ly', 'adf.ly', 'bit.do', 'short.link'
    ]
    
    try:
        parsed = urlparse(url)
        return any(short in parsed.netloc.lower() for short in short_domains)
    except:
        return False

def _is_phishing_url(url: str) -> bool:
    """Verificar si es URL de phishing conocida"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Patrones comunes de phishing
        phishing_patterns = [
            'paypal-secure', 'paypal-verify', 'paypal-update',
            'amazon-verify', 'amazon-security', 'amazon-update',
            'apple-support', 'apple-verify',
            'account-verify', 'account-update', 'account-security',
            'security-alert', 'security-update',
            'confirm-identity', 'verify-identity',
            'suspended-account', 'locked-account',
            'unusual-activity', 'suspicious-activity'
        ]
        
        return any(pattern in domain for pattern in phishing_patterns)
    except:
        return False

def _is_suspicious_email(email: str) -> bool:
    """Verificar si email es sospechoso"""
    try:
        domain = email.split('@')[1].lower()
        
        # Dominios temporales/desechables
        disposable_domains = [
            'tempmail.com', '10minutemail.com', 'guerrillamail.com',
            'mailinator.com', 'throwaway.email', 'temp-mail.org'
        ]
        
        return any(disposable in domain for disposable in disposable_domains)
    except:
        return False

def _detect_language(text: str) -> str:
    """Detección simple de idioma"""
    # English indicators
    english_words = ['the', 'is', 'are', 'was', 'were', 'have', 'has', 'will', 'can', 'this', 'that']
    
    # Spanish indicators
    spanish_words = ['el', 'la', 'los', 'las', 'es', 'son', 'está', 'están', 'de', 'del']
    
    text_lower = text.lower()
    
    english_count = sum(1 for word in english_words if f' {word} ' in f' {text_lower} ')
    spanish_count = sum(1 for word in spanish_words if f' {word} ' in f' {text_lower} ')
    
    if english_count >= 2:
        return 'en'
    elif spanish_count >= 2:
        return 'es'
    
    return 'unknown'
