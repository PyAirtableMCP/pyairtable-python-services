from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from datetime import datetime

app = FastAPI(
    title="PyAirtable AI Service",
    description="AI processing microservice",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "ai-service",
        "timestamp": datetime.utcnow().isoformat(),
        "port": 8200
    }

@app.get("/")
async def root():
    return {
        "message": "PyAirtable AI Service",
        "version": "1.0.0",
        "capabilities": ["text-processing", "data-analysis", "predictions"]
    }

@app.post("/process")
async def process_data(data: dict):
    return {
        "result": "processed",
        "input": data,
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8200))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
