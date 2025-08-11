"""
embedding-service - Text embedding generation
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from routes import health

# App lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"Starting embedding-service...")
    yield
    # Shutdown
    print(f"Shutting down embedding-service...")

# Create FastAPI app
app = FastAPI(
    title="embedding-service",
    description="Text embedding generation",
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

# Root endpoint
@app.get("/")
async def root():
    return {
        "service": "embedding-service",
        "version": "1.0.0",
        "description": "Text embedding generation"
    }

# Service info endpoint
@app.get("/api/v1/info")
async def info():
    return {
        "service": "embedding-service",
        "version": "1.0.0",
        "description": "Text embedding generation",
        "port": 8096
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8096"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENV", "production") == "development"
    )
