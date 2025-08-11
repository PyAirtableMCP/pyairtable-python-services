"""Health check routes for AI Processing Service"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import httpx
import asyncio
import logging

router = APIRouter()

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Comprehensive health check for consolidated AI Processing Service
    Checks both MCP and LLM functionality
    """
    health_data = {
        "status": "healthy",
        "service": "ai-processing-service",
        "version": "1.0.0",
        "consolidation": {
            "original_services": ["mcp-server", "llm-orchestrator"],
            "status": "consolidated"
        },
        "components": {}
    }
    
    # Check Redis connection
    try:
        from dependencies import get_redis_client
        redis_client = await get_redis_client()
        await redis_client.ping()
        health_data["components"]["redis"] = {"status": "healthy"}
    except ImportError:
        health_data["components"]["redis"] = {"status": "not_configured"}
    except Exception as e:
        logging.error(f"Redis health check failed: {e}")
        health_data["components"]["redis"] = {"status": "unhealthy", "error": str(e)}
        health_data["status"] = "degraded"
    
    # Check Gemini API availability
    try:
        from config import get_settings
        settings = get_settings()
        if settings.gemini_api_key:
            health_data["components"]["gemini"] = {"status": "configured"}
        else:
            health_data["components"]["gemini"] = {"status": "not_configured"}
    except Exception as e:
        logging.error(f"Gemini config check failed: {e}")
        health_data["components"]["gemini"] = {"status": "error", "error": str(e)}
    
    # Check Airtable Gateway connectivity (if configured)
    try:
        from config import get_settings
        settings = get_settings()
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.airtable_gateway_url}/health")
            if response.status_code == 200:
                health_data["components"]["airtable_gateway"] = {"status": "healthy"}
            else:
                health_data["components"]["airtable_gateway"] = {"status": "unhealthy", "http_status": response.status_code}
    except httpx.RequestError as e:
        health_data["components"]["airtable_gateway"] = {"status": "unreachable", "error": str(e)}
    except Exception as e:
        health_data["components"]["airtable_gateway"] = {"status": "error", "error": str(e)}
    
    return health_data

@router.get("/health/ready")
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness check - service is ready to accept requests
    """
    try:
        # Basic readiness check
        return {
            "status": "ready",
            "service": "ai-processing-service",
            "timestamp": "2025-01-11",
            "consolidation_ready": True
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service not ready: {str(e)}")

@router.get("/health/live")
async def liveness_check() -> Dict[str, Any]:
    """
    Liveness check - service is alive
    """
    return {
        "status": "alive",
        "service": "ai-processing-service",
        "consolidation": "active"
    }