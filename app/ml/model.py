import torch
from transformers import DistilBertTokenizer, DistilBertForSequenceClassification
from typing import Dict, Optional
import numpy as np

class MLModelPredictor:
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Load model (singleton pattern)"""
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Load tokenizer
        self.tokenizer = DistilBertTokenizer.from_pretrained(
            'distilbert-base-uncased'
        )
        
        # Load fine-tuned model
        self.model = DistilBertForSequenceClassification.from_pretrained(
            'ml/models/distilbert_spam_v1'
        )
        self.model.to(self.device)
        self.model.eval()
        
        self.labels = ['ham', 'spam', 'phishing', 'ai_generated', 'fraud']
        
        print(f"✅ ML Model loaded on {self.device}")
    
    async def predict(
        self,
        text: str,
        context: Optional[Dict] = None,
        return_explanation: bool = False
    ) -> Dict:
        """
        Predict spam category
        
        Returns:
            {
                'category': 'spam',
                'confidence': 0.95,
                'scores': {'ham': 0.02, 'spam': 0.95, ...},
                'risk_level': 'high',
                'explanation': {...}  # if requested
            }
        """
        # Tokenize
        inputs = self.tokenizer(
            text,
            return_tensors='pt',
            truncation=True,
            max_length=512,
            padding=True
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Predict
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
        
        # Risk level
        risk_level = self._calculate_risk_level(category, confidence, context)
        
        result = {
            'category': category,
            'confidence': confidence,
            'scores': scores,
            'risk_level': risk_level
        }
        
        # Explanation with SHAP (optional)
        if return_explanation:
            result['explanation'] = self._explain_prediction(text, inputs, outputs)
        
        return result
    
    def _calculate_risk_level(self, category: str, confidence: float, context: Optional[Dict]) -> str:
        """Calculate risk level"""
        if category == 'ham':
            return 'low'
        
        if category in ['phishing', 'fraud']:
            return 'critical'
        
        if category == 'spam':
            if confidence > 0.9:
                return 'high'
            elif confidence > 0.7:
                return 'medium'
            else:
                return 'low'
        
        if category == 'ai_generated':
            return 'medium'
        
        return 'low'
    
    def _explain_prediction(self, text: str, inputs: Dict, outputs) -> Dict:
        """Generate explanation using attention weights"""
        # TODO: Implement SHAP or attention visualization
        return {
            'top_words': [],  # Words that influenced decision
            'attention_scores': []
        }
