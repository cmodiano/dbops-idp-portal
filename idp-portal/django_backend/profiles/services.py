"""
ProfileService for business logic related to profiles and permissions.
Handles complex operations like cumulative permissions across multiple profiles and AD resolution.
Story M.8 - Task 9: Structured logging with structlog.
"""

from __future__ import annotations

from typing import Any

import structlog

from django.db import transaction
from django.db import IntegrityError
from django.db.models import QuerySet
from profiles.models import Profile, ProfileActionPermission, ProfileTargetPermission
from core.services import AuditService
from core.models import AuditActionType, AuditEntityType
from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)

_AUDITED_PROFILE_FIELDS = (
    'name', 'description', 'ad_group',
    'is_admin', 'is_auditor', 'is_approver',
)


class ProfileService:
    """
    Service for profile business logic.
    Handles complex operations like cumulative permissions and AD group resolution.
    """
    
    @transaction.atomic
    def create_profile(self, profile_data: dict[str, Any], user: Any = None) -> Profile:
        """
        Create a new profile with validation.

        Args:
            profile_data: Dict with profile fields (name, description, ad_group, is_admin, is_auditor, is_approver)
            user: Optional user instance for audit

        Returns:
            Profile instance

        Raises:
            IntegrityError: If profile name already exists
        """
        correlation_id = get_correlation_id()

        try:
            profile = Profile.objects.create(
                name=profile_data['name'],
                description=profile_data.get('description'),
                ad_group=profile_data['ad_group'],
                is_admin=1 if profile_data.get('is_admin', False) else 0,
                is_auditor=1 if profile_data.get('is_auditor', False) else 0,
                is_approver=1 if profile_data.get('is_approver', False) else 0,
            )

            # Log profile creation
            logger.info(
                "profile_created",
                profile_id=profile.id,
                profile_name=profile.name,
                ad_group=profile.ad_group,
                is_admin=bool(profile.is_admin),
                user_id=user.id if user else None,
                correlation_id=correlation_id
            )

            # Audit if user provided
            if user:
                AuditService.create_entry(
                    user_id=str(user.id),
                    action_type=AuditActionType.PROFILE_CREATED,
                    entity_type=AuditEntityType.PROFILE,
                    entity_id=profile.id,
                    details={'name': profile.name},
                    correlation_id=correlation_id
                )

            return profile
        except IntegrityError:
            logger.warning(
                "profile_creation_failed_duplicate",
                profile_name=profile_data['name'],
                correlation_id=correlation_id
            )
            raise ValueError(f"Un profil avec le nom '{profile_data['name']}' existe déjà")
    
    def list_all(self) -> QuerySet[Profile]:
        """
        List all profiles with permission count.

        Returns:
            QuerySet of profiles with permission_count annotation
        """
        return Profile.objects.list_with_permissions_count()

    def list_approvers(self) -> QuerySet[Profile]:
        """Liste uniquement les profils éligibles approbateurs (is_approver=1).

        Story 58.4 AC4.
        """
        return Profile.objects.filter(is_approver=1).order_by('name')

    def get_by_id(self, profile_id: int) -> Profile | None:
        """
        Get profile by ID with prefetched permissions.

        Args:
            profile_id: ID of the profile

        Returns:
            Profile instance or None
        """
        try:
            return Profile.objects.prefetch_related(
                'profileactionpermission',
                'profiletargetpermission'
            ).get(id=profile_id)
        except Profile.DoesNotExist:
            return None

    def get_by_name(self, name: str) -> Profile | None:
        """
        Get profile by name (for YAML import upsert).
        
        Args:
            name: Name of the profile
        
        Returns:
            Profile instance or None
        """
        try:
            return Profile.objects.get(name=name.strip())
        except Profile.DoesNotExist:
            return None
    
    @transaction.atomic
    def update_profile(self, profile_id: int, profile_update_data: dict[str, Any], user: Any = None) -> Profile | None:
        """
        Update profile with validation.
        
        Args:
            profile_id: ID of the profile
            profile_update_data: Dict with fields to update
            user: Optional user instance for audit
        
        Returns:
            Updated Profile instance or None if not found
        
        Raises:
            IntegrityError: If new name already exists
        """
        try:
            profile = Profile.objects.get(id=profile_id)
        except Profile.DoesNotExist:
            return None

        # Capturer les anciennes valeurs AVANT modification
        old_values = {}
        for field in _AUDITED_PROFILE_FIELDS:
            if field in profile_update_data:
                old_values[field] = getattr(profile, field)

        # Update fields
        if 'name' in profile_update_data:
            profile.name = profile_update_data['name']
        if 'description' in profile_update_data:
            profile.description = profile_update_data.get('description')
        if 'ad_group' in profile_update_data:
            profile.ad_group = profile_update_data['ad_group']
        if 'is_admin' in profile_update_data:
            profile.is_admin = 1 if profile_update_data['is_admin'] else 0
        if 'is_auditor' in profile_update_data:
            profile.is_auditor = 1 if profile_update_data['is_auditor'] else 0
        if 'is_approver' in profile_update_data:
            profile.is_approver = 1 if profile_update_data['is_approver'] else 0

        try:
            profile.save()
        except IntegrityError:
            raise ValueError(f"Un profil avec le nom '{profile_update_data.get('name', profile.name)}' existe déjà")

        # Construire changes pour l'audit
        changes = {}
        for field, old_val in old_values.items():
            new_val = getattr(profile, field)
            if old_val != new_val:
                changes[field] = {"old": old_val, "new": new_val}

        # Audit if user provided
        if user:
            AuditService.create_entry(
                user_id=str(user.id),
                action_type=AuditActionType.PROFILE_UPDATED,
                entity_type=AuditEntityType.PROFILE,
                entity_id=profile.id,
                details={'name': profile.name, 'changes': changes}
            )

        return profile
    
    @transaction.atomic
    def delete_profile(self, profile_id: int, user: Any = None) -> bool:
        """
        Delete profile with cascade deletion of permissions.
        
        Args:
            profile_id: ID of the profile
            user: Optional user instance for audit
        
        Returns:
            True if deleted, False if not found
        """
        try:
            profile = Profile.objects.get(id=profile_id)
            profile_name = profile.name  # Save name before deletion for audit
            
            # Permissions will be deleted automatically via CASCADE
            profile.delete()
            
            # Audit if user provided
            if user:
                AuditService.create_entry(
                    user_id=str(user.id),
                    action_type=AuditActionType.PROFILE_DELETED,
                    entity_type=AuditEntityType.PROFILE,
                    entity_id=profile_id,
                    details={'name': profile_name}
                )
            
            return True
        except Profile.DoesNotExist:
            return False
    
    @transaction.atomic
    def set_action_permissions(self, profile_id: int, permission_data: dict[str, Any], user: Any = None) -> ProfileActionPermission | None:
        """
        Set action permissions for a profile (UPSERT).
        
        Args:
            profile_id: ID of the profile
            permission_data: Dict with actions_type, action_ids, tag_patterns, environments
            user: Optional user instance for audit
        
        Returns:
            ProfileActionPermission instance
        """
        try:
            profile = Profile.objects.get(id=profile_id)
        except Profile.DoesNotExist:
            return None
        
        # Map actions_type to permission_type
        type_map = {'list': 'LIST', 'pattern': 'PATTERN', 'all': 'ALL'}
        permission_type = type_map.get(permission_data.get('actions_type', 'all'), 'ALL')
        
        # Create or update permission
        perm, created = ProfileActionPermission.objects.update_or_create(
            profile=profile,
            defaults={
                'permission_type': permission_type,
            }
        )
        
        # Set JSON fields
        if 'action_ids' in permission_data:
            perm.set_action_ids(permission_data['action_ids'])
        if 'tag_patterns' in permission_data:
            perm.set_tag_patterns(permission_data['tag_patterns'])
        if 'environments' in permission_data:
            perm.set_environments(permission_data['environments'])
        perm.save()
        
        return perm
    
    def get_action_permissions(self, profile_id: int) -> ProfileActionPermission | None:
        """
        Get action permissions for a profile.

        Args:
            profile_id: ID of the profile

        Returns:
            ProfileActionPermission instance or None
        """
        try:
            return ProfileActionPermission.objects.get(profile_id=profile_id)
        except ProfileActionPermission.DoesNotExist:
            return None

    def delete_action_permissions(self, profile_id: int) -> bool:
        """
        Delete action permissions for a profile.
        
        Args:
            profile_id: ID of the profile
        
        Returns:
            True if deleted, False if not found
        """
        try:
            perm = ProfileActionPermission.objects.get(profile_id=profile_id)
            perm.delete()
            return True
        except ProfileActionPermission.DoesNotExist:
            return False
    
    @transaction.atomic
    def set_target_permissions(self, profile_id: int, permission_data: dict[str, Any], user: Any = None) -> ProfileTargetPermission | None:
        """
        Set target permissions for a profile (UPSERT).
        
        Args:
            profile_id: ID of the profile
            permission_data: Dict with targets_type, target_names, target_patterns
            user: Optional user instance for audit
        
        Returns:
            ProfileTargetPermission instance
        """
        try:
            profile = Profile.objects.get(id=profile_id)
        except Profile.DoesNotExist:
            return None
        
        # Map targets_type to permission_type
        type_map = {'list': 'LIST', 'pattern': 'PATTERN', 'all': 'ALL'}
        permission_type = type_map.get(permission_data.get('targets_type', 'all'), 'ALL')
        
        # Create or update permission
        perm, created = ProfileTargetPermission.objects.update_or_create(
            profile=profile,
            defaults={
                'permission_type': permission_type,
            }
        )
        
        # Set JSON fields
        if 'target_names' in permission_data:
            perm.set_target_names(permission_data['target_names'])
        if 'target_patterns' in permission_data:
            perm.set_target_patterns(permission_data['target_patterns'])
        if 'filter_by_attribute' in permission_data:
            perm.set_filter_by_attribute(permission_data['filter_by_attribute'])
        # Story 25.6: Persist exclusion_patterns
        if 'exclusion_patterns' in permission_data:
            perm.set_exclusion_patterns(permission_data['exclusion_patterns'])
        perm.save()

        return perm
    
    def get_target_permissions(self, profile_id: int) -> ProfileTargetPermission | None:
        """
        Get target permissions for a profile.

        Args:
            profile_id: ID of the profile

        Returns:
            ProfileTargetPermission instance or None
        """
        try:
            return ProfileTargetPermission.objects.get(profile_id=profile_id)
        except ProfileTargetPermission.DoesNotExist:
            return None

    def delete_target_permissions(self, profile_id: int) -> bool:
        """
        Delete target permissions for a profile.

        Args:
            profile_id: ID of the profile

        Returns:
            True if deleted, False if not found
        """
        try:
            perm = ProfileTargetPermission.objects.get(profile_id=profile_id)
            perm.delete()
            return True
        except ProfileTargetPermission.DoesNotExist:
            return False

    def get_cumulative_permissions(self, user_id: int, ad_groups: list[str]) -> dict[str, Any]:
        """
        Get cumulative permissions for a user across all their profiles.
        Resolves profiles by AD groups and aggregates permissions.
        
        Args:
            user_id: ID of the user
            ad_groups: List of AD groups the user belongs to
        
        Returns:
            Dict with aggregated action and target permissions
        
        Raises:
            ValueError: If user_id is None or invalid
        """
        # Validate user_id
        if not user_id:
            raise ValueError("user_id is required and cannot be None")
        
        # Find profiles matching user's AD groups
        # Note: OneToOneField reverse relations require prefetch_related, not select_related
        profiles = Profile.objects.find_by_ad_groups(ad_groups).prefetch_related(
            'profileactionpermission', 'profiletargetpermission'
        )
        
        # Aggregate action permissions
        action_permissions = []
        for profile in profiles:
            # Use prefetched permissions instead of .get() to avoid N+1
            perm = getattr(profile, 'profileactionpermission', None)
            if perm:
                action_permissions.append({
                    'actions_type': perm.permission_type.lower(),
                    'action_ids': perm.get_action_ids(),
                    'tag_patterns': perm.get_tag_patterns(),
                    'environments': perm.get_environments(),
                })
            elif getattr(profile, 'is_admin', 0) == 1:
                # Admin profiles (DBOPS, DBA) without explicit ProfileActionPermission
                # get full access (actions=all, environments=all)
                action_permissions.append({
                    'actions_type': 'all',
                    'action_ids': [],
                    'tag_patterns': [],
                    'environments': [],
                })
        
        # Aggregate target permissions
        target_permissions = []
        for profile in profiles:
            # Use prefetched permissions instead of .get() to avoid N+1
            perm = getattr(profile, 'profiletargetpermission', None)
            if perm:
                target_permissions.append({
                    'targets_type': perm.permission_type.lower(),
                    'target_names': perm.get_target_names(),
                    'target_patterns': perm.get_target_patterns(),
                })
            elif getattr(profile, 'is_admin', 0) == 1:
                # Admin profiles (DBOPS, DBA) without explicit ProfileTargetPermission
                # get full access (targets=all)
                target_permissions.append({
                    'targets_type': 'all',
                    'target_names': [],
                    'target_patterns': [],
                })
        
        return {
            'action_permissions': action_permissions,
            'target_permissions': target_permissions,
        }
