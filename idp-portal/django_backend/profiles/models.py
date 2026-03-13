from __future__ import annotations

import structlog
from django.db import models
from django.db.models import Count, Q

logger = structlog.get_logger(__name__)


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
    # INCON-4 (Story 57.14): IntegerField intentionnel pour compatibilité Oracle.
    # Oracle n'a pas de type BOOLEAN natif — ces champs mappent NUMBER(1) avec CHECK (val IN (0, 1)).
    # Schema legacy Oracle existant. BooleanField Django créerait une incohérence.
    # CHECK constraint définie dans migration Flyway (gérée par DBA, pas Django ORM).
    # L'API Python utilise la property is_approver_bool (ci-dessous).
    # Les serializers DRF font la conversion int ↔ bool automatiquement.
    is_approver = models.IntegerField(default=0, db_column='IS_APPROVER')
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')
    # Story 64.11: CaC sync tracking
    last_synced_at = models.DateTimeField(null=True, blank=True, db_column='LAST_SYNCED_AT')
    last_synced_hash = models.CharField(max_length=64, null=True, blank=True, db_column='LAST_SYNCED_HASH')

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

    @property
    def is_approver_bool(self) -> bool:
        """Oracle NUMBER(1) → bool (1 = True, 0 = False)."""
        return self.is_approver == 1

    def __str__(self) -> str:
        return self.name


class ProfileActionPermission(models.Model):
    """
    Profile action permission model mapping to Oracle PROFILE_ACTION_PERMISSIONS table (V011).
    One row per profile: type (LIST/PATTERN/ALL).
    Data stored in normalized tables: PROFILE_ACTION_ALLOWLIST, PROFILE_ACTION_TAG_PATTERNS,
    PROFILE_ACTION_ENVS (Story 78.11). Legacy CLOB columns dropped in V136 (Story 78.15).
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
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')

    class Meta:
        db_table = 'PROFILE_ACTION_PERMISSIONS'

    def __str__(self) -> str:
        return f"{self.profile.name} - Action Permissions"


class ProfileTargetPermission(models.Model):
    """
    Profile target permission model mapping to Oracle PROFILE_TARGET_PERMISSIONS table (V012).
    One row per profile: type (LIST/PATTERN/ALL).
    Data stored in normalized tables: PROFILE_TARGET_ALLOWLIST, PROFILE_TARGET_PATTERNS,
    PROFILE_TARGET_ATTRIBUTE_FILTERS, PROFILE_TARGET_EXCLUSIONS (Story 78.12).
    Legacy CLOB columns dropped in V136 (Story 78.15).
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
    created_at = models.DateTimeField(auto_now_add=True, db_column='CREATED_AT')
    updated_at = models.DateTimeField(auto_now=True, db_column='UPDATED_AT')

    class Meta:
        db_table = 'PROFILE_TARGET_PERMISSIONS'

    def __str__(self) -> str:
        return f"{self.profile.name} - Target Permissions"
