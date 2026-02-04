"""
ProfileService for business logic related to profiles and permissions.
Handles complex operations like cumulative permissions across multiple profiles and AD resolution.
"""

import logging
from django.db import transaction
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from profiles.models import Profile, ProfileActionPermission, ProfileTargetPermission
from core.services import AuditService

logger = logging.getLogger(__name__)


class ProfileService:
    """
    Service for profile business logic.
    Handles complex operations like cumulative permissions and AD group resolution.
    """
    
    @transaction.atomic
    def create_profile(self, profile_data, user=None):
        """
        Create a new profile with validation.
        
        Args:
            profile_data: Dict with profile fields (name, description, ad_group, is_admin, is_auditor)
            user: Optional user instance for audit
        
        Returns:
            Profile instance
        
        Raises:
            IntegrityError: If profile name already exists
        """
        try:
            profile = Profile.objects.create(
                name=profile_data['name'],
                description=profile_data.get('description'),
                ad_group=profile_data['ad_group'],
                is_admin=1 if profile_data.get('is_admin', False) else 0,
                is_auditor=1 if profile_data.get('is_auditor', False) else 0,
            )
            
            # Audit if user provided
            if user:
                AuditService.create_entry(
                    user_id=str(user.id),
                    action_type='ACTION_CREATED',  # Note: Should be PROFILE_CREATED if exists
                    entity_type='permission',
                    entity_id=profile.id,
                    details={'name': profile.name}
                )
            
            return profile
        except IntegrityError:
            raise ValueError(f"Un profil avec le nom '{profile_data['name']}' existe déjà")
    
    def list_all(self):
        """
        List all profiles with permission count.
        
        Returns:
            QuerySet of profiles with permissions_count annotation
        """
        return Profile.objects.list_with_permissions_count()
    
    def get_by_id(self, profile_id: int):
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
    
    @transaction.atomic
    def update_profile(self, profile_id: int, profile_update_data, user=None):
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
        
        try:
            profile.save()
        except IntegrityError:
            raise ValueError(f"Un profil avec le nom '{profile_update_data.get('name', profile.name)}' existe déjà")
        
        # Audit if user provided
        if user:
            AuditService.create_entry(
                user_id=str(user.id),
                action_type='ACTION_UPDATED',  # Note: Should be PROFILE_UPDATED if exists
                entity_type='permission',
                entity_id=profile.id,
                details={'name': profile.name}
            )
        
        return profile
    
    @transaction.atomic
    def delete_profile(self, profile_id: int):
        """
        Delete profile with cascade deletion of permissions.
        
        Args:
            profile_id: ID of the profile
        
        Returns:
            True if deleted, False if not found
        """
        try:
            profile = Profile.objects.get(id=profile_id)
            # Permissions will be deleted automatically via CASCADE
            profile.delete()
            return True
        except Profile.DoesNotExist:
            return False
    
    @transaction.atomic
    def set_action_permissions(self, profile_id: int, permission_data, user=None):
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
    
    def get_action_permissions(self, profile_id: int):
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
    
    def delete_action_permissions(self, profile_id: int):
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
    def set_target_permissions(self, profile_id: int, permission_data, user=None):
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
        perm.save()
        
        return perm
    
    def get_target_permissions(self, profile_id: int):
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
    
    def delete_target_permissions(self, profile_id: int):
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
    
    def get_cumulative_permissions(self, user_id: int, ad_groups: list[str]):
        """
        Get cumulative permissions for a user across all their profiles.
        Resolves profiles by AD groups and aggregates permissions.
        
        Args:
            user_id: ID of the user
            ad_groups: List of AD groups the user belongs to
        
        Returns:
            Dict with aggregated action and target permissions
        """
        # Find profiles matching user's AD groups with select_related to avoid N+1 queries
        # Note: OneToOneField relations use select_related, not prefetch_related
        profiles = Profile.objects.find_by_ad_groups(ad_groups).select_related(
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
        
        return {
            'action_permissions': action_permissions,
            'target_permissions': target_permissions,
        }
