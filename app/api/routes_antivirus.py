"""
Rutas de la API para el módulo Antivirus
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import asyncio

from app.api.dependencies import verify_api_key, check_rate_limit
from app.modules.antivirus.scanner import FileScanner
from app.modules.antivirus.signatures import SignatureManager
from app.database import supabase

router = APIRouter(prefix="/api/v1/antivirus", tags=["antivirus"])

# ============================================
# MODELOS PYDANTIC
# ============================================

class ScanRequest(BaseModel):
    scan_type: str = Field(..., pattern="^(quick|full|custom)$")
    paths: Optional[List[str]] = None  # Para scan custom
    max_size_mb: int = Field(10, ge=1, le=50)
    
    class Config:
        json_schema_extra = {
            "example": {
                "scan_type": "quick",
                "max_size_mb": 10
            }
        }


class ScanProgressResponse(BaseModel):
    scan_id: str
    status: str
    progress: int
    files_scanned: int
    threats_found: int
    current_file: Optional[str] = None


class ThreatDetail(BaseModel):
    id: str
    file_path: str
    threat_type: str
    severity: str
    signature_matched: str
    code_snippet: str
    detected_at: str


class ScanResultResponse(BaseModel):
    scan_id: str
    status: str
    scan_type: str
    started_at: str
    completed_at: Optional[str]
    files_scanned: int
    threats_found: int
    threats: List[ThreatDetail]


# ============================================
# ENDPOINTS
# ============================================

@router.post("/scan/start")
async def start_scan(
    scan_request: ScanRequest,
    background_tasks: BackgroundTasks,
    site_id: str = Depends(verify_api_key),
    _: bool = Depends(check_rate_limit)
):
    """
    Iniciar un escaneo de malware
    
    Tipos de escaneo:
    - quick: Solo wp-content/plugins y wp-content/themes
    - full: Todo el sitio WordPress
    - custom: Rutas específicas
    """
    try:
        # Crear registro de escaneo en la BD
        scan_data = {
            'site_id': site_id,
            'scan_type': scan_request.scan_type,
            'status': 'pending',
            'started_at': datetime.utcnow().isoformat(),
            'files_scanned': 0,
            'threats_found': 0,
            'progress': 0
        }
        
        result = supabase.table('scans').insert(scan_data).execute()
        scan_id = result.data[0]['id']
        
        # Iniciar escaneo en background
        background_tasks.add_task(
            run_scan_background,
            scan_id,
            site_id,
            scan_request.scan_type,
            scan_request.paths,
            scan_request.max_size_mb
        )
        
        return {
            "success": True,
            "scan_id": scan_id,
            "message": "Scan started successfully",
            "status": "pending",
            "check_progress_at": f"/api/v1/antivirus/scan/{scan_id}/progress"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scan/{scan_id}/progress", response_model=ScanProgressResponse)
async def get_scan_progress(
    scan_id: str,
    site_id: str = Depends(verify_api_key)
):
    """
    Obtener progreso de un escaneo en curso
    """
    try:
        result = supabase.table('scans')\
            .select('*')\
            .eq('id', scan_id)\
            .eq('site_id', site_id)\
            .single()\
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        scan = result.data
        
        # Obtener archivo actual si está en progreso
        current_file = None
        if scan['status'] == 'running' and scan.get('results'):
            current_file = scan['results'].get('current_file')
        
        return ScanProgressResponse(
            scan_id=scan_id,
            status=scan['status'],
            progress=scan['progress'],
            files_scanned=scan['files_scanned'],
            threats_found=scan['threats_found'],
            current_file=current_file
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scan/{scan_id}/results", response_model=ScanResultResponse)
async def get_scan_results(
    scan_id: str,
    site_id: str = Depends(verify_api_key)
):
    """
    Obtener resultados completos de un escaneo
    """
    try:
        # Obtener escaneo
        scan_result = supabase.table('scans')\
            .select('*')\
            .eq('id', scan_id)\
            .eq('site_id', site_id)\
            .single()\
            .execute()
        
        if not scan_result.data:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        scan = scan_result.data
        
        # Obtener amenazas detectadas
        threats_result = supabase.table('threats')\
            .select('*')\
            .eq('scan_id', scan_id)\
            .order('severity', desc=True)\
            .execute()
        
        threats = [
            ThreatDetail(
                id=threat['id'],
                file_path=threat['file_path'],
                threat_type=threat['threat_type'],
                severity=threat['severity'],
                signature_matched=threat['signature_matched'],
                code_snippet=threat['code_snippet'],
                detected_at=threat['detected_at']
            )
            for threat in threats_result.data
        ]
        
        return ScanResultResponse(
            scan_id=scan_id,
            status=scan['status'],
            scan_type=scan['scan_type'],
            started_at=scan['started_at'],
            completed_at=scan.get('completed_at'),
            files_scanned=scan['files_scanned'],
            threats_found=scan['threats_found'],
            threats=threats
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scans/recent")
async def get_recent_scans(
    site_id: str = Depends(verify_api_key),
    limit: int = 10
):
    """
    Obtener escaneos recientes del sitio
    """
    try:
        result = supabase.table('scans')\
            .select('id, scan_type, status, started_at, completed_at, files_scanned, threats_found')\
            .eq('site_id', site_id)\
            .order('started_at', desc=True)\
            .limit(limit)\
            .execute()
        
        return {
            "scans": result.data,
            "total": len(result.data)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/threat/{threat_id}/quarantine")
async def quarantine_threat(
    threat_id: str,
    site_id: str = Depends(verify_api_key)
):
    """
    Poner una amenaza en cuarentena
    """
    try:
        # Obtener amenaza
        threat_result = supabase.table('threats')\
            .select('*')\
            .eq('id', threat_id)\
            .eq('site_id', site_id)\
            .single()\
            .execute()
        
        if not threat_result.data:
            raise HTTPException(status_code=404, detail="Threat not found")
        
        threat = threat_result.data
        
        # TODO: Implementar lógica de cuarentena real
        # Por ahora solo actualizamos el estado
        
        supabase.table('threats')\
            .update({'status': 'quarantined'})\
            .eq('id', threat_id)\
            .execute()
        
        return {
            "success": True,
            "message": "Threat quarantined successfully",
            "threat_id": threat_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/threat/{threat_id}/ignore")
async def ignore_threat(
    threat_id: str,
    site_id: str = Depends(verify_api_key)
):
    """
    Ignorar una amenaza (marcar como falso positivo)
    """
    try:
        supabase.table('threats')\
            .update({'status': 'ignored'})\
            .eq('id', threat_id)\
            .eq('site_id', site_id)\
            .execute()
        
        return {
            "success": True,
            "message": "Threat marked as false positive"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signatures")
async def get_signatures(
    site_id: str = Depends(verify_api_key)
):
    """
    Obtener firmas de malware disponibles
    """
    try:
        sig_manager = SignatureManager()
        signatures = sig_manager.load_signatures()
        
        return {
            "total": len(signatures),
            "signatures": signatures
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_antivirus_stats(
    site_id: str = Depends(verify_api_key)
):
    """
    Obtener estadísticas del antivirus
    """
    try:
        # Total de escaneos
        scans_result = supabase.table('scans')\
            .select('id', count='exact')\
            .eq('site_id', site_id)\
            .execute()
        
        # Amenazas activas
        threats_result = supabase.table('threats')\
            .select('id, severity', count='exact')\
            .eq('site_id', site_id)\
            .eq('status', 'active')\
            .execute()
        
        # Último escaneo
        last_scan_result = supabase.table('scans')\
            .select('*')\
            .eq('site_id', site_id)\
            .order('started_at', desc=True)\
            .limit(1)\
            .execute()
        
        last_scan = last_scan_result.data[0] if last_scan_result.data else None
        
        # Contar amenazas por severidad
        threats_by_severity = {}
        for threat in threats_result.data or []:
            severity = threat['severity']
            threats_by_severity[severity] = threats_by_severity.get(severity, 0) + 1
        
        return {
            "total_scans": scans_result.count,
            "active_threats": threats_result.count,
            "threats_by_severity": threats_by_severity,
            "last_scan": {
                "date": last_scan['started_at'] if last_scan else None,
                "threats_found": last_scan['threats_found'] if last_scan else 0,
                "status": last_scan['status'] if last_scan else None
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# FUNCIÓN DE BACKGROUND
# ============================================

async def run_scan_background(
    scan_id: str,
    site_id: str,
    scan_type: str,
    custom_paths: Optional[List[str]],
    max_size_mb: int
):
    """
    Ejecutar escaneo en background
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"🔍 Starting scan {scan_id} for site {site_id}")
        
        # Actualizar estado a "running"
        supabase.table('scans')\
            .update({'status': 'running'})\
            .eq('id', scan_id)\
            .execute()
        
        # Inicializar scanner
        scanner = FileScanner()
        
        # Determinar qué escanear según el tipo
        # NOTA: En producción, esto debería recibir las rutas desde WordPress
        # Por ahora usamos rutas de ejemplo
        if scan_type == 'quick':
            # Solo plugins y themes
            paths_to_scan = [
                'wp-content/plugins',
                'wp-content/themes'
            ]
        elif scan_type == 'full':
            # Todo el sitio
            paths_to_scan = ['wp-content', 'wp-includes', 'wp-admin']
        else:  # custom
            paths_to_scan = custom_paths or []
        
        # Callback para actualizar progreso
        async def progress_callback(progress: int, scan_result: dict):
            supabase.table('scans')\
                .update({
                    'progress': progress,
                    'files_scanned': scan_result.get('scanned_files', 0),
                    'results': {
                        'current_file': scan_result.get('file_path')
                    }
                })\
                .eq('id', scan_id)\
                .execute()
        
        # Ejecutar escaneo
        # NOTA: En producción real, WordPress enviaría los archivos o rutas
        # Por ahora simulamos con un escaneo local
        results = {
            'total_files': 0,
            'scanned_files': 0,
            'threats_found': 0,
            'suspicious_files': []
        }
        
        # Simular progreso (en producción real esto vendría del scanner)
        for i in range(0, 101, 10):
            await asyncio.sleep(0.5)  # Simular tiempo de escaneo
            await progress_callback(i, {'scanned_files': i, 'file_path': f'example-{i}.php'})
        
        # Guardar amenazas en la BD
        for suspicious_file in results.get('suspicious_files', []):
            for threat in suspicious_file.get('threats', []):
                threat_data = {
                    'scan_id': scan_id,
                    'site_id': site_id,
                    'file_path': suspicious_file['file_path'],
                    'threat_type': 'malware',
                    'severity': threat['severity'],
                    'signature_matched': threat['signature'],
                    'code_snippet': threat['code_snippet'],
                    'status': 'active'
                }
                supabase.table('threats').insert(threat_data).execute()
        
        # Actualizar estado final
        supabase.table('scans')\
            .update({
                'status': 'completed',
                'completed_at': datetime.utcnow().isoformat(),
                'progress': 100,
                'files_scanned': results['scanned_files'],
                'threats_found': results['threats_found'],
                'results': results
            })\
            .eq('id', scan_id)\
            .execute()
        
        logger.info(f"✅ Scan {scan_id} completed - {results['threats_found']} threats found")
        
    except Exception as e:
        logger.error(f"❌ Scan {scan_id} failed: {str(e)}")
        
        # Marcar como fallido
        supabase.table('scans')\
            .update({
                'status': 'failed',
                'completed_at': datetime.utcnow().isoformat(),
                'results': {'error': str(e)}
            })\
            .eq('id', scan_id)\
            .execute()
