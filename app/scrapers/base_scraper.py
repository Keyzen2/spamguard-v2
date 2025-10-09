"""
Clase base para todos los scrapers de vulnerabilidades.

Esta clase define la estructura común que todos los scrapers deben seguir.
Como principiante en Python, piensa en esto como una "plantilla" que 
todos los scrapers específicos van a usar.
"""
import httpx
import asyncio
from typing import List, Dict, Optional
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential

class BaseScraper:
    """
    Clase base para scrapers de vulnerabilidades.
    
    Todos los scrapers (WordPress, NVD, GitHub) van a heredar de esta clase.
    Herdar significa que van a tener todos estos métodos automáticamente.
    """
    
    def __init__(self, name: str):
        """
        Constructor - se ejecuta cuando creas un scraper.
        
        Args:
            name: Nombre del scraper (ejemplo: 'wordpress', 'nvd')
        """
        self.name = name
        self.vulnerabilities = []  # Lista para guardar vulnerabilidades encontradas
        
        # Configuración de httpx (para hacer requests HTTP)
        self.client_config = {
            'timeout': 30.0,  # 30 segundos de timeout
            'follow_redirects': True,  # Seguir redirecciones
            'headers': {
                'User-Agent': 'SpamGuard-Security-Scanner/1.0'  # Identificarnos
            }
        }
    
    @retry(
        stop=stop_after_attempt(3),  # Reintentar 3 veces si falla
        wait=wait_exponential(multiplier=1, min=2, max=10)  # Esperar 2, 4, 8 segundos
    )
    async def fetch_url(self, url: str, params: Optional[Dict] = None) -> httpx.Response:
        """
        Hacer una petición HTTP con reintentos automáticos.
        
        El decorador @retry hace que si falla, lo intente 3 veces automáticamente
        con pausas exponenciales (2s, 4s, 8s).
        
        Args:
            url: URL a consultar
            params: Parámetros de la URL (opcional)
            
        Returns:
            Respuesta HTTP
            
        Ejemplo de uso:
            response = await self.fetch_url('https://api.example.com', {'page': 1})
        """
        async with httpx.AsyncClient(**self.client_config) as client:
            print(f"  📡 Fetching: {url}")
            response = await client.get(url, params=params)
            response.raise_for_status()  # Lanzar error si status no es 200
            return response
    
    async def scrape(self) -> List[Dict]:
        """
        Método principal de scraping.
        
        ESTE MÉTODO DEBE SER IMPLEMENTADO por cada scraper específico.
        Es como decir: "cada scraper tiene que tener su propia forma de scrapear".
        
        Returns:
            Lista de vulnerabilidades encontradas
        """
        raise NotImplementedError(
            f"El scraper '{self.name}' debe implementar el método scrape()"
        )
    
    def normalize_vulnerability(self, raw_data: Dict) -> Dict:
      """
      Normalizar datos de vulnerabilidad a nuestro formato estándar.
      """
      return {
          'cve_id': raw_data.get('cve_id'),
          'source_id': raw_data.get('source_id'),
          'component_type': raw_data.get('component_type', 'plugin'),
          'component_slug': raw_data.get('component_slug'),
          'component_name': raw_data.get('component_name'),
          'affected_versions': raw_data.get('affected_versions', []),
          'patched_in': raw_data.get('patched_in'),
          'severity': raw_data.get('severity', 'medium'),
          'cvss_score': raw_data.get('cvss_score'),
          'title': raw_data.get('title'),
          'description': raw_data.get('description'),
          'vuln_type': raw_data.get('vuln_type'),
          'reference_urls': raw_data.get('reference_urls', {}),  # ← CAMBIADO
          'published_date': raw_data.get('published_date'),
          'discovered_by': raw_data.get('discovered_by'),
          'source': self.name,
          'verified': False,
          'active': True
      }
    
    def calculate_severity(self, cvss_score: Optional[float]) -> str:
        """
        Calcular severidad basada en CVSS score.
        
        CVSS es un estándar para medir la severidad de vulnerabilidades (0-10).
        Este método convierte el número a una palabra.
        
        Args:
            cvss_score: Score CVSS (0-10)
            
        Returns:
            Severidad en texto: 'critical', 'high', 'medium', 'low'
        """
        if not cvss_score:
            return 'medium'
        
        if cvss_score >= 9.0:
            return 'critical'
        elif cvss_score >= 7.0:
            return 'high'
        elif cvss_score >= 4.0:
            return 'medium'
        else:
            return 'low'
    
    async def run(self) -> List[Dict]:
        """
        Ejecutar el scraping completo.
        
        Este método:
        1. Llama a scrape() para obtener datos
        2. Normaliza cada vulnerabilidad
        3. Retorna la lista normalizada
        
        Returns:
            Lista de vulnerabilidades normalizadas
        """
        print(f"\n🚀 Starting {self.name} scraper...")
        
        try:
            # Llamar al método scrape() específico de cada scraper
            raw_vulnerabilities = await self.scrape()
            
            print(f"  ✅ Found {len(raw_vulnerabilities)} vulnerabilities")
            
            # Normalizar todas las vulnerabilidades
            normalized = [
                self.normalize_vulnerability(vuln) 
                for vuln in raw_vulnerabilities
            ]
            
            print(f"  ✅ Normalized {len(normalized)} vulnerabilities")
            
            return normalized
            
        except Exception as e:
            print(f"  ❌ Error in {self.name} scraper: {e}")
            return []
