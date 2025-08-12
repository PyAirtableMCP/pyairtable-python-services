"""Dependencies for Analytics service"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from redis import asyncio as aioredis
from config import get_settings

# Database setup
Base = declarative_base()
engine = None
async_session_maker = None

# Redis client instance
redis_client = None


async def get_database_engine():
    """Get database engine"""
    global engine
    if engine is None:
        settings = get_settings()
        engine = create_async_engine(
            settings.get_async_database_url(),
            echo=settings.environment == "development",
            pool_size=20,
            max_overflow=0,
            pool_pre_ping=True,
            pool_recycle=300,
        )
    return engine


async def get_async_session_maker():
    """Get async session maker"""
    global async_session_maker
    if async_session_maker is None:
        engine = await get_database_engine()
        async_session_maker = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )
    return async_session_maker


async def get_database_session() -> AsyncSession:
    """Get database session"""
    session_maker = await get_async_session_maker()
    async with session_maker() as session:
        yield session


async def get_redis_client() -> aioredis.Redis:
    """Get Redis client"""
    global redis_client
    if redis_client is None:
        settings = get_settings()
        redis_url = settings.redis_url
        
        # Check if the URL already contains authentication
        if "@" not in redis_url and settings.redis_password:
            # URL doesn't have auth, add it
            if redis_url.startswith("redis://"):
                host_part = redis_url.replace("redis://", "")
                if ":" in host_part:
                    host = host_part.split(":")[0]
                    port_db = host_part.split(":")[1]
                    if "/" in port_db:
                        port = port_db.split("/")[0]
                        db = port_db.split("/")[1]
                    else:
                        port = port_db
                        db = "0"
                else:
                    host = host_part
                    port = "6379"
                    db = "0"
                
                redis_url = f"redis://:{settings.redis_password}@{host}:{port}/{db}"
        
        # If URL already has authentication or no password needed, use as-is
        redis_client = await aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True
        )
    return redis_client


async def close_database_engine():
    """Close database engine"""
    global engine
    if engine:
        await engine.dispose()
        engine = None


async def close_redis_client():
    """Close Redis client"""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None


async def check_database_connection():
    """Check database connection health"""
    try:
        from sqlalchemy import text
        engine = await get_database_engine()
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        print(f"Database connection check failed: {e}")
        return False


async def check_redis_connection():
    """Check Redis connection health"""
    try:
        redis = await get_redis_client()
        await redis.ping()
        return True
    except Exception as e:
        print(f"Redis connection check failed: {e}")
        return False