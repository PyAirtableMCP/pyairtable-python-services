"""Session management service"""
import json
import uuid
from typing import Optional, List
from datetime import datetime
from redis import asyncio as aioredis

from models.chat import Session, Message
from config import get_settings


class SessionService:
    """Service for managing chat sessions"""
    
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self.settings = get_settings()
        self.key_prefix = "session"
    
    def _session_key(self, session_id: str) -> str:
        """Generate Redis key for session"""
        return f"{self.key_prefix}:{session_id}"
    
    async def create_session(self, user_id: Optional[str] = None) -> Session:
        """Create a new session"""
        session = Session(
            id=str(uuid.uuid4()),
            user_id=user_id,
            messages=[],
            metadata={},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Store in Redis
        await self.redis.setex(
            self._session_key(session.id),
            self.settings.session_ttl,
            session.model_dump_json()
        )
        
        return session
    
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Get session by ID"""
        data = await self.redis.get(self._session_key(session_id))
        if data:
            return Session.model_validate_json(data)
        return None
    
    async def update_session(self, session: Session) -> Session:
        """Update session"""
        session.updated_at = datetime.utcnow()
        
        # Update in Redis
        await self.redis.setex(
            self._session_key(session.id),
            self.settings.session_ttl,
            session.model_dump_json()
        )
        
        return session
    
    async def add_message(self, session_id: str, message: Message) -> Optional[Session]:
        """Add message to session"""
        session = await self.get_session(session_id)
        if not session:
            return None
        
        session.messages.append(message)
        return await self.update_session(session)
    
    async def get_messages(self, session_id: str, limit: Optional[int] = None) -> List[Message]:
        """Get messages from session"""
        session = await self.get_session(session_id)
        if not session:
            return []
        
        messages = session.messages
        if limit:
            messages = messages[-limit:]
        
        return messages
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete session"""
        result = await self.redis.delete(self._session_key(session_id))
        return result > 0
    
    async def list_user_sessions(self, user_id: str) -> List[Session]:
        """List all sessions for a user"""
        sessions = []
        
        # Scan for all session keys
        cursor = 0
        while True:
            cursor, keys = await self.redis.scan(
                cursor,
                match=f"{self.key_prefix}:*",
                count=100
            )
            
            for key in keys:
                data = await self.redis.get(key)
                if data:
                    session = Session.model_validate_json(data)
                    if session.user_id == user_id:
                        sessions.append(session)
            
            if cursor == 0:
                break
        
        # Sort by updated_at descending
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions
    
    async def cleanup_expired_sessions(self):
        """Clean up expired sessions (called periodically)"""
        # Redis handles expiration automatically with TTL
        pass