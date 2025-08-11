"""Health check routes"""
from fastapi import APIRouter
from datetime import datetime

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "embedding-service",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/ready")
async def readiness_check():
    """Readiness check endpoint"""
    # TODO: Add actual readiness checks (DB connection, etc.)
    return {
        "status": "ready",
        "service": "embedding-service",
        "timestamp": datetime.utcnow().isoformat()
    }
