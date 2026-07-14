from functools import lru_cache

import redis.asyncio as redis

from app.core.config import settings


@lru_cache
def get_redis_client() -> redis.Redis:
    print("[redis] REDIS_URL ->", settings.REDIS_URL)
    return redis.from_url(settings.REDIS_URL, decode_responses=True)
