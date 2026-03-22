import pytest
import asyncio
from unittest.mock import AsyncMock
from app.utils.cache import CacheManager

@pytest.fixture
def cache():
    return CacheManager()

@pytest.mark.asyncio
async def test_cache_in_memory_basic(cache):
    await cache.initialize()
    await cache.set("k1", "v1")
    assert await cache.get("k1") == "v1"
    await cache.delete("k1")
    assert await cache.get("k1") is None

@pytest.mark.asyncio
async def test_cache_redis_backend(cache):
    # Bypass settings checks by manually injecting a mock
    mock_redis = AsyncMock()
    mock_redis.get.return_value = '{"redis": "ok"}'
    
    await cache.initialize()
    cache._redis = mock_redis
    
    val = await cache.get("test_key")
    assert val == {"redis": "ok"}
    mock_redis.get.assert_called_with("accesslens:test_key")

@pytest.mark.asyncio
async def test_cache_clear(cache):
    await cache.initialize()
    await cache.set("a", 1)
    await cache.clear()
    assert await cache.get("a") is None
