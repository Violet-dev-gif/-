from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings

try:
    import redis.asyncio as redis
except Exception:  # pragma: no cover
    redis = None


@dataclass
class CacheEntry:
    payload: dict[str, Any]
    expires_at: float


class CacheService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._redis_client = None
        self._memory_store: dict[str, CacheEntry] = {}

    @property
    def is_connected(self) -> bool:
        return self._redis_client is not None

    async def connect(self) -> None:
        if not self.settings.redis_url or redis is None:
            return
        client = redis.from_url(self.settings.redis_url, decode_responses=True)
        await client.ping()
        self._redis_client = client

    async def get(self, key: str) -> dict[str, Any] | None:
        if self._redis_client is not None:
            raw = await self._redis_client.get(key)
            return json.loads(raw) if raw else None

        entry = self._memory_store.get(key)
        if not entry:
            return None
        if entry.expires_at < time.time():
            self._memory_store.pop(key, None)
            return None
        return entry.payload

    async def set(self, key: str, payload: dict[str, Any], ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds or self.settings.cache_ttl_seconds
        if self._redis_client is not None:
            await self._redis_client.setex(key, ttl, json.dumps(payload, ensure_ascii=False))
            return

        self._memory_store[key] = CacheEntry(payload=payload, expires_at=time.time() + ttl)
