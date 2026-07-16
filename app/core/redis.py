from functools import lru_cache

import redis.asyncio as redis

from app.core.config import settings


@lru_cache
def get_redis_client() -> redis.Redis:          
    return redis.from_url(settings.REDIS_URL, decode_responses=True)
