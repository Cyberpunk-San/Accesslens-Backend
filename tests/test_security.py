import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings

@pytest.fixture
def enforce_production_security():
    """Ensure debug is False so SSRF protection is fully active."""
    original_debug = settings.debug
    settings.debug = False
    settings.testing = True # Ensure rate limiting is still bypassed
    yield settings
    settings.debug = original_debug

@pytest.mark.asyncio
async def test_ssrf_protection_blocks_localhost(enforce_production_security):
    """Verify that localhost and loopback addresses are blocked."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        
        response = await client.post(
            "/api/v1/audit",
            json={"url": "http://localhost:8080/admin"}
        )
        assert response.status_code == 422
        assert "SSRF" in response.json()["detail"]

        response = await client.post(
            "/api/v1/audit",
            json={"url": "http://127.0.0.1:9090/metrics"}
        )
        assert response.status_code == 422

@pytest.mark.asyncio
async def test_ssrf_protection_blocks_private_ips(enforce_production_security):
    """Verify that local network CIDRs are blocked."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        
        # 192.168.x.x
        response = await client.post(
            "/api/v1/audit",
            json={"url": "http://192.168.1.1/config"}
        )
        assert response.status_code == 422

        # 10.x.x.x
        response = await client.post(
            "/api/v1/audit",
            json={"url": "http://10.0.0.5/api"}
        )
        assert response.status_code == 422

        # 169.254.169.254 (Cloud metadata service)
        response = await client.post(
            "/api/v1/audit",
            json={"url": "http://169.254.169.254/latest/meta-data/"}
        )
        assert response.status_code == 422

@pytest.mark.asyncio
async def test_ssrf_protection_allows_valid_public_urls(enforce_production_security):
    """Verify that public internet URLs are allowed through."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        
        response = await client.post(
            "/api/v1/audit",
            json={"url": "https://example.com"}
        )
        # Should not get 422. Might get 200 indicating audit started.
        assert response.status_code == 200
        assert "audit_id" in response.json()
