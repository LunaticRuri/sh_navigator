# -*- coding: utf-8 -*-

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from routers import books, subjects, network, chatbot
from database.database_manager import initialize_database_manager, close_database_manager, get_database_manager
from service.book_service import set_book_service
from service.subject_service import set_subject_service
from service.chat_manager import chat_session_manager
from core.kdc_cache import initialize_kdc_cache


import logging

# Local imports
from core.config import (
    CORS_ORIGINS,
    CORS_ORIGINS
)


# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s [%(levelname)s] %(message)s - %(module)s @ %(funcName)s"
)
logger = logging.getLogger(__name__)


# ===================================================================
# Application Initialization
# ===================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown events."""
    try:
        await initialize_kdc_cache()
        logger.info("KDC cache initialized successfully")

        await initialize_database_manager()

        database_manager = get_database_manager()
        
        set_book_service(database_manager)
        set_subject_service(database_manager)
        
        logger.info("Application started successfully")
        yield
    
    finally:
        await close_database_manager()
        logger.info("Application shutdown complete")

# ===================================================================
# FastAPI Application Setup
# ===================================================================
def create_app() -> FastAPI:
    app = FastAPI(
        title="SH Navigator API",
        description="주제 표목 네트워크 API - 도서 및 주제명 검색, 네트워크 시각화, 챗봇 서비스",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(books.router)
    app.include_router(subjects.router)
    app.include_router(network.router)
    app.include_router(chatbot.router)

    @app.get("/info", tags=["General"])
    async def root():
        """API root endpoint with basic information."""
        return {
            "message": "SH Navigator API",
            "version": "1.0.0",
            "description": "주제 표목 네트워크 API",
            "endpoints": {
                "books": "/books/*",
                "subjects": "/subjects/*",
                "network": "/network/*",
                "chatbot": "/chatbot/*"
            }
        }

    @app.get("/debug/chat-stats", tags=["Debug"])
    async def get_chat_stats():
        """채팅 세션 통계를 확인합니다."""
        return chat_session_manager.get_session_stats()
    
    # Mount static files for frontend
    app.mount("/", StaticFiles(directory="../server_frontend", html=True), name="static")

    return app

# ===================================================================
# Application Entry Point
# ===================================================================

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info",
        access_log=True
    )
