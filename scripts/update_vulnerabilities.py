"""
Script principal para actualizar la base de datos de vulnerabilidades
Ejecutar diariamente con Railway Cron
"""
import asyncio
import os
import sys

# Añadir path del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.scrapers.aggregator import VulnerabilityAggregator
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()


async def main():
    """
    Función principal
    """
    print("🛡️  SpamGuard Vulnerability Database Updater")
    print("=" * 60)
    
    # Obtener credenciales
    nvd_api_key = os.getenv('NVD_API_KEY')  # Opcional
    github_token = os.getenv('GITHUB_TOKEN')  # Opcional
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    if not supabase_url or not supabase_key:
        print("❌ Error: SUPABASE_URL and SUPABASE_KEY are required")
        return
    
    # Crear aggregator
    aggregator = VulnerabilityAggregator(
        nvd_api_key=nvd_api_key,
        github_token=github_token,
        supabase_url=supabase_url,
        supabase_key=supabase_key
    )
    
    # Ejecutar scraping
    results = await aggregator.scrape_all()
    
    # Mostrar resultados finales
    print("\n🎉 Update completed!")
    print(f"   Total vulnerabilities found: {results['total_found']}")
    print(f"   Unique vulnerabilities: {results['unique']}")
    print(f"   Saved to database: {results['saved']}")
    print(f"   Duration: {results['duration_seconds']:.2f} seconds")


if __name__ == '__main__':
    asyncio.run(main())
