"""
SAML utilities for Django - request conversion and auth creation.
Mirrors FastAPI implementation for contract parity.
"""

from django.http import HttpRequest
from onelogin.saml2.auth import OneLogin_Saml2_Auth

from idp_auth.saml_config import get_saml_settings


def prepare_django_request(request: HttpRequest) -> dict:
    """Convert a Django HttpRequest into the dict format expected by python3-saml.

    Args:
        request: Django HttpRequest object

    Returns:
        dict: Request data in python3-saml format
    """
    # Determine if HTTPS based on request or forwarded headers
    is_https = request.is_secure() or request.META.get('HTTP_X_FORWARDED_PROTO', '') == 'https'

    # Get host and port
    http_host = request.get_host()

    # If host includes port, extract it
    if ':' in http_host:
        host_parts = http_host.rsplit(':', 1)
        host = host_parts[0]
        port = host_parts[1]
    else:
        host = http_host
        port = '443' if is_https else '80'

    return {
        "https": "on" if is_https else "off",
        "http_host": host,
        "server_port": port,
        "script_name": request.path,
        "get_data": dict(request.GET),
        "post_data": {},  # POST data must be passed separately
    }


def create_saml_auth(request: HttpRequest, post_data: dict | None = None) -> OneLogin_Saml2_Auth:
    """Create a OneLogin_Saml2_Auth instance from a Django request.

    Args:
        request: Django HttpRequest object
        post_data: Optional POST data dict (from request.POST)

    Returns:
        OneLogin_Saml2_Auth: SAML auth instance ready for login() or process_response()
    """
    req = prepare_django_request(request)
    if post_data:
        req["post_data"] = post_data
    return OneLogin_Saml2_Auth(req, get_saml_settings())
