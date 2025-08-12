"""
analytics-service - Analytics and reporting
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from routes import health
from config import get_settings
from dependencies import close_database_engine, close_redis_client

# App lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    print(f"Starting {settings.service_name} v{settings.service_version}...")
    print(f"Environment: {settings.environment}")
    print(f"Database URL: {settings.get_async_database_url()}")
    print(f"Redis URL: {settings.redis_url}")
    yield
    # Shutdown
    print(f"Shutting down {settings.service_name}...")
    await close_database_engine()
    await close_redis_client()

# Create FastAPI app
settings = get_settings()
app = FastAPI(
    title=settings.service_name,
    description="Analytics and reporting for PyAirtable platform",
    version=settings.service_version,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )

# Include routers
app.include_router(health.router, tags=["health"])

# Root endpoint
@app.get("/")
async def root():
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "description": "Analytics and reporting for PyAirtable platform",
        "environment": settings.environment
    }

# Service info endpoint
@app.get("/api/v1/info")
async def info():
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "description": "Analytics and reporting for PyAirtable platform",
        "port": settings.port,
        "environment": settings.environment
    }

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development"
    )
