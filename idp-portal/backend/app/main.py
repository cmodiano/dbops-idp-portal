"""IDP Portal API - Main application entry point."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import create_pool, close_pool
from app.core.exceptions import IdpError
from app.core.logging import configure_logging
from app.core.middleware import CorrelationIdMiddleware, RequestLoggingMiddleware
from app.api.v1 import admin, audit, auth, catalog, dashboard, executions, health, inventory, tags, users
from app.api import websocket_routes
from app.services.inventory_service import sync_inventory

import structlog

logger = structlog.get_logger()

# Global task handle for inventory sync (Story 4.2, Task 1.3)
_inventory_sync_task: asyncio.Task | None = None


async def _inventory_sync_loop() -> None:
    """Background task for periodic inventory synchronization (Story 4.2, Task 1.3)."""
    interval_hours = getattr(settings, "inventory_sync_interval_hours", 1)
    interval_seconds = interval_hours * 3600

    # Initial sync on startup
    api_url = getattr(settings, "inventory_api_url", None)
    if api_url:
        logger.info("inventory_sync_startup")
        try:
            await sync_inventory()
        except Exception as e:
            logger.warning("inventory_sync_startup_failed", error=str(e))

    # Periodic sync loop
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            api_url = getattr(settings, "inventory_api_url", None)
            if api_url:
                await sync_inventory()
        except asyncio.CancelledError:
            logger.info("inventory_sync_loop_cancelled")
            break
        except Exception as e:
            logger.warning("inventory_sync_loop_error", error=str(e))
            # Continue loop even on error


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _inventory_sync_task

    configure_logging()
    try:
        create_pool()
        logger.info("oracle_pool_started")
    except Exception as exc:
        logger.warning("oracle_pool_failed", error=str(exc))
        raise  # Fail startup so pool is never None; user sees real error (e.g. Oracle unreachable)

    # Start inventory sync background task (Story 4.2, Task 1.3)
    api_url = getattr(settings, "inventory_api_url", None)
    if api_url:
        _inventory_sync_task = asyncio.create_task(_inventory_sync_loop())
        logger.info("inventory_sync_task_started")

    # Validate Vault connection at startup if configured (Story 4.2bis, HIGH-4 fix)
    vault_addr = getattr(settings, "vault_addr", None)
    if vault_addr:
        try:
            from app.api.services import get_vault_service
            vault_service = get_vault_service()
            logger.info("vault_connection_validated", vault_addr=vault_addr)
        except Exception as exc:
            logger.warning("vault_connection_failed_at_startup", vault_addr=vault_addr, error=str(exc))

    yield

    # Cleanup: cancel inventory sync task
    if _inventory_sync_task:
        _inventory_sync_task.cancel()
        try:
            await _inventory_sync_task
        except asyncio.CancelledError:
            pass
        logger.info("inventory_sync_task_stopped")

    await close_pool()
    logger.info("oracle_pool_closed")


app = FastAPI(
    title="IDP Portal API",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware (order matters: last added = outermost, first to receive request)
# Execution order: CORS → CorrelationId → RequestLogging → handler
app.add_middleware(RequestLoggingMiddleware)  # Innermost: logs with correlation_id already bound
app.add_middleware(CorrelationIdMiddleware)   # Middle: binds correlation_id
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


# Handler for FastAPI validation errors (422)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle FastAPI request/response validation errors (422)."""
    logger.error(
        "fastapi_validation_error",
        path=request.url.path,
        method=request.method,
        errors=exc.errors(),
        exc_info=True,
    )
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Erreur de validation de la requête ou de la réponse",
                "details": {"validation_errors": exc.errors()},
            }
        },
    )


# Mount API v1 routers
app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(tags.router, prefix="/api/v1", tags=["tags"])
app.include_router(admin.router, prefix="/api/v1", tags=["admin"])
app.include_router(catalog.router, prefix="/api/v1", tags=["catalog"])
app.include_router(users.router, prefix="/api/v1", tags=["users"])
app.include_router(executions.router, prefix="/api/v1", tags=["executions"])
app.include_router(inventory.router, prefix="/api/v1", tags=["inventory"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["dashboard"])
app.include_router(audit.router, prefix="/api/v1", tags=["audit"])
app.include_router(websocket_routes.router, prefix="/ws", tags=["websocket"])

# Mount static files for uploaded icons (Story 4.9, Task 3.3; LOW-8, LOW-9 fixes)
static_path = settings.get_static_path()
static_path.mkdir(parents=True, exist_ok=True)

# Verify static directory is writable (Story 4.9, LOW-8 fix)
try:
    test_file = static_path / ".write_test"
    test_file.touch()
    test_file.unlink()
    logger.info("static_files_mounted", path=str(static_path), writable=True)
except (OSError, PermissionError) as e:
    logger.error("static_files_not_writable", path=str(static_path), error=str(e))
    # Continue startup but log critical warning
    logger.warning("icon_upload_will_fail", reason="static directory not writable")

app.mount("/static", StaticFiles(directory=static_path), name="static")
