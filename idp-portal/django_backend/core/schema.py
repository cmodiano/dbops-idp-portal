"""
OpenAPI schema extensions for drf-spectacular.
Story 22.20: JWT authentication extension and common schema helpers.
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class JWTAuthenticationExtension(OpenApiAuthenticationExtension):
    """Tell drf-spectacular how to represent our custom JWTAuthentication."""
    target_class = 'idp_auth.authentication.JWTAuthentication'
    name = 'bearerAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
        }
