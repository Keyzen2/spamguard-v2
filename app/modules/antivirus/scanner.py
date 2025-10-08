"""
Módulo de escaneo de archivos para detección de malware
"""
import os
import hashlib
import re
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import datetime
import asyncio

class FileScanner:
    
    def __init__(self, signatures_path: str = "signatures/malware_patterns.json"):
        self.signatures = self._load_signatures(signatures_path)
        self.suspicious_functions = [
            'eval', 'base64_decode', 'gzinflate', 'str_rot13',
            'assert', 'create_function', 'preg_replace', 'exec',
            'shell_exec', 'system', 'passthru', 'proc_open',
            'popen', 'curl_exec', 'curl_multi_exec', 'parse_str',
            'extract', 'putenv', 'ini_set', 'mail', 'header',
            'file_get_contents', 'file_put_contents', 'fopen',
            'readfile', 'require', 'include', 'require_once',
            'include_once'
        ]
    
    def _load_signatures(self, path: str) -> List[Dict]:
        """Cargar firmas de malware desde archivo JSON"""
        import json
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Firmas por defecto si no existe el archivo
            return [
                {
                    "name": "eval_base64",
                    "pattern": r"eval\s*\(\s*base64_decode",
                    "severity": "critical"
                },
                {
                    "name": "eval_gzinflate",
                    "pattern": r"eval\s*\(\s*gzinflate",
                    "severity": "critical"
                },
                {
                    "name": "preg_replace_eval",
                    "pattern": r"preg_replace\s*\(.*\/e",
                    "severity": "high"
                },
                {
                    "name": "assert_post",
                    "pattern": r"assert\s*\(\s*\$_(POST|GET|REQUEST|COOKIE)",
                    "severity": "critical"
                },
                {
                    "name": "backdoor_shell",
                    "pattern": r"<\?php\s*@?eval\s*\(\s*\$_(POST|GET|REQUEST)",
                    "severity": "critical"
                },
                {
                    "name": "obfuscated_globals",
                    "pattern": r"\$GLOBALS\s*\[\s*['\"]___['\"]",
                    "severity": "high"
                },
                {
                    "name": "create_function_exploit",
                    "pattern": r"create_function\s*\(.*\$_(POST|GET|REQUEST)",
                    "severity": "high"
                },
                {
                    "name": "system_exec",
                    "pattern": r"(system|exec|shell_exec|passthru)\s*\(\s*\$_(POST|GET|REQUEST)",
                    "severity": "critical"
                }
            ]
    
    async def scan_file(self, file_path: str) -> Dict:
        """
        Escanear un archivo individual
        
        Returns:
            Dict con: is_malicious, threats, suspicious_functions, file_hash
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Calcular hash
            file_hash = hashlib.md5(content.encode()).hexdigest()
            
            # Buscar firmas de malware
            threats = []
            for signature in self.signatures:
                if re.search(signature['pattern'], content, re.IGNORECASE):
                    # Extraer contexto (5 líneas antes y después)
                    match = re.search(signature['pattern'], content, re.IGNORECASE)
                    start = max(0, content[:match.start()].rfind('\n', 0, match.start() - 200))
                    end = content.find('\n', match.end() + 200)
                    if end == -1:
                        end = len(content)
                    
                    code_snippet = content[start:end]
                    
                    threats.append({
                        'signature': signature['name'],
                        'severity': signature['severity'],
                        'pattern': signature['pattern'],
                        'code_snippet': code_snippet[:500]  # Limitar tamaño
                    })
            
            # Buscar funciones sospechosas
            suspicious = []
            for func in self.suspicious_functions:
                pattern = rf'\b{func}\s*\('
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    suspicious.append({
                        'function': func,
                        'count': len(matches)
                    })
            
            return {
                'file_path': file_path,
                'is_malicious': len(threats) > 0,
                'threats': threats,
                'suspicious_functions': suspicious,
                'file_hash': file_hash,
                'file_size': os.path.getsize(file_path),
                'modified_time': datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat()
            }
            
        except Exception as e:
            return {
                'file_path': file_path,
                'error': str(e),
                'is_malicious': False,
                'threats': [],
                'suspicious_functions': []
            }
    
    async def scan_directory(
        self, 
        directory: str, 
        extensions: List[str] = ['.php'],
        max_size_mb: int = 10,
        progress_callback = None
    ) -> Dict:
        """
        Escanear un directorio completo
        
        Args:
            directory: Ruta del directorio
            extensions: Extensiones a escanear
            max_size_mb: Tamaño máximo de archivo a escanear
            progress_callback: Función para reportar progreso
        """
        results = {
            'total_files': 0,
            'scanned_files': 0,
            'threats_found': 0,
            'suspicious_files': [],
            'clean_files': [],
            'errors': [],
            'start_time': datetime.utcnow().isoformat()
        }
        
        # Obtener lista de archivos
        files_to_scan = []
        for ext in extensions:
            files_to_scan.extend(Path(directory).rglob(f'*{ext}'))
        
        results['total_files'] = len(files_to_scan)
        max_size_bytes = max_size_mb * 1024 * 1024
        
        # Escanear archivos
        for idx, file_path in enumerate(files_to_scan):
            # Verificar tamaño
            if file_path.stat().st_size > max_size_bytes:
                continue
            
            # Escanear
            scan_result = await self.scan_file(str(file_path))
            results['scanned_files'] += 1
            
            # Categorizar resultado
            if scan_result.get('error'):
                results['errors'].append(scan_result)
            elif scan_result['is_malicious']:
                results['threats_found'] += 1
                results['suspicious_files'].append(scan_result)
            else:
                # Solo guardar archivos con funciones sospechosas
                if scan_result['suspicious_functions']:
                    results['suspicious_files'].append(scan_result)
                else:
                    results['clean_files'].append(scan_result['file_path'])
            
            # Reportar progreso
            if progress_callback:
                progress = int((idx + 1) / results['total_files'] * 100)
                await progress_callback(progress, scan_result)
        
        results['end_time'] = datetime.utcnow().isoformat()
        
        return results
