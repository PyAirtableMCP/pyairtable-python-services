"""
Workspace Service - Workspace management and collaboration
"""
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import uvicorn

from routes import health, workspaces
from config import get_settings
from dependencies import close_database_engine, close_redis_client

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


# App lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    logger.info("Starting service",
               service=settings.service_name,
               version=settings.service_version,
               environment=settings.environment,
               port=settings.port)
    
    yield
    
    # Shutdown
    logger.info("Shutting down service", service=settings.service_name)
    await close_database_engine()
    await close_redis_client()


# Create FastAPI app
settings = get_settings()
app = FastAPI(
    title=settings.service_name,
    description="Workspace management and collaboration service for PyAirtable platform",
    version=settings.service_version,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
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


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    logger.warning("HTTP exception",
                  path=request.url.path,
                  method=request.method,
                  status_code=exc.status_code,
                  detail=exc.detail)
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "error_code": f"HTTP_{exc.status_code}"
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors"""
    logger.warning("Validation error",
                  path=request.url.path,
                  method=request.method,
                  errors=exc.errors())
    
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Validation error",
            "error_code": "VALIDATION_ERROR",
            "details": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error("Unexpected error",
                path=request.url.path,
                method=request.method,
                error=str(exc),
                exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "error_code": "INTERNAL_ERROR"
        }
    )


# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(workspaces.router, tags=["workspaces"])


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with service information"""
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "description": "Workspace management and collaboration service",
        "environment": settings.environment,
        "docs": "/docs",
        "health": "/health"
    }


# Service info endpoint
@app.get("/api/v1/info")
async def info():
    """Service information endpoint"""
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "description": "Workspace management and collaboration service",
        "port": settings.port,
        "environment": settings.environment,
        "features": [
            "workspace_crud",
            "member_management",
            "invitation_system",
            "role_based_permissions",
            "pagination_support"
        ]
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower()
    )