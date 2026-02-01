"""Oracle database pool management using python-oracledb (Thin mode).

AC #7: Configures oracledb.create_pool_async() for async connection pooling.
The pool and acquire() are async so repositories can use async with get_connection().

CLOB/BLOB columns are fetched as strings/bytes (fetch_lobs=False) so repositories
do not need to handle AsyncLOB/LOB objects when parsing JSON or text.
"""

import oracledb

# Fetch CLOB/BLOB as string/bytes instead of LOB locators (avoids AsyncLOB in row data)
oracledb.defaults.fetch_lobs = False
from contextlib import asynccontextmanager
from typing import AsyncIterator

from app.core.config import settings

pool: oracledb.AsyncConnectionPool | None = None


def create_pool() -> None:
    """Create Oracle async connection pool (AC #7).
    
    Uses create_pool_async() (sync in oracledb 3.x) so pool.acquire() returns an async context manager.
    
    Pool configuration:
    - min: Minimum connections (default 2)
    - max: Maximum connections (default 10)
    - dsn: Oracle database connection string
    """
    global pool
    # create_pool_async() returns AsyncConnectionPool directly (no await in oracledb 3.x)
    pool = oracledb.create_pool_async(
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
