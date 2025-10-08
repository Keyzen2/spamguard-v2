"""
ML Model: Spam Detection with DistilBERT
"""
import torch
from transformers import DistilBertTokenizer, DistilBertForSequenceClassification
from typing import Dict, Optional, List
import numpy as np
from app.ml.features import extract_features
from app.ml.preprocessing import preprocess_text
import asyncio
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

class MLModelPredictor:
    """Singleton ML Model Predictor"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance"""
        instance = cls()
        if not cls._initialized:
            instance._initialize()
            cls._initialized = True
        return instance
    
    def _initialize(self):
        """Initialize model (called once)"""
        logger.info("🤖 Initializing ML Model...")
        
        # Determine device
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        logger.info(f"   Device: {self.device}")
        
        try:
            # Load tokenizer
            self.tokenizer = DistilBertTokenizer.from_pretrained(
                'distilbert-base-uncased'
            )
            
            # Load model
            # TODO: Replace with your fine-tuned model path
            # For now, using base model (you'll need to train this)
            self.model = DistilBertForSequenceClassification.from_pretrained(
                'distilbert-base-uncased',
                num_labels=5  # ham, spam, phishing, ai_generated, fraud
            )
            
            self.model.to(self.device)
            self.model.eval()
            
            # Labels
            self.labels = ['ham', 'spam', 'phishing', 'ai_generated', 'fraud']
            
            logger.info("   ✅ Model loaded successfully")
            
        except Exception as e:
            logger.error(f"   ❌ Error loading model: {str(e)}")
            raise
    
    async def predict(
        self,
        text: str,
        context: Optional[Dict] = None,
        language: Optional[str] = None,
        return_explanation: bool = False
    ) -> Dict:
        """
        Predict spam category
        
        Args:
            text: Text to analyze
            context: Additional context (email, IP, etc.)
            language: Language code (auto-detect if None)
            return_explanation: Whether to return explanation
        
        Returns:
            {
                'category': 'spam',
                'confidence': 0.95,
                'scores': {'ham': 0.02, 'spam': 0.95, ...},
                'risk_level': 'high',
                'flags': ['urgency_words', 'money_references'],
                'language': 'en',
                'explanation': {...}  # if requested
            }
        """
        # Preprocess text
        processed_text = preprocess_text(text)
        
        # Extract rule-based features
        features = extract_features(text, context)
        
        # Tokenize for BERT
        inputs = self.tokenizer(
            processed_text,
            return_tensors='pt',
            truncation=True,
            max_length=512,
            padding=True
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Predict with model
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=1)[0]
        
        # Get prediction
        pred_idx = torch.argmax(probs).item()
        category = self.labels[pred_idx]
        confidence = probs[pred_idx].item()
        
        # All scores
        scores = {
            label: float(prob)
            for label, prob in zip(self.labels, probs)
        }
        
        # Adjust based on rule-based features
        category, confidence = self._adjust_with_rules(
            category, confidence, features
        )
        
        # Calculate risk level
        risk_level = self._calculate_risk_level(category, confidence, features)
        
        # Extract flags
        flags = self._extract_flags(features)
        
        result = {
            'category': category,
            'confidence': confidence,
            'scores': scores,
            'risk_level': risk_level,
            'flags': flags,
            'language': language or features.get('language', 'unknown')
        }
        
        # Add explanation if requested
        if return_explanation:
            result['explanation'] = self._generate_explanation(
                text, category, confidence, features, inputs, outputs
            )
        
        return result
    
    def _adjust_with_rules(
        self,
        category: str,
        confidence: float,
        features: Dict
    ) -> tuple[str, float]:
        """Adjust ML prediction with rule-based features"""
        
        # Strong signals override ML
        if features['has_phishing_url']:
            return 'phishing', 0.99
        
        if features['excessive_caps_ratio'] > 0.5 and features['has_money_words']:
            if category == 'ham':
                category = 'spam'
                confidence = max(confidence, 0.85)
        
        if features['has_urgency_words'] and features['has_money_words']:
            if category in ['ham', 'spam']:
                confidence = min(confidence + 0.1, 1.0)
        
        if features['suspicious_link_count'] >= 3:
            if category == 'ham':
                category = 'spam'
                confidence = max(confidence, 0.75)
        
        return category, confidence
    
    def _calculate_risk_level(
        self,
        category: str,
        confidence: float,
        features: Dict
    ) -> str:
        """Calculate risk level"""
        
        if category == 'ham':
            return 'low'
        
        if category in ['phishing', 'fraud']:
            return 'critical'
        
        if category == 'spam':
            if confidence > 0.9 or features['has_phishing_url']:
                return 'high'
            elif confidence > 0.7:
                return 'medium'
            else:
                return 'low'
        
        if category == 'ai_generated':
            return 'medium'
        
        return 'low'
    
    def _extract_flags(self, features: Dict) -> List[str]:
        """Extract triggered flags"""
        flags = []
        
        if features['excessive_caps_ratio'] > 0.3:
            flags.append('excessive_capitalization')
        
        if features['has_urgency_words']:
            flags.append('urgency_words')
        
        if features['has_money_words']:
            flags.append('money_references')
        
        if features['suspicious_link_count'] > 0:
            flags.append('suspicious_links')
        
        if features['has_phishing_url']:
            flags.append('phishing_url')
        
        if features.get('multiple_exclamation', 0) > 3:
            flags.append('excessive_punctuation')
        
        return flags
    
    def _generate_explanation(
        self,
        text: str,
        category: str,
        confidence: float,
        features: Dict,
        inputs: Dict,
        outputs
    ) -> Dict:
        """Generate explanation for prediction"""
        
        explanation = {
            'decision': f"Classified as '{category}' with {confidence:.1%} confidence",
            'key_factors': []
        }
        
        # Add key factors
        if features['excessive_caps_ratio'] > 0.3:
            explanation['key_factors'].append(
                f"Excessive capitalization ({features['excessive_caps_ratio']:.1%})"
            )
        
        if features['has_urgency_words']:
            explanation['key_factors'].append("Contains urgency words")
        
        if features['has_money_words']:
            explanation['key_factors'].append("Contains money-related terms")
        
        if features['suspicious_link_count'] > 0:
            explanation['key_factors'].append(
                f"{features['suspicious_link_count']} suspicious link(s)"
            )
        
        # TODO: Add SHAP values or attention visualization
        # explanation['attention_words'] = self._get_attention_words(inputs, outputs)
        
        return explanation
