import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.exception_handlers import http_exception_handler
from contextlib import asynccontextmanager
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator
import logging
import time
from typing import Dict, Any, List

from .api.routes import router
from .core.browser_manager import browser_manager
from .core.report_storage import report_storage
from .core.config import settings
from .middleware import RateLimitMiddleware, rate_limiter
from .engines.registry import EngineRegistry
from .engines.wcag_engine import WCAGEngine
from .engines.contrast_engine import ContrastEngine
from .engines.structural_engine import StructuralEngine
from .core.logging_config import setup_logging
from .utils.cache import cache_manager


setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    Handles startup and shutdown events.
    """

    # Initialize cache manager (must happen before routes handle requests)
    await cache_manager.initialize()
    logger.info("Cache manager initialized")

    # Initialize browser manager
    await browser_manager.initialize(headless=settings.browser_headless)
    logger.info("Browser manager initialized")

    # Initialize rate limiter cleanup task
    await rate_limiter.start_cleanup_task()
    logger.info("Rate limiter initialized")

    # Initialize report storage
    await report_storage.initialize()
    logger.info("Report storage initialized")

    # Engines are pre-registered at top level, but we log here
    logger.info(f"Registered {len(app.state.engine_registry._engines)} engines (with aliases)")

    yield

    # Cleanup
    logger.info("Shutting down AccessLens API...")
    await browser_manager.close()
    await rate_limiter.shutdown()
    await report_storage.close()
    await cache_manager.clear()
    logger.info("Cleanup complete")


app = FastAPI(
    title="AccessLens API",
    description="Layered accessibility auditing framework",
    version="1.0.0",
    lifespan=lifespan
)

# Initialize app state attributes early so they are available even without lifespan (useful for tests)
app.state.report_storage = report_storage
app.state.engine_registry = EngineRegistry()

# Pre-register engines so they are available for metadata/listing immediately
from .engines.wcag_engine import WCAGEngine
from .engines.structural_engine import StructuralEngine
from .engines.contrast_engine import ContrastEngine
from .engines.heuristic_engine import HeuristicEngine
from .engines.navigation_engine import NavigationEngine
from .engines.form_engine import FormEngine
from .engines.ai_engine import AIEngine

app.state.engine_aliases = {
    "wcag": "wcag_deterministic",
    "structural": "structural_engine",
    "contrast": "contrast_engine",
    "heuristic": "heuristic",
    "navigation": "navigation",
    "form": "form_engine",
    "ai": "ai_engine"
}

app.state.engine_registry.register(WCAGEngine())
app.state.engine_registry.register(StructuralEngine())
app.state.engine_registry.register(ContrastEngine())
app.state.engine_registry.register(HeuristicEngine())
app.state.engine_registry.register(NavigationEngine())
app.state.engine_registry.register(FormEngine())
app.state.engine_registry.register(AIEngine())


# Add rate limiting middleware FIRST (before CORS and other middleware)
app.add_middleware(RateLimitMiddleware)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics
Instrumentator().instrument(app).expose(app)

# Security headers middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Removed X-Frame-Options: DENY for Hugging Face compatibility
    response.headers["Content-Security-Policy"] = (
        "default-src 'self' https://huggingface.co; "
        "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' fonts.googleapis.com cdn.jsdelivr.net; "
        "img-src 'self' data: fastapi.tiangolo.com; "
        "font-src 'self' fonts.gstatic.com; "
        "connect-src 'self' cdn.jsdelivr.net;"
    )
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    return response

# Include API routes
app.include_router(router, prefix="/api/v1")


@app.get("/", response_class=FileResponse)
async def root():
    """
    Root endpoint serving the high-impact "Cyber HUD" splash page.
    """
    static_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
    return FileResponse(static_file)


@app.get("/health")
async def health_check():
    """
    Health check endpoint for monitoring.
    """
    return {
        "status": "healthy",
        "version": app.version,
        "timestamp": time.time(),
        "engines": [
            {
                "name": engine.name,
                "version": engine.version,
                "capabilities": engine.capabilities
            }
            for engine in app.state.engine_registry.get_all()
        ]
    }

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return await http_exception_handler(request, exc)
    
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if app.debug else "An unexpected error occurred"
        }
    )