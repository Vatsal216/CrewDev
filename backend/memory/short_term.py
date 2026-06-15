import json
from typing import Optional
import redis.asyncio as aioredis
from config import settings


class ShortTermMemory:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.key = f"session:{session_id}:history"
        self._redis: Optional[aioredis.Redis] = None

    async def _get_redis(self) -> aioredis.Redis:
        if not self._redis:
            self._redis = await aioredis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    async def add(self, role: str, content: str, meta: dict = None):
        r = await self._get_redis()
        entry = {"role": role, "content": content, "meta": meta or {}}
        await r.rpush(self.key, json.dumps(entry))
        await r.expire(self.key, 86400 * 7)  # 7 days TTL
        # Keep last N entries
        length = await r.llen(self.key)
        if length > settings.short_term_history_k * 2:
            await r.ltrim(self.key, -settings.short_term_history_k * 2, -1)

    async def get_recent(self, k: int = 20) -> list[dict]:
        r = await self._get_redis()
        raw = await r.lrange(self.key, -k, -1)
        return [json.loads(x) for x in raw]

    async def get_context_string(self, k: int = 10) -> str:
        history = await self.get_recent(k)
        lines = []
        for m in history:
            lines.append(f"{m['role'].upper()}: {m['content'][:500]}")
        return "\n".join(lines)

    async def clear(self):
        r = await self._get_redis()
        await r.delete(self.key)

    async def set_agent_state(self, key: str, value: dict):
        r = await self._get_redis()
        state_key = f"session:{self.session_id}:agent_state:{key}"
        await r.set(state_key, json.dumps(value), ex=3600)

    async def get_agent_state(self, key: str) -> Optional[dict]:
        r = await self._get_redis()
        state_key = f"session:{self.session_id}:agent_state:{key}"
        raw = await r.get(state_key)
        return json.loads(raw) if raw else None
