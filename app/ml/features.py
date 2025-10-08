"""
Rule-based feature extraction
"""
import re
from typing import Dict, Optional
from urllib.parse import urlparse

def extract_features(text: str, context: Optional[Dict] = None) -> Dict:
    """
    Extract rule-based features from text
    
    Returns dict with boolean and numeric features
    """
    features = {}
    
    # Text statistics
    features['length'] = len(text)
    features['word_count'] = len(text.split())
    
    # Capitalization
    caps_count = sum(1 for c in text if c.isupper())
    features['excessive_caps_ratio'] = caps_count / len(text) if len(text) > 0 else 0
    
    # Punctuation
    features['exclamation_count'] = text.count('!')
    features['question_count'] = text.count('?')
    features['multiple_exclamation'] = len(re.findall(r'!{2,}', text))
    
    # Spam keywords
    spam_keywords = [
        'viagra', 'casino', 'lottery', 'winner', 'congratulations',
        'click here', 'buy now', 'limited time', 'act now', 'free money',
        'no cost', 'risk free', 'credit card', 'weight loss'
    ]
    features['spam_keyword_count'] = sum(
        1 for keyword in spam_keywords if keyword.lower() in text.lower()
    )
    
    # Urgency words
    urgency_words = [
        'urgent', 'immediate', 'now', 'today', 'hurry', 'limited',
        'expires', 'act fast', 'don\'t miss', 'last chance'
    ]
    features['has_urgency_words'] = any(
        word.lower() in text.lower() for word in urgency_words
    )
    
    # Money words
    money_words = [
        'money', 'cash', 'dollar', 'prize', 'win', 'million',
        'thousand', 'free', 'bonus', 'reward', '$', '€', '£'
    ]
    features['has_money_words'] = any(
        word in text.lower() for word in money_words
    )
    
    # Links
    urls = re.findall(r'https?://[^\s]+', text)
    features['link_count'] = len(urls)
    features['suspicious_link_count'] = sum(
        1 for url in urls if _is_suspicious_url(url)
    )
    features['has_phishing_url'] = any(
        _is_phishing_url(url) for url in urls
    )
    
    # Context features
    if context:
        features['has_email'] = bool(context.get('email'))
        features['has_ip'] = bool(context.get('ip'))
        
        # Check if IP is suspicious (if you have a blacklist)
        # features['suspicious_ip'] = _check_ip_reputation(context.get('ip'))
    
    # Language detection (simple)
    features['language'] = _detect_language(text)
    
    return features

def _is_suspicious_url(url: str) -> bool:
    """Check if URL looks suspicious"""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Shortened URLs
        short_domains = ['bit.ly', 'tinyurl.com', 't.co', 'goo.gl']
        if any(short in domain for short in short_domains):
            return True
        
        # IP addresses instead of domains
        if re.match(r'\d+\.\d+\.\d+\.\d+', domain):
            return True
        
        # Suspicious TLDs
        suspicious_tlds = ['.tk', '.ml', '.ga', '.cf', '.xyz', '.top']
        if any(domain.endswith(tld) for tld in suspicious_tlds):
            return True
        
        # Long subdomains
        if domain.count('.') > 3:
            return True
        
        return False
    except:
        return True

def _is_phishing_url(url: str) -> bool:
    """Check if URL is known phishing"""
    # TODO: Integrate with PhishTank or Google Safe Browsing API
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Common phishing patterns
        phishing_patterns = [
            'paypal-secure',
            'amazon-verify',
            'account-update',
            'security-alert',
            'confirm-identity'
        ]
        
        return any(pattern in domain for pattern in phishing_patterns)
    except:
        return False

def _detect_language(text: str) -> str:
    """Simple language detection"""
    # TODO: Use proper language detection library (langdetect)
    # For now, just return 'en' or 'unknown'
    
    # English indicators
    english_words = ['the', 'is', 'are', 'was', 'have', 'will', 'can']
    text_lower = text.lower()
    
    english_count = sum(1 for word in english_words if f' {word} ' in f' {text_lower} ')
    
    if english_count >= 2:
        return 'en'
    
    return 'unknown'
