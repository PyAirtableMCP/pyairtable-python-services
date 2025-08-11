"""Chat routes for LLM Orchestrator"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from redis import asyncio as aioredis

from models.chat import ChatRequest, ChatResponse, Message, Session
from services.gemini import GeminiService
from services.session import SessionService
from dependencies import get_redis_client

router = APIRouter(prefix="/api/v1", tags=["chat"])


async def get_session_service(redis: aioredis.Redis = Depends(get_redis_client)) -> SessionService:
    """Get session service instance"""
    return SessionService(redis)


@router.post("/chat/completions", response_model=ChatResponse)
async def create_chat_completion(
    request: ChatRequest,
    session_service: SessionService = Depends(get_session_service)
) -> ChatResponse:
    """Create a chat completion"""
    try:
        gemini_service = GeminiService()
        
        # Handle session
        session = None
        if request.session_id:
            session = await session_service.get_session(request.session_id)
            if session:
                # Add previous messages to context
                all_messages = session.messages + request.messages
                request.messages = all_messages[-20:]  # Keep last 20 messages for context
        
        # Generate completion
        if request.stream:
            raise HTTPException(
                status_code=400, 
                detail="Use /chat/completions/stream endpoint for streaming"
            )
        
        response = await gemini_service.complete(request)
        
        # Save to session if provided
        if session:
            # Add user message
            for msg in request.messages:
                if msg not in session.messages:
                    await session_service.add_message(session.id, msg)
            
            # Add assistant response
            assistant_msg = Message(
                role="assistant",
                content=response.choices[0]["message"]["content"]
            )
            await session_service.add_message(session.id, assistant_msg)
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/completions/stream")
async def stream_chat_completion(
    request: ChatRequest,
    session_service: SessionService = Depends(get_session_service)
):
    """Stream a chat completion"""
    try:
        gemini_service = GeminiService()
        
        # Handle session
        if request.session_id:
            session = await session_service.get_session(request.session_id)
            if session:
                # Add previous messages to context
                all_messages = session.messages + request.messages
                request.messages = all_messages[-20:]  # Keep last 20 messages
        
        # Stream response
        return StreamingResponse(
            gemini_service.stream_complete(request),
            media_type="text/event-stream"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions", response_model=Session)
async def create_session(
    user_id: Optional[str] = None,
    session_service: SessionService = Depends(get_session_service)
) -> Session:
    """Create a new chat session"""
    return await session_service.create_session(user_id)


@router.get("/sessions/{session_id}", response_model=Session)
async def get_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service)
) -> Session:
    """Get session by ID"""
    session = await session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/sessions/{session_id}/messages", response_model=List[Message])
async def get_session_messages(
    session_id: str,
    limit: Optional[int] = Query(None, ge=1, le=100),
    session_service: SessionService = Depends(get_session_service)
) -> List[Message]:
    """Get messages from a session"""
    messages = await session_service.get_messages(session_id, limit)
    if not messages and not await session_service.get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return messages


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    session_service: SessionService = Depends(get_session_service)
) -> dict:
    """Delete a session"""
    deleted = await session_service.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success", "message": "Session deleted"}


@router.get("/users/{user_id}/sessions", response_model=List[Session])
async def list_user_sessions(
    user_id: str,
    session_service: SessionService = Depends(get_session_service)
) -> List[Session]:
    """List all sessions for a user"""
    return await session_service.list_user_sessions(user_id)


@router.post("/models/count-tokens")
async def count_tokens(
    text: str,
    model: Optional[str] = None
) -> dict:
    """Count tokens in text"""
    try:
        gemini_service = GeminiService()
        token_count = gemini_service.count_tokens(text, model)
        return {"token_count": token_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))