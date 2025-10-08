"""
Script de Reentrenamiento del Modelo SpamGuard v3.0 Hybrid
Ejecutar manualmente: python app/retrain_model.py
O programar con cron/Railway workers
"""

import sys
import os
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime
import json
import joblib
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import make_pipeline
from sklearn.metrics import (
    accuracy_score, 
    precision_score, 
    recall_score, 
    f1_score,
    confusion_matrix,
    classification_report
)

# Importar configuración de la app
try:
    from supabase import create_client
    from app.config import settings
except ImportError as e:
    print(f"❌ Error importando módulos: {e}")
    print("Asegúrate de ejecutar desde el directorio raíz del proyecto")
    sys.exit(1)


class ModelRetrainer:
    
    def __init__(self):
        # Supabase client
        self.supabase = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY
        )
        
        # Detectar si estamos en Railway con volumen persistente
        volume_path = os.getenv('RAILWAY_VOLUME_MOUNT_PATH')
        
        if volume_path:
            # Usar almacenamiento persistente de Railway
            base_dir = Path(volume_path)
            print(f"📦 Usando volumen persistente: {volume_path}")
        else:
            # Usar almacenamiento local (desarrollo)
            base_dir = Path('.')
            print("📁 Usando almacenamiento local")
        
        self.models_dir = base_dir / 'models'
        self.backups_dir = self.models_dir / 'backups'
        self.model_path = self.models_dir / 'spam_model.pkl'
        self.metadata_path = self.models_dir / 'model_metadata.json'
        
        # Crear directorios si no existen
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(exist_ok=True)
    
    def fetch_training_data(self, min_samples=100, user_id=None):
        """
        Obtener datos de entrenamiento desde Supabase
        
        Args:
            min_samples: Mínimo de muestras requeridas
            user_id: Si se especifica, entrena solo con datos de ese usuario
        """
        print("\n" + "="*60)
        print("📊 OBTENIENDO DATOS DE ENTRENAMIENTO")
        if user_id:
            print(f"   (Solo usuario: {user_id})")
        else:
            print("   (Todos los usuarios - v3.0 Hybrid)")
        print("="*60)
        
        try:
            # v3.0: Obtener de feedback_queue (multi-tenant)
            query = self.supabase.table('feedback_queue')\
                .select('*, comments_analyzed(*)')\
                .eq('processed', False)
            
            # Filtrar por usuario si se especifica
            if user_id:
                query = query.eq('user_id', user_id)
            
            response = query.execute()
            
            data = response.data
            
            if not data:
                print("❌ No se encontraron datos de entrenamiento")
                return None
            
            # Procesar datos
            processed_data = []
            for item in data:
                comment = item.get('comments_analyzed')
                if comment and comment.get('comment_content'):
                    processed_data.append({
                        'content': comment['comment_content'],
                        'actual_label': item['new_label'],
                        'old_label': item['old_label'],
                        'feedback_id': item['id']
                    })
            
            if not processed_data:
                print("❌ No hay comentarios válidos para entrenar")
                return None
            
            df = pd.DataFrame(processed_data)
            
            print(f"✅ Obtenidos {len(df)} comentarios con feedback")
            
            # Estadísticas
            spam_count = sum(df['actual_label'] == 'spam')
            ham_count = len(df) - spam_count
            
            print(f"\n📈 Distribución:")
            print(f"   - Spam: {spam_count} ({spam_count/len(df)*100:.1f}%)")
            print(f"   - Ham:  {ham_count} ({ham_count/len(df)*100:.1f}%)")
            
            # Verificar balance mínimo
            if spam_count < 50 or ham_count < 50:
                print(f"\n⚠️  Advertencia: Dataset desbalanceado")
                print(f"   Recomendado: al menos 50 ejemplos de cada clase")
            
            if len(df) < min_samples:
                print(f"\n❌ Insuficientes datos: {len(df)} (mínimo {min_samples})")
                return None
            
            return df
            
        except Exception as e:
            print(f"❌ Error obteniendo datos: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def prepare_data(self, df):
        """
        Preparar datos para entrenamiento
        """
        print("\n" + "="*60)
        print("🔧 PREPARANDO DATOS")
        print("="*60)
        
        # Limpiar contenido
        df['content'] = df['content'].fillna('')
        
        # Convertir labels a binario (1=spam, 0=ham)
        df['label'] = (df['actual_label'] == 'spam').astype(int)
        
        # Eliminar duplicados
        original_len = len(df)
        df = df.drop_duplicates(subset=['content'])
        duplicates_removed = original_len - len(df)
        
        if duplicates_removed > 0:
            print(f"🧹 Eliminados {duplicates_removed} duplicados")
            print(f"   (Esto es correcto - evita memorización)")
        
        # Filtrar contenido muy corto
        df = df[df['content'].str.len() >= 10]
        
        print(f"✅ Dataset final: {len(df)} ejemplos únicos")
        
        return df
    
    def train_model(self, df):
        """
        Entrenar nuevo modelo
        """
        print("\n" + "="*60)
        print("🤖 ENTRENANDO NUEVO MODELO")
        print("="*60)
        
        # Preparar X e y
        X = df['content']
        y = df['label']
        
        # Split train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, 
            test_size=0.2, 
            random_state=42, 
            stratify=y
        )
        
        print(f"📊 Train set: {len(X_train)} ejemplos")
        print(f"📊 Test set:  {len(X_test)} ejemplos")
        
        # Crear pipeline
        print("\n⚙️  Entrenando modelo...")
        
        model = make_pipeline(
            TfidfVectorizer(
                max_features=5000,
                ngram_range=(1, 2),
                min_df=2,
                max_df=0.95,
                strip_accents='unicode',
                lowercase=True
            ),
            MultinomialNB(alpha=0.1)
        )
        
        # Entrenar
        model.fit(X_train, y_train)
        
        print("✅ Entrenamiento completado")
        
        # Evaluar
        return self.evaluate_model(model, X_test, y_test, X_train, y_train)
    
    def evaluate_model(self, model, X_test, y_test, X_train, y_train):
        """
        Evaluar rendimiento del modelo
        """
        print("\n" + "="*60)
        print("📈 EVALUANDO MODELO")
        print("="*60)
        
        # Predicciones
        y_pred_train = model.predict(X_train)
        y_pred_test = model.predict(X_test)
        
        # Métricas train
        train_accuracy = accuracy_score(y_train, y_pred_train)
        
        # Métricas test
        test_accuracy = accuracy_score(y_test, y_pred_test)
        test_precision = precision_score(y_test, y_pred_test, zero_division=0)
        test_recall = recall_score(y_test, y_pred_test, zero_division=0)
        test_f1 = f1_score(y_test, y_pred_test, zero_division=0)
        
        print(f"\n🎯 Métricas en Train Set:")
        print(f"   Accuracy: {train_accuracy:.4f}")
        
        print(f"\n🎯 Métricas en Test Set:")
        print(f"   Accuracy:  {test_accuracy:.4f}")
        print(f"   Precision: {test_precision:.4f}")
        print(f"   Recall:    {test_recall:.4f}")
        print(f"   F1 Score:  {test_f1:.4f}")
        
        # Matriz de confusión
        cm = confusion_matrix(y_test, y_pred_test)
        print(f"\n📊 Matriz de Confusión:")
        print(f"   TN: {cm[0,0]:4d}  FP: {cm[0,1]:4d}")
        print(f"   FN: {cm[1,0]:4d}  TP: {cm[1,1]:4d}")
        
        # Reporte detallado
        print(f"\n📋 Reporte de Clasificación:")
        print(classification_report(
            y_test, y_pred_test, 
            target_names=['Ham', 'Spam'],
            digits=4
        ))
        
        # Verificar overfitting
        overfitting_diff = train_accuracy - test_accuracy
        if overfitting_diff > 0.1:
            print(f"\n⚠️  Advertencia: Posible overfitting")
            print(f"   Diferencia Train-Test: {overfitting_diff:.4f}")
        
        metrics = {
            'train_accuracy': float(train_accuracy),
            'test_accuracy': float(test_accuracy),
            'precision': float(test_precision),
            'recall': float(test_recall),
            'f1_score': float(test_f1),
            'confusion_matrix': cm.tolist()
        }
        
        return model, metrics
    
    def backup_current_model(self):
        """
        Hacer backup del modelo actual
        """
        if not self.model_path.exists():
            print("ℹ️  No hay modelo anterior para hacer backup")
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backups_dir / f'spam_model_{timestamp}_backup.pkl'
        
        import shutil
        shutil.copy(self.model_path, backup_path)
        
        print(f"💾 Backup guardado: {backup_path.name}")
        
        # Limpiar backups viejos (mantener solo los 5 más recientes)
        backups = sorted(self.backups_dir.glob('spam_model_*_backup.pkl'), reverse=True)
        for old_backup in backups[5:]:
            old_backup.unlink()
            print(f"🗑️  Eliminado backup antiguo: {old_backup.name}")
        
        return backup_path
    
    def save_model(self, model, metrics, training_samples):
        """
        Guardar nuevo modelo y metadata
        """
        print("\n" + "="*60)
        print("💾 GUARDANDO MODELO")
        print("="*60)
        
        # Guardar modelo
        joblib.dump(model, self.model_path)
        print(f"✅ Modelo guardado: {self.model_path}")
        
        # Guardar metadata
        metadata = {
            'trained_at': datetime.now().isoformat(),
            'training_samples': int(training_samples),
            'unique_samples': int(training_samples),
            'metrics': metrics,
            'model_version': '3.0',  # ← v3.0 Hybrid
            'api_version': 'v3.0-hybrid'
        }
        
        with open(self.metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"✅ Metadata guardada: {self.metadata_path}")
        
        return metadata
    
    def mark_feedback_as_processed(self, df):
        """
        Marcar feedback como procesado (v3.0)
        """
        if 'feedback_id' not in df.columns:
            return
        
        print("\n📝 Marcando feedback como procesado...")
        
        try:
            feedback_ids = df['feedback_id'].tolist()
            
            self.supabase.table('feedback_queue')\
                .update({'processed': True})\
                .in_('id', feedback_ids)\
                .execute()
            
            print(f"✅ {len(feedback_ids)} feedbacks marcados como procesados")
        except Exception as e:
            print(f"⚠️  Error marcando feedback: {e}")
    
    def compare_with_previous(self):
        """
        Comparar con modelo anterior si existe
        """
        if not self.metadata_path.exists():
            return
        
        try:
            with open(self.metadata_path, 'r') as f:
                old_metadata = json.load(f)
            
            print("\n" + "="*60)
            print("📊 COMPARACIÓN CON MODELO ANTERIOR")
            print("="*60)
            
            old_acc = old_metadata.get('metrics', {}).get('test_accuracy', 0)
            print(f"Accuracy anterior: {old_acc:.4f}")
            print(f"Fecha entrenamiento: {old_metadata.get('trained_at', 'N/A')}")
            print(f"Muestras anteriores: {old_metadata.get('training_samples', 0)}")
            print(f"Versión: {old_metadata.get('model_version', 'N/A')}")
            
        except Exception as e:
            print(f"⚠️  No se pudo cargar metadata anterior: {e}")
    
    def run(self, min_samples=100, user_id=None):
        """
        Ejecutar proceso completo de reentrenamiento
        """
        print("\n" + "🚀 " + "="*58 + " 🚀")
        print("   SPAMGUARD AI v3.0 - REENTRENAMIENTO DEL MODELO")
        print("🚀 " + "="*58 + " 🚀\n")
        
        start_time = datetime.now()
        
        # 1. Comparar con anterior
        self.compare_with_previous()
        
        # 2. Obtener datos
        df = self.fetch_training_data(min_samples, user_id)
        if df is None:
            print("\n❌ Reentrenamiento cancelado: datos insuficientes")
            return False
        
        # 3. Preparar datos
        df = self.prepare_data(df)
        if len(df) < min_samples:
            print(f"\n❌ Después de limpiar: {len(df)} < {min_samples}")
            return False
        
        # 4. Backup modelo actual
        self.backup_current_model()
        
        # 5. Entrenar nuevo modelo
        model, metrics = self.train_model(df)
        
        # 6. Guardar modelo
        metadata = self.save_model(model, metrics, len(df))
        
        # 7. Marcar feedback como procesado (v3.0)
        self.mark_feedback_as_processed(df)
        
        # 8. Resumen final
        elapsed = (datetime.now() - start_time).total_seconds()
        
        print("\n" + "="*60)
        print("✅ REENTRENAMIENTO COMPLETADO")
        print("="*60)
        print(f"⏱️  Tiempo total: {elapsed:.1f}s")
        print(f"📊 Accuracy: {metrics['test_accuracy']:.4f}")
        print(f"📈 F1 Score: {metrics['f1_score']:.4f}")
        print(f"🎯 Muestras únicas: {len(df)}")
        print(f"📦 Guardado en volumen persistente Railway")
        print("\n🔄 Modelo listo - se cargará automáticamente")
        print("="*60 + "\n")
        
        return True


def main():
    """
    Función principal
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Reentrenar modelo de SpamGuard v3.0')
    parser.add_argument(
        '--min-samples',
        type=int,
        default=100,
        help='Mínimo de muestras requeridas (default: 100)'
    )
    parser.add_argument(
        '--user-id',
        type=str,
        default=None,
        help='Entrenar solo con datos de un usuario específico (opcional)'
    )
    
    args = parser.parse_args()
    
    retrainer = ModelRetrainer()
    success = retrainer.run(
        min_samples=args.min_samples,
        user_id=args.user_id
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
