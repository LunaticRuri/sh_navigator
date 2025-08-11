# -*- coding: utf-8 -*-
"""
Database dependencies for FastAPI.
"""

from database.database_manager import get_database_manager


async def get_db():
    """FastAPI dependency for database connection."""
    db_manager = get_database_manager()
    async with db_manager.get_connection() as conn:
        yield conn
