"""
Gestor de firmas de malware
"""
import json
from pathlib import Path
from typing import List, Dict

class SignatureManager:
    
    def __init__(self, signatures_dir: str = "signatures"):
        self.signatures_dir = Path(signatures_dir)
        self.signatures_dir.mkdir(exist_ok=True)
    
    def load_signatures(self) -> List[Dict]:
        """Cargar todas las firmas"""
        signatures_file = self.signatures_dir / 'malware_patterns.json'
        
        if not signatures_file.exists():
            # Crear archivo con firmas por defecto
            default_signatures = self._get_default_signatures()
            self.save_signatures(default_signatures)
            return default_signatures
        
        with open(signatures_file, 'r') as f:
            return json.load(f)
    
    def save_signatures(self, signatures: List[Dict]):
        """Guardar firmas"""
        signatures_file = self.signatures_dir / 'malware_patterns.json'
        with open(signatures_file, 'w') as f:
            json.dump(signatures, f, indent=2)
    
    def _get_default_signatures(self) -> List[Dict]:
        """Firmas de malware por defecto"""
        return [
            {
                "id": "eval_base64",
                "name": "Eval with Base64",
                "description": "Código ofuscado con eval y base64_decode",
                "pattern": r"eval\s*\(\s*base64_decode",
                "severity": "critical",
                "category": "obfuscation"
            },
            {
                "id": "eval_gzinflate",
                "name": "Eval with gzinflate",
                "description": "Código ofuscado con eval y gzinflate",
                "pattern": r"eval\s*\(\s*gzinflate",
                "severity": "critical",
                "category": "obfuscation"
            },
            {
                "id": "preg_replace_eval",
                "name": "preg_replace /e modifier",
                "description": "Uso de modificador /e en preg_replace (deprecated)",
                "pattern": r"preg_replace\s*\(.*\/e",
                "severity": "high",
                "category": "code_execution"
            },
            {
                "id": "assert_superglobal",
                "name": "Assert with superglobals",
                "description": "Uso de assert con variables POST/GET",
                "pattern": r"assert\s*\(\s*\$_(POST|GET|REQUEST|COOKIE)",
                "severity": "critical",
                "category": "backdoor"
            },
            {
                "id": "backdoor_shell",
                "name": "PHP Backdoor Shell",
                "description": "Shell PHP clásico",
                "pattern": r"<\?php\s*@?eval\s*\(\s*\$_(POST|GET|REQUEST)",
                "severity": "critical",
                "category": "backdoor"
            },
            {
                "id": "obfuscated_globals",
                "name": "Obfuscated GLOBALS",
                "description": "Variables GLOBALS ofuscadas",
                "pattern": r"\$GLOBALS\s*\[\s*['\"]___['\"]",
                "severity": "high",
                "category": "obfuscation"
            },
            {
                "id": "create_function_exploit",
                "name": "create_function exploit",
                "description": "Uso de create_function con variables de usuario",
                "pattern": r"create_function\s*\(.*\$_(POST|GET|REQUEST)",
                "severity": "high",
                "category": "code_execution"
            },
            {
                "id": "system_exec_superglobal",
                "name": "System execution with user input",
                "description": "Ejecución de comandos del sistema con input de usuario",
                "pattern": r"(system|exec|shell_exec|passthru)\s*\(\s*\$_(POST|GET|REQUEST)",
                "severity": "critical",
                "category": "command_injection"
            },
            {
                "id": "file_upload_shell",
                "name": "File upload shell",
                "description": "Shell que sube archivos",
                "pattern": r"move_uploaded_file.*\$_(FILES|POST|REQUEST)",
                "severity": "high",
                "category": "file_upload"
            },
            {
                "id": "base64_long_string",
                "name": "Long base64 string",
                "description": "String base64 sospechosamente largo",
                "pattern": r"base64_decode\s*\(\s*['\"][A-Za-z0-9+/=]{200,}",
                "severity": "medium",
                "category": "obfuscation"
            }
        ]
