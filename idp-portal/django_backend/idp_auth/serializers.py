"""
Serializers for authentication endpoints.
"""

from django.utils import timezone
from rest_framework import serializers

from idp_auth.models import APIKey, APIKeyScope


class UserProfileSerializer(serializers.Serializer):
    """
    Serializer for user profile (GET /auth/me response).
    Read-only serializer.
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
    """
    access_token = serializers.CharField(read_only=True)
    token_type = serializers.CharField(read_only=True, default="bearer")


class APIKeyCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    scope = serializers.ChoiceField(
        choices=APIKeyScope.values,
        required=False,
        allow_null=True,
    )


class APIKeyListSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    class Meta:
        model = APIKey
        fields = ['id', 'name', 'scope', 'created_at', 'expires_at', 'is_active', 'status']

    def get_status(self, obj: APIKey) -> str:
        if obj.expires_at and obj.expires_at < timezone.now():
            return 'expired'
        return 'active'
