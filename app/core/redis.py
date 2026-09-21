from app.analytics import ai_usage_logger
from functools import lru_cache
import logging
import redis.asyncio as redis

from app.core.config import settings

logger = logging.getLogger(__name__)


@lru_cache
def get_redis_client() -> redis.Redis:          
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


async def check_redis_connection():
    try:
        redis_client = get_redis_client()
        await redis_client.ping()
        logger.info("Redis connected successfully")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise