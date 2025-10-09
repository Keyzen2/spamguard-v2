"""
NVD (National Vulnerability Database) Scraper
Obtiene CVEs oficiales relacionados con WordPress

API Documentation: https://nvd.nist.gov/developers/vulnerabilities

IMPORTANTE: 
- API pública sin key: 5 requests cada 30 segundos
- Con API key (gratuita): 50 requests cada 30 segundos
- Respetar rate limits es CRÍTICO
"""
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from .base_scraper import BaseScraper


class NVDScraper(BaseScraper):
    """
    Scraper de la National Vulnerability Database (NVD)
    
    Estrategia:
    1. Buscar CVEs con keyword "wordpress"
    2. Filtrar solo los relevantes para plugins/themes
    3. Extraer información estructurada
    4. Respetar rate limits
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: API key de NVD (opcional, pero recomendado)
                    Obtener gratis en: https://nvd.nist.gov/developers/request-an-api-key
        """
        super().__init__(name='nvd')
        self.api_base = 'https://services.nvd.nist.gov/rest/json/cves/2.0'
        self.api_key = api_key
        
        # Rate limiting
        # Sin API key: 5 requests/30s = 1 request cada 6 segundos
        # Con API key: 50 requests/30s = 1 request cada 0.6 segundos
        self.delay_between_requests = 0.7 if api_key else 6.5
        
        # Keywords para filtrar CVEs relevantes
        self.wordpress_keywords = [
            'wordpress plugin',
            'wordpress theme',
            'wp plugin',
            'wp theme'
        ]
    
    async def scrape(self) -> List[Dict]:
        """
        Método principal de scraping
        
        Returns:
            Lista de vulnerabilidades encontradas
        """
        vulnerabilities = []
        
        # Buscar CVEs de los últimos 2 años (para no saturar)
        # En producción, esto se ejecutaría diariamente solo con CVEs nuevos
        start_date = datetime.now() - timedelta(days=730)  # 2 años
        
        print(f"  📅 Searching CVEs since {start_date.date()}")
        
        # Hacer requests paginados
        start_index = 0
        results_per_page = 100  # Máximo permitido por NVD
        total_results = None
        
        while True:
            print(f"  📡 Fetching results {start_index} - {start_index + results_per_page}")
            
            try:
                # Hacer request con rate limiting
                response = await self.fetch_cves(
                    keyword='wordpress',
                    start_index=start_index,
                    results_per_page=results_per_page,
                    pub_start_date=start_date.strftime('%Y-%m-%dT00:00:00.000')
                )
                
                if not response:
                    break
                
                # Obtener total de resultados (solo en primera iteración)
                if total_results is None:
                    total_results = response.get('totalResults', 0)
                    print(f"  📊 Total CVEs found: {total_results}")
                
                # Procesar vulnerabilidades
                cves = response.get('vulnerabilities', [])
                
                for cve_item in cves:
                    cve = cve_item.get('cve', {})
                    
                    # Verificar que sea relevante para WordPress
                    if self.is_wordpress_related(cve):
                        vuln = self.parse_cve(cve)
                        if vuln:
                            vulnerabilities.append(vuln)
                
                # Verificar si hay más páginas
                start_index += results_per_page
                
                if start_index >= total_results:
                    break
                
                # Rate limiting: esperar antes del siguiente request
                print(f"  ⏳ Waiting {self.delay_between_requests}s (rate limiting)...")
                await asyncio.sleep(self.delay_between_requests)
                
            except Exception as e:
                print(f"  ❌ Error fetching CVEs: {e}")
                break
        
        return vulnerabilities
    
    async def fetch_cves(
        self, 
        keyword: str,
        start_index: int = 0,
        results_per_page: int = 100,
        pub_start_date: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Hacer request a la API de NVD
        
        Args:
            keyword: Palabra clave para buscar
            start_index: Índice de inicio para paginación
            results_per_page: Resultados por página (máx 100)
            pub_start_date: Fecha de inicio de publicación (ISO format)
            
        Returns:
            Respuesta JSON de la API
        """
        params = {
            'keywordSearch': keyword,
            'resultsPerPage': results_per_page,
            'startIndex': start_index
        }
        
        if pub_start_date:
            params['pubStartDate'] = pub_start_date
        
        headers = {}
        if self.api_key:
            headers['apiKey'] = self.api_key
        
        try:
            # Usar configuración personalizada para NVD
            async with self.get_client(headers=headers) as client:
                response = await client.get(self.api_base, params=params)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"      ⚠️  Request failed: {e}")
            return None
    
    def get_client(self, headers: Dict = None):
        """
        Crear cliente HTTP personalizado
        """
        import httpx
        
        config = self.client_config.copy()
        if headers:
            config['headers'].update(headers)
        
        return httpx.AsyncClient(**config)
    
    def is_wordpress_related(self, cve: Dict) -> bool:
        """
        Verificar si un CVE es relevante para WordPress
        
        Args:
            cve: Datos del CVE
            
        Returns:
            True si es relevante, False si no
        """
        # Obtener descripción
        descriptions = cve.get('descriptions', [])
        
        if not descriptions:
            return False
        
        # Descripción principal (inglés)
        description = descriptions[0].get('value', '').lower()
        
        # Verificar keywords
        for keyword in self.wordpress_keywords:
            if keyword in description:
                return True
        
        return False
    
    def parse_cve(self, cve: Dict) -> Optional[Dict]:
        """
        Parsear CVE de NVD a nuestro formato
        
        Args:
            cve: Datos del CVE desde NVD
            
        Returns:
            Vulnerabilidad normalizada
        """
        cve_id = cve.get('id')
        
        # Descripción
        descriptions = cve.get('descriptions', [])
        description = descriptions[0].get('value', '') if descriptions else ''
        
        # Extraer información del componente (plugin/theme)
        component_info = self.extract_component_info(description)
        
        if not component_info:
            return None  # No pudimos identificar el componente
        
        # CVSS Score (métrica de severidad)
        cvss_score = self.extract_cvss_score(cve)
        severity = self.calculate_severity(cvss_score)
        
        # Tipo de vulnerabilidad
        vuln_type = self.extract_vulnerability_type(cve)
        
        # Referencias
        references = self.extract_references(cve)
        
        # Fechas
        published_date = cve.get('published')
        last_modified = cve.get('lastModified')
        
        return {
            'cve_id': cve_id,
            'source_id': f"nvd-{cve_id}",
            'component_type': component_info['type'],
            'component_slug': component_info['slug'],
            'component_name': component_info['name'],
            'affected_versions': component_info.get('versions', []),
            'severity': severity,
            'cvss_score': cvss_score,
            'title': self.generate_title(cve_id, component_info['name']),
            'description': description,
            'vuln_type': vuln_type,
            'reference_urls': references,
            'published_date': published_date,
            'last_modified': last_modified
        }
    
    def extract_component_info(self, description: str) -> Optional[Dict]:
        """
        Extraer información del plugin/theme desde la descripción
        
        Args:
            description: Texto de la descripción del CVE
            
        Returns:
            Diccionario con info del componente o None
        """
        import re
        
        description_lower = description.lower()
        
        # Determinar tipo
        if 'plugin' in description_lower:
            component_type = 'plugin'
        elif 'theme' in description_lower:
            component_type = 'theme'
        else:
            return None
        
        # Intentar extraer nombre
        # Patrones comunes:
        # "The X plugin for WordPress"
        # "X WordPress plugin"
        # "WordPress X plugin"
        
        patterns = [
            r'the\s+([a-z0-9\s\-]+?)\s+(?:plugin|theme)\s+for\s+wordpress',
            r'([a-z0-9\s\-]+?)\s+wordpress\s+(?:plugin|theme)',
            r'wordpress\s+([a-z0-9\s\-]+?)\s+(?:plugin|theme)',
        ]
        
        name = None
        for pattern in patterns:
            match = re.search(pattern, description_lower)
            if match:
                name = match.group(1).strip()
                break
        
        if not name:
            # Fallback: tomar las primeras palabras
            words = description.split()[:5]
            name = ' '.join(words)
        
        # Generar slug (nombre sin espacios, minúsculas)
        slug = name.lower().replace(' ', '-').replace('_', '-')
        slug = re.sub(r'[^a-z0-9\-]', '', slug)
        
        # Intentar extraer versiones afectadas
        versions = self.extract_affected_versions(description)
        
        return {
            'type': component_type,
            'name': name.title(),
            'slug': slug,
            'versions': versions
        }
    
    def extract_affected_versions(self, description: str) -> List[str]:
        """
        Extraer versiones afectadas de la descripción
        
        Args:
            description: Texto de la descripción
            
        Returns:
            Lista de rangos de versiones
        """
        import re
        
        versions = []
        
        # Patrones comunes:
        # "versions before 1.2.3"
        # "version 1.0 through 1.5"
        # "versions up to 2.0"
        
        patterns = [
            (r'before\s+(?:version\s+)?(\d+\.\d+(?:\.\d+)?)', lambda v: f'< {v}'),
            (r'prior\s+to\s+(?:version\s+)?(\d+\.\d+(?:\.\d+)?)', lambda v: f'< {v}'),
            (r'up\s+to\s+(?:version\s+)?(\d+\.\d+(?:\.\d+)?)', lambda v: f'<= {v}'),
        ]
        
        for pattern, formatter in patterns:
            match = re.search(pattern, description.lower())
            if match:
                version = match.group(1)
                versions.append(formatter(version))
        
        return versions if versions else ['unknown']
    
    def extract_cvss_score(self, cve: Dict) -> Optional[float]:
        """
        Extraer CVSS score del CVE
        
        Args:
            cve: Datos del CVE
            
        Returns:
            CVSS score (0-10) o None
        """
        metrics = cve.get('metrics', {})
        
        # Intentar CVSS v3.1 primero (más reciente)
        cvss_v31 = metrics.get('cvssMetricV31', [])
        if cvss_v31:
            return cvss_v31[0].get('cvssData', {}).get('baseScore')
        
        # Intentar CVSS v3.0
        cvss_v30 = metrics.get('cvssMetricV30', [])
        if cvss_v30:
            return cvss_v30[0].get('cvssData', {}).get('baseScore')
        
        # Intentar CVSS v2
        cvss_v2 = metrics.get('cvssMetricV2', [])
        if cvss_v2:
            return cvss_v2[0].get('cvssData', {}).get('baseScore')
        
        return None
    
    def extract_vulnerability_type(self, cve: Dict) -> str:
        """
        Extraer tipo de vulnerabilidad
        
        Args:
            cve: Datos del CVE
            
        Returns:
            Tipo de vulnerabilidad
        """
        # Obtener CWE (Common Weakness Enumeration)
        weaknesses = cve.get('weaknesses', [])
        
        if weaknesses:
            cwe_data = weaknesses[0].get('description', [])
            if cwe_data:
                cwe_id = cwe_data[0].get('value', '')
                
                # Mapear CWE común a nombres amigables
                cwe_map = {
                    'CWE-79': 'XSS',
                    'CWE-89': 'SQLi',
                    'CWE-352': 'CSRF',
                    'CWE-94': 'Code Injection',
                    'CWE-434': 'File Upload',
                    'CWE-22': 'Path Traversal',
                    'CWE-287': 'Authentication Bypass',
                }
                
                return cwe_map.get(cwe_id, 'Security Issue')
        
        return 'Security Issue'
    
    def extract_references(self, cve: Dict) -> Dict:
        """
        Extraer URLs de referencia
        
        Args:
            cve: Datos del CVE
            
        Returns:
            Diccionario con URLs
        """
        references = cve.get('references', [])
        
        urls = {
            'nvd': f"https://nvd.nist.gov/vuln/detail/{cve.get('id')}",
            'references': []
        }
        
        for ref in references[:5]:  # Máximo 5 referencias
            url = ref.get('url')
            if url:
                urls['references'].append(url)
        
        return urls
    
    def generate_title(self, cve_id: str, component_name: str) -> str:
        """
        Generar título descriptivo
        
        Args:
            cve_id: ID del CVE
            component_name: Nombre del componente
            
        Returns:
            Título formateado
        """
        return f"{cve_id} - {component_name}"
