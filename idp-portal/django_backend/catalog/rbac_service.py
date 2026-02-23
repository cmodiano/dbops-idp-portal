"""
Catalog RBAC Service - Centralized RBAC logic for catalog actions.

Story 26.3: Extracted from catalog/views.py to eliminate duplication
and improve testability. Encapsulates permission aggregation, action
filtering, and single-action access checks.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, cast

import structlog
from django.core.cache import cache

from core.auth_utils import get_user_ad_groups
from core.middleware import get_correlation_id
from profiles.cache import RBAC_CACHE_VERSION_KEY, RBAC_CACHE_TTL
from profiles.services import ProfileService

if TYPE_CHECKING:
    from django.contrib.auth.models import User
    from catalog.models import Action

logger = structlog.get_logger(__name__)


class CatalogRBACService:
    """Service for catalog RBAC permission checks.

    Centralizes the logic previously spread across module-level functions
    in catalog/views.py: _get_cumulative_permissions_for_user,
    _filter_by_rbac, and _check_rbac_for_action.

    Story 33.4 (DIP): accepts optional injected services for testability.
    """

    def __init__(
        self,
        profile_service: ProfileService | None = None,
        inventory_service: Any = None,
    ) -> None:
        """
        Args:
            profile_service:   Optional ProfileService (defaults to new instance).
            inventory_service: Optional InventoryService (defaults to new instance
                               when needed; kept None here to preserve the lazy
                               import that avoids circular dependencies).
        """
        self._profile_service = profile_service
        self._inventory_service = inventory_service

    def get_permissions(self, user: User | None) -> dict | None:
        """
        Get cumulative RBAC permissions for user across all profiles.

        Uses Django cache with a version key for invalidation. When profiles or
        permissions are modified, invalidate_permissions_cache() deletes the version
        key, causing all user caches to miss on the next request.

        Args:
            user: Django User instance or None.

        Returns:
            Dict with:
                - actions_type: 'all' | 'pattern' | 'list'
                - action_ids: list[int] (sorted)
                - tag_patterns: list[str] (sorted)
                - environments: list[str] (sorted)
            Returns None if user invalid or no permissions.

        Story 26.3 - AC2: Migrated from _get_cumulative_permissions_for_user.
        Story 30.14 - AC3: Added cache with invalidation via version key.
        """
        if not user or not user.is_authenticated:
            return None

        # Check cache: version key + user-specific key
        try:
            cache_version = cache.get(RBAC_CACHE_VERSION_KEY)
            if cache_version is not None:
                cache_key = f'rbac:permissions:user:{user.id}:v:{cache_version}'
                cached = cache.get(cache_key)
                if cached is not None:
                    return cast(dict, cached)
        except Exception:  # noqa: BLE001
            # Cache unavailability should not break permission lookups
            pass

        ad_groups = get_user_ad_groups(user)
        try:
            profile_service = self._profile_service or ProfileService()
            permissions = profile_service.get_cumulative_permissions(user.id, ad_groups)
        except Exception as e:
            # Story 17.6: Justified broad catch - ProfileService can raise various exceptions
            logger.warning(
                "profile_service_unavailable_no_rbac_filtering",
                user_id=user.id,
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=get_correlation_id(),
                exc_info=True,
            )
            return None

        if not permissions or not permissions.get('action_permissions'):
            return None

        # Aggregate action permissions (union across profiles)
        action_ids: set[int] = set()
        tag_patterns: set[str] = set()
        environments: set[str] = set()
        actions_type_all = False

        for perm in permissions.get('action_permissions', []):
            if perm.get('actions_type') == 'all':
                actions_type_all = True
            else:
                action_ids.update(perm.get('action_ids', []) or [])
                tag_patterns.update(perm.get('tag_patterns', []) or [])
            environments.update(perm.get('environments', []) or [])

        # Determine final actions_type
        if actions_type_all:
            actions_type = 'all'
        elif tag_patterns:
            actions_type = 'pattern'
        else:
            actions_type = 'list'

        # When profile has full action access (all) but no explicit environments,
        # default to all environments from inventory (Story 13.7).
        if not environments and actions_type_all:
            # Lazy import to avoid circular dependency (LOW-1 documented reason)
            from inventory.services import InventoryService  # noqa: PLC0415
            try:
                inventory_service = self._inventory_service or InventoryService()
                environments = set(inventory_service.list_environments())
            except Exception as e:
                # Story 17.6: Justified broad catch - InventoryService can raise various exceptions
                logger.warning(
                    "inventory_service_unavailable_fallback_environments",
                    user_id=user.id,
                    error=str(e),
                    error_type=type(e).__name__,
                    correlation_id=get_correlation_id(),
                    exc_info=True,
                )
                environments = {'dev', 'staging', 'prod'}

        result = {
            'actions_type': actions_type,
            'action_ids': sorted(action_ids),
            'tag_patterns': sorted(tag_patterns),
            'environments': sorted(environments),
        }

        # Cache the result with version key (atomic get_or_set to avoid race condition)
        try:
            cache_version = cache.get_or_set(
                RBAC_CACHE_VERSION_KEY,
                default=str(int(time.time())),
                timeout=RBAC_CACHE_TTL,
            )
            cache_key = f'rbac:permissions:user:{user.id}:v:{cache_version}'
            cache.set(cache_key, result, RBAC_CACHE_TTL)
        except Exception:  # noqa: BLE001
            # Cache unavailability should not break permission lookups
            pass

        return result

    def filter_actions(
        self,
        actions: list[Action | dict],
        permissions: dict | None,
    ) -> list[Action | dict]:
        """
        Filter actions by RBAC permissions.

        Args:
            actions: List of Action instances or dicts. Can be heterogeneous mix.
            permissions: Dict from get_permissions() or None.

        Returns:
            Filtered list of actions user has access to.

        Note:
            Requires actions to have tags prefetched via .with_tags()
            to avoid N+1 queries.

        Story 26.3 - AC3: Migrated from _filter_by_rbac.
        """
        if permissions is None:
            return actions

        # MEDIUM-2 fix: Validate permissions structure
        if not isinstance(permissions, dict):
            logger.warning(  # type: ignore[unreachable]
                "filter_actions_invalid_permissions_type",
                permissions_type=type(permissions).__name__,
                correlation_id=get_correlation_id(),
            )
            return actions

        actions_type = permissions.get('actions_type', 'all')
        if actions_type == 'all':
            return actions

        action_ids = set(permissions.get('action_ids', []) or [])
        tag_patterns = set(permissions.get('tag_patterns', []) or [])

        # MEDIUM-2 fix: Pre-build action->tags map to avoid N+1 queries
        # Tags should already be prefetched via with_tags() manager method
        action_tags_map = {}
        for act in actions:
            if hasattr(act, 'id'):
                # Use prefetched actiontag_set (already loaded, no extra query)
                if hasattr(act, '_prefetched_objects_cache') and 'actiontag_set' in act._prefetched_objects_cache:
                    action_tags_map[act.id] = {at.tag.name for at in act.actiontag_set.all()}  # type: ignore[union-attr]
                elif hasattr(act, 'actiontag_set'):
                    # Fallback: tags might be in cache from prefetch_related
                    action_tags_map[act.id] = {at.tag.name for at in act.actiontag_set.all()}
                else:
                    action_tags_map[act.id] = set()
            else:
                action_tags_map[act.get('id')] = set(act.get('tags', []) or [])

        result = []
        for act in actions:
            if hasattr(act, 'id'):
                act_id = act.id
            else:
                act_id = act.get('id')

            # Check if action_id is in allowed list
            if act_id in action_ids:
                result.append(act)
                continue

            # Check if any tag matches pattern (using pre-built map)
            act_tags = action_tags_map.get(act_id, set())
            if act_tags & tag_patterns:
                result.append(act)

        return result

    def check_action(
        self,
        action: Action | dict,
        permissions: dict | None,
    ) -> bool:
        """
        Check if user has access to a single action.

        Delegates to filter_actions to eliminate duplication.

        Args:
            action: Action instance or dict.
            permissions: Dict from get_permissions() or None.

        Returns:
            True if user has access, False otherwise.

        Story 26.3 - AC4: Migrated from _check_rbac_for_action.
        """
        # MEDIUM-2: Permissions validation is handled in filter_actions
        filtered = self.filter_actions([action], permissions)
        return len(filtered) > 0
