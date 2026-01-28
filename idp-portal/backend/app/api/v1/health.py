"""Health check endpoint."""

from fastapi import APIRouter
from app.core.database import get_pool

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Return service health status including Oracle connectivity."""
    oracle_ok = False
    try:
        p = get_pool()
        async with p.acquire() as conn:
            cursor = await conn.execute("SELECT 1 FROM DUAL")
            await cursor.close()
        oracle_ok = True
    except Exception:
        pass

    status = "healthy" if oracle_ok else "degraded"
    status_code = 200 if oracle_ok else 503

    from starlette.responses import JSONResponse

    return JSONResponse(
        status_code=status_code,
        content={
            "data": {
                "status": status,
                "oracle": "connected" if oracle_ok else "disconnected",
            }
        },
    )
