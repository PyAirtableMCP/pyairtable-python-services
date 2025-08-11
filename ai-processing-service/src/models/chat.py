"""Chat models for AI Processing Service"""
from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    message: str
    context: Dict[str, Any] = {}


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    response: str
    timestamp: str