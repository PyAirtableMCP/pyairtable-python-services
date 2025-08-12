"""Health check routes"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from config import get_settings
from dependencies import check_database_connection, check_redis_connection

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    settings = get_settings()
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": settings.service_version,
        "environment": settings.environment,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/ready")
async def readiness_check():
    """Readiness check endpoint with actual database and Redis connectivity tests"""
    settings = get_settings()
    
    # Check database connection
    db_healthy = await check_database_connection()
    
    # Check Redis connection
    redis_healthy = await check_redis_connection()
    
    # Overall status
    is_ready = db_healthy and redis_healthy
    
    status_details = {
        "status": "ready" if is_ready else "not_ready",
        "service": settings.service_name,
        "version": settings.service_version,
        "environment": settings.environment,
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": "healthy" if db_healthy else "unhealthy",
            "redis": "healthy" if redis_healthy else "unhealthy"
        }
    }
    
    if not is_ready:
        raise HTTPException(status_code=503, detail=status_details)
    
    return status_details
