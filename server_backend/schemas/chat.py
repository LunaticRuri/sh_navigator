import uuid
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional
from datetime import datetime
from core.config import SESSION_TIMEOUT


class ChatMessage(BaseModel):
    """Chat message model with validation."""
    role: str = Field(..., description="Message role (user/assistant)")
    content: str = Field(..., min_length=1, description="Message content")
    session_id: str = Field(None, description="Session identifier")
    timestamp: datetime = Field(default_factory=datetime.now, description="Message timestamp")
    
    @validator('role')
    def validate_role(cls, v):
        if v not in ['user', 'assistant', 'system']:
            raise ValueError('Role must be user, assistant, or system')
        return v
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ChatSession(BaseModel):
    """Chat session model with validation."""
    session_id: str = Field(..., description="Unique session identifier")
    messages: List[ChatMessage] = Field(default_factory=list, description="Session messages")
    created_at: datetime = Field(default_factory=datetime.now, description="Session creation time")
    last_activity: Optional[datetime] = Field(None, description="Last activity timestamp")
    
    @validator('session_id')
    def validate_session_id(cls, v):
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('session_id must be a valid UUID')
    
    def add_message(self, role: str, content: str) -> None:
        """Add a message to the session."""
        message = ChatMessage(role=role, content=content)
        self.messages.append(message)
        self.last_activity = message.timestamp
    
    def is_expired(self, timeout_seconds: int = SESSION_TIMEOUT) -> bool:
        """Check if session has expired."""
        if not self.last_activity and not self.messages:
            # Empty session, check creation time
            return (datetime.now() - self.created_at).total_seconds() > timeout_seconds
        
        last_time = self.last_activity or (self.messages[-1].timestamp if self.messages else self.created_at)
        return (datetime.now() - last_time).total_seconds() > timeout_seconds
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ChatResponse(BaseModel):
    """Model for chat responses"""
    response: str = Field(..., description="Bot response content")
    session_id: str = Field(..., description="Chat session ID")
    error: Optional[str] = Field(None, description="Error message if any")


class SessionStats(BaseModel):
    """Session statistics model."""
    total_sessions: int = Field(..., ge=0, description="Total number of sessions")
    total_messages: int = Field(..., ge=0, description="Total number of messages")
    average_messages_per_session: float = Field(..., ge=0, description="Average messages per session")


class ChatbotStatus(BaseModel):
    """Model for chatbot status responses"""
    status: str = Field(..., description="Service status (active/inactive)")
    message: str = Field(..., description="Status description")


class SessionResponse(BaseModel):
    """Model for session information responses"""
    session_id: str = Field(..., description="Session identifier")
    messages: List[Dict] = Field(..., description="Session messages")
    message_count: int = Field(..., description="Number of messages")


class UserNeeds(BaseModel):
    _subject: str = Field(..., description="Subject of the user need")
    _predicate: str = Field(..., description="Predicate of the user need")
    _object: str = Field(..., description="Object of the user need")
    keywords: List[str] = Field(..., min_items=3, description="Keywords related to the user need")

class UserNeedsAnalysis(BaseModel):
    """Model for user needs analysis response"""
    needs_exist: bool = Field(..., description="Indicates if user needs exist")
    needs: Optional[List[UserNeeds]] = Field(..., description="List of user needs extracted from input")