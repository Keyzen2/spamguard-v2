"""
Text preprocessing for ML model
"""
import re
import html

def preprocess_text(text: str) -> str:
    """
    Preprocess text for ML model
    
    Args:
        text: Raw text
    
    Returns:
        Cleaned text
    """
    # Decode HTML entities
    text = html.unescape(text)
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove zero-width characters
    text = re.sub(r'[\u200B-\u200D\uFEFF]', '', text)
    
    # Normalize URLs (replace with placeholder)
    text = re.sub(r'https?://[^\s]+', '[URL]', text)
    
    # Normalize emails
    text = re.sub(r'\S+@\S+', '[EMAIL]', text)
    
    # Normalize phone numbers
    text = re.sub(r'\+?\d[\d\s\-\(\)]{7,}\d', '[PHONE]', text)
    
    # Strip
    text = text.strip()
    
    return text
