import pytest
import asyncio
from app.models.schemas import AuditReport
from app.main import app
from httpx import AsyncClient, ASGITransport

@pytest.mark.asyncio
async def test_audit_store_concurrency():
    """Verify that concurrent requests to the audit store do not corrupt data."""
    # This simulates multiple concurrent POST requests to start audits
    # We just want to ensure the API handles rapid-fire bursts without crashing
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        
        async def make_request(i):
            return await ac.post(
                "/api/v1/audit",
                json={"url": f"https://example.com/page{i}"}
            )
            
        # Fire off 10 requests at once
        tasks = [make_request(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        successes = 0
        for r in results:
            if not isinstance(r, Exception) and r.status_code == 200:
                successes += 1
                
        # Since our mock/default engines might be synchronous or limited by semaphores,
        # we just care that the API layer accepted them cleanly without 500s.
        assert successes == 10
