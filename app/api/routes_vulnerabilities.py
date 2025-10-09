"""
Vulnerability API Routes
Endpoints para consultar vulnerabilidades de WordPress
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta

from app.api.dependencies import verify_api_key
from app.database import supabase


router = APIRouter(prefix="/api/v1/vulnerabilities", tags=["vulnerabilities"])


# ============================================
# MODELOS PYDANTIC
# ============================================

class ComponentCheckRequest(BaseModel):
    """Request para verificar vulnerabilidades de componentes"""
    components: List[dict]


class BulkCheckResponse(BaseModel):
    """Respuesta de verificación masiva"""
    total_checked: int
    vulnerable_count: int
    vulnerable_components: List[dict]
    all_results: List[dict]


# ============================================
# ENDPOINTS
# ============================================

@router.post("/check", response_model=BulkCheckResponse)
async def check_vulnerabilities(
    request: ComponentCheckRequest,
    site_id: str = Depends(verify_api_key)
):
    """
    Verificar vulnerabilidades en plugins, themes y WordPress core
    
    Request body example:
    {
      "components": [
        {"type": "core", "version": "6.4.2"},
        {"type": "plugin", "slug": "woocommerce", "version": "8.0.0"},
        {"type": "theme", "slug": "twentytwentyfour", "version": "1.0"}
      ]
    }
    """
    results = []
    vulnerable_components = []
    
    for component in request.components:
        component_type = component.get('type', 'plugin')
        component_slug = component.get('slug', '')
        component_version = component.get('version', '')
        
        if not component_slug and component_type != 'core':
            continue
        
        # Buscar vulnerabilidades en BD
        query = supabase.table('vulnerabilities')\
            .select('*')\
            .eq('component_type', component_type)\
            .eq('active', True)
        
        if component_type != 'core':
            query = query.eq('component_slug', component_slug)
        
        response = query.execute()
        
        # Filtrar por versión
        matching_vulns = []
        
        for vuln in response.data:
            if is_version_vulnerable(
                component_version, 
                vuln.get('affected_versions', []), 
                vuln.get('patched_in')
            ):
                matching_vulns.append(vuln)
        
        component_result = {
            'type': component_type,
            'slug': component_slug,
            'version': component_version,
            'is_vulnerable': len(matching_vulns) > 0,
            'vulnerability_count': len(matching_vulns),
            'vulnerabilities': matching_vulns
        }
        
        results.append(component_result)
        
        if matching_vulns:
            vulnerable_components.append(component_result)
    
    return {
        'total_checked': len(request.components),
        'vulnerable_count': len(vulnerable_components),
        'vulnerable_components': vulnerable_components,
        'all_results': results
    }


@router.get("/search")
async def search_vulnerabilities(
    query: str = Query(..., description="Término de búsqueda"),
    component_type: Optional[str] = Query(None, description="Filtrar por tipo"),
    severity: Optional[str] = Query(None, description="Filtrar por severidad"),
    limit: int = Query(20, ge=1, le=100, description="Número de resultados"),
    site_id: str = Depends(verify_api_key)
):
    """
    Buscar vulnerabilidades por texto
    
    Ejemplos:
    - /api/v1/vulnerabilities/search?query=xss
    - /api/v1/vulnerabilities/search?query=woocommerce&severity=critical
    """
    db_query = supabase.table('vulnerabilities')\
        .select('*')\
        .eq('active', True)\
        .or_(f'title.ilike.%{query}%,description.ilike.%{query}%,component_slug.ilike.%{query}%')\
        .limit(limit)
    
    if component_type:
        db_query = db_query.eq('component_type', component_type)
    
    if severity:
        db_query = db_query.eq('severity', severity)
    
    response = db_query.execute()
    
    return {
        'success': True,
        'query': query,
        'filters': {
            'component_type': component_type,
            'severity': severity
        },
        'total_results': len(response.data),
        'results': response.data
    }


@router.get("/plugin/{slug}")
async def get_plugin_vulnerabilities(
    slug: str,
    site_id: str = Depends(verify_api_key)
):
    """Obtener vulnerabilidades de un plugin específico"""
    response = supabase.table('vulnerabilities')\
        .select('*')\
        .eq('component_type', 'plugin')\
        .eq('component_slug', slug)\
        .eq('active', True)\
        .order('published_date', desc=True)\
        .execute()
    
    return {
        'success': True,
        'plugin_slug': slug,
        'total_vulnerabilities': len(response.data),
        'vulnerabilities': response.data
    }


@router.get("/theme/{slug}")
async def get_theme_vulnerabilities(
    slug: str,
    site_id: str = Depends(verify_api_key)
):
    """Obtener vulnerabilidades de un theme específico"""
    response = supabase.table('vulnerabilities')\
        .select('*')\
        .eq('component_type', 'theme')\
        .eq('component_slug', slug)\
        .eq('active', True)\
        .order('published_date', desc=True)\
        .execute()
    
    return {
        'success': True,
        'theme_slug': slug,
        'total_vulnerabilities': len(response.data),
        'vulnerabilities': response.data
    }


@router.get("/stats")
async def get_vulnerability_stats(
    site_id: str = Depends(verify_api_key)
):
    """Obtener estadísticas generales de vulnerabilidades"""
    
    # Total
    total = supabase.table('vulnerabilities')\
        .select('id', count='exact')\
        .eq('active', True)\
        .execute()
    
    # Por severidad
    severities = ['critical', 'high', 'medium', 'low']
    by_severity = {}
    
    for severity in severities:
        count = supabase.table('vulnerabilities')\
            .select('id', count='exact')\
            .eq('severity', severity)\
            .eq('active', True)\
            .execute()
        by_severity[severity] = count.count
    
    # Por tipo
    types = ['plugin', 'theme', 'core']
    by_type = {}
    
    for comp_type in types:
        count = supabase.table('vulnerabilities')\
            .select('id', count='exact')\
            .eq('component_type', comp_type)\
            .eq('active', True)\
            .execute()
        by_type[comp_type] = count.count
    
    # Recientes (últimos 30 días)
    thirty_days_ago = (datetime.now() - timedelta(days=30)).isoformat()
    
    recent = supabase.table('vulnerabilities')\
        .select('id', count='exact')\
        .gte('published_date', thirty_days_ago)\
        .eq('active', True)\
        .execute()
    
    return {
        'success': True,
        'total_vulnerabilities': total.count,
        'by_severity': by_severity,
        'by_type': by_type,
        'recent_count': recent.count,
        'last_updated': datetime.now().isoformat()
    }


@router.get("/recent")
async def get_recent_vulnerabilities(
    days: int = Query(30, ge=1, le=365, description="Días hacia atrás"),
    limit: int = Query(50, ge=1, le=100, description="Número de resultados"),
    site_id: str = Depends(verify_api_key)
):
    """Obtener vulnerabilidades recientes"""
    date_from = (datetime.now() - timedelta(days=days)).isoformat()
    
    response = supabase.table('vulnerabilities')\
        .select('*')\
        .gte('published_date', date_from)\
        .eq('active', True)\
        .order('published_date', desc=True)\
        .limit(limit)\
        .execute()
    
    return {
        'success': True,
        'days': days,
        'total_results': len(response.data),
        'vulnerabilities': response.data
    }


# ============================================
# HELPER FUNCTIONS
# ============================================

def is_version_vulnerable(
    current_version: str,
    affected_versions: List[str],
    patched_in: Optional[str]
) -> bool:
    """
    Verificar si una versión está afectada por una vulnerabilidad
    """
    from packaging import version
    
    try:
        current = version.parse(current_version)
    except:
        return False
    
    # Verificar con patched_in
    if patched_in:
        try:
            patched = version.parse(patched_in)
            if current < patched:
                return True
        except:
            pass
    
    # Verificar rangos de affected_versions
    for version_range in affected_versions:
        if check_version_range(current_version, version_range):
            return True
    
    return False


def check_version_range(current_version: str, version_range: str) -> bool:
    """
    Verificar si una versión está dentro de un rango
    
    Ejemplos: "< 2.0", "<= 3.0", ">= 1.5", ">= 1.0 < 2.0"
    """
    from packaging import version
    import re
    
    try:
        current = version.parse(current_version)
    except:
        return False
    
    patterns = [
        (r'<\s*(\d+\.\d+(?:\.\d+)?)', lambda v: current < version.parse(v)),
        (r'<=\s*(\d+\.\d+(?:\.\d+)?)', lambda v: current <= version.parse(v)),
        (r'>\s*(\d+\.\d+(?:\.\d+)?)', lambda v: current > version.parse(v)),
        (r'>=\s*(\d+\.\d+(?:\.\d+)?)', lambda v: current >= version.parse(v)),
    ]
    
    conditions_met = True
    
    for pattern, comparator in patterns:
        matches = re.findall(pattern, version_range)
        for match in matches:
            try:
                if not comparator(match):
                    conditions_met = False
                    break
            except:
                continue
    
    return conditions_met
