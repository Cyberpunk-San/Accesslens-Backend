import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from app.utils.cache import CacheManager
import time

pytestmark = pytest.mark.unit

@pytest.fixture
def cache():
    return CacheManager()

@pytest.mark.asyncio
async def test_cache_init_redis_success(cache):
    with patch("app.core.config.settings.redis_url", "redis://localhost:6379"):
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis
            await cache.initialize()
            assert cache._redis is not None
            mock_redis.ping.assert_called_once()

@pytest.mark.asyncio
async def test_cache_init_redis_failure(cache):
    with patch("app.core.config.settings.redis_url", "redis://localhost:6379"):
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.ping.side_effect = Exception("Connection Refused")
            mock_from_url.return_value = mock_redis
            await cache.initialize()
            # Falls back to in-memory silently
            assert cache._redis is None

@pytest.mark.asyncio
async def test_cache_reinit_closing_old(cache):
    with patch("app.core.config.settings.redis_url", "redis://localhost:6379"):
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_redis1 = AsyncMock()
            mock_from_url.return_value = mock_redis1
            await cache.initialize()
            
            # Simulate disconnect in testing mode to trigger reinit
            with patch("app.core.config.settings.testing", True):
                mock_redis1.ping.side_effect = Exception("Disconnected")
                mock_redis2 = AsyncMock()
                mock_from_url.return_value = mock_redis2
                await cache.initialize()
                
                mock_redis1.aclose.assert_called_once()
                assert cache._redis is mock_redis2

@pytest.mark.asyncio
async def test_cache_get_expired(cache):
    await cache.initialize()
    # Set with negative TTL
    await cache.set("k1", "v1", ttl=-1)
    # Should return None and evict
    assert await cache.get("k1") is None
    assert "k1" not in cache._local_cache

@pytest.mark.asyncio
async def test_cache_redis_get(cache):
    with patch("app.core.config.settings.redis_url", "redis://localhost:6379"):
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.get.return_value = '{"foo": "bar"}'
            mock_from_url.return_value = mock_redis
            await cache.initialize()
            
            val = await cache.get("k1")
            assert val == {"foo": "bar"}
            mock_redis.get.assert_called_with("accesslens:k1")

@pytest.mark.asyncio
async def test_cache_redis_get_exception(cache):
    with patch("app.core.config.settings.redis_url", "redis://localhost:6379"):
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.get.side_effect = Exception("Redis Error")
            mock_from_url.return_value = mock_redis
            await cache.initialize()
            
            val = await cache.get("k1")
            assert val is None

@pytest.mark.asyncio
async def test_cache_redis_set_exception(cache):
    with patch("app.core.config.settings.redis_url", "redis://localhost:6379"):
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_redis.set.side_effect = Exception("Redis Set Error")
            mock_from_url.return_value = mock_redis
            await cache.initialize()
            
            await cache.set("k1", "v1")
            # Local cache still works
            assert cache._local_cache["k1"]["data"] == "v1"

@pytest.mark.asyncio
async def test_cache_redis_clear(cache):
    with patch("app.core.config.settings.redis_url", "redis://localhost:6379"):
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis
            await cache.initialize()
            
            await cache.set("k1", "v1")
            await cache.clear()
            mock_redis.delete.assert_called_with("accesslens:k1")
            assert len(cache._tracked_keys) == 0

@pytest.mark.asyncio
async def test_cache_redis_delete(cache):
    with patch("app.core.config.settings.redis_url", "redis://localhost:6379"):
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_redis = AsyncMock()
            mock_from_url.return_value = mock_redis
            await cache.initialize()
            
            await cache.set("k1", "v1")
            await cache.delete("k1")
            mock_redis.delete.assert_called_with("accesslens:k1")
            assert "k1" not in cache._tracked_keys
            assert "k1" not in cache._local_cache
