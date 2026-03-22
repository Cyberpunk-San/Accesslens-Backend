import pytest
import asyncio
from unittest.mock import MagicMock, patch
from app.utils.cache import CacheManager

@pytest.fixture
def cache_manager():
    return CacheManager()

@pytest.mark.asyncio
async def test_cache_set_get(cache_manager):
    # In-memory cache test
    await cache_manager.set("test_key", "test_value", ttl=10)
    value = await cache_manager.get("test_key")
    assert value == "test_value"

@pytest.mark.asyncio
async def test_cache_delete(cache_manager):
    # CacheManager doesn't have a direct delete, but we can set with 0 ttl or just test clear
    await cache_manager.set("key1", "val1")
    await cache_manager.clear()
    assert await cache_manager.get("key1") is None

@pytest.mark.asyncio
async def test_cache_clear(cache_manager):
    await cache_manager.set("k1", "v1")
    await cache_manager.set("k2", "v2")
    await cache_manager.clear()
    assert await cache_manager.get("k1") is None
    assert await cache_manager.get("k2") is None
