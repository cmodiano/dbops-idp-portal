"""FastAPI dependency injection: authentication and authorization."""

from __future__ import annotations

import structlog
from fastapi import Request

from app.core.config import settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import verify_token
from app.models.auth import UserProfile
from app.repositories import user_repository, profile_repository
from app.services import rbac_service

# Fallback when AUTH_DEV_BYPASS=true but dev-user not in DB (e.g. seed not run); user_id=0 breaks FK on favorites/executions
_DEV_USER_FALLBACK = UserProfile(id=0, username="dev-user", display_name="Dev User", profile="dbops")

_DEV_BYPASS_USERNAME = "dev-user"


async def get_current_user(request: Request) -> UserProfile:
    """Extract Bearer token, verify JWT, resolve profiles by ad_groups, return UserProfile (Story 2.12).

    Raises 401 if invalid, 403 NO_PROFILE if user has no matching profile.
    Binds user_id to structlog for request logging (AC #3).
    When AUTH_DEV_BYPASS=true, resolves dev-user from DB so USER_FAVORITES/EXECUTIONS FK succeed; falls back to id=0 if not seeded.
    """
    if settings.auth_dev_bypass:
        user = await user_repository.get_by_username(_DEV_BYPASS_USERNAME)
        if not user:
            try:
                await user_repository.create_or_update(
                    _DEV_BYPASS_USERNAME,
                    display_name="Dev User",
                    profile="DBOPS",
                    saml_subject="dev-user@local",
                )
                user = await user_repository.get_by_username(_DEV_BYPASS_USERNAME)
            except Exception:  # noqa: BLE001
                user = None
        if user:
            ad_groups = [user.get("profile", "dbops").lower()]
            profiles = await profile_repository.find_by_ad_groups(ad_groups)
            profile_ids = [p.id for p in profiles] if profiles else []
            cumulative = (
                await rbac_service.get_cumulative_permissions_cached(user["id"], profile_ids)
                if profile_ids
                else None
            )
            # Story 6.3: check if any profile has is_auditor=True
            is_auditor = any(p.is_auditor for p in profiles) if profiles else False
            user_profile = UserProfile(
                **user,
                profile_ids=profile_ids,
                cumulative_permissions=cumulative,
                is_auditor=is_auditor,
            )
            structlog.contextvars.bind_contextvars(user_id=str(user_profile.id))
            return user_profile
        structlog.contextvars.bind_contextvars(user_id=str(_DEV_USER_FALLBACK.id))
        return _DEV_USER_FALLBACK

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise UnauthorizedError(code="NO_TOKEN", message="Token d'authentification requis")

    token = auth_header.split(" ")[1]
    payload = verify_token(token, expected_type="access")

    user = await user_repository.get_by_username(payload.username)
    if not user:
        raise UnauthorizedError(code="USER_NOT_FOUND", message="Utilisateur introuvable")

    ad_groups = getattr(payload, "ad_groups", None) or []
    if not ad_groups and user.get("profile"):
        ad_groups = [user["profile"]]
    profiles = await profile_repository.find_by_ad_groups(ad_groups)
    if not profiles:
        raise ForbiddenError(
            code="NO_PROFILE",
            message="Aucun profil associé à votre compte.",
        )
    profile_ids = [p.id for p in profiles]
    cumulative = await rbac_service.get_cumulative_permissions_cached(user["id"], profile_ids)
    # Story 6.3: check if any profile has is_auditor=True
    is_auditor = any(p.is_auditor for p in profiles)
    user_profile = UserProfile(
        **user,
        profile_ids=profile_ids,
        cumulative_permissions=cumulative,
        is_auditor=is_auditor,
    )
    structlog.contextvars.bind_contextvars(user_id=str(user_profile.id))
    return user_profile


async def get_optional_user(request: Request) -> UserProfile | None:
    """Same as get_current_user but returns None if no token present. Resolves profiles when token present (2.12)."""
    if settings.auth_dev_bypass:
        return await get_current_user(request)

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ")[1]
    try:
        payload = verify_token(token, expected_type="access")
    except UnauthorizedError:
        return None

    user = await user_repository.get_by_username(payload.username)
    if not user:
        return None

    ad_groups = getattr(payload, "ad_groups", None) or []
    if not ad_groups and user.get("profile"):
        ad_groups = [user["profile"]]
    profiles = await profile_repository.find_by_ad_groups(ad_groups)
    if not profiles:
        # Optional user: no profile = no user context, return None (don't raise like get_current_user)
        return None
    profile_ids = [p.id for p in profiles]
    cumulative = await rbac_service.get_cumulative_permissions_cached(user["id"], profile_ids)
    # Story 6.3: check if any profile has is_auditor=True
    is_auditor = any(p.is_auditor for p in profiles)
    return UserProfile(
        **user,
        profile_ids=profile_ids,
        cumulative_permissions=cumulative,
        is_auditor=is_auditor,
    )
