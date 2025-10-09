"""
WordPress.org Scraper
Obtiene vulnerabilidades desde el repositorio oficial de WordPress.

FUENTES:
1. API de WordPress.org para obtener lista de plugins
2. Changelogs de cada plugin buscando menciones de seguridad
3. README files con información de versiones
"""
import re
import httpx
from typing import List, Dict, Optional
from datetime import datetime
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper


class WordPressScraper(BaseScraper):
    """
    Scraper del repositorio oficial de WordPress.org
    
    Estrategia:
    1. Obtener lista de plugins populares (API oficial)
    2. Para cada plugin, revisar changelog
    3. Buscar palabras clave de seguridad
    4. Extraer información de versiones afectadas
    """
    
    def __init__(self):
        super().__init__(name='wordpress')
        self.api_base = 'https://api.wordpress.org/plugins/info/1.2/'
        self.plugin_page_base = 'https://wordpress.org/plugins'
        
        # Palabras clave que indican una vulnerabilidad de seguridad
        self.security_keywords = [
            'security',
            'vulnerability',
            'xss',
            'sql injection',
            'csrf',
            'remote code execution',
            'rce',
            'authentication bypass',
            'privilege escalation',
            'arbitrary file',
            'path traversal',
            'security fix',
            'security patch',
            'security issue',
            'security update',
            'cve-',
            'exploit'
        ]
    
    async def scrape(self) -> List[Dict]:
        """
        Método principal de scraping
        
        Returns:
            Lista de vulnerabilidades encontradas
        """
        vulnerabilities = []
        
        # Paso 1: Obtener lista de plugins populares
        print("  📋 Getting list of popular plugins...")
        plugins = await self.get_popular_plugins(per_page=100, pages=5)  # 500 plugins
        print(f"  ✅ Got {len(plugins)} plugins to analyze")
        
        # Paso 2: Analizar cada plugin
        for i, plugin in enumerate(plugins, 1):
            print(f"  🔍 [{i}/{len(plugins)}] Analyzing: {plugin['slug']}")
            
            try:
                plugin_vulns = await self.analyze_plugin(plugin)
                vulnerabilities.extend(plugin_vulns)
                
                if plugin_vulns:
                    print(f"    ⚠️  Found {len(plugin_vulns)} vulnerabilities")
                
            except Exception as e:
                print(f"    ❌ Error analyzing {plugin['slug']}: {e}")
                continue
        
        return vulnerabilities
    
    async def get_popular_plugins(self, per_page: int = 100, pages: int = 1) -> List[Dict]:
        """
        Obtener lista de plugins populares desde la API de WordPress.org
        
        Args:
            per_page: Plugins por página
            pages: Número de páginas a obtener
            
        Returns:
            Lista de plugins
        """
        plugins = []
        
        for page in range(1, pages + 1):
            try:
                response = await self.fetch_url(
                    self.api_base,
                    params={
                        'action': 'query_plugins',
                        'request[browse]': 'popular',
                        'request[per_page]': per_page,
                        'request[page]': page
                    }
                )
                
                data = response.json()
                
                if 'plugins' in data:
                    plugins.extend(data['plugins'])
                
            except Exception as e:
                print(f"    ⚠️  Error fetching page {page}: {e}")
        
        return plugins
    
    async def analyze_plugin(self, plugin: Dict) -> List[Dict]:
        """
        Analizar un plugin específico buscando vulnerabilidades
        
        Args:
            plugin: Datos del plugin desde la API
            
        Returns:
            Lista de vulnerabilidades encontradas
        """
        vulnerabilities = []
        slug = plugin['slug']
        
        # Obtener changelog del plugin
        changelog = await self.get_plugin_changelog(slug)
        
        if not changelog:
            return []
        
        # Buscar entradas de changelog que mencionen seguridad
        security_entries = self.find_security_entries(changelog)
        
        # Convertir cada entrada a vulnerabilidad
        for entry in security_entries:
            vuln = self.parse_security_entry(
                entry=entry,
                plugin_slug=slug,
                plugin_name=plugin.get('name', slug)
            )
            
            if vuln:
                vulnerabilities.append(vuln)
        
        return vulnerabilities
    
    async def get_plugin_changelog(self, slug: str) -> Optional[str]:
        """
        Obtener el changelog de un plugin
        
        Args:
            slug: Slug del plugin
            
        Returns:
            Texto del changelog o None si no se encuentra
        """
        try:
            # La página de changelog está en: /plugins/{slug}/#developers
            url = f"{self.plugin_page_base}/{slug}/"
            
            response = await self.fetch_url(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # El changelog suele estar en una sección específica
            changelog_section = soup.find('div', {'id': 'developers'})
            
            if changelog_section:
                return changelog_section.get_text()
            
            # Alternativa: buscar en todo el contenido
            return soup.get_text()
            
        except Exception as e:
            print(f"      ⚠️  Could not fetch changelog: {e}")
            return None
    
    def find_security_entries(self, changelog: str) -> List[Dict]:
        """
        Buscar entradas de changelog que mencionen seguridad
        
        Args:
            changelog: Texto completo del changelog
            
        Returns:
            Lista de entradas relacionadas con seguridad
        """
        entries = []
        
        # Dividir changelog en versiones
        # Patrón común: "= 1.2.3 = " o "Version 1.2.3"
        version_pattern = r'(?:=\s*)?(?:Version\s+)?(\d+\.\d+(?:\.\d+)?)\s*=?'
        
        # Dividir por versiones
        sections = re.split(version_pattern, changelog, flags=re.IGNORECASE)
        
        # sections será: ['texto antes', '1.2.3', 'contenido versión 1.2.3', '1.2.2', ...]
        for i in range(1, len(sections), 2):
            if i + 1 < len(sections):
                version = sections[i].strip()
                content = sections[i + 1].strip()
                
                # Verificar si menciona seguridad
                content_lower = content.lower()
                
                for keyword in self.security_keywords:
                    if keyword in content_lower:
                        entries.append({
                            'version': version,
                            'content': content,
                            'matched_keyword': keyword
                        })
                        break  # Ya encontramos match, no seguir buscando
        
        return entries
    
    def parse_security_entry(self, entry: Dict, plugin_slug: str, plugin_name: str) -> Optional[Dict]:
        """
        Convertir entrada de changelog en vulnerabilidad estructurada
        
        Args:
            entry: Entrada del changelog con info de seguridad
            plugin_slug: Slug del plugin
            plugin_name: Nombre del plugin
            
        Returns:
            Vulnerabilidad normalizada o None
        """
        version = entry['version']
        content = entry['content']
        keyword = entry['matched_keyword']
        
        # Determinar tipo de vulnerabilidad
        vuln_type = self.detect_vulnerability_type(content)
        
        # Determinar severidad (por ahora, heurística simple)
        severity = self.estimate_severity(content, vuln_type)
        
        # Extraer título del changelog
        title = self.extract_title(content, plugin_name, version)
        
        return {
            'component_type': 'plugin',
            'component_slug': plugin_slug,
            'component_name': plugin_name,
            'patched_in': version,
            'affected_versions': [f'< {version}'],  # Versiones anteriores están afectadas
            'severity': severity,
            'title': title,
            'description': content[:500],  # Primeros 500 caracteres
            'vuln_type': vuln_type,
            'reference_urls': {
                'wordpress_org': f"{self.plugin_page_base}/{plugin_slug}/",
                'changelog': f"{self.plugin_page_base}/{plugin_slug}/#developers"
            },
            'published_date': datetime.now().isoformat(),
            'source_id': f"wordpress-{plugin_slug}-{version}"
        }
    
    def detect_vulnerability_type(self, content: str) -> str:
        """
        Detectar tipo de vulnerabilidad basado en el contenido
        
        Args:
            content: Texto del changelog
            
        Returns:
            Tipo de vulnerabilidad
        """
        content_lower = content.lower()
        
        # Orden de prioridad en detección
        if 'rce' in content_lower or 'remote code execution' in content_lower:
            return 'RCE'
        elif 'sql injection' in content_lower or 'sqli' in content_lower:
            return 'SQLi'
        elif 'xss' in content_lower or 'cross-site scripting' in content_lower:
            return 'XSS'
        elif 'csrf' in content_lower or 'cross-site request forgery' in content_lower:
            return 'CSRF'
        elif 'authentication bypass' in content_lower or 'auth bypass' in content_lower:
            return 'Authentication Bypass'
        elif 'privilege escalation' in content_lower:
            return 'Privilege Escalation'
        elif 'path traversal' in content_lower or 'directory traversal' in content_lower:
            return 'Path Traversal'
        elif 'arbitrary file' in content_lower:
            return 'Arbitrary File Upload'
        else:
            return 'Security Issue'
    
    def estimate_severity(self, content: str, vuln_type: str) -> str:
        """
        Estimar severidad basada en tipo y contenido
        
        Args:
            content: Texto del changelog
            vuln_type: Tipo de vulnerabilidad
            
        Returns:
            Severidad: 'critical', 'high', 'medium', 'low'
        """
        content_lower = content.lower()
        
        # Critical: RCE, SQLi crítico
        if vuln_type in ['RCE', 'SQLi']:
            return 'critical'
        
        # High: Auth bypass, privilege escalation, XSS stored
        if vuln_type in ['Authentication Bypass', 'Privilege Escalation']:
            return 'high'
        
        if 'stored xss' in content_lower:
            return 'high'
        
        # Medium: CSRF, XSS reflected, file upload
        if vuln_type in ['CSRF', 'XSS', 'Arbitrary File Upload']:
            return 'medium'
        
        # Default
        return 'medium'
    
    def extract_title(self, content: str, plugin_name: str, version: str) -> str:
        """
        Extraer título descriptivo de la vulnerabilidad
        
        Args:
            content: Contenido del changelog
            plugin_name: Nombre del plugin
            version: Versión parcheada
            
        Returns:
            Título descriptivo
        """
        # Buscar primera línea no vacía
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        if lines:
            first_line = lines[0]
            # Limpiar caracteres especiales
            first_line = re.sub(r'^[\*\-\+]\s*', '', first_line)
            
            if len(first_line) > 100:
                first_line = first_line[:97] + '...'
            
            return f"{plugin_name} - {first_line}"
        
        # Fallback
        return f"{plugin_name} - Security fix in version {version}"
