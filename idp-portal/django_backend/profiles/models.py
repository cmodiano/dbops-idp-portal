import json
import logging
from django.db import models

logger = logging.getLogger(__name__)


class ProfileManager(models.Manager):
    """
    Custom manager for Profile model.
    Provides query methods for common profile queries.
    """
    
    def find_by_ad_groups(self, ad_groups: list[str]):
        """
        Find profiles whose AD_GROUP is in the given list.
        
        Args:
            ad_groups: List of AD group names
        
        Returns:
            QuerySet of profiles matching any of the AD groups, ordered by name
        """
        if not ad_groups:
            return self.none()
        return self.filter(ad_group__in=ad_groups).order_by('name')
    
    def list_with_permissions_count(self):
        """
        List all profiles with permission count annotation.
        Counts both action and target permissions.
        
        Returns:
            QuerySet with permissions_count annotation
        """
        from django.db.models import Count, Q
        
        return self.annotate(
            permissions_count=Count(
                'profileactionpermission',
                filter=Q(profileactionpermission__isnull=False),
                distinct=True
            ) + Count(
                'profiletargetpermission',
                filter=Q(profiletargetpermission__isnull=False),
                distinct=True
            )
        )


class Profile(models.Model):
    """
    Profile model mapping to Oracle PROFILES table (V010).
    Represents a user profile with AD group mapping.
    """
    id = models.BigAutoField(primary_key=True, db_column='ID')
    name = models.CharField(max_length=255, unique=True, db_column='NAME')
    description = models.CharField(max_length=4000, null=True, blank=True, db_column='DESCRIPTION')
    ad_group = models.CharField(max_length=512, db_column='AD_GROUP')
    is_admin = models.IntegerField(default=0, db_column='IS_ADMIN')  # Oracle NUMBER(1) CHECK: 0, 1
    is_auditor = models.IntegerField(default=0, db_column='IS_AUDITOR')  # Oracle NUMBER(1) CHECK: 0, 1
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')
    
    # Custom manager
    objects = ProfileManager()

    class Meta:
        db_table = 'PROFILES'
        ordering = ['name']

    def __str__(self):
        return self.name


class ProfileActionPermission(models.Model):
    """
    Profile action permission model mapping to Oracle PROFILE_ACTION_PERMISSIONS table (V011).
    One row per profile: type (LIST/PATTERN/ALL), action_ids/tag_patterns/envs in JSON (CLOB).
    """
    profile = models.OneToOneField(
        Profile,
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='PROFILE_ID'
    )
    permission_type = models.CharField(
        max_length=20,
        choices=[
            ('LIST', 'List'),
            ('PATTERN', 'Pattern'),
            ('ALL', 'All')
        ],
        db_column='PERMISSION_TYPE'
    )
    # CLOB fields - using TextField with JSON serialization helpers
    action_ids_json = models.TextField(null=True, blank=True, db_column='ACTION_IDS_JSON')
    tag_patterns_json = models.TextField(null=True, blank=True, db_column='TAG_PATTERNS_JSON')
    environments_json = models.TextField(null=True, blank=True, db_column='ENVIRONMENTS_JSON')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')

    class Meta:
        db_table = 'PROFILE_ACTION_PERMISSIONS'

    def __str__(self):
        return f"{self.profile.name} - Action Permissions"

    # JSON field helpers
    def get_action_ids(self):
        """Deserialize JSON array from CLOB."""
        if self.action_ids_json:
            try:
                return json.loads(self.action_ids_json)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize action_ids for Profile {self.profile_id}: {e}")
                return []
        return []

    def set_action_ids(self, value):
        """Serialize JSON array to CLOB."""
        if value is not None:
            self.action_ids_json = json.dumps(value)
        else:
            self.action_ids_json = None

    def get_tag_patterns(self):
        """Deserialize JSON array from CLOB."""
        if self.tag_patterns_json:
            try:
                return json.loads(self.tag_patterns_json)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize tag_patterns for Profile {self.profile_id}: {e}")
                return []
        return []

    def set_tag_patterns(self, value):
        """Serialize JSON array to CLOB."""
        if value is not None:
            self.tag_patterns_json = json.dumps(value)
        else:
            self.tag_patterns_json = None

    def get_environments(self):
        """Deserialize JSON array from CLOB."""
        if self.environments_json:
            try:
                return json.loads(self.environments_json)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize environments for Profile {self.profile_id}: {e}")
                return []
        return []

    def set_environments(self, value):
        """Serialize JSON array to CLOB."""
        if value is not None:
            self.environments_json = json.dumps(value)
        else:
            self.environments_json = None


class ProfileTargetPermission(models.Model):
    """
    Profile target permission model mapping to Oracle PROFILE_TARGET_PERMISSIONS table (V012).
    One row per profile: type (LIST/PATTERN/ALL), target_names/target_patterns in JSON (CLOB).
    """
    profile = models.OneToOneField(
        Profile,
        on_delete=models.CASCADE,
        primary_key=True,
        db_column='PROFILE_ID'
    )
    permission_type = models.CharField(
        max_length=20,
        choices=[
            ('LIST', 'List'),
            ('PATTERN', 'Pattern'),
            ('ALL', 'All')
        ],
        db_column='PERMISSION_TYPE'
    )
    # CLOB fields - using TextField with JSON serialization helpers
    target_names_json = models.TextField(null=True, blank=True, db_column='TARGET_NAMES_JSON')
    target_patterns_json = models.TextField(null=True, blank=True, db_column='TARGET_PATTERNS_JSON')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')

    class Meta:
        db_table = 'PROFILE_TARGET_PERMISSIONS'

    def __str__(self):
        return f"{self.profile.name} - Target Permissions"

    # JSON field helpers
    def get_target_names(self):
        """Deserialize JSON array from CLOB."""
        if self.target_names_json:
            try:
                return json.loads(self.target_names_json)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize target_names for Profile {self.profile_id}: {e}")
                return []
        return []

    def set_target_names(self, value):
        """Serialize JSON array to CLOB."""
        if value is not None:
            self.target_names_json = json.dumps(value)
        else:
            self.target_names_json = None

    def get_target_patterns(self):
        """Deserialize JSON array from CLOB."""
        if self.target_patterns_json:
            try:
                return json.loads(self.target_patterns_json)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize target_patterns for Profile {self.profile_id}: {e}")
                return []
        return []

    def set_target_patterns(self, value):
        """Serialize JSON array to CLOB."""
        if value is not None:
            self.target_patterns_json = json.dumps(value)
        else:
            self.target_patterns_json = None
