import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
import time

@pytest.mark.asyncio
async def test_api_load_capacity():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        
        start = time.time()
        
        async def fetch_health():
            return await ac.get("/health")
            
        tasks = [fetch_health() for _ in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        duration = time.time() - start
        
        successes = 0
        for r in results:
            if not isinstance(r, Exception) and r.status_code == 200:
                successes += 1
                
        assert successes == 20
        assert duration < 5.0
