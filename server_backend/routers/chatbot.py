# routers/chatbot.py
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Dict, Any, Optional
from schemas.chat import ChatMessage, ChatResponse, ChatbotStatus, SessionResponse
from service.chat_service import get_chat_service

router = APIRouter(prefix="/chatbot", tags=["Chatbot"])

@router.post("/chat", response_model=ChatResponse)
async def chat_with_gemini(
    chat_message: ChatMessage, 
    chat_service = Depends(get_chat_service)
):
    """Gemini AI 챗봇과 대화합니다."""
    return await chat_service.chat(chat_message)

@router.get("/status", response_model=ChatbotStatus)
async def get_chatbot_status(chat_service = Depends(get_chat_service)):
    """챗봇 서비스 상태를 확인합니다."""
    return chat_service.get_status()

@router.get("/session/{session_id}", response_model=SessionResponse)
async def get_chat_session(session_id: str, chat_service = Depends(get_chat_service)):
    """특정 세션의 대화 기록을 반환합니다."""
    try:
        return chat_service.get_session_info(session_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

@router.delete("/session/{session_id}")
async def clear_chat_session(session_id: str, chat_service = Depends(get_chat_service)):
    """특정 세션의 대화 기록을 삭제합니다."""
    if chat_service.clear_session(session_id):
        return {"message": "세션이 삭제되었습니다."}
    else:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

@router.post("/session/new")
async def create_new_session(chat_service = Depends(get_chat_service)):
    """새로운 채팅 세션을 생성합니다."""
    session_id = chat_service.create_new_session()
    return {"session_id": session_id}