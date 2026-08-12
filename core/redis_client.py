import time
from typing import Dict, Any, Optional
import redis.asyncio as aioredis
from config import Config

class RedisClientManager:
    """
    مُدير الـ Redis مع نظام Fallback تلقائي للذاكرة العشوائية (In-Memory Dictionary)
    في حال عدم توفر خادم Redis.
    """
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.use_fallback = False
        self._memory_store: Dict[str, Any] = {}
        self._memory_ttl: Dict[str, float] = {}

    async def init(self):
        try:
            self.redis = aioredis.from_url(Config.REDIS_URL, decode_responses=True)
            await self.redis.ping()
            self.use_fallback = False
        except Exception:
            self.redis = None
            self.use_fallback = True

    async def get(self, key: str) -> Optional[str]:
        if not self.use_fallback and self.redis:
            try:
                return await self.redis.get(key)
            except Exception:
                pass
        
        # Memory Fallback
        if key in self._memory_ttl and time.time() > self._memory_ttl[key]:
            del self._memory_store[key]
            del self._memory_ttl[key]
            return None
        return self._memory_store.get(key)

    async def set(self, key: str, value: str, ex: Optional[int] = None):
        if not self.use_fallback and self.redis:
            try:
                await self.redis.set(key, value, ex=ex)
                return
            except Exception:
                pass

        # Memory Fallback
        self._memory_store[key] = value
        if ex:
            self._memory_ttl[key] = time.time() + ex
        elif key in self._memory_ttl:
            del self._memory_ttl[key]

    async def incr(self, key: str) -> int:
        if not self.use_fallback and self.redis:
            try:
                return await self.redis.incr(key)
            except Exception:
                pass

        val = int(await self.get(key) or 0) + 1
        await self.set(key, str(val))
        return val

    async def expire(self, key: str, seconds: int):
        if not self.use_fallback and self.redis:
            try:
                await self.redis.expire(key, seconds)
                return
            except Exception:
                pass

        if key in self._memory_store:
            self._memory_ttl[key] = time.time() + seconds

redis_manager = RedisClientManager()
