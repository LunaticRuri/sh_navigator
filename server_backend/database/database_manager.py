from typing import Optional
from contextlib import asynccontextmanager
from database.database_pool import AsyncConnectionPool
from core.config import DATABASE_PATH, DB_POOL_MAX_CONNECTIONS, DB_POOL_MIN_CONNECTIONS
import os
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Simplified database manager for single database with connection pooling.
    Optimized for FastAPI concurrent requests.
    """
    
    def __init__(self):
        self._pool: Optional[AsyncConnectionPool] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize database connection pool."""
        if self._initialized:
            return

        if not os.path.exists(DATABASE_PATH):
            raise FileNotFoundError(f"Database not found: {DATABASE_PATH}")

        try:
            # 단일 데이터베이스 풀 초기화
            self._pool = AsyncConnectionPool(
                database_path=DATABASE_PATH,
                max_connections=DB_POOL_MAX_CONNECTIONS,
                min_connections=DB_POOL_MIN_CONNECTIONS
            )
            await self._pool.initialize_pool()
            
            self._initialized = True
            logger.info(f"DatabaseManager initialized with single database: {DATABASE_PATH}")
            logger.info(f"Connection pool: min={DB_POOL_MIN_CONNECTIONS}, max={DB_POOL_MAX_CONNECTIONS}")
            
        except Exception as e:
            logger.error(f"Failed to initialize DatabaseManager: {e}")
            raise
    
    @asynccontextmanager
    async def get_connection(self):
        """Get database connection from pool."""
        if not self._initialized:
            await self.initialize()
            
        if not self._pool:
            raise RuntimeError("Database pool not initialized")
            
        async with self._pool.get_connection() as conn:
            yield conn
    
    async def close_all(self):
        """Close all database connections."""
        if self._pool:
            try:
                await self._pool.close_all_connections()
                logger.info("Database pool closed")
            except Exception as e:
                logger.error(f"Error closing database pool: {e}")
        
        self._pool = None
        self._initialized = False
    
    async def get_pool_status(self) -> dict:
        """Get database pool status."""
        if not self._pool:
            return {"status": "not_initialized"}
        return await self._pool.get_pool_status()


# Global instance
_database_manager_instance: Optional[DatabaseManager] = None


def get_database_manager() -> DatabaseManager:
    """Get global database manager instance."""
    global _database_manager_instance
    if _database_manager_instance is None:
        _database_manager_instance = DatabaseManager()
    return _database_manager_instance


async def initialize_database_manager():
    """Initialize global database manager."""
    manager = get_database_manager()
    await manager.initialize()


async def close_database_manager():
    """Close global database manager."""
    global _database_manager_instance
    if _database_manager_instance:
        await _database_manager_instance.close_all()
        _database_manager_instance = None