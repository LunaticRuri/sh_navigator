from functools import lru_cache
import asyncio
import logging
from typing import List, Dict
from fastapi import HTTPException

import google.generativeai as genai

from schemas.chat import ChatMessage, ChatResponse, UserNeeds, UserNeedsAnalysis, ResourcesFromNeeds
from chatbot.chat_pipeline import analyze_user_needs, find_resources_from_needs, find_resources_by_isbn, find_resources_by_node_id, add_one_more_resource
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

        # Configure Gemini API if API key is provided
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
        Handles user needs analysis and resource finding.
        """
        if not self.is_available:
            # Service unavailable if API key is missing
            raise HTTPException(
                status_code=503,
                detail="챗봇 서비스를 사용할 수 없습니다. API 키가 설정되지 않았습니다."
            )
        try:
            # Retrieve or create chat session
            session_id = chat_session_manager.get_or_create_session(chat_message.session_id)
            history = chat_session_manager.get_session_history(session_id)
            
            # If session is new, add system prompt
            if not history:
                chat_session_manager.add_message_to_session(session_id, 'user', get_system_prompt())
                history = chat_session_manager.get_session_history(session_id)
            
            # Analyze user needs from the message
            needs_analysis: UserNeedsAnalysis = await analyze_user_needs(chat_message.content)
            if not needs_analysis.needs_exist:
                # If no needs detected, generate a simple response
                response_text = await self._generate_response(chat_message.content, history)
                chat_session_manager.add_message_to_session(session_id, 'user', chat_message.content)
                chat_session_manager.add_message_to_session(session_id, 'assistant', response_text)
                return ChatResponse(response=response_text, session_id=session_id)
            
            # For each detected need, find related resources and build response text
            resource_text = ""
            for need in needs_analysis.needs:
                resource_from_needs: ResourcesFromNeeds = await find_resources_from_needs(need)
                resource_text += f"<요구분석 내용> -> {need} \n 관련 책과 주제명 표목 -> {resource_from_needs}\n\n"

            # Enhance user content with resource information for better response
            enhanced_content = (
                f"{chat_message.content}\n"
                f"아래는 사용자 요구 분석 결과와 그에 따른 관련 책과 주제명 표목이다. 이를 활용하여 사용자의 정보요구를 해결하고, 지적 탐험을 도와라.\n"
                f"{resource_text}"
            ) 
            
            # Generate response using enhanced content
            response_text = await self._generate_response(enhanced_content, history)
            chat_session_manager.add_message_to_session(session_id, 'user', enhanced_content)
            chat_session_manager.add_message_to_session(session_id, 'assistant', response_text)
            return ChatResponse(response=response_text, session_id=session_id)

        except Exception as e:
            # Handle errors gracefully and log them
            logger.error(f"Chat response generation error: {e}")
            session_id = chat_session_manager.get_or_create_session(chat_message.session_id)
            return ChatResponse(
                response="죄송합니다. 현재 응답을 생성할 수 없습니다. 잠시 후 다시 시도해주세요.",
                session_id=session_id,
                error=str(e)
            )

    async def chat_with_book(self, chat_message: ChatMessage) -> ChatResponse:
        """
        Start a conversation about a specific book.
        Uses the chat history to generate a response.
        """
        if not self.is_available:
            raise HTTPException(
                status_code=503,
                detail="챗봇 서비스를 사용할 수 없습니다. API 키가 설정되지 않았습니다."
            )
        try:
            session_id = chat_session_manager.get_or_create_session(chat_message.session_id)
            history = chat_session_manager.get_session_history(session_id)

            # If session is new, add system prompt
            if not history:
                chat_session_manager.add_message_to_session(session_id, 'user', get_system_prompt())
                history = chat_session_manager.get_session_history(session_id)

            # Try to find book information by ISBN
            try:
                resoruce_str = await find_resources_by_isbn(chat_message.content.strip())
            except RuntimeError as e:
                logger.error(f"Error finding book by ISBN: {e}")

            # Build enhanced content for Gemini response
            enhanced_content = (
                f"사용자에게 주어진 정보를 바탕으로 책을 소개하라. 주어진 정보가 없거나 부족하다면 이를 안내하라.\n"
                f"{resoruce_str}\n"
            )

            response_text = await self._generate_response(enhanced_content, history)
            chat_session_manager.add_message_to_session(session_id, 'user', enhanced_content)
            chat_session_manager.add_message_to_session(session_id, 'assistant', response_text)
            return ChatResponse(response=response_text, session_id=session_id)

        except Exception as e:
            logger.error(f"Error in chat_with_book: {e}")
            raise HTTPException(status_code=500, detail="책에 대한 대화 중 오류가 발생했습니다.")
    
    async def chat_with_subject(self, chat_message: ChatMessage) -> ChatResponse:
        """
        Start a conversation about a specific subject.
        Uses the chat history to generate a response.
        """
        if not self.is_available:
            raise HTTPException(
                status_code=503,
                detail="챗봇 서비스를 사용할 수 없습니다. API 키가 설정되지 않았습니다."
            )
        try:
            session_id = chat_session_manager.get_or_create_session(chat_message.session_id)
            history = chat_session_manager.get_session_history(session_id)

            # If session is new, add system prompt
            if not history:
                chat_session_manager.add_message_to_session(session_id, 'user', get_system_prompt())
                history = chat_session_manager.get_session_history(session_id)

            # Try to find subject information by node ID
            try:
                subject_response = await find_resources_by_node_id(chat_message.content.strip())
            except RuntimeError as e:
                logger.error(f"Error finding subject by node ID: {e}")
                raise HTTPException(status_code=404, detail="주제를 찾을 수 없습니다.")
            
            # Build enhanced content for Gemini response
            enhanced_content = (
                "아래 주제에 대해 안내하라. 너의 역할은 주어진 주제와 관련된 책이나 관련된 주제 등을 통해 이용자에게 접근점을 제시하는 것이다.\n"
                "주제를 안내하기 위해 주어진 관련 정보가 없거나 부족하다면 이를 밝혀라.\n"
                "관련 주제 관계에 대해서는 모두 밝힐 필요가 없고, 사용자가 다양한 관점을 가질 수 있도록 돕는 주제들을 중심으로 선정하여 설명하자.\n"
                f"{subject_response}\n"
            )
            response_text = await self._generate_response(enhanced_content, history)
            chat_session_manager.add_message_to_session(session_id, 'user', enhanced_content)
            chat_session_manager.add_message_to_session(session_id, 'assistant', response_text)
            
            return ChatResponse(response=response_text, session_id=session_id)

        except Exception as e:
            logger.error(f"Error in chat_with_subject: {e}")
            raise HTTPException(status_code=500, detail="주제에 대한 대화 중 오류가 발생했습니다.")
    
    async def chat_with_discover(self, chat_message: ChatMessage) -> ChatResponse:
        """
        Provide one more related resource or perspective.
        Uses the chat history to generate a response.
        """
        if not self.is_available:
            raise HTTPException(
                status_code=503,
                detail="챗봇 서비스를 사용할 수 없습니다. API 키가 설정되지 않았습니다."
            )
        try:
            session_id = chat_session_manager.get_or_create_session(chat_message.session_id)
            history = chat_session_manager.get_session_history(session_id)

            # If session is new, add system prompt
            if not history:
                chat_session_manager.add_message_to_session(session_id, 'user', get_system_prompt())
                history = chat_session_manager.get_session_history(session_id)

            # Build prompt for discovering additional resources
            one_more_string = (
                "다음은 이용자가 다양한 관점이나 창의적 지적 탐험을 할 수 있기 위해 주제명 표목 네트워크에서 찾은 주제 자원 후보이다.\n"
                "이를 활용하여 이용자가 더 깊이 탐구할 수 있도록 돕는 추가 정보를 제공하라.\n"
                "단, 이용자가 이미 알고 있는 정보는 반복하지 말고, 새로운 관점이나 관련된 주제를 중심으로 안내하라.\n"
                "'좋은 질문입니다'같은 인삿말, 추임새 등 필요없는 내용은 말하지 않아도 됨.\n"
                "'subject_candidates_path'는 원래 주제와 새로운 주제 후보의 연결 경로들이다.\n"
                "이 중 필요한 경로 후보를 선정하여 주제간 연결을 설명하라. 이때 가능하다면 텍스트 다이어그램(graph td) 등을 활용해도 좋다.\n"
            )
            # Find one more resource for the user
            one_more_resource = await add_one_more_resource(history=history, resource_id=chat_message.content.strip())
            one_more_content = f"{one_more_string}\n{one_more_resource}\n"
            one_more_response_text = await self._generate_response(one_more_content, history)
            chat_session_manager.add_message_to_session(session_id, 'user', one_more_content)
            chat_session_manager.add_message_to_session(session_id, 'assistant', one_more_response_text)
            
            return ChatResponse(response=one_more_response_text, session_id=session_id)

        except Exception as e:
            logger.error(f"Error in chat_with_one_more_thing: {e}")
            raise HTTPException(status_code=500, detail="추가 정보 제공 중 오류가 발생했습니다.")

    async def _generate_response(self, message: str, history: List[Dict]) -> str:
        """
        Generate a response using Gemini API.
        Uses chat history and system prompt if available.
        """
        try:
            # Format chat history for Gemini API
            chat_history = format_gemini_chat_history(history)
            # Start chat and send message using Gemini model
            chat = self.model.start_chat(history=chat_history)
            response = await asyncio.to_thread(chat.send_message, message)
            return response.text

        except Exception as e:
            logger.error(f"Error generating Gemini response: {e}")
            raise e

    def get_status(self) -> Dict[str, str]:
        """
        Get chatbot service status.
        Returns whether the service is active or inactive.
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
        Returns session ID, messages, and message count.
        """
        history = chat_session_manager.get_session_history(session_id)
        # Filter messages to only include user and assistant roles
        return {
            "session_id": session_id,
            "messages": [msg for msg in history if msg['role'] in ['user', 'assistant']],
            "message_count": len(history)
        }

    def clear_session(self, session_id: str) -> bool:
        """
        Clear a specific chat session.
        Removes all messages from the session.
        """
        return chat_session_manager.delete_session(session_id)

    def create_new_session(self) -> str:
        """
        Create a new chat session.
        Returns the new session ID.
        """
        return chat_session_manager.get_or_create_session()

    def get_session_stats(self) -> Dict:
        """
        Get statistics about all chat sessions.
        Returns session stats from the manager.
        """
        return chat_session_manager.get_session_stats()

# Global chat service instance
chat_service = ChatService()

@lru_cache()
def get_chat_service() -> ChatService:
    """
    FastAPI dependency for providing the chat service instance.
    Returns the global chat_service instance.
    """
    return chat_service
