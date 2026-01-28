"""Catalog routes: public catalog access with RBAC filtering (Story 2.3, AC #3).

Provides read-only access to published actions with RBAC-based invisible filtering.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_optional_user
from app.models.auth import UserProfile
from app.models.catalog import ActionStatus, UserProfile as CatalogUserProfile
from app.repositories import catalog_repository

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _map_auth_profile_to_catalog_profile(auth_profile: str | None) -> CatalogUserProfile | None:
    """Map authentication profile string to CatalogUserProfile enum.

    Args:
        auth_profile: Profile string from JWT token

    Returns:
        CatalogUserProfile enum value or None if not mappable
    """
    if auth_profile is None:
        return None

    profile_mapping = {
        "dba_app": CatalogUserProfile.DBA_APPLICATIF,
        "dba_applicatif": CatalogUserProfile.DBA_APPLICATIF,
        "dba_infra": CatalogUserProfile.DBA_INFRASTRUCTURE,
        "dba_infrastructure": CatalogUserProfile.DBA_INFRASTRUCTURE,
        "client": CatalogUserProfile.CLIENT_BUSINESS,
        "client_business": CatalogUserProfile.CLIENT_BUSINESS,
        "dbops": CatalogUserProfile.DBOPS,
    }
    return profile_mapping.get(auth_profile.lower())


@router.get("/actions")
async def list_catalog_actions(
    user: UserProfile | None = Depends(get_optional_user),
) -> dict:
    """List published actions in the catalog with RBAC filtering (AC #3).

    Returns only published actions.
    - Non-authenticated or unrecognized profile: returns all published actions
      (no RBAC filter). Design: unknown profile is treated as "no filter" for
      backward compatibility; consider restricting in future if needed.
    - DBOPS: all published actions (no filter).
    - Recognized profile (dba_applicatif, dba_infrastructure, client_business):
      actions are filtered invisibly based on RBAC policies.

    Returns:
        { "data": list[ActionResponse] }
    """
    # Map auth profile to catalog profile for RBAC filtering
    catalog_profile = None
    if user is not None:
        catalog_profile = _map_auth_profile_to_catalog_profile(user.profile)

    # DBOPS sees all actions without filtering
    if catalog_profile == CatalogUserProfile.DBOPS:
        catalog_profile = None

    actions = await catalog_repository.list_all(
        status=ActionStatus.PUBLISHED,
        user_profile=catalog_profile,
    )
    return {"data": [a.model_dump(mode="json") for a in actions]}
