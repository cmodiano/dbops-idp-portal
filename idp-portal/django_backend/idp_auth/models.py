from __future__ import annotations

import hashlib
import secrets

from django.db import models
from django.utils import timezone


class UserManager(models.Manager["User"]):
    """
    Custom manager for User model.
    Provides query methods for common user queries.
    """
    
    def create_or_update(self, username: str, display_name: str | None = None,
                        profile: str | None = None, saml_subject: str | None = None,
                        email: str | None = None) -> User:
        """
        Create or update a user (UPSERT on username).

        Args:
            username: Username (unique identifier)
            display_name: Optional display name
            profile: Optional profile name
            saml_subject: Optional SAML subject
            email: Optional email address

        Returns:
            User instance
        """
        user, created = self.update_or_create(
            username=username,
            defaults={
                'display_name': display_name,
                'profile': profile or '',
                'saml_subject': saml_subject,
                'email': email,
            }
        )
        return user
    
    def find_by_username(self, username: str) -> User | None:
        """
        Find user by username.
        
        Args:
            username: Username to search for
        
        Returns:
            User instance or None
        """
        try:
            return self.get(username=username)
        except self.model.DoesNotExist:
            return None


class User(models.Model):
    """
    User model mapping to Oracle USERS table (V001).
    Custom user model (not django.contrib.auth.User).
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    username = models.CharField(max_length=255, unique=True, db_column='USERNAME')
    display_name = models.CharField(max_length=255, null=True, blank=True, db_column='DISPLAY_NAME')
    profile = models.CharField(max_length=50, db_column='PROFILE')
    saml_subject = models.CharField(max_length=512, null=True, blank=True, db_column='SAML_SUBJECT')
    email = models.EmailField(max_length=254, null=True, blank=True, db_column='EMAIL')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')

    # Story 30.12 (AC5): Class attribute (not a property/method) for Django compatibility.
    # Django's auth middleware checks request.user.is_authenticated. Since this is a custom
    # User model (not django.contrib.auth.User), we set it as a class attribute:
    # - All User instances are always authenticated (SAML 2.0 guarantees identity).
    # - AnonymousUser (Django built-in) has is_authenticated = False automatically.
    # - No soft-delete exists on User; deactivation is handled at AD/SAML level.
    # If soft-delete is added later, convert to @property checking is_deleted.
    is_authenticated = True

    # Custom manager
    objects = UserManager()

    class Meta:
        db_table = 'USERS'
        ordering = ['username']

    def __str__(self) -> str:
        return self.username


class APIKeyScope(models.TextChoices):
    EXECUTIONS = 'executions', 'Executions'
    CATALOG = 'catalog', 'Catalog'
    FULL = 'full', 'Full'


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()


def _generate_raw_key() -> str:
    return secrets.token_urlsafe(32)


class APIKeyManager(models.Manager['APIKey']):

    def create_key(self, user: 'User', name: str, scope: str | None = None) -> tuple['APIKey', str]:
        if scope is not None and scope not in APIKeyScope.values:
            raise ValueError(f"Invalid scope '{scope}'. Valid scopes: {list(APIKeyScope.values)}")
        raw_key = _generate_raw_key()
        key_hash = _hash_key(raw_key)
        instance = self.create(
            user=user,
            name=name,
            key_hash=key_hash,
            scope=scope,
        )
        return instance, raw_key

    def verify_key(self, raw_key: str) -> 'APIKey | None':
        key_hash = _hash_key(raw_key)
        try:
            instance = self.select_related('user').get(key_hash=key_hash, is_active=True)
        except self.model.DoesNotExist:
            return None
        if instance.expires_at is not None:
            now = timezone.now()
            if instance.expires_at < now:
                return None
        return instance


class APIKey(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='ID')
    user = models.ForeignKey(
        'idp_auth.User',
        on_delete=models.CASCADE,
        db_column='USER_ID',
        related_name='api_keys',
    )
    key_hash = models.CharField(max_length=64, unique=True, db_column='KEY_HASH')
    name = models.CharField(max_length=255, blank=True, default='', db_column='NAME')
    scope = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=APIKeyScope.choices,
        db_column='SCOPE',
    )
    expires_at = models.DateTimeField(null=True, blank=True, db_column='EXPIRES_AT')
    is_active = models.BooleanField(default=True, db_column='IS_ACTIVE')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')

    objects = APIKeyManager()

    class Meta:
        db_table = 'API_KEYS'
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'APIKey({self.name}, user={self.user_id})'
