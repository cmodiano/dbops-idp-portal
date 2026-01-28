"""Admin routes: protected by DBOPS profile requirement."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import require_profile
from app.models.auth import UserProfile

router = APIRouter()


@router.get("/admin/status")
async def admin_status(user: UserProfile = Depends(require_profile("dbops"))):
    """Admin status endpoint. Requires DBOPS profile."""
    return {"data": {"status": "ok"}}
