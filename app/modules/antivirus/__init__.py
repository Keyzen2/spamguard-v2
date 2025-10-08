"""
Módulo Antivirus de SpamGuard Security Suite
"""
__version__ = "1.0.0-beta"

from .scanner import FileScanner
from .signatures import SignatureManager

__all__ = ['FileScanner', 'SignatureManager']
