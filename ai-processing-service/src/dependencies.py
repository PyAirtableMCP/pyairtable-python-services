"""Dependencies for AI Processing Service"""
import redis.asyncio as redis
from functools import lru_cache
from config import get_settings

# Redis client instance
_redis_client = None

async def get_redis_client():
    """Get Redis client instance"""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        if settings.redis_password:
            _redis_client = redis.from_url(
                f"redis://:{settings.redis_password}@{settings.redis_url.split('@')[-1]}"
            )
        else:
            _redis_client = redis.from_url(settings.redis_url)
    return _redis_client

async def close_redis_client():
    """Close Redis client connection"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None