"""Dependencies for LLM Orchestrator"""
from redis import asyncio as aioredis
from config import get_settings

# Redis client instance
redis_client = None


async def get_redis_client() -> aioredis.Redis:
    """Get Redis client"""
    global redis_client
    if redis_client is None:
        settings = get_settings()
        redis_client = await aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
    return redis_client


async def close_redis_client():
    """Close Redis client"""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None