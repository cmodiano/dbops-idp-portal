"""Agrégation des permissions RBAC multi-profils pour l'inventaire — InventoryService.

Story 34.8 - AC1: Extraction de _aggregate_profile_permissions, get_allowed_environments_for_user,
et _normalize_environment de InventoryService (SRP).
"""

from __future__ import annotations

from typing import Any, Callable

import structlog
from django.db.models import QuerySet

from core.environment import EnvironmentHelper
from inventory.query_executor import InventoryServiceError
from profiles.models import Profile

logger = structlog.get_logger(__name__)


class RBACPermissionAggregator:
    """Agrégation des permissions RBAC multi-profils pour l'inventaire."""

    def __init__(
        self,
        list_environments_fn: Callable[[], list[str]],
        get_default_environments_fn: Callable[[], list[str]],
    ) -> None:
        self._list_environments = list_environments_fn
        self._get_default_environments = get_default_environments_fn

    def aggregate(
        self,
        profiles: QuerySet,
        environment: str | None,
        correlation_id: str,
    ) -> dict[str, Any] | None:
        """
        Aggregate permissions from all user profiles.

        Extrait de InventoryService._aggregate_profile_permissions (Story 34.8 - AC1).

        Args:
            profiles: QuerySet of user's Profile objects
            environment: Optional environment filter
            correlation_id: Correlation ID for logging

        Returns:
            Dict with keys: has_all_access, target_restrictions, attribute_filters,
            all_access_attribute_filters, exclusion_patterns, allowed_environments.
            Returns None if no environments are allowed.
        """
        allowed_environments: set[str] = set()
        target_restrictions: list[tuple[str, list[str] | None]] = []
        attribute_filters: list[dict | None] = []
        all_exclusion_patterns: list[str] = []
        has_all_access = False
        all_access_attribute_filters: list[dict | None] = []

        for profile in profiles:
            is_admin = getattr(profile, 'is_admin', 0) == 1

            action_perm = getattr(profile, 'profileactionpermission', None)
            if action_perm:
                envs = action_perm.get_environments()
                if envs:
                    self._add_normalized_environments(envs, allowed_environments)
            elif is_admin:
                try:
                    allowed_environments.update(self._list_environments())
                except InventoryServiceError:
                    allowed_environments.update(self._get_default_environments())

            target_perm = getattr(profile, 'profiletargetpermission', None)
            attr_filter = None
            if target_perm:
                try:
                    attr_filter = target_perm.get_filter_by_attribute()
                except Exception as e:
                    logger.error(
                        "rbac_filter_by_attribute_error",
                        profile_id=profile.id,
                        error=str(e),
                        correlation_id=correlation_id,
                        exc_info=True
                    )

                try:
                    patterns = target_perm.get_exclusion_patterns()
                    if patterns:
                        all_exclusion_patterns.extend(patterns)
                        logger.debug(
                            "rbac_exclusion_patterns_collected",
                            profile_id=profile.id,
                            patterns=patterns,
                            correlation_id=correlation_id
                        )
                except Exception as e:
                    logger.error(
                        "rbac_exclusion_patterns_error",
                        profile_id=profile.id,
                        error=str(e),
                        correlation_id=correlation_id,
                        exc_info=True
                    )

            if target_perm:
                perm_type = target_perm.permission_type
                if perm_type == 'ALL':
                    has_all_access = True
                    all_access_attribute_filters.append(attr_filter)
                elif perm_type == 'PATTERN':
                    patterns = target_perm.get_target_patterns()
                    if patterns:
                        target_restrictions.append(('PATTERN', patterns))
                        attribute_filters.append(attr_filter)
                elif perm_type == 'LIST':
                    names = target_perm.get_target_names()
                    if names:
                        target_restrictions.append(('LIST', names))
                        attribute_filters.append(attr_filter)
            elif is_admin:
                has_all_access = True
                all_access_attribute_filters.append(None)

        # Admin fallback for empty environments
        if not allowed_environments and any(getattr(p, 'is_admin', 0) == 1 for p in profiles):
            try:
                allowed_environments = set(self._list_environments())
            except InventoryServiceError:
                allowed_environments = set(self._get_default_environments())

        # Apply environment filter (Story 26.7 AC4: using EnvironmentHelper)
        if environment:
            if not EnvironmentHelper.is_in(environment, list(allowed_environments)):
                return None
            allowed_environments = {e for e in allowed_environments if EnvironmentHelper.matches(e, environment)}

        if not allowed_environments:
            return None

        return {
            'has_all_access': has_all_access,
            'target_restrictions': target_restrictions,
            'attribute_filters': attribute_filters,
            'all_access_attribute_filters': all_access_attribute_filters,
            'exclusion_patterns': all_exclusion_patterns,
            'allowed_environments': allowed_environments,
        }

    def get_allowed_environments(self, ad_groups: list[str]) -> set[str]:
        """
        Get allowed environments for a user based on their profiles.

        Extrait de InventoryService.get_allowed_environments_for_user (Story 34.8 - AC1).

        Args:
            ad_groups: User's AD groups

        Returns:
            Set of allowed environment values (includes both raw and normalized).
        """
        profiles = Profile.objects.find_by_ad_groups(ad_groups).prefetch_related(
            'profileactionpermission'
        )

        allowed_environments: set[str] = set()
        for profile in profiles:
            action_perm = getattr(profile, 'profileactionpermission', None)
            if action_perm:
                envs = action_perm.get_environments()
                if envs:
                    self._add_normalized_environments(envs, allowed_environments)

        return allowed_environments

    def _add_normalized_environments(self, envs: list, target_set: set[str]) -> None:
        """Add environment strings to target_set in both basic and alias-normalized forms.

        Adds the alias-normalized form (e.g. 'certif' → 'staging') and, if different,
        also the EnvironmentHelper-normalized form (lowercase/stripped) to preserve
        backward-compat with callers that use either representation.
        """
        for e in envs:
            if isinstance(e, str):
                basic_env = EnvironmentHelper.normalize(e)
                normalized_env = self._normalize_environment(e)
                target_set.add(normalized_env)
                if basic_env and basic_env != normalized_env:
                    target_set.add(basic_env)

    def _normalize_environment(self, raw_env: str | None) -> str:
        """
        Normalize environment value from external sources.
        Handles legacy aliases like 'certif' -> 'staging'.

        Extrait de InventoryService._normalize_environment (Story 34.8 - AC1).

        Args:
            raw_env: Raw environment string (None or empty returns '')

        Returns:
            Normalized environment value
        """
        if not raw_env:
            return ''
        env_aliases = {
            'certif': 'staging',
            'certification': 'staging',
            'stg': 'staging',
            'development': 'dev',
            'production': 'prod',
        }
        normalized = EnvironmentHelper.normalize(raw_env)
        if normalized in env_aliases:
            return env_aliases[normalized]
        return normalized
