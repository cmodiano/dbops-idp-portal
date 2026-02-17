from __future__ import annotations

import json
import logging
from typing import Any, cast
from django.db import models
from django.db.models import Q

logger = logging.getLogger(__name__)


class ProfileManager(models.Manager):
    """
    Custom manager for Profile model.
    Provides query methods for common profile queries.
    """
    
    def find_by_ad_groups(self, ad_groups: list[str]) -> models.QuerySet[Profile]:
        """
        Find profiles matching the given AD group identifiers.

        Notes:
        - In real SSO/JWT payloads, groups can be expressed as:
          - a full DN like "CN=GRP-IDP-DBOPS,OU=...,DC=..."
          - a short group name like "GRP-IDP-DBOPS"
          - sometimes a profile code like "dbops"
        - For robustness, we match against BOTH:
          - `Profile.ad_group`
          - `Profile.name`
        - Matching is case-insensitive.
        
        Args:
            ad_groups: List of AD group names
        
        Returns:
            QuerySet of profiles matching any of the AD groups, ordered by name
        """
        if not ad_groups:
            return self.none()  # type: ignore[return-value]

        normalized: set[str] = set()
        for raw in ad_groups:
            if not raw:
                continue
            s = str(raw).strip()
            if not s:
                continue
            normalized.add(s)

            # If DN contains CN=..., also add CN value
            up = s.upper()
            if "CN=" in up:
                try:
                    start = up.index("CN=") + 3
                    # Use original string slice to preserve case around separators
                    # Find comma after CN=...
                    comma_idx = s.find(",", start)
                    cn_val = s[start:comma_idx] if comma_idx != -1 else s[start:]
                    cn_val = cn_val.strip()
                    if cn_val:
                        normalized.add(cn_val)
                except ValueError:
                    pass

        if not normalized:
            return self.none()  # type: ignore[return-value]

        q = Q()
        for val in normalized:
            q |= Q(ad_group__iexact=val) | Q(name__iexact=val)

        return self.filter(q).order_by("name")  # type: ignore[return-value]
    
    def list_with_permissions_count(self) -> models.QuerySet[Profile]:
        """
        List all profiles with permission count annotation.
        Counts both action and target permissions.

        Returns:
            QuerySet with permission_count annotation (used by ProfileListSerializer).
        """
        from django.db.models import Count, Q

        return self.annotate(  # type: ignore[no-any-return]
            permission_count=Count(
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
    # INCON-4 (Story 30.16): IntegerField intentionnel pour compatibilité Oracle.
    # Oracle n'a pas de type BOOLEAN natif — ces champs mappent NUMBER(1) avec CHECK (val IN (0, 1)).
    # Schema legacy Oracle existant (migrations Flyway V001-V075). BooleanField Django créerait une incohérence.
    # CHECK constraint défini dans migration Flyway (gérée par DBA, pas Django ORM).
    # L'API Python utilise les properties is_admin_bool / is_auditor_bool (ci-dessous).
    # Les serializers DRF font la conversion int ↔ bool automatiquement.
    is_admin = models.IntegerField(default=0, db_column='IS_ADMIN')
    is_auditor = models.IntegerField(default=0, db_column='IS_AUDITOR')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')
    
    # Custom manager
    objects = ProfileManager()

    class Meta:
        db_table = 'PROFILES'
        ordering = ['name']

    @property
    def is_admin_bool(self) -> bool:
        """Oracle NUMBER(1) → bool (1 = True, 0 = False)."""
        return self.is_admin == 1

    @property
    def is_auditor_bool(self) -> bool:
        """Oracle NUMBER(1) → bool (1 = True, 0 = False)."""
        return self.is_auditor == 1

    def __str__(self) -> str:
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

    def __str__(self) -> str:
        return f"{self.profile.name} - Action Permissions"

    # JSON field helpers
    def get_action_ids(self) -> list[int]:
        """Deserialize JSON array from CLOB."""
        if self.action_ids_json:
            try:
                return json.loads(self.action_ids_json)  # type: ignore[no-any-return]
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize action_ids for Profile {self.profile_id}: {e}")
                return []
        return []

    def set_action_ids(self, value: list[int] | None) -> None:
        """Serialize JSON array to CLOB."""
        if value is not None:
            self.action_ids_json = json.dumps(value)
        else:
            self.action_ids_json = None

    def get_tag_patterns(self) -> list[str]:
        """Deserialize JSON array from CLOB."""
        if self.tag_patterns_json:
            try:
                return json.loads(self.tag_patterns_json)  # type: ignore[no-any-return]
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize tag_patterns for Profile {self.profile_id}: {e}")
                return []
        return []

    def set_tag_patterns(self, value: list[str] | None) -> None:
        """Serialize JSON array to CLOB."""
        if value is not None:
            self.tag_patterns_json = json.dumps(value)
        else:
            self.tag_patterns_json = None

    def get_environments(self) -> list[str]:
        """Deserialize JSON array from CLOB."""
        if self.environments_json:
            try:
                return json.loads(self.environments_json)  # type: ignore[no-any-return]
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize environments for Profile {self.profile_id}: {e}")
                return []
        return []

    def set_environments(self, value: list[str] | None) -> None:
        """Serialize JSON array to CLOB."""
        if value is not None:
            self.environments_json = json.dumps(value)
        else:
            self.environments_json = None


class ProfileTargetPermission(models.Model):
    """
    Profile target permission model mapping to Oracle PROFILE_TARGET_PERMISSIONS table (V012).
    One row per profile: type (LIST/PATTERN/ALL), target_names/target_patterns in JSON (CLOB).

    Story 23.4: Added filter_by_attribute_json for attribute-based RBAC filtering.
    Format: {"engine_type": ["oracle", "sqlserver"], "zone": ["prod"], ...}
    Keys are business concept names from InventoryMapper config (stable, not Oracle columns).
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
    filter_by_attribute_json = models.TextField(
        null=True,
        blank=True,
        db_column='FILTER_BY_ATTRIBUTE_JSON',
        help_text='JSON dict filtering targets by inventory attributes. Format: {"engine_type": ["oracle"], ...}'
    )
    exclusion_patterns_json = models.TextField(
        null=True,
        blank=True,
        db_column='EXCLUSION_PATTERNS_JSON',
        help_text='JSON array filtering out targets matching any pattern. Applied after inclusion rules. Format: ["PROD-CRITICAL-*", "DR-*"]. Story 25.6'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')

    class Meta:
        db_table = 'PROFILE_TARGET_PERMISSIONS'

    def __str__(self) -> str:
        return f"{self.profile.name} - Target Permissions"

    # JSON field helpers
    def get_target_names(self) -> list[str]:
        """Deserialize JSON array from CLOB."""
        if self.target_names_json:
            try:
                return json.loads(self.target_names_json)  # type: ignore[no-any-return]
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize target_names for Profile {self.profile_id}: {e}")
                return []
        return []

    def set_target_names(self, value: list[str] | None) -> None:
        """Serialize JSON array to CLOB."""
        if value is not None:
            self.target_names_json = json.dumps(value)
        else:
            self.target_names_json = None

    def get_target_patterns(self) -> list[str]:
        """Deserialize JSON array from CLOB."""
        if self.target_patterns_json:
            try:
                return json.loads(self.target_patterns_json)  # type: ignore[no-any-return]
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize target_patterns for Profile {self.profile_id}: {e}")
                return []
        return []

    def set_target_patterns(self, value: list[str] | None) -> None:
        """Serialize JSON array to CLOB."""
        if value is not None:
            self.target_patterns_json = json.dumps(value)
        else:
            self.target_patterns_json = None

    def get_filter_by_attribute(self) -> dict[str, list[str]] | None:
        """
        Deserialize filter_by_attribute from JSON CLOB.

        Returns:
            Dict mapping attribute concept keys to list of values, or None if not set.
            Example: {"engine_type": ["oracle", "sqlserver"], "zone": ["prod"]}

        Story 23.4 - RBAC filter by inventory attributes.
        """
        if self.filter_by_attribute_json:
            try:
                return cast("dict[str, list[str]] | None", json.loads(self.filter_by_attribute_json))
            except (json.JSONDecodeError, TypeError) as e:
                # Code review fix: JSON malformé = ERROR (corruption données), pas WARNING
                logger.error(
                    f"Failed to deserialize filter_by_attribute for Profile {self.profile_id}: {e}"
                )
                return None
        return None

    def set_filter_by_attribute(self, value: dict | None) -> None:
        """
        Serialize filter_by_attribute to JSON CLOB.

        Args:
            value: Dict mapping attribute keys to list of values, or None to clear.

        Story 23.4 - RBAC filter by inventory attributes.
        """
        if value is not None:
            self.filter_by_attribute_json = json.dumps(value)
        else:
            self.filter_by_attribute_json = None

    def get_exclusion_patterns(self) -> list[str]:
        """
        Deserialize exclusion_patterns from JSON CLOB.

        Returns:
            List of exclusion patterns, or empty list if not set.
            Example: ["PROD-CRITICAL-*", "DR-*"]

        Story 25.6 - Deny explicit RBAC (exclusion patterns).
        Code review fix: Use ERROR level for data corruption (consistency with filter_by_attribute).
        """
        if self.exclusion_patterns_json:
            try:
                patterns = json.loads(self.exclusion_patterns_json)
                # Validate that it's a list of strings
                if not isinstance(patterns, list):
                    # Code review fix: ERROR (not WARNING) - this is data corruption
                    logger.error(
                        f"exclusion_patterns for Profile {self.profile_id} is not a list (data corruption), returning empty"
                    )
                    return []
                # Filter out invalid patterns (non-string, empty)
                valid_patterns = [p for p in patterns if isinstance(p, str) and p.strip()]
                if len(valid_patterns) != len(patterns):
                    logger.warning(
                        f"exclusion_patterns for Profile {self.profile_id} contained invalid patterns (filtered out)"
                    )
                return valid_patterns
            except (json.JSONDecodeError, TypeError) as e:
                logger.error(
                    f"Failed to deserialize exclusion_patterns for Profile {self.profile_id}: {e}"
                )
                return []
        return []

    def set_exclusion_patterns(self, value: list[str] | None) -> None:
        """
        Serialize exclusion_patterns to JSON CLOB.

        Args:
            value: List of exclusion patterns (strings), or None to clear.

        Story 25.6 - Deny explicit RBAC (exclusion patterns).
        """
        if value is not None:
            self.exclusion_patterns_json = json.dumps(value)
        else:
            self.exclusion_patterns_json = None
