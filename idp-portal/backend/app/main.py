"""IDP Portal API - Main application entry point."""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import create_pool, close_pool
from app.core.exceptions import IdpError
from app.core.logging import configure_logging
from app.core.middleware import CorrelationIdMiddleware
from app.api.v1 import admin, auth, health

import structlog

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    try:
        await create_pool()
        logger.info("oracle_pool_started")
    except Exception as exc:
        logger.warning("oracle_pool_failed", error=str(exc))
    yield
    await close_pool()
    logger.info("oracle_pool_closed")


app = FastAPI(
    title="IDP Portal API",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(IdpError)
async def idp_error_handler(request: Request, exc: IdpError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                **({"details": exc.details} if exc.details else {}),
            }
        },
    )


# Mount API v1 routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(admin.router, prefix="/api/v1", tags=["admin"])
