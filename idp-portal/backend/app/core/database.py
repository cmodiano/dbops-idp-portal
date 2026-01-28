"""Oracle database pool management using python-oracledb (Thin mode).

AC #7: Configures oracledb.create_pool() for async connection pooling.
The pool is created synchronously but returns an AsyncConnectionPool
that can be used with async/await for acquiring connections.
"""

import oracledb
from contextlib import asynccontextmanager
from typing import AsyncIterator

from app.core.config import settings

pool: oracledb.AsyncConnectionPool | None = None


def create_pool() -> None:
    """Create Oracle connection pool (AC #7).
    
    Creates a connection pool synchronously. The returned pool
    supports async operations via pool.acquire() in async context.
    
    Pool configuration:
    - min: Minimum connections (default 2)
    - max: Maximum connections (default 10)
    - dsn: Oracle database connection string
    """
    global pool
    # Note: create_pool() is synchronous but returns AsyncConnectionPool
    # for use with async/await. There is no create_pool_async() function.
    pool = oracledb.create_pool(
        user=settings.oracle_user,
        password=settings.oracle_password,
        dsn=settings.oracle_dsn,
        min=settings.oracle_min_pool,
        max=settings.oracle_max_pool,
    )


async def close_pool() -> None:
    """Close Oracle connection pool and cleanup resources."""
    global pool
    if pool:
        await pool.close()
        pool = None


def get_pool() -> oracledb.AsyncConnectionPool:
    """Get the current Oracle connection pool.
    
    Raises:
        RuntimeError: If pool has not been initialized via create_pool()
    
    Returns:
        The active AsyncConnectionPool instance
    """
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


@asynccontextmanager
async def get_connection() -> AsyncIterator[oracledb.AsyncConnection]:
    """Get an async connection from the pool (context manager).
    
    Usage:
        async with get_connection() as conn:
            cursor = await conn.cursor()
            await cursor.execute("SELECT 1 FROM DUAL")
    
    Yields:
        An async Oracle connection from the pool
    """
    p = get_pool()
    async with p.acquire() as conn:
        yield conn
