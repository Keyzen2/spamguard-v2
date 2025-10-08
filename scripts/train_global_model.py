"""
Script para entrenar el modelo global con los datos iniciales
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.ml_model import SpamDetector
from app.database import Database
from app.config import get_settings
import asyncio

settings = get_settings()

async def train_global_model():
    """Entrena el modelo global con los datos de entrenamiento"""
    
    print("🤖 Iniciando entrenamiento del modelo global...")
    print("=" * 60)
    
    detector = SpamDetector()
    
    # Entrenar con datos del sitio 'global'
    result = await detector.train_site_model('global')
    
    if result['success']:
        print("\n✅ ¡Modelo entrenado exitosamente!")
        print(f"\n📊 Métricas del modelo:")
        print(f"  • Accuracy:  {result['metrics']['accuracy']:.2%}")
        print(f"  • Precision: {result['metrics']['precision']:.2%}")
        print(f"  • Recall:    {result['metrics']['recall']:.2%}")
        print(f"  • F1-Score:  {result['metrics']['f1']:.2%}")
        print(f"\n📈 Muestras utilizadas: {result['samples_used']}")
        
        # Renombrar modelo a 'global'
        import shutil
        old_model = os.path.join(settings.ml_model_path, 'model_global.joblib')
        old_scaler = os.path.join(settings.ml_model_path, 'scaler_global.joblib')
        new_model = os.path.join(settings.ml_model_path, 'global_model.joblib')
        new_scaler = os.path.join(settings.ml_model_path, 'global_scaler.joblib')
        
        os.makedirs(settings.ml_model_path, exist_ok=True)
        
        if os.path.exists(old_model):
            shutil.copy(old_model, new_model)
            shutil.copy(old_scaler, new_scaler)
            print(f"\n💾 Modelo guardado en: {new_model}")
            print("🎯 Este modelo se usará como base para todos los sitios nuevos")
    else:
        print(f"\n❌ Error: {result['message']}")

if __name__ == "__main__":
    asyncio.run(train_global_model())
