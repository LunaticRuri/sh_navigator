from typing import Dict, Optional
from contextlib import asynccontextmanager
from database.database_pool import AsyncConnectionPool
from core.config import SUBJECTS_DB_PATH, BOOKS_DB_PATH
import os
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Centralized database manager for handling multiple database connections.
    """
    
    def __init__(self):
        self._pools: Dict[str, AsyncConnectionPool] = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize all database connection pools."""
        if self._initialized:
            return

        if not os.path.exists(BOOKS_DB_PATH):
            raise FileNotFoundError(f"Books database not found: {BOOKS_DB_PATH}")
        if not os.path.exists(SUBJECTS_DB_PATH):
            raise FileNotFoundError(f"Subjects database not found: {SUBJECTS_DB_PATH}")

        try:
            # Initialize subjects database pool
            self._pools['subjects'] = AsyncConnectionPool(SUBJECTS_DB_PATH)
            await self._pools['subjects'].initialize_pool()
            
            self._pools['books'] = AsyncConnectionPool(BOOKS_DB_PATH)
            await self._pools['books'].initialize_pool()
            
            self._initialized = True
            logger.info("DatabaseManager initialized with pools: %s", list(self._pools.keys()))
            
        except Exception as e:
            logger.error(f"Failed to initialize DatabaseManager: {e}")
            raise
    
    @asynccontextmanager
    async def get_subjects_connection(self):
        """Get connection to subjects database."""
        if not self._initialized:
            await self.initialize()
            
        async with self._pools['subjects'].get_connection() as conn:
            yield conn
    
    @asynccontextmanager
    async def get_books_connection(self):
        """Get connection to books database."""
        if not self._initialized:
            await self.initialize()
            
        if 'books' not in self._pools:
            raise RuntimeError("Books database not configured")
            
        async with self._pools['books'].get_connection() as conn:
            yield conn
    
    async def close_all(self):
        """Close all database connections."""
        for pool_name, pool in self._pools.items():
            try:
                await pool.close_all_connections()
                logger.info(f"Closed {pool_name} database pool")
            except Exception as e:
                logger.error(f"Error closing {pool_name} pool: {e}")
        
        self._pools.clear()
        self._initialized = False
    
    async def get_all_pool_status(self) -> Dict[str, dict]:
        """Get status of all database pools."""
        status = {}
        for pool_name, pool in self._pools.items():
            status[pool_name] = await pool.get_pool_status()
        return status


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