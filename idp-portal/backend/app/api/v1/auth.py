"""Authentication routes: SAML 2.0 login/callback, JWT refresh, user profile, logout."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse

from app.core.config import settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.saml import create_saml_auth
from app.core.security import create_access_token, create_refresh_token, verify_token
from app.api.deps import get_current_user
from app.models.auth import UserProfile
from app.repositories import user_repository, profile_repository
from app.services import rbac_service

logger = structlog.get_logger()

router = APIRouter()

# Default profile mapping for SAML attributes
_DEFAULT_PROFILE = "dba_applicatif"
_ALLOWED_PROFILES = {"dba_applicatif", "dba_infrastructure", "dbops"}


@router.get("/auth/saml/login")
async def saml_login(request: Request):
    """Initiate SP-initiated SAML flow. Redirects browser to IdP SSO URL.
    When AUTH_DEV_BYPASS is true, skips IdP and redirects to frontend with dev JWT (dev-only).
    """
    if settings.auth_dev_bypass:
        token_data = {
            "sub": "0",
            "username": "dev-user",
            "profile": "dbops",
            "ad_groups": ["dbops"],
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        redirect_url = f"{settings.cors_origin}/auth/callback#access_token={access_token}"
        response = RedirectResponse(url=redirect_url, status_code=302)
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=settings.app_env != "development",
            samesite="lax",
            max_age=settings.jwt_refresh_token_expire_hours * 3600,
            path="/api/v1/auth",
        )
        logger.info("auth_dev_bypass_login", redirect_origin=settings.cors_origin)
        return response

    auth = create_saml_auth(request)
    sso_url = auth.login()
    logger.info("saml_login_redirect", sso_url=sso_url)
    return RedirectResponse(url=sso_url)


@router.post("/auth/saml/callback")
async def saml_callback(request: Request):
    """Receive SAML assertion from IdP, validate, create/update user, emit JWT tokens."""
    form_data = await request.form()
    post_data = dict(form_data)

    auth = create_saml_auth(request, post_data=post_data)
    auth.process_response()
    errors = auth.get_errors()

    if errors:
        logger.error("saml_callback_error", errors=errors, reason=auth.get_last_error_reason())
        raise ForbiddenError(code="SAML_VALIDATION_FAILED", message=f"SAML validation failed: {errors}")

    if not auth.is_authenticated():
        raise ForbiddenError(code="SAML_NOT_AUTHENTICATED", message="SAML authentication failed")

    # Extract attributes from assertion (Story 2.12: groups for multi-profile)
    attributes = auth.get_attributes()
    name_id = auth.get_nameid()

    username = attributes.get("username", [name_id])[0] if attributes.get("username") else name_id
    display_name = attributes.get("displayName", [None])[0] if attributes.get("displayName") else None
    raw_profile = attributes.get("profile", [_DEFAULT_PROFILE])[0] if attributes.get("profile") else _DEFAULT_PROFILE
    saml_subject = name_id

    # AD groups: "groups", "memberOf" or "ad_groups"; fallback single "profile" for backward compat
    raw_groups = (
        attributes.get("groups")
        or attributes.get("memberOf")
        or attributes.get("ad_groups")
        or []
    )
    if isinstance(raw_groups, str):
        ad_groups = [raw_groups.strip()] if raw_groups.strip() else []
    else:
        ad_groups = [g.strip() for g in raw_groups if g and str(g).strip()]
    if not ad_groups and raw_profile:
        ad_groups = [raw_profile]

    # Resolve profiles by AD groups (AC1, AC3): no profile -> 403 NO_PROFILE
    profiles = await profile_repository.find_by_ad_groups(ad_groups)
    if not profiles:
        logger.warning("saml_callback_no_profile", username=username, ad_groups=ad_groups)
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "NO_PROFILE",
                    "message": "Aucun profil associé à votre compte.",
                }
            },
        )

    # Validate profile against allowed values — fall back to default if unknown
    profile = raw_profile.lower() if raw_profile else _DEFAULT_PROFILE
    if profile not in _ALLOWED_PROFILES:
        logger.warning("saml_unknown_profile", raw_profile=raw_profile, fallback=_DEFAULT_PROFILE)
        profile = _DEFAULT_PROFILE
    # For USERS table: keep first resolved profile name for backward compat
    profile_for_db = profiles[0].name.lower() if profiles else profile

    logger.info("saml_callback_success", username=username, profile=profile, profile_count=len(profiles))

    # Create or update user in DB
    user = await user_repository.create_or_update(
        username=username,
        display_name=display_name,
        profile=profile_for_db,
        saml_subject=saml_subject,
    )

    # Generate JWT tokens (include ad_groups for RBAC cumulative permissions, Story 2.12)
    token_data = {
        "sub": str(user["id"]),
        "username": user["username"],
        "profile": user["profile"],
        "ad_groups": ad_groups,
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Redirect to SPA with access token as URL fragment, set refresh token as httpOnly cookie
    redirect_url = f"{settings.cors_origin}/auth/callback#access_token={access_token}"
    response = RedirectResponse(url=redirect_url, status_code=302)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.app_env != "development",
        samesite="lax",
        max_age=settings.jwt_refresh_token_expire_hours * 3600,
        path="/api/v1/auth",
    )
    return response


@router.post("/auth/refresh")
async def refresh_access_token(request: Request):
    """Exchange refresh token (httpOnly cookie) for a new access token."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise UnauthorizedError(code="NO_REFRESH_TOKEN", message="Refresh token manquant")

    payload = verify_token(refresh_token, expected_type="refresh")

    # Generate new access token (preserve ad_groups for RBAC, Story 2.12)
    token_data = {
        "sub": payload.sub,
        "username": payload.username,
        "profile": payload.profile,
        "ad_groups": getattr(payload, "ad_groups", None) or [],
    }
    new_access_token = create_access_token(token_data)

    return {"data": {"access_token": new_access_token, "token_type": "bearer"}}


@router.get("/auth/me")
async def get_current_user_profile(user: UserProfile = Depends(get_current_user)):
    """Return the authenticated user's profile with navigation permissions.

    Story 7.1: Includes is_business_profile flag for simplified UI.
    """
    data = user.model_dump()
    data["navigation_tabs"] = rbac_service.get_user_navigation_permissions(user.profile)
    # Story 7.1: Flag for business profile (simplified catalog UI)
    data["is_business_profile"] = rbac_service.is_business_profile(user.profile)
    return {"data": data}


@router.post("/auth/logout")
async def logout(response: Response):
    """Clear the refresh token cookie."""
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")
    return {"data": {"message": "Deconnexion reussie"}}
