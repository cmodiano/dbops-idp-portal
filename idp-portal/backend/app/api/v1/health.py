"""Health check endpoint."""

from typing import Any

import structlog
from fastapi import APIRouter, Request
from starlette.responses import JSONResponse

from app.core.database import get_pool
from app.core.middleware import CORRELATION_HEADER

logger = structlog.get_logger()
router = APIRouter()


@router.get("/health")
async def health_check(request: Request) -> JSONResponse:
    """Return service health status including Oracle connectivity.
    
    AC #1: Returns HTTP 200 if Oracle is connected, 503 otherwise.
    AC #2: Correlation ID is propagated in response headers.
    """
    oracle_ok = False
    oracle_error = None
    try:
        p = get_pool()
        async with p.acquire() as conn:
            cursor = await conn.execute("SELECT 1 FROM DUAL")
            await cursor.close()
        oracle_ok = True
    except Exception as exc:
        oracle_error = str(exc)
        logger.warning(
            "oracle_health_check_failed",
            error=oracle_error,
            correlation_id=request.headers.get(CORRELATION_HEADER),
        )

    status = "healthy" if oracle_ok else "degraded"
    status_code = 200 if oracle_ok else 503

    response = JSONResponse(
        status_code=status_code,
        content={
            "data": {
                "status": status,
                "oracle": "connected" if oracle_ok else "disconnected",
            }
        },
    )
    
    # Propagate correlation ID in response (AC #2)
    correlation_id = request.headers.get(CORRELATION_HEADER)
    if correlation_id:
        response.headers[CORRELATION_HEADER] = correlation_id
    
    return response