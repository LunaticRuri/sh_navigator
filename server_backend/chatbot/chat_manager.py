# -*- coding: utf-8 -*-
"""
Chat session management for SH Navigator API

This module handles chat session management, including session creation,
message storage, and cleanup of expired sessions using Redis for multi-worker support.
"""

import redis
import uuid
import json
import logging
from typing import Dict, List, Optional
from schemas.chat import ChatSession, SessionStats, ChatMessage
from core.config import REDIS_URL, REDIS_SESSION_PREFIX, SESSION_TIMEOUT

logger = logging.getLogger(__name__)


class ChatSessionManager:
    """
    Manages chat sessions for the chatbot functionality using Redis.
    
    Handles session creation, message storage, session cleanup,
    and session timeout management with Redis for multi-worker support.
    """

    def __init__(self, redis_url: str = None):
        """Initialize the chat session manager with Redis connection."""
        self.redis_url = redis_url or REDIS_URL
        self.redis_client = None
        self.session_prefix = REDIS_SESSION_PREFIX
        self._connect_redis()
    
    def _connect_redis(self):
        """Establish Redis connection with error handling."""
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            # Test connection
            self.redis_client.ping()
            logger.info(f"Connected to Redis at {self.redis_url}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            # Fallback to in-memory storage for development
            self.redis_client = None
            self.sessions = {}
            logger.warning("Falling back to in-memory session storage")
    
    def _get_session_key(self, session_id: str) -> str:
        """Get Redis key for session."""
        return f"{self.session_prefix}{session_id}"
    
    def _serialize_session(self, session: ChatSession) -> str:
        """Serialize ChatSession to JSON string."""
        return session.model_dump_json()
    
    def _deserialize_session(self, session_data: str) -> ChatSession:
        """Deserialize JSON string to ChatSession."""
        try:
            data = json.loads(session_data)
        except Exception as e:
            logger.error(f"Error deserializing session data: {e}")
            raise
        return ChatSession(**data)
    
    def cleanup_expired_sessions(self) -> None:
        """Clean up expired chat sessions to prevent memory leaks."""
        if self.redis_client is None:
            # Fallback to in-memory cleanup
            expired_sessions = [
                session_id for session_id, session in self.sessions.items()
                if session.is_expired()
            ]
            
            for session_id in expired_sessions:
                del self.sessions[session_id]
                logger.info(f"Expired session removed: {session_id}")
        else:
            # Redis sessions are automatically cleaned up by TTL
            # This method can be used to manually clean up if needed
            keys = self.redis_client.keys(f"{self.session_prefix}*")
            expired_count = 0
            
            for key in keys:
                try:
                    session_data = self.redis_client.get(key)
                    if session_data:
                        session = self._deserialize_session(session_data)
                        if session.is_expired():
                            self.redis_client.delete(key)
                            expired_count += 1
                except Exception as e:
                    logger.error(f"Error checking session expiry for {key}: {e}")
                    self.redis_client.delete(key)
                    logger.warning(f"Deleted session {key} due to error")
                    expired_count += 1
            
            if expired_count > 0:
                logger.info(f"Manually cleaned up {expired_count} expired sessions")
    
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
        
        if self.redis_client is None:
            # Fallback to in-memory storage
            if session_id and session_id in self.sessions:
                return session_id
            
            # Create new session
            new_session_id = str(uuid.uuid4())
            self.sessions[new_session_id] = ChatSession(session_id=new_session_id)
            return new_session_id
        else:
            if session_id:
                session_key = self._get_session_key(session_id)
                if self.redis_client.exists(session_key):
                    # Refresh TTL
                    self.redis_client.expire(session_key, SESSION_TIMEOUT)
                    return session_id
            
            # Create new session
            new_session_id = str(uuid.uuid4())
            session = ChatSession(session_id=new_session_id)
            session_key = self._get_session_key(new_session_id)
            
            # Store in Redis with TTL
            self.redis_client.setex(
                session_key, 
                SESSION_TIMEOUT, 
                self._serialize_session(session)
            )
            
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
        if self.redis_client is None:
            # Fallback to in-memory storage
            if session_id not in self.sessions:
                # Create session if it doesn't exist
                self.sessions[session_id] = ChatSession(session_id=session_id)
            
            self.sessions[session_id].add_message(role, content, session_id)
        else:
            # Redis storage
            session_key = self._get_session_key(session_id)
            session_data = self.redis_client.get(session_key)
            
            if session_data:
                session = self._deserialize_session(session_data)
            else:
                # Create session if it doesn't exist
                session = ChatSession(session_id=session_id)
            
            # Add message
            session.add_message(role=role, content=content, session_id=session_id)
            
            # Store back to Redis with refreshed TTL
            self.redis_client.setex(
                session_key,
                SESSION_TIMEOUT,
                self._serialize_session(session)
            )
    
    def get_session_history(self, session_id: str) -> List[Dict]:
        """
        Get the chat history for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            List of messages in the session
        """
        if self.redis_client is None:
            # Fallback to in-memory storage
            if session_id not in self.sessions:
                return []
            
            return [message.model_dump() for message in self.sessions[session_id].messages]
        else:
            # Redis storage
            session_key = self._get_session_key(session_id)
            session_data = self.redis_client.get(session_key)
            
            if not session_data:
                return []
            try:
                session = self._deserialize_session(session_data)
                return [message.model_dump() for message in session.messages]
            except Exception as e:
                logger.error(f"Error retrieving session history for {session_id}: {e}")
                self.redis_client.delete(session_key)
                return []
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """
        Get a chat session object.
        
        Args:
            session_id: Session identifier
            
        Returns:
            ChatSession object or None if not found
        """
        if self.redis_client is None:
            # Fallback to in-memory storage
            return self.sessions.get(session_id)
        else:
            # Redis storage
            session_key = self._get_session_key(session_id)
            session_data = self.redis_client.get(session_key)
            
            if not session_data:
                return None
            try:
                return self._deserialize_session(session_data)
            except Exception as e:
                logger.error(f"Error retrieving session {session_id}: {e}")
                self.redis_client.delete(session_key)
                return None
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a chat session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was deleted, False if not found
        """
        if self.redis_client is None:
            # Fallback to in-memory storage
            if session_id in self.sessions:
                del self.sessions[session_id]
                logger.info(f"Session deleted: {session_id}")
                return True
            return False
        else:
            # Redis storage
            session_key = self._get_session_key(session_id)
            result = self.redis_client.delete(session_key)
            
            if result:
                logger.info(f"Session deleted: {session_id}")
                return True
            return False
    
    def get_session_count(self) -> int:
        """
        Get the current number of active sessions.
        
        Returns:
            Number of active sessions
        """
        if self.redis_client is None:
            return len(self.sessions)
        else:
            keys = self.redis_client.keys(f"{self.session_prefix}*")
            return len(keys)
    
    def get_session_stats(self) -> SessionStats:
        """
        Get statistics about current sessions.
        
        Returns:
            SessionStats object containing session statistics
        """
        if self.redis_client is None:
            # Fallback to in-memory storage
            total_sessions = len(self.sessions)
            total_messages = sum(len(session.messages) for session in self.sessions.values())
            
            return SessionStats(
                total_sessions=total_sessions,
                total_messages=total_messages,
                average_messages_per_session=total_messages / total_sessions if total_sessions > 0 else 0
            )
        else:
            # Redis storage
            keys = self.redis_client.keys(f"{self.session_prefix}*")
            total_sessions = len(keys)
            total_messages = 0
            
            for key in keys:
                try:
                    session_data = self.redis_client.get(key)
                    if session_data:
                        session = self._deserialize_session(session_data)
                        total_messages += len(session.messages)
                except Exception as e:
                    logger.error(f"Error reading session stats for {key}: {e}")
            
            return SessionStats(
                total_sessions=total_sessions,
                total_messages=total_messages,
                average_messages_per_session=total_messages / total_sessions if total_sessions > 0 else 0
            )


# Global session manager instance
chat_session_manager = ChatSessionManager()