# tests/test_rate_limit_units.py

import pytest
pytestmark = pytest.mark.unit

from fastapi import Request
from app.middleware.rate_limit import RateLimiter
import asyncio
from unittest.mock import MagicMock

class TestRateLimiterUnits:
    @pytest.fixture
    def limiter(self):
        return RateLimiter(default_requests_per_minute=10)

    def test_get_client_ip_headers(self, limiter):
        mock_request = MagicMock(spec=Request)
        mock_request.headers = {}
        mock_request.client = MagicMock()
        mock_request.client.host = "1.2.3.4"
        assert limiter._get_client_ip(mock_request) == "1.2.3.4"

        mock_request.headers = {"X-Forwarded-For": "5.6.7.8, 1.2.3.4"}
        assert limiter._get_client_ip(mock_request) == "5.6.7.8"

        mock_request.headers = {"X-Real-IP": "9.10.11.12"}
        assert limiter._get_client_ip(mock_request) == "9.10.11.12"
        
        mock_request.headers = {"X-Forwarded-For": "invalid-ip"}
        assert limiter._get_client_ip(mock_request) == "1.2.3.4"

    def test_get_endpoint_limit_patterns(self, limiter):
        assert limiter._get_endpoint_limit("/health") == 300
        assert limiter._get_endpoint_limit("/api/v1/audit/123/status") == 120  # status checks: bumped 60→120
        assert limiter._get_endpoint_limit("/api/v1/unknown") == 10
        assert limiter._get_endpoint_limit("/api/v1/audit") == 60  # audit creates: bumped 20→60

    @pytest.mark.asyncio
    async def test_cleanup_entries(self, limiter):
        import time
        limiter.requests["1.2.3.4"] = [time.time() - 70, time.time() - 30]
        await limiter._cleanup_old_entries()
        assert len(limiter.requests["1.2.3.4"]) == 1
        
        limiter.requests["5.6.7.8"] = [time.time() - 100]
        await limiter._cleanup_old_entries()
        assert "5.6.7.8" not in limiter.requests

    @pytest.mark.asyncio
    async def test_shutdown(self, limiter):
        await limiter.start_cleanup_task()
        assert limiter._cleanup_task is not None
        await limiter.shutdown()
        assert limiter._cleanup_task.cancelled()
