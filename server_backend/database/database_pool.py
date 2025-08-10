# -*- coding: utf-8 -*-
"""
Database connection pool module for SH Navigator API

This module provides an asynchronous connection pool implementation
for managing SQLite database connections efficiently.
"""

import asyncio
import aiosqlite
import logging
from contextlib import asynccontextmanager
from typing import Optional
from core.config import DB_POOL_INITIAL_CONNECTIONS, DB_POOL_MAX_CONNECTIONS

logger = logging.getLogger(__name__)


class AsyncConnectionPool:
    """
    Asynchronous database connection pool for SQLite databases.
    
    This class manages a pool of database connections to improve performance
    and handle concurrent database operations efficiently.
    """

    def __init__(self, db_path: str):
        """
        Initialize the connection pool.
        
        Args:
            db_path: Path to the SQLite database file
            max_connections: Maximum number of concurrent connections
        """
        self.db_path = db_path
        self.start_connections = DB_POOL_INITIAL_CONNECTIONS
        self.max_connections = DB_POOL_MAX_CONNECTIONS
        self.pool = asyncio.Queue(maxsize=self.max_connections)
        self.current_connections = 0
        self.lock = asyncio.Lock()
        
    async def initialize_pool(self) -> None:
        """Initialize the connection pool with initial connections."""
        initial_connections = min(self.start_connections, self.max_connections)
        
        for _ in range(initial_connections):
            conn = await self._create_connection()
            if conn:
                await self.pool.put(conn)
                async with self.lock:
                    self.current_connections += 1
                    
        logger.info(f"Initialized connection pool for {self.db_path} with {initial_connections} connections")
    
    async def _create_connection(self) -> Optional[aiosqlite.Connection]:
        """
        Create a new database connection with optimized settings.
        
        Returns:
            Database connection or None if creation failed
        """
        try:
            conn = await aiosqlite.connect(self.db_path)
            conn.row_factory = aiosqlite.Row
            
            # Optimize connection settings
            await conn.execute("PRAGMA journal_mode=WAL")  # Enable WAL mode for better concurrency
            await conn.execute("PRAGMA query_only=1")      # Set read-only for safety
            # await conn.execute("PRAGMA cache_size=10000")  # Increase cache size
            # await conn.execute("PRAGMA temp_store=memory") # Use memory for temp storage
            
            return conn
            
        except Exception as e:
            logger.error(f"Failed to create database connection for {self.db_path}: {e}")
            return None
    
    async def _is_connection_valid(self, conn: aiosqlite.Connection) -> bool:
        """
        Check if a database connection is still valid.
        
        Args:
            conn: Database connection to validate
            
        Returns:
            True if connection is valid, False otherwise
        """
        try:
            cursor = await conn.cursor()
            await cursor.execute("SELECT 1")
            await cursor.fetchone()
            await cursor.close()
            return True
            
        except Exception as e:
            logger.warning(f"Connection validation failed: {e}")
            return False
    
    async def _close_connection_safely(self, conn: aiosqlite.Connection) -> None:
        """
        Safely close a database connection and update connection count.
        
        Args:
            conn: Database connection to close
        """
        try:
            await conn.close()
        except Exception as e:
            logger.warning(f"Failed to close connection: {e}")
        finally:
            async with self.lock:
                self.current_connections = max(0, self.current_connections - 1)
    
    @asynccontextmanager
    async def get_connection(self):
        """
        Context manager for acquiring database connections from the pool.
        
        Yields:
            A valid database connection
            
        Raises:
            HTTPException: If unable to acquire a connection
        """
        conn = None
        connection_from_pool = False
        
        try:
            # Try to get connection from pool
            try:
                conn = self.pool.get_nowait()
                connection_from_pool = True
                
                # Validate connection from pool
                if not await self._is_connection_valid(conn):
                    logger.debug("Pool connection invalid, creating new one")
                    await self._close_connection_safely(conn)
                    conn = None
                    connection_from_pool = False
                    
            except asyncio.QueueEmpty:
                pass
            
            # Create new connection if needed
            if not conn:
                async with self.lock:
                    if self.current_connections < self.max_connections:
                        conn = await self._create_connection()
                        if conn:
                            self.current_connections += 1
                    else:
                        # Wait for available connection
                        logger.debug("Max connections reached, waiting for available connection")
                        conn = await asyncio.wait_for(self.pool.get(), timeout=10)
                        connection_from_pool = True
                        
                        # Validate waited connection
                        if not await self._is_connection_valid(conn):
                            logger.debug("Waited connection invalid, creating new one")
                            await self._close_connection_safely(conn)
                            
                            async with self.lock:
                                if self.current_connections < self.max_connections:
                                    conn = await self._create_connection()
                                    if conn:
                                        self.current_connections += 1
                                else:
                                    conn = None
            
            if not conn:
                from fastapi import HTTPException
                raise HTTPException(status_code=500, detail="Failed to acquire database connection")
            
            logger.debug(f"Connection acquired: {id(conn)}, from_pool: {connection_from_pool}")
            yield conn
            
        except Exception as e:
            # Handle connection errors
            if conn:
                logger.error(f"Error using connection: {e}")
                
                is_valid = await self._is_connection_valid(conn)
                if not is_valid:
                    logger.debug("Error occurred, connection invalid, removing")
                    await self._close_connection_safely(conn)
                    conn = None
            
            raise e
            
        finally:
            # Return connection to pool or close it
            if conn:
                try:
                    if await self._is_connection_valid(conn):
                        self.pool.put_nowait(conn)
                        logger.debug(f"Connection returned to pool: {id(conn)}")
                    else:
                        logger.debug("Connection invalid at return, closing")
                        await self._close_connection_safely(conn)
                        
                except asyncio.QueueFull:
                    logger.debug("Pool full, closing connection")
                    await self._close_connection_safely(conn)
                except Exception as e:
                    logger.error(f"Error returning connection: {e}")
                    await self._close_connection_safely(conn)

    async def close_all_connections(self) -> None:
        """Close all connections in the pool. Used during application shutdown."""
        logger.info(f"Closing all connections for {self.db_path}")
        
        # Close all pooled connections
        while not self.pool.empty():
            try:
                conn = self.pool.get_nowait()
                await self._close_connection_safely(conn)
            except asyncio.QueueEmpty:
                break
            except Exception as e:
                logger.error(f"Error closing pooled connection: {e}")
        
        async with self.lock:
            self.current_connections = 0
            
        logger.info(f"All connections closed for {self.db_path}")
    
    async def get_pool_status(self) -> dict:
        """
        Get current pool status for debugging.
        
        Returns:
            Dictionary containing pool status information
        """
        async with self.lock:
            return {
                "current_connections": self.current_connections,
                "max_connections": self.max_connections,
                "pool_size": self.pool.qsize(),
                "pool_available": not self.pool.empty(),
                "db_path": self.db_path
            }
