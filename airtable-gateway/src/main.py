"""
airtable-gateway - Airtable API integration gateway
"""
import os
import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

# Initialize OpenTelemetry before importing other modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'shared'))
try:
    from telemetry import initialize_telemetry
    
    # Initialize telemetry for Airtable Gateway (Port 8002)
    tracer = initialize_telemetry(
        service_name="airtable-gateway",
        service_version="1.0.0",
        service_tier="integration",
        otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
        resource_attributes={
            "service.port": "8002",
            "service.type": "airtable-gateway",
            "service.layer": "api-integration"
        }
    )
    
    logging.info("OpenTelemetry initialized for airtable-gateway")
except ImportError as e:
    logging.warning(f"OpenTelemetry initialization failed: {e}")
    tracer = None

from routes import health

# App lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"Starting airtable-gateway...")
    from dependencies import get_redis_client
    # Initialize Redis connection
    await get_redis_client()
    yield
    # Shutdown
    print(f"Shutting down airtable-gateway...")
    from dependencies import close_redis_client
    await close_redis_client()

# Create FastAPI app
app = FastAPI(
    title="airtable-gateway",
    description="Airtable API integration gateway",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication middleware
from middleware.auth import AuthMiddleware
from config import get_settings
settings = get_settings()
app.add_middleware(AuthMiddleware, internal_api_key=settings.internal_api_key)

# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )

# Include routers
app.include_router(health.router, tags=["health"])
from routes.airtable import router as airtable_router
app.include_router(airtable_router)

# Root endpoint
@app.get("/")
async def root():
    return {
        "service": "airtable-gateway",
        "version": "1.0.0",
        "description": "Airtable API integration gateway"
    }

# Service info endpoint
@app.get("/api/v1/info")
async def info():
    from config import get_settings
    settings = get_settings()
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "description": "Airtable API integration gateway",
        "port": settings.port,
        "features": [
            "Rate limiting",
            "Response caching",
            "Batch operations",
            "Schema introspection"
        ]
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8002"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENV", "production") == "development"
    )
