"""
AuthService for authentication and authorization business logic.
Handles complex operations like SAML subject lookup and profile resolution.
Story M.8 - Task 9: Structured logging with structlog.
"""

import structlog

from django.db import transaction
from idp_auth.models import User
from profiles.models import Profile
from catalog.models import UserFavorite, Action, ActionStatus
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)


class AuthService:
    """
    Service for authentication business logic.
    Handles complex operations like SAML subject lookup and profile resolution.
    """
    
    def create_or_update_user(self, username: str, display_name: str | None = None,
                             profile: str | None = None, saml_subject: str | None = None):
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
        user, created = User.objects.update_or_create(
            username=username,
            defaults={
                'display_name': display_name,
                'profile': profile or '',
                'saml_subject': saml_subject,
            }
        )
        
        # Audit
        AuditService.create_entry(
            user_id=str(user.id),
            action_type=AuditActionType.USER_CREATED if created else AuditActionType.USER_UPDATED,
            entity_type=AuditEntityType.USER,
            entity_id=user.id,
            details={'username': user.username, 'profile': user.profile}
        )
        
        return user
    
    def get_by_username(self, username: str):
        """
        Get user by username.
        
        Args:
            username: Username to search for
        
        Returns:
            User instance or None
        """
        return User.objects.find_by_username(username)
    
    def get_by_id(self, user_id: int):
        """
        Get user by ID.
        
        Args:
            user_id: ID of the user
        
        Returns:
            User instance or None
        """
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None
    
    def find_by_saml_subject(self, saml_subject: str):
        """
        Find user by SAML subject.
        
        Args:
            saml_subject: SAML subject identifier
        
        Returns:
            User instance or None
        """
        try:
            return User.objects.get(saml_subject=saml_subject)
        except User.DoesNotExist:
            return None
    
    def resolve_user_profiles(self, user: User, ad_groups: list[str]):
        """
        Resolve user profiles based on AD groups.
        
        Args:
            user: User instance
            ad_groups: List of AD groups the user belongs to
        
        Returns:
            List of Profile instances matching user's AD groups
        """
        return Profile.objects.find_by_ad_groups(ad_groups)
    
    # UserFavorite CRUD methods
    @transaction.atomic
    def add_favorite(self, user_id: int, action_id: int):
        """
        Add an action to user's favorites (idempotent).
        
        Args:
            user_id: ID of the user
            action_id: ID of the action
        
        Returns:
            UserFavorite instance
        """
        user = self.get_by_id(user_id)
        if not user:
            raise ValueError(f"User with ID {user_id} not found")
        
        action = Action.objects.get(id=action_id)
        if not action:
            raise ValueError(f"Action with ID {action_id} not found")
        
        favorite, created = UserFavorite.objects.get_or_create(
            user=user,
            action=action
        )
        
        # Audit only if newly created
        if created:
            AuditService.create_entry(
                user_id=str(user_id),
                action_type=AuditActionType.FAVORITE_ADDED,
                entity_type=AuditEntityType.ACTION,
                entity_id=action_id,
                details={'action_name': action.name}
            )
        
        return favorite
    
    @transaction.atomic
    def remove_favorite(self, user_id: int, action_id: int):
        """
        Remove an action from user's favorites.
        
        Args:
            user_id: ID of the user
            action_id: ID of the action
        
        Returns:
            True if removed, False if not found
        """
        try:
            favorite = UserFavorite.objects.get(user_id=user_id, action_id=action_id)
            action_name = favorite.action.name
            favorite.delete()
            
            # Audit
            AuditService.create_entry(
                user_id=str(user_id),
                action_type=AuditActionType.FAVORITE_REMOVED,
                entity_type=AuditEntityType.ACTION,
                entity_id=action_id,
                details={'action_name': action_name}
            )
            
            return True
        except UserFavorite.DoesNotExist:
            return False
    
    def list_favorites(self, user_id: int):
        """
        List all favorites for a user, excluding disabled actions.

        Story 18.5: Returns only draft and published actions to maintain UX consistency.
        Catalog UI filters out disabled actions, so badge count must match visible list.

        Args:
            user_id: ID of the user

        Returns:
            QuerySet of UserFavorite instances, ordered by created_at DESC
        """
        return (
            UserFavorite.objects
            .filter(user_id=user_id)
            .select_related('action')
            # Story 18.5: Exclude disabled actions for UX consistency (badge count matches visible actions)
            .exclude(action__status=ActionStatus.DISABLED)
            .order_by('-created_at')
        )
    
    def is_favorite(self, user_id: int, action_id: int):
        """
        Check if an action is in user's favorites (excluding disabled actions).

        Story 18.5: Only active favorites (draft/published) are considered, matching
        list_favorites() behavior for UX consistency.

        Args:
            user_id: ID of the user
            action_id: ID of the action

        Returns:
            True if favorite and action is active, False otherwise
        """
        return (
            UserFavorite.objects
            .filter(user_id=user_id, action_id=action_id)
            .select_related('action')
            .exclude(action__status=ActionStatus.DISABLED)
            .exists()
        )
