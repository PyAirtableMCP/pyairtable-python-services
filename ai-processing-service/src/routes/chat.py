"""Chat routes for AI Processing Service"""
from fastapi import APIRouter
from datetime import datetime
from models.chat import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/api/ai/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Basic chat endpoint that echoes messages
    Currently returns mock responses - actual AI logic to be implemented later
    """
    return ChatResponse(
        response=f"Echo: {request.message}",
        timestamp=datetime.utcnow().isoformat()
    )