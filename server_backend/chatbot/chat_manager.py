# -*- coding: utf-8 -*-
"""
Chat session management for SH Navigator API

This module handles chat session management, including session creation,
message storage, and cleanup of expired sessions.
"""

import uuid
import logging
from typing import Dict, List, Optional
from schemas.chat import ChatSession, SessionStats

logger = logging.getLogger(__name__)


class ChatSessionManager:
    """
    Manages chat sessions for the chatbot functionality.
    
    Handles session creation, message storage, session cleanup,
    and session timeout management with Pydantic validation.
    """

    def __init__(self):
        """Initialize the chat session manager."""
        self.sessions: Dict[str, ChatSession] = {}
    
    def cleanup_expired_sessions(self) -> None:
        """Clean up expired chat sessions to prevent memory leaks."""
        expired_sessions = [
            session_id for session_id, session in self.sessions.items()
            if session.is_expired()
        ]
        
        for session_id in expired_sessions:
            del self.sessions[session_id]
            logger.info(f"Expired session removed: {session_id}")
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> str:
        """
        Get an existing session or create a new one.
        
        Args:
            session_id: Existing session ID or None to create new session
            
        Returns:
            Session ID (existing or newly created)
        """
        # Clean up expired sessions first
        self.cleanup_expired_sessions()
        
        # Return existing session if valid
        if session_id and session_id in self.sessions:
            return session_id
        
        # Create new session
        new_session_id = str(uuid.uuid4())
        self.sessions[new_session_id] = ChatSession(session_id=new_session_id)
        logger.info(f"New chat session created: {new_session_id}")
        
        return new_session_id
    
    def add_message_to_session(self, session_id: str, role: str, content: str) -> None:
        """
        Add a message to a chat session.
        
        Args:
            session_id: Session identifier
            role: Message role (user/assistant)
            content: Message content
            
        Raises:
            ValueError: If role or content is invalid
            KeyError: If session doesn't exist
        """
        if session_id not in self.sessions:
            # Create session if it doesn't exist
            self.sessions[session_id] = ChatSession(session_id=session_id)
        
        self.sessions[session_id].add_message(role, content)
        logger.debug(f"Message added to session {session_id}: {role}")
    
    def get_session_history(self, session_id: str) -> List[Dict]:
        """
        Get the chat history for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of messages in the session
        """
        if session_id not in self.sessions:
            return []
        
        return [message.model_dump() for message in self.sessions[session_id].messages]
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        Get a chat session object.
        
        Args:
            session_id: Session identifier
            
        Returns:
            ChatSession object or None if not found
        """
        return self.sessions.get(session_id)
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a chat session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was deleted, False if not found
        """
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Session deleted: {session_id}")
            return True
        
        return False
    
    def get_session_count(self) -> int:
        """
        Get the current number of active sessions.
        
        Returns:
            Number of active sessions
        """
        return len(self.sessions)
    
    def get_session_stats(self) -> SessionStats:
        """
        Get statistics about current sessions.
        
        Returns:
            SessionStats object containing session statistics
        """
        total_sessions = len(self.sessions)
        total_messages = sum(len(session.messages) for session in self.sessions.values())
        
        return SessionStats(
            total_sessions=total_sessions,
            total_messages=total_messages,
            average_messages_per_session=total_messages / total_sessions if total_sessions > 0 else 0
        )


# Global session manager instance
chat_session_manager = ChatSessionManager()