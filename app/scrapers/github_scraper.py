"""
GitHub Security Advisories Scraper
Obtiene security advisories relacionados con WordPress

API: https://docs.github.com/en/graphql/overview/explorer

IMPORTANTE:
- API pública: 60 requests/hora sin autenticación
- Con token: 5000 requests/hora
- Token gratuito: https://github.com/settings/tokens
"""
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from .base_scraper import BaseScraper


class GitHubScraper(BaseScraper):
    """
    Scraper de GitHub Security Advisories
    
    Estrategia:
    1. Usar GraphQL API de GitHub
    2. Filtrar advisories relacionados con WordPress
    3. Extraer información estructurada
    """
    
    def __init__(self, github_token: Optional[str] = None):
        """
        Args:
            github_token: GitHub personal access token (opcional pero recomendado)
                         Crear en: https://github.com/settings/tokens
                         Permisos necesarios: public_repo (solo lectura)
        """
        super().__init__(name='github')
        self.api_url = 'https://api.github.com/graphql'
        self.github_token = github_token
    
    async def scrape(self) -> List[Dict]:
        """
        Método principal de scraping
        
        Returns:
            Lista de vulnerabilidades encontradas
        """
        if not self.github_token:
            print("  ⚠️  No GitHub token provided. Limited to 60 requests/hour.")
            print("     Get a free token at: https://github.com/settings/tokens")
        
        vulnerabilities = []
        
        # Hacer query GraphQL
        print("  🔍 Querying GitHub Security Advisories...")
        
        advisories = await self.fetch_advisories()
        
        print(f"  ✅ Found {len(advisories)} advisories")
        
        # Parsear cada advisory
        for advisory in advisories:
            vuln = self.parse_advisory(advisory)
            if vuln:
                vulnerabilities.append(vuln)
        
        return vulnerabilities
    
    async def fetch_advisories(self) -> List[Dict]:
        """
        Obtener security advisories desde GitHub GraphQL API
        
        Returns:
            Lista de advisories
        """
        # Query GraphQL
        query = """
        query($cursor: String) {
          securityAdvisories(first: 100, after: $cursor) {
            pageInfo {
              hasNextPage
              endCursor
            }
            nodes {
              ghsaId
              summary
              description
              severity
              publishedAt
              updatedAt
              withdrawnAt
              vulnerabilities(first: 10) {
                nodes {
                  package {
                    name
                    ecosystem
                  }
                  vulnerableVersionRange
                  firstPatchedVersion {
                    identifier
                  }
                }
              }
              references {
                url
              }
              cwes(first: 5) {
                nodes {
                  cweId
                  name
                }
              }
            }
          }
        }
        """
        
        all_advisories = []
        cursor = None
        has_next_page = True
        
        headers = {
            'Content-Type': 'application/json'
        }
        
        if self.github_token:
            headers['Authorization'] = f'Bearer {self.github_token}'
        
        while has_next_page:
            variables = {'cursor': cursor}
            
            try:
                async with self.get_client(headers=headers) as client:
                    response = await client.post(
                        self.api_url,
                        json={'query': query, 'variables': variables}
                    )
                    response.raise_for_status()
                    data = response.json()
                
                if 'errors' in data:
                    print(f"  ❌ GraphQL errors: {data['errors']}")
                    break
                
                advisories_data = data['data']['securityAdvisories']
                nodes = advisories_data['nodes']
                
                # Filtrar solo los relacionados con WordPress
                wordpress_advisories = [
                    adv for adv in nodes 
                    if self.is_wordpress_related(adv)
                ]
                
                all_advisories.extend(wordpress_advisories)
                
                # Paginación
                page_info = advisories_data['pageInfo']
                has_next_page = page_info['hasNextPage']
                cursor = page_info['endCursor']
                
                print(f"    Fetched {len(wordpress_advisories)} WordPress-related advisories")
                
                # Límite de seguridad (máximo 5 páginas = 500 advisories)
                if len(all_advisories) >= 500:
                    print("  ⚠️  Reached 500 advisories limit")
                    break
                
            except Exception as e:
                print(f"  ❌ Error fetching advisories: {e}")
                break
        
        return all_advisories
    
    def get_client(self, headers: Dict = None):
        """
        Crear cliente HTTP personalizado
        """
        import httpx
        
        config = self.client_config.copy()
        if headers:
            config['headers'].update(headers)
        
        return httpx.AsyncClient(**config)
    
    def is_wordpress_related(self, advisory: Dict) -> bool:
        """
        Verificar si un advisory es relevante para WordPress
        
        Args:
            advisory: Datos del advisory
            
        Returns:
            True si es relevante
        """
        summary = advisory.get('summary', '').lower()
        description = advisory.get('description', '').lower()
        
        wordpress_keywords = ['wordpress', 'wp-', 'woocommerce']
        
        for keyword in wordpress_keywords:
            if keyword in summary or keyword in description:
                return True
        
        # Verificar en vulnerabilities
        vulnerabilities = advisory.get('vulnerabilities', {}).get('nodes', [])
        for vuln in vulnerabilities:
            package_name = vuln.get('package', {}).get('name', '').lower()
            if any(kw in package_name for kw in wordpress_keywords):
                return True
        
        return False
    
    def parse_advisory(self, advisory: Dict) -> Optional[Dict]:
        """
        Parsear advisory de GitHub a nuestro formato
        
        Args:
            advisory: Datos del advisory
            
        Returns:
            Vulnerabilidad normalizada
        """
        ghsa_id = advisory.get('ghsaId')
        summary = advisory.get('summary')
        description = advisory.get('description')
        severity = advisory.get('severity', 'MODERATE').lower()
        
        # Mapear severidad de GitHub a nuestro formato
        severity_map = {
            'critical': 'critical',
            'high': 'high',
            'moderate': 'medium',
            'low': 'low'
        }
        mapped_severity = severity_map.get(severity, 'medium')
        
        # Extraer información del paquete
        vulnerabilities = advisory.get('vulnerabilities', {}).get('nodes', [])
        
        if not vulnerabilities:
            return None
        
        first_vuln = vulnerabilities[0]
        package = first_vuln.get('package', {})
        package_name = package.get('name', '')
        
        # Determinar si es plugin o theme
        component_type = 'plugin'  # Por defecto
        if 'theme' in package_name.lower() or 'theme' in summary.lower():
            component_type = 'theme'
        
        # Versiones afectadas
        version_range = first_vuln.get('vulnerableVersionRange', '')
        patched_version = first_vuln.get('firstPatchedVersion', {})
        patched_in = patched_version.get('identifier') if patched_version else None
        
        # Tipo de vulnerabilidad desde CWE
        vuln_type = self.extract_vulnerability_type(advisory)
        
        # Referencias
        references = advisory.get('references', [])
        reference_urls = {
            'github': f"https://github.com/advisories/{ghsa_id}",
            'references': [ref['url'] for ref in references[:5]]
        }
        
        # Fechas
        published_at = advisory.get('publishedAt')
        
        return {
            'source_id': f"github-{ghsa_id}",
            'component_type': component_type,
            'component_slug': self.slugify(package_name),
            'component_name': package_name,
            'affected_versions': [version_range] if version_range else [],
            'patched_in': patched_in,
            'severity': mapped_severity,
            'title': summary,
            'description': description[:500] if description else summary,
            'vuln_type': vuln_type,
            'reference_urls': reference_urls,
            'published_date': published_at
        }
    
    def extract_vulnerability_type(self, advisory: Dict) -> str:
        """
        Extraer tipo de vulnerabilidad desde CWEs
        
        Args:
            advisory: Datos del advisory
            
        Returns:
            Tipo de vulnerabilidad
        """
        cwes = advisory.get('cwes', {}).get('nodes', [])
        
        if not cwes:
            return 'Security Issue'
        
        first_cwe = cwes[0]
        cwe_id = first_cwe.get('cweId', '')
        
        # Mapear CWE a nombres amigables
        cwe_map = {
            'CWE-79': 'XSS',
            'CWE-89': 'SQLi',
            'CWE-352': 'CSRF',
            'CWE-94': 'Code Injection',
            'CWE-434': 'File Upload',
            'CWE-22': 'Path Traversal',
        }
        
        return cwe_map.get(cwe_id, 'Security Issue')
    
    def slugify(self, text: str) -> str:
        """
        Convertir texto a slug
        
        Args:
            text: Texto a convertir
            
        Returns:
            Slug (minúsculas, guiones)
        """
        import re
        
        text = text.lower()
        text = re.sub(r'[^a-z0-9\s\-]', '', text)
        text = re.sub(r'[\s\-]+', '-', text)
        return text.strip('-')
