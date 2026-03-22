"""
Modular cache utility for AccessLens.
Supports both in-memory and Redis backends.
"""
from typing import Any, Optional, Dict
import json
import time
import logging
from ..core.config import settings

logger = logging.getLogger(__name__)

class CacheManager:
    def __init__(self):
        self._local_cache: Dict[str, Dict[str, Any]] = {}
        self._tracked_keys: set = set()  # track keys we've set for safe Redis clear
        self._redis = None
        self._prefix = "accesslens:"
        self._initialized = False

    async def initialize(self):
        # In-memory is always active as L1
        if settings.redis_url:
            reinit = False
            if not self._initialized:
                reinit = True
            elif self._redis and settings.testing:
                try:
                    await self._redis.ping()
                except Exception:
                    reinit = True

            if reinit:
                self._prefix = "accesslens:"
                try:
                    import redis.asyncio as aioredis

                    if self._redis:
                        try:
                            await self._redis.aclose()
                        except Exception:
                            pass

                    self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
                    await self._redis.ping()
                    logger.info("Redis cache initialized")
                except Exception as e:
                    logger.warning(f"Redis not available, using in-memory cache only: {e}")
                    self._redis = None
        else:
            logger.info("Redis not configured, using in-memory cache only")

        self._initialized = True

    async def get(self, key: str) -> Optional[Any]:
        # Check local L1 first
        if key in self._local_cache:
            entry = self._local_cache[key]
            if entry["expiry"] > time.time():
                return entry["data"]
            else:
                del self._local_cache[key]

        # Check Redis L2
        if self._redis:
            try:
                val = await self._redis.get(f"{self._prefix}{key}")
                if val:
                    return json.loads(val)
            except Exception as e:
                logger.error(f"Redis get failed: {e}")
        
        return None

    async def set(self, key: str, value: Any, ttl: int = 3600):
        # Set local L1
        self._local_cache[key] = {
            "data": value,
            "expiry": time.time() + ttl
        }
        self._tracked_keys.add(key)

        # Set Redis L2
        if self._redis:
            try:
                await self._redis.set(f"{self._prefix}{key}", json.dumps(value), ex=ttl)
            except Exception as e:
                logger.error(f"Redis set failed: {e}")

    async def clear(self):
        """Clear all keys managed by this CacheManager instance."""
        self._local_cache.clear()
        if self._redis and self._tracked_keys:
            try:
                prefixed_keys = [f"{self._prefix}{k}" for k in self._tracked_keys]
                await self._redis.delete(*prefixed_keys)
            except Exception as e:
                logger.error(f"Redis clear failed: {e}")
        self._tracked_keys.clear()

    async def delete(self, key: str):
        """Delete a key from both local and Redis cache."""
        if key in self._local_cache:
            del self._local_cache[key]
        if key in self._tracked_keys:
            self._tracked_keys.remove(key)
        
        if self._redis:
            try:
                await self._redis.delete(f"{self._prefix}{key}")
            except Exception as e:
                logger.error(f"Redis delete failed: {e}")

cache_manager = CacheManager()
