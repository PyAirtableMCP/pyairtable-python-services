"""Health check routes"""
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
from dependencies import get_redis_client
import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/health")
async def health_check():
    """Health check endpoint with dependency checks"""
    health = {
        "status": "healthy",
        "service": "airtable-gateway",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "redis": "ok",
            "airtable_api": "ok"
        }
    }
    
    # Check Redis connection
    try:
        redis_client = await get_redis_client()
        # Test Redis connection with timeout
        await asyncio.wait_for(redis_client.ping(), timeout=5.0)
    except Exception as e:
        health["status"] = "degraded"
        health["checks"]["redis"] = "failed"
        logger.error(f"Redis health check failed: {e}")
        # Redis failure is non-critical for basic operations
        return JSONResponse(status_code=200, content=health)
    
    # Basic Airtable API availability check could be added here
    # For now, we assume it's available if the service is running
    
    return JSONResponse(status_code=200, content=health)

@router.get("/ready")
async def readiness_check():
    """Readiness check endpoint with dependency verification"""
    ready = {
        "status": "ready",
        "service": "airtable-gateway",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "redis": "ready"
        }
    }
    
    # Check if Redis is ready for operations
    try:
        redis_client = await get_redis_client()
        await asyncio.wait_for(redis_client.ping(), timeout=3.0)
        # Test a basic operation
        await asyncio.wait_for(redis_client.set("readiness_check", "ok", ex=10), timeout=3.0)
        await asyncio.wait_for(redis_client.delete("readiness_check"), timeout=3.0)
    except Exception as e:
        ready["status"] = "not_ready"
        ready["checks"]["redis"] = "not_ready"
        logger.error(f"Redis readiness check failed: {e}")
        return JSONResponse(status_code=503, content=ready)
    
    return JSONResponse(status_code=200, content=ready)
