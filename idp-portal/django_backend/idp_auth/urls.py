"""
URL configuration for authentication endpoints.
Story M.7 - Full SAML and JWT auth endpoints.
"""

from django.urls import path
from idp_auth.views import (
    APIKeyDetailView,
    APIKeysView,
    SAMLLoginView,
    SAMLCallbackView,
    CurrentUserProfileView,
    RefreshTokenView,
    LogoutView,
    UserFavoritesView,
    UserFavoriteItemView,
    APIKeyTokenView,
)

app_name = 'idp_auth'

urlpatterns = [
    # SAML endpoints (Story M.7)
    path('auth/saml/login/', SAMLLoginView.as_view(), name='saml-login'),
    path('auth/saml/callback/', SAMLCallbackView.as_view(), name='saml-callback'),

    # API key token exchange (Story 44.2)
    path('auth/token/', APIKeyTokenView.as_view(), name='api-key-token'),
    path('auth/api-keys/', APIKeysView.as_view(), name='api-keys'),
    path('auth/api-keys/<int:pk>/', APIKeyDetailView.as_view(), name='api-key-detail'),

    # JWT auth endpoints
    path('auth/me/', CurrentUserProfileView.as_view(), name='current-user-profile'),
    path('auth/refresh/', RefreshTokenView.as_view(), name='refresh-token'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),

    # User favorites (used by Catalog frontend)
    path('users/me/favorites/', UserFavoritesView.as_view(), name='user-favorites'),
    path('users/me/favorites/<int:action_id>/', UserFavoriteItemView.as_view(), name='user-favorite-item'),
]
