"""
ML Model Predictor (mejorado para v3.0)
"""
import joblib
import numpy as np
from typing import Dict, Optional, List
from app.ml.features import extract_features
from app.ml.preprocessing import preprocess_text
import logging
from pathlib import Path
from app.config import settings

logger = logging.getLogger(__name__)

class MLPredictor:
    """Predictor ML mejorado"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def get_instance(cls):
        instance = cls()
        if not cls._initialized:
            instance._initialize()
            cls._initialized = True
        return instance
    
    def _initialize(self):
        """Cargar modelo"""
        logger.info("🤖 Loading ML Model...")
        
        try:
            model_path = Path(settings.MODEL_PATH)
            
            # Cargar modelo (puede ser logistic regression por ahora)
            if model_path.exists():
                self.model = joblib.load(model_path / 'model.pkl')
                self.vectorizer = joblib.load(model_path / 'vectorizer.pkl')
                logger.info("   ✅ Model loaded from disk")
            else:
                # Modelo por defecto (crear si no existe)
                logger.warning("   ⚠️ Model not found, using rule-based fallback")
                self.model = None
                self.vectorizer = None
            
            self.categories = ['ham', 'spam', 'phishing']
            
        except Exception as e:
            logger.error(f"   ❌ Error loading model: {str(e)}")
            self.model = None
            self.vectorizer = None
    
    async def predict(
        self,
        text: str,
        context: Optional[Dict] = None
    ) -> Dict:
        """
        Predecir categoría del texto
        
        Returns:
            {
                'category': 'spam',
                'confidence': 0.95,
                'scores': {'ham': 0.05, 'spam': 0.95, 'phishing': 0.0},
                'risk_level': 'high',
                'flags': ['excessive_caps', 'urgency_words']
            }
        """
        # 1. Preprocesar texto
        processed_text = preprocess_text(text)
        
        # 2. Extraer features
        features = extract_features(text, context)
        
        # 3. Predecir con modelo (si existe)
        if self.model and self.vectorizer:
            prediction = self._predict_with_model(processed_text, features)
        else:
            # Fallback a reglas
            prediction = self._predict_with_rules(features)
        
        return prediction
    
    def _predict_with_model(self, text: str, features: Dict) -> Dict:
        """Predicción con modelo ML"""
        try:
            # Vectorizar texto
            X = self.vectorizer.transform([text])
            
            # Predecir
            proba = self.model.predict_proba(X)[0]
            pred_idx = np.argmax(proba)
            
            category = self.categories[pred_idx]
            confidence = float(proba[pred_idx])
            
            scores = {
                cat: float(prob) 
                for cat, prob in zip(self.categories, proba)
            }
            
            # Ajustar con reglas
            category, confidence = self._adjust_with_rules(category, confidence, features)
            
            return {
                'category': category,
                'confidence': confidence,
                'scores': scores,
                'risk_level': self._calculate_risk_level(category, confidence, features),
                'flags': self._extract_flags(features)
            }
        except Exception as e:
            logger.error(f"Model prediction error: {str(e)}")
            return self._predict_with_rules(features)
    
    def _predict_with_rules(self, features: Dict) -> Dict:
        """Predicción basada en reglas (fallback)"""
        spam_score = 0
        
        # Reglas de spam
        if features['excessive_caps_ratio'] > 0.3:
            spam_score += 30
        
        if features['has_urgency_words']:
            spam_score += 25
        
        if features['has_money_words']:
            spam_score += 25
        
        if features['suspicious_link_count'] > 0:
            spam_score += 20
        
        if features['spam_keyword_count'] > 0:
            spam_score += features['spam_keyword_count'] * 10
        
        # Phishing checks
        if features['has_phishing_url']:
            return {
                'category': 'phishing',
                'confidence': 0.99,
                'scores': {'ham': 0.0, 'spam': 0.01, 'phishing': 0.99},
                'risk_level': 'critical',
                'flags': self._extract_flags(features)
            }
        
        # Determinar categoría
        is_spam = spam_score > 50
        confidence = min(spam_score / 100, 1.0)
        category = 'spam' if is_spam else 'ham'
        
        scores = {
            'ham': 1 - confidence if is_spam else confidence,
            'spam': confidence if is_spam else 1 - confidence,
            'phishing': 0.0
        }
        
        return {
            'category': category,
            'confidence': confidence,
            'scores': scores,
            'risk_level': self._calculate_risk_level(category, confidence, features),
            'flags': self._extract_flags(features)
        }
    
    def _adjust_with_rules(
        self,
        category: str,
        confidence: float,
        features: Dict
    ) -> tuple:
        """Ajustar predicción ML con reglas"""
        
        # Override fuerte: phishing
        if features['has_phishing_url']:
            return 'phishing', 0.99
        
        # Boost spam si hay múltiples señales
        if category == 'ham':
            if features['excessive_caps_ratio'] > 0.5 and features['has_money_words']:
                category = 'spam'
                confidence = max(confidence, 0.85)
        
        # Boost confidence si hay urgencia + dinero
        if category == 'spam':
            if features['has_urgency_words'] and features['has_money_words']:
                confidence = min(confidence + 0.1, 1.0)
        
        return category, confidence
    
    def _calculate_risk_level(
        self,
        category: str,
        confidence: float,
        features: Dict
    ) -> str:
        """Calcular nivel de riesgo"""
        
        if category == 'ham':
            return 'low'
        
        if category == 'phishing':
            return 'critical'
        
        if category == 'spam':
            if confidence > 0.9 or features['has_phishing_url']:
                return 'high'
            elif confidence > 0.7:
                return 'medium'
            else:
                return 'low'
        
        return 'low'
    
    def _extract_flags(self, features: Dict) -> List[str]:
        """Extraer flags activados"""
        flags = []
        
        if features['excessive_caps_ratio'] > 0.3:
            flags.append('excessive_caps')
        
        if features['has_urgency_words']:
            flags.append('urgency_words')
        
        if features['has_money_words']:
            flags.append('money_words')
        
        if features['suspicious_link_count'] > 0:
            flags.append('suspicious_links')
        
        if features['has_phishing_url']:
            flags.append('phishing_url')
        
        if features.get('spam_keyword_count', 0) > 0:
            flags.append('spam_keywords')
        
        return flags
