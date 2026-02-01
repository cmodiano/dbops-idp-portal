"""Authentication routes: SAML 2.0 login/callback, JWT refresh, user profile, logout."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from app.core.config import settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.saml import create_saml_auth
from app.core.security import create_access_token, create_refresh_token, verify_token
from app.api.deps import get_current_user
from app.models.auth import UserProfile
from app.repositories import user_repository
from app.services import rbac_service

logger = structlog.get_logger()

router = APIRouter()

# Default profile mapping for SAML attributes
_DEFAULT_PROFILE = "dba_applicatif"
_ALLOWED_PROFILES = {"dba_applicatif", "dba_infrastructure", "dbops"}


@router.get("/auth/saml/login")
async def saml_login(request: Request):
    """Initiate SP-initiated SAML flow. Redirects browser to IdP SSO URL."""
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

    # Extract attributes from assertion
    attributes = auth.get_attributes()
    name_id = auth.get_nameid()

    username = attributes.get("username", [name_id])[0] if attributes.get("username") else name_id
    display_name = attributes.get("displayName", [None])[0] if attributes.get("displayName") else None
    raw_profile = attributes.get("profile", [_DEFAULT_PROFILE])[0] if attributes.get("profile") else _DEFAULT_PROFILE
    saml_subject = name_id

    # Validate profile against allowed values — fall back to default if unknown
    profile = raw_profile.lower() if raw_profile else _DEFAULT_PROFILE
    if profile not in _ALLOWED_PROFILES:
        logger.warning("saml_unknown_profile", raw_profile=raw_profile, fallback=_DEFAULT_PROFILE)
        profile = _DEFAULT_PROFILE

    logger.info("saml_callback_success", username=username, profile=profile)

    # Create or update user in DB
    user = await user_repository.create_or_update(
        username=username,
        display_name=display_name,
        profile=profile,
        saml_subject=saml_subject,
    )

    # Generate JWT tokens
    token_data = {"sub": str(user["id"]), "username": user["username"], "profile": user["profile"]}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    # Response strategy:
    # - redirect: portal flow (browser redirected to FRONTEND_BASE_URL)
    # - json: API-only flow (tokens returned as JSON)
    if settings.saml_callback_mode == "json":
        response: Response = JSONResponse(
            status_code=200,
            content={
                "data": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "bearer",
                }
            },
        )
    else:
        redirect_url = f"{settings.frontend_base_url}/auth/callback#access_token={access_token}"
        response = RedirectResponse(url=redirect_url, status_code=302)

    # Set refresh token as httpOnly cookie (used by /auth/refresh)
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

    # Generate new access token
    token_data = {"sub": payload.sub, "username": payload.username, "profile": payload.profile}
    new_access_token = create_access_token(token_data)

    return {"data": {"access_token": new_access_token, "token_type": "bearer"}}


@router.get("/auth/me")
async def get_current_user_profile(user: UserProfile = Depends(get_current_user)):
    """Return the authenticated user's profile with navigation permissions."""
    data = user.model_dump()
    data["navigation_tabs"] = rbac_service.get_user_navigation_permissions(user.profile)
    return {"data": data}


@router.post("/auth/logout")
async def logout(response: Response):
    """Clear the refresh token cookie."""
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")
    return {"data": {"message": "Deconnexion reussie"}}
