"""
Authentication views package — barrel re-exports.
Story 54.7 (MAINT-BE-2): Split monolithic views.py into domain modules.

All public symbols are re-exported here so that existing imports
``from idp_auth.views import X`` continue to work unchanged.
"""

from idp_auth.views.helpers import _extract_ad_groups
from idp_auth.views.saml import (
    SAMLLoginView,
    SAMLCallbackView,
)
from idp_auth.views.jwt import (
    CurrentUserProfileView,
    RefreshTokenView,
    LogoutView,
)
from idp_auth.views.favorites import (
    UserFavoritesView,
    UserFavoriteItemView,
)
from idp_auth.views.service_login import (
    ServiceLoginView,
)
from idp_auth.views.api_keys import (
    APIKeyTokenView,
    APIKeysView,
    APIKeyDetailView,
)

__all__ = [
    "_extract_ad_groups",
    "SAMLLoginView",
    "SAMLCallbackView",
    "CurrentUserProfileView",
    "RefreshTokenView",
    "LogoutView",
    "UserFavoritesView",
    "UserFavoriteItemView",
    "ServiceLoginView",
    "APIKeyTokenView",
    "APIKeysView",
    "APIKeyDetailView",
]
