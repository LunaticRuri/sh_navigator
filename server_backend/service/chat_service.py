from functools import lru_cache
import asyncio
import logging
from typing import List, Dict
from fastapi import HTTPException

import google.generativeai as genai

from schemas.chat import ChatMessage, ChatResponse, UserNeeds, UserNeedsAnalysis, ResourcesFromNeeds
from chatbot.chat_pipeline import analyze_user_needs, find_resources_from_needs
from chatbot.chat_manager import chat_session_manager
from chatbot.chat_utils import get_system_prompt
from core.utils import format_gemini_chat_history
from core.config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)


class ChatService:
    """Service class for chatbot operations."""

    def __init__(self):
        """
        Initialize the chat service with Gemini API.
        Sets up the generative model if API key is available.
        """
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
        """
        if not self.is_available:
            raise HTTPException(
                status_code=503,
                detail="챗봇 서비스를 사용할 수 없습니다. API 키가 설정되지 않았습니다."
            )
        try:
            session_id = chat_session_manager.get_or_create_session(chat_message.session_id)
            history = chat_session_manager.get_session_history(session_id)

            needs_analysis: UserNeedsAnalysis = await analyze_user_needs(chat_message.content)
            if not needs_analysis.needs_exist:
                response_text = await self._generate_response(chat_message.content, history)
                chat_session_manager.add_message_to_session(session_id, 'user', chat_message.content)
                chat_session_manager.add_message_to_session(session_id, 'assistant', response_text)
                return ChatResponse(response=response_text, session_id=session_id)

            for need in needs_analysis.needs:
                resource_from_needs: ResourcesFromNeeds = await find_resources_from_needs(need)
                logger.info(need)
                logger.info(resource_from_needs)
            
            #TODO: 임시 생성이라서 나중에 제대로 로직 짜서 고쳐야 함.
            # Generate response based on user needs
            needs_analysis_text = str(needs_analysis)
            resources_text = str(resource_from_needs)

            enhanced_content = (
                f"{chat_message.content}\n"
                f"아래는 사용자 요구 분석 결과와 그에 따른 관련 책과 주제명 표목이다. 이를 활용하여 사용자의 정보요구를 해결하고, 지적 탐험을 도와라.\n"
                f"요구분석 내용: {resources_text}\n"
                f"관련 책과 주제명 표목: {needs_analysis_text}\n"
            ) 
            
            
            response_text = await self._generate_response(enhanced_content, history)
            chat_session_manager.add_message_to_session(session_id, 'user', enhanced_content)
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
        """
        try:
            chat_history = format_gemini_chat_history(history)
            if not chat_history:
                system_prompt = get_system_prompt()
                chat_history = [
                    {
                        'role': 'user',
                        'parts': [
                            '안녕! 나는 도서관의 책과 주제명 표목을 통해 지적 탐색을 수행하고 싶은 사용자야.'
                        ]
                    },
                    {
                        'role': 'model',
                        'parts': [
                            system_prompt + '\n\n안녕하세요! 도서관과 주제명표목에 대한 질문이 있으시면 언제든 물어보세요.'
                        ]
                    }
                ]
            
            chat = self.model.start_chat(history=chat_history)
            response = await asyncio.to_thread(chat.send_message, message)

            return response.text

        except Exception as e:
            logger.error(f"Error generating Gemini response: {e}")
            raise e

    def get_status(self) -> Dict[str, str]:
        """
        Get chatbot service status.
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
        """
        return chat_session_manager.delete_session(session_id)

    def create_new_session(self) -> str:
        """
        Create a new chat session.
        """
        return chat_session_manager.get_or_create_session()

    def get_session_stats(self) -> Dict:
        """
        Get statistics about all chat sessions.
        """
        return chat_session_manager.get_session_stats()


chat_service = ChatService()


@lru_cache()
def get_chat_service() -> ChatService:
    """
    FastAPI dependency for providing the chat service instance.
    Returns the global chat_service instance.
    """
    return chat_service
