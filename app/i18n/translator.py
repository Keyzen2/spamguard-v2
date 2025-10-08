"""
Sistema de traducción SIMPLE para FastAPI
Solo inglés y español
"""
import gettext
from pathlib import Path
from typing import Optional

class SimpleTranslator:
    
    def __init__(self):
        self.locale_dir = Path(__file__).parent / 'locales'
        
        # Cargar español
        try:
            self.es_translation = gettext.translation(
                'messages',
                localedir=str(self.locale_dir),
                languages=['es']
            )
        except:
            self.es_translation = None
    
    def translate(self, message: str, lang: str = 'en') -> str:
        """Traducir mensaje"""
        if lang == 'es' and self.es_translation:
            return self.es_translation.gettext(message)
        return message  # Inglés por defecto

# Instancia global
_translator = SimpleTranslator()

def _(message: str, lang: str = 'en') -> str:
    """Función corta para traducir"""
    return _translator.translate(message, lang)
