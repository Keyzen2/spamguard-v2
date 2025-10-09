"""
SpamGuard ML Model v3.0 Hybrid
Sistema hibrido: Random Forest + Naive Bayes
"""
import numpy as np
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from typing import Dict, List
import os

from app.features import FeatureExtractor


class SpamDetector:
    """
    Detector hibrido de spam
    Combina Random Forest (base) + Naive Bayes (entrenado)
    """
    
    def __init__(self):
        self.feature_extractor = FeatureExtractor()
        
        # Modelo base: Random Forest con reglas
        self.rf_model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        self.rf_trained = False
        
        # Modelo secundario: Naive Bayes desde retrain_model.py
        self.nb_model = None
        self.nb_available = False
        
        # Intentar cargar Naive Bayes
        self._load_naive_bayes()
    
    def _load_naive_bayes(self):
        """
        Cargar modelo Naive Bayes entrenado (si existe)
        """
        # Detectar ruta del volumen persistente
        volume_path = os.getenv('RAILWAY_VOLUME_MOUNT_PATH', '/data')
        model_path = Path(volume_path) / 'models' / 'spam_model.pkl'
        
        if not model_path.exists():
            print("INFO: No hay modelo Naive Bayes entrenado aun")
            print(f"Buscado en: {model_path}")
            return
        
        try:
            self.nb_model = joblib.load(model_path)
            self.nb_available = True
            
            # Leer metadata
            metadata_path = model_path.parent / 'model_metadata.json'
            if metadata_path.exists():
                import json
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                print("SUCCESS: Modelo Naive Bayes cargado!")
                print(f"Accuracy: {metadata.get('metrics', {}).get('test_accuracy', 0):.4f}")
                print(f"Muestras: {metadata.get('training_samples', 0)}")
                print(f"Entrenado: {metadata.get('trained_at', 'N/A')}")
            else:
                print("SUCCESS: Modelo Naive Bayes cargado (sin metadata)")
        
        except Exception as e:
            print(f"WARNING: Error cargando Naive Bayes: {e}")
            self.nb_model = None
            self.nb_available = False
    
    def predict(self, comment_data: Dict) -> Dict:
        """
        Prediccion hibrida: RF + NB
        """
        # 1. Extraer features para Random Forest
        features = self.feature_extractor.extract(comment_data)
        
        # 2. Prediccion con Random Forest (reglas + heuristicas)
        rf_score = self._predict_with_rules(features)
        
        # 3. Prediccion con Naive Bayes (si esta disponible)
        nb_score = 0.5  # Neutral por defecto

        if self.nb_available and self.nb_model is not None:
            nb_score = self._predict_with_nb(comment_data.get('content', ''))
        
        # 4. Combinar scores
        if self.nb_available:
            # Sistema hibrido: dar mas peso a NB si esta entrenado
            final_score = (rf_score * 0.4) + (nb_score * 0.6)
            model_used = 'hybrid'
        else:
            # Solo Random Forest
            final_score = rf_score
            model_used = 'rf_only'
        
        # 5. Clasificacion final
        is_spam = final_score > 0.5
        confidence = final_score if is_spam else (1 - final_score)
        spam_score = final_score * 100  # Score 0-100

        # 6. Nivel de riesgo
        if confidence >= 0.8:
            risk_level = 'high'
        elif confidence >= 0.6:
            risk_level = 'medium'
        else:
            risk_level = 'low'

        # 7. Generar razones
        reasons = self._generate_reasons(features, is_spam)

        return {
            'is_spam': is_spam,
            'confidence': float(confidence),
            'score': float(spam_score),
            'reasons': reasons,
            'risk_level': risk_level,
            'model_used': model_used,
            'scores': {
                'rf': float(rf_score),
                'nb': float(nb_score) if self.nb_available else None,
                'final': float(final_score)
            },
            'features_count': len(features)
        }
    
    def _predict_with_rules(self, features: Dict) -> float:
        """Prediccion basada en reglas heuristicas + Random Forest"""
        spam_score = 0.0
        
        # Regla 1: URLs sospechosas
        if features.get('url_count', 0) > 3:
            spam_score += 0.3
        elif features.get('url_count', 0) > 0:
            spam_score += 0.1
        
        # Regla 2: Palabras spam
        spam_density = features.get('spam_keyword_density', 0)
        if spam_density > 0.1:
            spam_score += 0.4
        elif spam_density > 0.05:
            spam_score += 0.2
        
        # Regla 3: Caracteres especiales excesivos
        if features.get('special_char_ratio', 0) > 0.3:
            spam_score += 0.2
        
        # Regla 4: Mayusculas excesivas
        if features.get('uppercase_ratio', 0) > 0.5:
            spam_score += 0.2
        
        # Regla 5: Email sospechoso
        if features.get('email_domain_suspicious', False):
            spam_score += 0.2
        
        # Regla 6: Contenido HTML
        if features.get('has_html', False):
            spam_score += 0.15
        
        # Regla 7: Comentario de noche (bot)
        if features.get('is_night_time', False):
            spam_score += 0.1
        
        # Regla 8: User agent es bot
        if features.get('is_bot', False):
            spam_score += 0.3
        
        # Normalizar entre 0 y 1
        spam_score = min(1.0, spam_score)
        
        return spam_score
    
    def _predict_with_nb(self, text: str) -> float:
        """Prediccion con Naive Bayes"""
        if not self.nb_available or self.nb_model is None:
            return 0.5

        try:
            # El modelo de retrain_model.py es un pipeline TF-IDF + NB
            proba = self.nb_model.predict_proba([text])[0]
            return float(proba[1])  # Probabilidad de clase 'spam' (1)
        except Exception as e:
            print(f"WARNING: Error en prediccion NB: {e}")
            return 0.5

    def _generate_reasons(self, features: Dict, is_spam: bool) -> List[str]:
        """Genera lista de razones para la clasificacion"""
        reasons = []

        if is_spam:
            # Razones por las que ES spam
            if features.get('spam_keyword_count', 0) > 0:
                reasons.append(f"Contiene {features['spam_keyword_count']} palabras tipicas de spam")

            if features.get('url_count', 0) > 3:
                reasons.append(f"Exceso de enlaces ({features['url_count']})")
            elif features.get('url_count', 0) > 0:
                reasons.append(f"Contiene {features['url_count']} enlaces")

            if features.get('has_suspicious_tld', 0):
                reasons.append("Dominios con extensiones sospechosas")

            if features.get('email_domain_suspicious', 0):
                reasons.append("Email de servicio temporal")

            if features.get('is_bot', 0):
                reasons.append("User-agent identificado como bot")

            if features.get('uppercase_ratio', 0) > 0.5:
                reasons.append(f"Exceso de mayusculas ({round(features['uppercase_ratio']*100)}%)")

            if features.get('has_html', 0):
                reasons.append("Contiene codigo HTML")

            if features.get('special_char_ratio', 0) > 0.3:
                reasons.append("Exceso de caracteres especiales")

            if features.get('is_night_time', 0):
                reasons.append("Publicado en horario nocturno (actividad de bot)")

            if not reasons:
                reasons.append("Patron general sospechoso detectado por el modelo ML")
        else:
            # Razones por las que NO es spam
            if features.get('spam_keyword_count', 0) == 0:
                reasons.append("No contiene palabras tipicas de spam")

            if features.get('url_count', 0) == 0:
                reasons.append("No contiene enlaces promocionales")

            if features.get('text_length', 0) > 100:
                reasons.append("Comentario sustancial y detallado")

            if not features.get('is_bot', 0):
                reasons.append("User-agent legitimo")

            if not features.get('email_domain_suspicious', 0):
                reasons.append("Email de dominio confiable")

            if not reasons:
                reasons.append("Patron general legitimo detectado")

        return reasons
    
    def reload_model(self):
        """Recargar modelo Naive Bayes (util despues de reentrenar)"""
        print("Recargando modelo Naive Bayes...")
        self._load_naive_bayes()
    
    def get_model_info(self) -> Dict:
        """Informacion del modelo actual"""
        info = {
            'rf_available': True,
            'nb_available': self.nb_available,
            'model_type': 'hybrid' if self.nb_available else 'rf_only'
        }
        
        if self.nb_available:
            volume_path = os.getenv('RAILWAY_VOLUME_MOUNT_PATH', '/data')
            metadata_path = Path(volume_path) / 'models' / 'model_metadata.json'
            
            if metadata_path.exists():
                import json
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                info['nb_metadata'] = metadata
        
        return info


# Instancia global
_detector = None


def get_detector() -> SpamDetector:
    """Obtener instancia singleton del detector"""
    global _detector
    if _detector is None:
        _detector = SpamDetector()
    return _detector

# Compatibilidad con código antiguo
spam_detector = get_detector()
