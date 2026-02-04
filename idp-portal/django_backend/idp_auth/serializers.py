"""
Serializers for authentication endpoints.
Matches FastAPI UserProfile and TokenRefreshResponse models.
"""

from rest_framework import serializers


class UserProfileSerializer(serializers.Serializer):
    """
    Serializer for user profile (GET /auth/me response).
    Read-only serializer matching FastAPI UserProfile model.
    """
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(read_only=True)
    display_name = serializers.CharField(read_only=True, allow_null=True)
    profile = serializers.CharField(read_only=True)
    profile_ids = serializers.ListField(
        child=serializers.IntegerField(),
        read_only=True,
        allow_null=True,
        required=False
    )
    cumulative_permissions = serializers.DictField(
        read_only=True,
        allow_null=True,
        required=False
    )
    is_auditor = serializers.BooleanField(read_only=True, default=False)
    navigation_tabs = serializers.ListField(
        child=serializers.CharField(),
        read_only=True,
        required=False
    )
    is_business_profile = serializers.BooleanField(read_only=True, default=False)


class TokenRefreshResponseSerializer(serializers.Serializer):
    """
    Serializer for token refresh response (POST /auth/refresh response).
    Matches FastAPI TokenRefreshResponse model.
    """
    access_token = serializers.CharField(read_only=True)
    token_type = serializers.CharField(read_only=True, default="bearer")
