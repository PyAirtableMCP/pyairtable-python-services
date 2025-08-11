"""
formula-engine - Formula parsing and execution
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
    print(f"Starting formula-engine...")
    yield
    # Shutdown
    print(f"Shutting down formula-engine...")

# Create FastAPI app
app = FastAPI(
    title="formula-engine",
    description="Formula parsing and execution",
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
        "service": "formula-engine",
        "version": "1.0.0",
        "description": "Formula parsing and execution"
    }

# Service info endpoint
@app.get("/api/v1/info")
async def info():
    return {
        "service": "formula-engine",
        "version": "1.0.0",
        "description": "Formula parsing and execution",
        "port": 8095
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8095"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("ENV", "production") == "development"
    )
