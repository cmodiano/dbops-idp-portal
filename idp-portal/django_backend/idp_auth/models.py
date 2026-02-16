from __future__ import annotations

from django.db import models


class UserManager(models.Manager["User"]):
    """
    Custom manager for User model.
    Provides query methods for common user queries.
    """
    
    def create_or_update(self, username: str, display_name: str | None = None,
                        profile: str | None = None, saml_subject: str | None = None) -> User:
        """
        Create or update a user (UPSERT on username).
        
        Args:
            username: Username (unique identifier)
            display_name: Optional display name
            profile: Optional profile name
            saml_subject: Optional SAML subject
        
        Returns:
            User instance
        """
        user, created = self.update_or_create(
            username=username,
            defaults={
                'display_name': display_name,
                'profile': profile or '',
                'saml_subject': saml_subject,
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
