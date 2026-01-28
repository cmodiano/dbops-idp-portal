"""Oracle database pool management using python-oracledb (Thin mode)."""

import oracledb
from contextlib import asynccontextmanager
from typing import AsyncIterator

from app.core.config import settings

pool: oracledb.AsyncConnectionPool | None = None


async def create_pool() -> None:
    global pool
    pool = oracledb.create_pool_async(
        user=settings.oracle_user,
        password=settings.oracle_password,
        dsn=settings.oracle_dsn,
        min=settings.oracle_min_pool,
        max=settings.oracle_max_pool,
    )


async def close_pool() -> None:
    global pool
    if pool:
        await pool.close()
        pool = None


def get_pool() -> oracledb.AsyncConnectionPool:
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


@asynccontextmanager
async def get_connection() -> AsyncIterator[oracledb.AsyncConnection]:
    p = get_pool()
    async with p.acquire() as conn:
        yield conn
