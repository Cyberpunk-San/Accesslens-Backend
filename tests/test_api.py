


import pytest
pytestmark = pytest.mark.browser

from httpx import AsyncClient, ASGITransport
from app.main import app
pytestmark = pytest.mark.browser
import uuid
from typing import Dict

@pytest.mark.asyncio
async def test_health_check():

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "engines" in data
    assert data["version"] == "1.0.0"

@pytest.mark.asyncio
async def test_root_endpoint():

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "AccessLens API"
    assert "documentation" in data
    assert "endpoints" in data

@pytest.mark.asyncio
async def test_list_engines():

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/api/v1/engines")

    assert response.status_code == 200
    engines = response.json()
    assert len(engines) >= 3


    wcag_engine = next((e for e in engines if e["internal_name"] == "wcag_deterministic"), None)
    assert wcag_engine is not None
    assert wcag_engine["name"] == "wcag"

    for engine in engines:
        assert "name" in engine
        assert "internal_name" in engine
        assert "version" in engine
        assert "capabilities" in engine

@pytest.mark.asyncio
async def test_start_audit():

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/audit",
            json={
                "url": "https://example.com",
                "engines": ["wcag"],  
                "enable_ai": False
            }
        )

    assert response.status_code == 200
    data = response.json()
    assert "audit_id" in data
    assert data["status"] == "started"
    assert data["url"] == "https://example.com"

@pytest.mark.asyncio
async def test_get_audit_status():


    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        start_response = await ac.post(
            "/api/v1/audit",
            json={"url": "https://example.com"}
        )
        audit_id = start_response.json()["audit_id"]


        status_response = await ac.get(f"/api/v1/audit/{audit_id}/status")

        assert status_response.status_code == 200
        data = status_response.json()
        assert data["audit_id"] == audit_id
        assert data["status"] in ["in_progress", "completed"]

@pytest.mark.asyncio
async def test_get_nonexistent_audit():

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        fake_id = str(uuid.uuid4())
        response = await ac.get(f"/api/v1/audit/{fake_id}")

        assert response.status_code == 404

@pytest.mark.asyncio
async def test_cancel_audit():

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            f"/api/v1/audit/{str(uuid.uuid4())}/cancel"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

@pytest.mark.asyncio
async def test_invalid_url_validation():

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/audit",
            json={
                "url": "not-a-valid-url",
                "engines": ["wcag_deterministic"]
            }
        )

        print(f"DEBUG TEST: Status={response.status_code}")
        print(f"DEBUG TEST: Content={response.text}")
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data