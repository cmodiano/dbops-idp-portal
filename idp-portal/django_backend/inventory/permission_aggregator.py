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
from profiles.action_permission_repository import get_environments as repo_get_environments
from profiles.target_permission_repository import (
    get_filter_by_attribute as repo_get_filter_by_attribute,
    get_exclusion_patterns as repo_get_exclusion_patterns,
    get_target_patterns as repo_get_target_patterns,
    get_target_names as repo_get_target_names,
)
from profiles.models import Profile

logger = structlog.get_logger(__name__)


class RBACPermissionAggregator:
    """Agrégation des permissions RBAC multi-profils pour l'inventaire."""

    def __init__(
        self,
        list_environments_fn: Callable[[], list[str]],
    ) -> None:
        self._list_environments = list_environments_fn

    def aggregate(
        self,
        profiles: QuerySet,
        environment: str | None,
        correlation_id: str | None,  # INV-LOW-02: consistent with codebase convention (str | None)
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
                envs = repo_get_environments(action_perm)
                if envs:
                    self._add_normalized_environments(envs, allowed_environments)
            elif is_admin:
                try:
                    allowed_environments.update(self._list_environments())
                except InventoryServiceError:
                    pass  # Inventory unavailable — no environments added (source of truth unavailable)

            target_perm = getattr(profile, 'profiletargetpermission', None)
            attr_filter = None
            if target_perm:
                try:
                    attr_filter = repo_get_filter_by_attribute(target_perm)
                except Exception as e:  # noqa: BLE001 — graceful-degradation: filter attribute error logged, aggregation continues
                    logger.error(
                        "rbac_filter_by_attribute_error",
                        profile_id=profile.id,
                        error=str(e),
                        correlation_id=correlation_id,
                        exc_info=True
                    )

                try:
                    patterns = repo_get_exclusion_patterns(target_perm)
                    if patterns:
                        all_exclusion_patterns.extend(patterns)
                        logger.debug(
                            "rbac_exclusion_patterns_collected",
                            profile_id=profile.id,
                            patterns=patterns,
                            correlation_id=correlation_id
                        )
                except Exception as e:  # noqa: BLE001 — graceful-degradation: exclusion patterns error logged, aggregation continues
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
                    try:
                        patterns = repo_get_target_patterns(target_perm)
                        if patterns:
                            target_restrictions.append(('PATTERN', patterns))
                            attribute_filters.append(attr_filter)
                    except Exception as e:  # noqa: BLE001 — graceful-degradation: target patterns error logged, aggregation continues
                        logger.error(
                            "rbac_target_patterns_error",
                            profile_id=profile.id,
                            error=str(e),
                            correlation_id=correlation_id,
                            exc_info=True
                        )
                elif perm_type == 'LIST':
                    try:
                        names = repo_get_target_names(target_perm)
                        if names:
                            target_restrictions.append(('LIST', names))
                            attribute_filters.append(attr_filter)
                    except Exception as e:  # noqa: BLE001 — graceful-degradation: target names error logged, aggregation continues
                        logger.error(
                            "rbac_target_names_error",
                            profile_id=profile.id,
                            error=str(e),
                            correlation_id=correlation_id,
                            exc_info=True
                        )
            elif is_admin:
                has_all_access = True
                all_access_attribute_filters.append(None)

        # Admin fallback for empty environments
        if not allowed_environments and any(getattr(p, 'is_admin', 0) == 1 for p in profiles):
            try:
                allowed_environments = set(self._list_environments())
            except InventoryServiceError:
                pass  # Inventory unavailable — no environments added (source of truth unavailable)

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
                envs = repo_get_environments(action_perm)
                if envs:
                    self._add_normalized_environments(envs, allowed_environments)

        return allowed_environments

    def _add_normalized_environments(self, envs: list, target_set: set[str]) -> None:
        """Add environment values (lowercased) to target_set. No alias normalization — inventory is the source of truth."""
        for e in envs:
            if isinstance(e, str):
                basic_env = EnvironmentHelper.normalize(e)
                if basic_env:
                    target_set.add(basic_env)

    def _normalize_environment(self, raw_env: str | None) -> str:
        """Normalize environment to lowercase only. No alias mapping — inventory is the source of truth.

        Extrait de InventoryService._normalize_environment (Story 34.8 - AC1).
        Note: kept for backward-compat delegation from InventoryService._normalize_environment.
        Not called internally — _add_normalized_environments calls EnvironmentHelper.normalize directly.

        Args:
            raw_env: Raw environment string (None or empty returns '')

        Returns:
            Normalized environment value (lowercase/stripped only)
        """
        if not raw_env:
            return ''
        return EnvironmentHelper.normalize(raw_env)
