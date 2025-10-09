"""
Vulnerability Aggregator
Combina todos los scrapers y elimina duplicados
"""
import asyncio
from typing import List, Dict
from datetime import datetime
from supabase import create_client, Client
import os

from .wordpress_scraper import WordPressScraper
from .nvd_scraper import NVDScraper
from .github_scraper import GitHubScraper


class VulnerabilityAggregator:
    """
    Agregador de vulnerabilidades desde múltiples fuentes
    
    Combina scrapers de:
    - WordPress.org
    - NVD (National Vulnerability Database)
    - GitHub Security Advisories
    """
    
    def __init__(
        self,
        nvd_api_key: str = None,
        github_token: str = None,
        supabase_url: str = None,
        supabase_key: str = None
    ):
        """
        Args:
            nvd_api_key: API key de NVD (opcional)
            github_token: GitHub token (opcional)
            supabase_url: URL de Supabase
            supabase_key: Key de Supabase
        """
        # Inicializar scrapers
        self.scrapers = {
            'wordpress': WordPressScraper(),
            'nvd': NVDScraper(api_key=nvd_api_key),
            'github': GitHubScraper(github_token=github_token)
        }
        
        # Supabase client
        self.supabase_url = supabase_url or os.getenv('SUPABASE_URL')
        self.supabase_key = supabase_key or os.getenv('SUPABASE_KEY')
        
        if self.supabase_url and self.supabase_key:
            self.supabase: Client = create_client(self.supabase_url, self.supabase_key)
        else:
            self.supabase = None
            print("⚠️  No Supabase credentials. Will not save to database.")
    
    async def scrape_all(self) -> Dict:
        """
        Ejecutar todos los scrapers en paralelo
        
        Returns:
            Diccionario con resultados
        """
        print("🚀 Starting vulnerability aggregation from all sources\n")
        print("=" * 60)
        
        start_time = datetime.now()
        
        # Ejecutar scrapers en paralelo
        tasks = [
            scraper.run() 
            for scraper in self.scrapers.values()
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Combinar resultados
        all_vulnerabilities = []
        stats = {}
        
        for source_name, result in zip(self.scrapers.keys(), results):
            if isinstance(result, Exception):
                print(f"\n❌ {source_name} failed: {result}")
                stats[source_name] = {'count': 0, 'error': str(result)}
            else:
                print(f"\n✅ {source_name}: {len(result)} vulnerabilities")
                all_vulnerabilities.extend(result)
                stats[source_name] = {'count': len(result)}
        
        print("\n" + "=" * 60)
        print(f"\n📊 AGGREGATION RESULTS:")
        print(f"   Total vulnerabilities (before deduplication): {len(all_vulnerabilities)}")
        
        # Deduplicar
        unique_vulnerabilities = self.deduplicate(all_vulnerabilities)
        print(f"   Unique vulnerabilities (after deduplication): {len(unique_vulnerabilities)}")
        
        # Guardar en BD
        saved_count = 0
        if self.supabase:
            saved_count = await self.save_to_database(unique_vulnerabilities)
            print(f"   Saved to database: {saved_count}")
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"\n⏱️  Total time: {duration:.2f} seconds")
        print("=" * 60)
        
        return {
            'total_found': len(all_vulnerabilities),
            'unique': len(unique_vulnerabilities),
            'saved': saved_count,
            'duration_seconds': duration,
            'by_source': stats,
            'vulnerabilities': unique_vulnerabilities
        }
    
    def deduplicate(self, vulnerabilities: List[Dict]) -> List[Dict]:
        """
        Eliminar vulnerabilidades duplicadas
        
        Estrategia:
        1. Si tienen mismo CVE_ID → duplicado
        2. Si no tienen CVE, comparar por slug + título
        
        Args:
            vulnerabilities: Lista de vulnerabilidades
            
        Returns:
            Lista sin duplicados
        """
        seen = {}
        unique = []
        
        for vuln in vulnerabilities:
            # Generar key única
            cve_id = vuln.get('cve_id')
            
            if cve_id:
                # Usar CVE como key principal
                key = cve_id
            else:
                # Usar combinación de slug + primeras palabras del título
                slug = vuln.get('component_slug', '')
                title_words = vuln.get('title', '').split()[:5]
                key = f"{slug}_{' '.join(title_words)}"
            
            if key not in seen:
                seen[key] = vuln
                unique.append(vuln)
            else:
                # Ya existe, mergear información
                seen[key] = self.merge_vulnerability_data(seen[key], vuln)
        
        return unique
    
    def merge_vulnerability_data(self, existing: Dict, new: Dict) -> Dict:
        """
        Mergear datos de dos vulnerabilidades duplicadas
        
        Estrategia: Mantener la info más completa
        
        Args:
            existing: Vulnerabilidad existente
            new: Nueva vulnerabilidad
            
        Returns:
            Vulnerabilidad mergeada
        """
        merged = existing.copy()
        
        # Si la nueva tiene CVE y la vieja no, actualizar
        if new.get('cve_id') and not existing.get('cve_id'):
            merged['cve_id'] = new['cve_id']
        
        # Si la nueva tiene CVSS score y la vieja no, actualizar
        if new.get('cvss_score') and not existing.get('cvss_score'):
            merged['cvss_score'] = new['cvss_score']
        
        # Mergear referencias
        existing_refs = existing.get('reference_urls', {})
        new_refs = new.get('reference_urls', {})
        
        merged_refs = existing_refs.copy()
        merged_refs.update(new_refs)
        merged['reference_urls'] = merged_refs
        
        # Usar descripción más larga
        if len(new.get('description', '')) > len(existing.get('description', '')):
            merged['description'] = new['description']
        
        return merged
    
    async def save_to_database(self, vulnerabilities: List[Dict]) -> int:
        """
        Guardar vulnerabilidades en Supabase
        
        Args:
            vulnerabilities: Lista de vulnerabilidades
            
        Returns:
            Número de vulnerabilidades guardadas
        """
        if not self.supabase:
            return 0
        
        print("\n💾 Saving to database...")
        saved_count = 0
        updated_count = 0
        
        for vuln in vulnerabilities:
            try:
                # Verificar si ya existe (por CVE o source_id)
                query = self.supabase.table('vulnerabilities').select('id')
                
                if vuln.get('cve_id'):
                    query = query.eq('cve_id', vuln['cve_id'])
                else:
                    query = query.eq('source_id', vuln.get('source_id'))
                
                existing = query.execute()
                
                if not existing.data:
                    # Insertar nuevo
                    self.supabase.table('vulnerabilities').insert(vuln).execute()
                    saved_count += 1
                else:
                    # Actualizar existente
                    vuln_id = existing.data[0]['id']
                    vuln['updated_at'] = datetime.now().isoformat()
                    self.supabase.table('vulnerabilities')\
                        .update(vuln)\
                        .eq('id', vuln_id)\
                        .execute()
                    updated_count += 1
                
            except Exception as e:
                print(f"  ❌ Error saving vulnerability: {e}")
                continue
        
        print(f"  ✅ Inserted: {saved_count}")
        print(f"  🔄 Updated: {updated_count}")
        
        return saved_count + updated_count
