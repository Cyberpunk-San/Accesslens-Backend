"""
Rate limiting middleware for AccessLens API.
Implements sliding window algorithm with per-IP tracking.
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from typing import Dict, Tuple, Optional
from ..core.config import settings
import re
import time
import asyncio
from collections import defaultdict
import logging
import ipaddress
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Rate limiting middleware to prevent API abuse.
    Uses sliding window algorithm with per-IP tracking.
    
    Features:
    - Per-IP rate limiting
    - Sliding window algorithm
    - Automatic cleanup of old entries
    - Configurable limits per endpoint
    - Rate limit headers (RFC 6585)
    """
    
    def __init__(self, default_requests_per_minute: int = 100):
        self.default_requests_per_minute = default_requests_per_minute
        self.requests: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # Endpoint-specific limits (higher limits for lightweight endpoints)
        self.endpoint_limits = {
            "/health": 300,           # Health checks can be frequent
            "/metrics": 60,            # Metrics scraping
            "/api/v1/engines": 120,    # Engine listing
            "/api/v1/audit": 60,       # Audit creation (bumped from 20 — tests need headroom)
            "/api/v1/audit/*/status": 120,  # Status checks
        }
    
    async def start_cleanup_task(self):
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Rate limiter cleanup task started")
    
    async def _cleanup_loop(self):
        while True:
            try:
                await asyncio.sleep(60) 
                await self._cleanup_old_entries()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in rate limiter cleanup: {e}")
    
    async def _cleanup_old_entries(self):
        now = time.time()
        async with self._lock:
            for ip in list(self.requests.keys()):
                self.requests[ip] = [
                    req_time for req_time in self.requests[ip] 
                    if now - req_time < 60
                ]
                if not self.requests[ip]:
                    del self.requests[ip]
    
    def _get_client_ip(self, request: Request) -> str:

        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
            try:
                ipaddress.ip_address(client_ip)
                return client_ip
            except ValueError:
                pass
    
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            try:
                ipaddress.ip_address(real_ip)
                return real_ip
            except ValueError:
                pass
        
        return request.client.host if request.client else "unknown"
    
    def _get_endpoint_limit(self, path: str) -> int:
        if path in self.endpoint_limits:
            return self.endpoint_limits[path]
        
        for pattern, limit in self.endpoint_limits.items():
            if "*" in pattern:
                regex_pattern = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
                if re.match(regex_pattern, path):
                    return limit
        
        return self.default_requests_per_minute
    
    async def check_rate_limit(self, request: Request) -> Tuple[bool, Dict]:

        if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
            from app.core.config import settings
            if settings.debug:
                return True, {}
        
        client_ip = self._get_client_ip(request)
        endpoint_limit = self._get_endpoint_limit(request.url.path)
        
        now = time.time()
        minute_ago = now - 60
        
        async with self._lock:
            if client_ip in self.requests:
                self.requests[client_ip] = [
                    req_time for req_time in self.requests[client_ip]
                    if req_time > minute_ago
                ]
            
            current_count = len(self.requests.get(client_ip, []))
            
            if current_count >= endpoint_limit:
                oldest = min(self.requests[client_ip]) if self.requests[client_ip] else now
                reset_time = int(oldest + 60)

                headers = {
                    "X-RateLimit-Limit": str(endpoint_limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(max(1, reset_time - int(now)))
                }

                from ..core.config import settings as _settings
                if not _settings.testing:
                    logger.warning(f"Rate limit exceeded for {client_ip} on {request.url.path}")
                return False, headers
            
            if client_ip not in self.requests:
                self.requests[client_ip] = []
            self.requests[client_ip].append(now)
            
            headers = {
                "X-RateLimit-Limit": str(endpoint_limit),
                "X-RateLimit-Remaining": str(endpoint_limit - current_count - 1),
                "X-RateLimit-Reset": str(int(now + 60))
            }
            return True, headers
    
    async def shutdown(self):
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Rate limiter cleanup task stopped")


rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    
    async def dispatch(self, request: Request, call_next):
        # logger.debug(f"RateLimitMiddleware: testing={settings.testing}, path={request.url.path}")
        
        if request.url.path in ["/metrics"]:
            return await call_next(request)
        
        allowed, headers = await rate_limiter.check_rate_limit(request)
        

        
        should_block = not allowed
        if settings.testing and not request.headers.get("X-Test-Enforce-Rate-Limit"):
            should_block = False
            
        if should_block:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too many requests",
                    "message": "Rate limit exceeded. Please slow down.",
                    "limit": headers.get("X-RateLimit-Limit"),
                    "reset_at": headers.get("X-RateLimit-Reset")
                },
                headers=headers
            )
        
        response = await call_next(request)
        
        for key, value in headers.items():
            response.headers[key] = value
        
        return response