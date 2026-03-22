


import pytest
pytestmark = pytest.mark.browser

from httpx import AsyncClient, ASGITransport
from app.main import app
import asyncio
import time

@pytest.mark.asyncio
async def test_complete_audit_flow():


    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:

        start_response = await ac.post(
            "/api/v1/audit",
            json={
                "url": "https://example.com",
                "engines": ["wcag_deterministic", "contrast_engine", "structural_engine"],
                "enable_ai": False,
                "depth": "quick"
            }
        )

        assert start_response.status_code == 200
        audit_data = start_response.json()
        audit_id = audit_data["audit_id"]


        max_attempts = 10
        for attempt in range(max_attempts):
            await asyncio.sleep(2)

            status_response = await ac.get(f"/api/v1/audit/{audit_id}/status")
            assert status_response.status_code == 200

            status_data = status_response.json()

            if status_data["status"] == "completed":

                report_response = await ac.get(f"/api/v1/audit/{audit_id}")
                assert report_response.status_code == 200

                report = report_response.json()
                assert "summary" in report
                assert "issues" in report
                assert "request" in report


                assert report["summary"]["total_issues"] >= 0
                assert "by_severity" in report["summary"]
                assert "score" in report["summary"]

                break
            elif attempt == max_attempts - 1:
                pytest.fail("Audit did not complete in time")

@pytest.mark.asyncio
async def test_concurrent_audits():


    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:

        audit_ids = []
        urls = [
            "https://example.com",
            "https://google.com",
            "https://github.com"
        ]

        for url in urls:
            response = await ac.post(
                "/api/v1/audit",
                json={"url": url, "engines": ["wcag_deterministic"]}
            )
            assert response.status_code == 200
            audit_ids.append(response.json()["audit_id"])


        await asyncio.sleep(5)


        for audit_id in audit_ids:
            response = await ac.get(f"/api/v1/audit/{audit_id}/status")
            assert response.status_code == 200
            status = response.json()["status"]
            assert status in ["completed", "in_progress"]

@pytest.mark.asyncio
async def test_error_handling():


    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:

        response = await ac.post("/api/v1/audit", json={})
        assert response.status_code == 422


        response = await ac.post(
            "/api/v1/audit",
            json={
                "url": "https://example.com",
                "engines": ["non_existent_engine"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "audit_id" in data

@pytest.mark.asyncio
async def test_system_health():


    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:

        for _ in range(10):
            response = await ac.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"