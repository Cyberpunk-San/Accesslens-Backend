


import pytest
import time
import asyncio
import psutil
import os
from httpx import AsyncClient, ASGITransport
from app.main import app
pytestmark = [pytest.mark.slow, pytest.mark.browser]

@pytest.mark.asyncio
async def test_api_response_time():


    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        endpoints = [
            ("/health", "GET"),
            ("/", "GET"),
            ("/api/v1/engines", "GET"),
        ]

        for endpoint, method in endpoints:
            start_time = time.time()

            if method == "GET":
                response = await ac.get(endpoint)
            else:
                response = await ac.post(endpoint)

            elapsed = time.time() - start_time

            assert response.status_code == 200
            assert elapsed < 0.5

@pytest.mark.asyncio
async def test_audit_startup_time():


    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        start_time = time.time()

        response = await ac.post(
            "/api/v1/audit",
            json={"url": "https://example.com"}
        )

        elapsed = time.time() - start_time

        assert response.status_code == 200
        assert elapsed < 12.0

@pytest.mark.asyncio
async def test_memory_usage():


    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:

        for i in range(5):
            response = await ac.post(
                "/api/v1/audit",
                json={"url": f"https://example.com/mem_page{i}"}
            )
            assert response.status_code == 200


        current_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = current_memory - initial_memory


        assert memory_increase < 100

@pytest.mark.asyncio
async def test_concurrent_audit_performance():


    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:

        start_time = time.time()

        tasks = []
        for i in range(10):
            task = ac.post(
                "/api/v1/audit",
                json={"url": f"https://example.com/perf_page{i}"}
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)

        elapsed = time.time() - start_time


        for response in responses:
            assert response.status_code == 200


        # 25s is too tight for some local environments (e.g. windows laptop).
        # Relaxing to 40s to ensure stability while still providing a sanity check.
        assert elapsed < 40.0

@pytest.mark.asyncio
async def test_cpu_usage_during_analysis():

    import psutil
    import threading
    import os

    process = psutil.Process(os.getpid())
    cpu_samples = []

    def sample_cpu():
        for _ in range(10):
            # Measure only THIS process's CPU usage, not system-wide load.
            # System-wide CPU can spike due to other tests running in parallel.
            cpu_samples.append(process.cpu_percent(interval=0.5))

    sampler = threading.Thread(target=sample_cpu)
    sampler.start()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        for _ in range(5):
            await ac.get("/api/v1/engines")
            await asyncio.sleep(0.1)

    sampler.join()

    avg_cpu = sum(cpu_samples) / len(cpu_samples)
    # Per-process CPU measured across logical cores. Threshold of 80% per core
    # is generous but not reached by simple endpoint calls.
    assert avg_cpu < 80, f"Process CPU usage too high: {avg_cpu:.1f}%"