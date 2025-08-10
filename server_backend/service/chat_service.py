from functools import lru_cache
import asyncio
import logging
from typing import List, Dict
from fastapi import HTTPException

import google.generativeai as genai

from schemas.chat import ChatMessage, ChatResponse
from service.chat_manager import chat_session_manager
from core.utils import format_gemini_chat_history, get_system_prompt
from core.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)


class ChatService:
    """Service class for chatbot operations."""

    def __init__(self):
        """Initialize the chat service with Gemini API."""
        self.model = None
        self.is_available = False
        
        if GEMINI_API_KEY:
            try:
                genai.configure(api_key=GEMINI_API_KEY)
                self.model = genai.GenerativeModel(GEMINI_MODEL)
                self.is_available = True
                logger.info("Gemini API initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini API: {e}")
                self.is_available = False
        else:
            logger.warning("GEMINI_API_KEY not set. Chatbot functionality disabled.")
            self.is_available = False

    async def chat(self, chat_message: ChatMessage) -> ChatResponse:
        """
        Process a chat message and generate a response.
        
        Args:
            chat_message: User's chat message
            
        Returns:
            ChatResponse with bot's reply
        """
        if not self.is_available:
            raise HTTPException(
                status_code=503, 
                detail="챗봇 서비스를 사용할 수 없습니다. API 키가 설정되지 않았습니다."
            )
        try:
            # Get or create session
            session_id = chat_session_manager.get_or_create_session(chat_message.session_id)
            
            # Get conversation history
            history = chat_session_manager.get_session_history(session_id)

            # Generate response
            response_text = await self._generate_response(chat_message.content, history)
            
            # Save messages to session
            chat_session_manager.add_message_to_session(session_id, 'user', chat_message.content)
            chat_session_manager.add_message_to_session(session_id, 'assistant', response_text)
            
            return ChatResponse(response=response_text, session_id=session_id)
            
        except Exception as e:
            logger.error(f"Chat response generation error: {e}")
            session_id = chat_session_manager.get_or_create_session(chat_message.session_id)
            
            return ChatResponse(
                response="죄송합니다. 현재 응답을 생성할 수 없습니다. 잠시 후 다시 시도해주세요.",
                session_id=session_id,
                error=str(e)
            )

    async def _generate_response(self, message: str, history: List[Dict]) -> str:
        """
        Generate a response using Gemini API.
        
        Args:
            message: User's message
            history: Conversation history
            
        Returns:
            Generated response text
        """
        try:
            # Format history for Gemini API
            chat_history = format_gemini_chat_history(history)
            
            # Add system prompt for new conversations
            if not chat_history:
                system_prompt = get_system_prompt()
                chat_history = [
                    {
                        'role': 'user',
                        'parts': ['안녕하세요! 도서관 관련 질문이 있습니다.']
                    },
                    {
                        'role': 'model',
                        'parts': [system_prompt + '\n\n안녕하세요! 도서관과 주제명표목에 대한 질문이 있으시면 언제든 물어보세요.']
                    }
                ]
            
            # Generate response
            if chat_history:
                # Use chat session for existing conversation
                chat = self.model.start_chat(history=chat_history)
                response = await asyncio.to_thread(chat.send_message, message)
            else:
                # Generate response for new conversation
                full_prompt = f"""당신은 도서관과 주제명표목에 대한 전문 지식을 가진 AI 어시스턴트입니다. 
다음 역할을 수행합니다:

1. 도서 검색 및 추천에 대한 도움
2. 주제명표목(Subject Headings) 시스템에 대한 설명
3. 한국십진분류법(KDC)에 대한 정보 제공
4. 도서관 이용 방법 안내
5. 일반적인 질문에 대한 친근하고 도움이 되는 답변

사용자의 질문에 정확하고 친절하게 답변해주세요.

사용자 질문: {message}"""
                
                response = await asyncio.to_thread(self.model.generate_content, full_prompt)
            
            return response.text
            
        except Exception as e:
            logger.error(f"Error generating Gemini response: {e}")
            raise e

    def get_status(self) -> Dict[str, str]:
        """
        Get chatbot service status.
        
        Returns:
            Status dictionary
        """
        if self.is_available:
            return {
                "status": "active", 
                "message": "챗봇 서비스가 활성화되어 있습니다."
            }
        else:
            return {
                "status": "inactive", 
                "message": "챗봇 서비스가 비활성화되어 있습니다. API 키를 확인해주세요."
            }

    def get_session_info(self, session_id: str) -> Dict:
        """
        Get information about a specific chat session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session information dictionary
        """
        history = chat_session_manager.get_session_history(session_id)
        
        return {
            "session_id": session_id,
            "messages": [msg for msg in history if msg['role'] in ['user', 'assistant']],
            "message_count": len(history)
        }

    def clear_session(self, session_id: str) -> bool:
        """
        Clear a specific chat session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session was cleared, False if not found
        """
        return chat_session_manager.delete_session(session_id)

    def create_new_session(self) -> str:
        """
        Create a new chat session.
        
        Returns:
            New session ID
        """
        return chat_session_manager.get_or_create_session()

    def get_session_stats(self) -> Dict:
        """
        Get statistics about all chat sessions.
        
        Returns:
            Session statistics dictionary
        """
        return chat_session_manager.get_session_stats()


# Global chat service instance
chat_service = ChatService()


@lru_cache()
def get_chat_service() -> ChatService:
    """FastAPI 의존성으로 사용할 chat service 인스턴스 반환"""
    return chat_service  # 기존 전역 인스턴스 사용