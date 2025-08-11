"""
llm-orchestrator - LLM orchestration with Gemini integration
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
    
    # Initialize telemetry for LLM Orchestrator (Port 8003)
    tracer = initialize_telemetry(
        service_name="llm-orchestrator",
        service_version="1.0.0",
        service_tier="ai-ml",
        otlp_endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"),
        resource_attributes={
            "service.port": "8003",
            "service.type": "llm-orchestrator",
            "service.layer": "ai-processing"
        }
    )
    
    logging.info("OpenTelemetry initialized for llm-orchestrator")
except ImportError as e:
    logging.warning(f"OpenTelemetry initialization failed: {e}")
    tracer = None

from routes import health

# App lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"Starting llm-orchestrator...")
    from dependencies import get_redis_client
    # Initialize Redis connection
    await get_redis_client()
    yield
    # Shutdown
    print(f"Shutting down llm-orchestrator...")
    from dependencies import close_redis_client
    await close_redis_client()

# Create FastAPI app
app = FastAPI(
    title="llm-orchestrator",
    description="LLM orchestration with Gemini integration",
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

# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)}
    )

# Include routers
app.include_router(health.router, tags=["health"])
from routes.chat import router as chat_router
app.include_router(chat_router)
from routes.table_analysis import router as analysis_router
app.include_router(analysis_router)
from routes.workflow import router as workflow_router
app.include_router(workflow_router)

# Root endpoint
@app.get("/")
async def root():
    return {
        "service": "llm-orchestrator",
        "version": "1.0.0",
        "description": "LLM orchestration with Gemini integration"
    }

# Service info endpoint
@app.get("/api/v1/info")
async def info():
    from config import get_settings
    settings = get_settings()
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "description": "LLM orchestration with Gemini integration",
        "port": settings.port,
        "model": settings.gemini_model,
        "features": [
            "Chat completions",
            "Streaming responses",
            "Session management",
            "Token counting",
            "Cost tracking",
            "Table analysis",
            "Batch processing",
            "Optimization recommendations"
        ]
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8091"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENV", "production") == "development"
    )