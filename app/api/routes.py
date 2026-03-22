
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
import asyncio
import logging
import uuid
import time
from datetime import datetime
from prometheus_client import Counter, Histogram
from ..core.config import settings
from ..utils.validators import is_valid_url
from ..utils.cache import cache_manager

from ..models.schemas import AuditRequest, AuditReport, AuditSummary
from ..core.audit_orchestrator import AuditOrchestrator
# Note: slowapi limiter removed — rate limiting is handled by RateLimitMiddleware

router = APIRouter()
logger = logging.getLogger(__name__)

# Metrics initialization

# Custom Prometheus Metrics
AUDIT_REQUESTS = Counter(
    'accesslens_audit_requests_total',
    'Total number of audit requests received',
    ['status']
)

AUDIT_DURATION = Histogram(
    'accesslens_audit_duration_seconds',
    'Time spent processing an entire audit',
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, float('inf'))
)

ISSUES_FOUND = Counter(
    'accesslens_issues_found_total',
    'Total number of accessibility issues found by severity',
    ['severity']
)

def resolve_engine_name(app, name: str):
    return app.state.engine_aliases.get(name, name)

@router.post("/audit", response_model=Dict[str, str])
async def start_audit(
    audit_request: AuditRequest,
    background_tasks: BackgroundTasks,
    request: Request
):
    is_safe, error_msg = is_valid_url(audit_request.url, allow_private=settings.debug)
    logger.info(f"URL Validation for {audit_request.url}: is_safe={is_safe}, error={error_msg}")
    
    if not is_safe:
        return JSONResponse(status_code=422, content={"detail": error_msg})

    cache_key = f"audit:{audit_request.url}:{hash(tuple(audit_request.engines or []))}"
    
    cached_status = await cache_manager.get(cache_key)
    if cached_status and not settings.testing:
        raise HTTPException(status_code=429, detail="Audit for this URL is recently completed or in progress.")
            
    await cache_manager.set(cache_key, "in_progress", ttl=30)

    audit_id = str(uuid.uuid4())

    logger.info(f"Starting audit {audit_id} for URL: {audit_request.url}")

    if audit_request.engines:
        audit_request.engines = [
            resolve_engine_name(request.app, name)
            for name in audit_request.engines
        ]

    orchestrator = AuditOrchestrator(
        engine_registry=request.app.state.engine_registry
    )

    background_tasks.add_task(
        run_audit_background,
        audit_id,
        audit_request,
        orchestrator,
        request.app.state.report_storage
    )

    return {
        "audit_id": audit_id,
        "status": "started",
        "url": audit_request.url
    }

@router.get("/audit", response_model=List[Dict[str, Any]])
async def list_audits(
    request: Request,
    limit: int = 10,
    offset: int = 0
):
    """List recent audit reports"""
    storage = request.app.state.report_storage
    return await storage.list_reports(limit=limit, offset=offset)

@router.get("/audit/{audit_id}", response_model=AuditReport)
async def get_audit_results(audit_id: str, request: Request):
    storage = request.app.state.report_storage
    report = await storage.get_report(audit_id)
    if not report:
        raise HTTPException(status_code=404, detail="Audit not found")
    return report

@router.get("/audit/{audit_id}/status")
async def get_audit_status(audit_id: str, request: Request):
    storage = request.app.state.report_storage
    # Check status by fetching from storage
    report = await storage.get_report(audit_id)
    
    if not report:
        return {"audit_id": audit_id, "status": "in_progress"}

    return {
        "audit_id": audit_id,
        "status": "completed",
        "summary": report.summary
    }

@router.get("/engines")
async def list_engines(request: Request):
    engines = request.app.state.engine_registry.get_all()
    aliases = request.app.state.engine_aliases

    # reverse mapping
    reverse_alias = {v: k for k, v in aliases.items()}
    
    return [
        {
            "name": reverse_alias.get(engine.name, engine.name),  # 👈 alias
            "internal_name": engine.name,
            "version": engine.version,
            "capabilities": engine.capabilities
        }
        for engine in engines
    ]

@router.post("/audit/{audit_id}/cancel")
async def cancel_audit(audit_id: str):


    return {"status": "cancelled", "audit_id": audit_id}

async def run_audit_background(
    audit_id: str,
    request: AuditRequest,
    orchestrator: 'AuditOrchestrator',
    storage: Any
):

    start_time = time.time()
    try:
        logger.info(f"Running audit {audit_id} in background")


        report = await orchestrator.run_audit(request)
        report.id = audit_id

        # Save to persistent storage
        await storage.save_report(report)

        # Record Metrics
        duration = time.time() - start_time
        AUDIT_DURATION.observe(duration)
        AUDIT_REQUESTS.labels(status='success').inc()
        
        for severity, count in report.summary.by_severity.items():
            if count > 0:
                ISSUES_FOUND.labels(severity=severity.value if hasattr(severity, 'value') else severity).inc(count)

        logger.info(f"Audit {audit_id} completed with {report.summary.total_issues} issues in {duration:.2f}s")

    except Exception as e:
        logger.error(f"Audit {audit_id} failed: {e}", exc_info=True)
        
        AUDIT_REQUESTS.labels(status='failed').inc()

        # Save error report to persistent storage
        error_report = AuditReport(
            request=request,
            summary=AuditSummary(
                total_issues=0,
                by_severity={},
                by_source={},
                by_wcag_level={},
                score=0,
                confidence_avg=0
            ),
            issues=[],
            metadata={"error": str(e)}
        )
        error_report.id = audit_id
        await storage.save_report(error_report)