"""Chargement des targets depuis l'inventaire (multi-table ou flat-table) — InventoryService.

Story 34.8 - AC2: Extraction de InventoryService._load_targets (SRP).
"""

from __future__ import annotations

from typing import Any, Callable

import structlog

from inventory.query_executor import (
    InventoryQueryExecutor,
    InventoryServiceError,
)
from inventory.rbac_filter import MAX_TARGETS_FOR_RBAC_FILTER

logger = structlog.get_logger(__name__)


class TargetLoader:
    """Chargement des targets depuis l'inventaire (multi-table ou flat-table)."""

    def __init__(
        self,
        query_executor: InventoryQueryExecutor,
        list_targets_fn: Callable,
        list_servers_fn: Callable,
        get_mapper_fn: Callable | None = None,
    ) -> None:
        self._query_executor = query_executor
        self._list_targets = list_targets_fn
        self._list_servers = list_servers_fn
        # get_mapper_fn allows tests to patch InventoryService._get_inventory_mapper
        # via @patch.object; defaults to calling query_executor directly.
        self._get_mapper = get_mapper_fn or (lambda: query_executor._get_inventory_mapper())

    def load(
        self,
        permissions: dict,
        allowed_environments: set[str],
        search: str | None,
        target_type: str | None,
        user_id: int,
        correlation_id: str,
    ) -> tuple[list[dict[str, Any]], bool]:
        """
        Load targets from inventory source.

        Extrait de InventoryService._load_targets (Story 34.8 - AC2).

        Args:
            permissions: Aggregated permissions dict
            allowed_environments: Set of allowed environment values
            search: Optional search query
            target_type: Optional target type filter
            user_id: User ID for logging
            correlation_id: Correlation ID for logging

        Returns:
            Tuple of (all_targets list, rbac_truncated bool)
        """
        mapper = self._get_mapper()
        use_multi_table = mapper is not None and mapper.is_multi_table

        if use_multi_table:
            all_targets: list[dict[str, Any]] = []
            failed_envs: list[str] = []
            for env in allowed_environments:
                try:
                    servers = self._list_servers(environment=env)
                    for s in servers:
                        target: dict[str, Any] = {
                            'name': s.get('name', ''),
                            'environment': s.get('environment', ''),
                            'target_type': 'server',
                            'metadata': None,
                        }
                        for key, val in s.items():
                            if key not in target:
                                target[key] = val
                        all_targets.append(target)
                except InventoryServiceError as e:
                    failed_envs.append(env)
                    logger.warning(
                        "list_servers_failed_for_env",
                        environment=env,
                        user_id=user_id,
                        error=str(e),
                        correlation_id=correlation_id,
                    )

            if failed_envs and len(failed_envs) == len(allowed_environments):
                logger.error(
                    "list_targets_for_user_all_environments_failed",
                    user_id=user_id,
                    failed_environments=failed_envs,
                    correlation_id=correlation_id,
                )
                raise InventoryServiceError(
                    f"Failed to load servers from all {len(failed_envs)} allowed environments"
                )

            rbac_truncated = False

            logger.info(
                "rbac_using_multi_table_servers",
                user_id=user_id,
                environments_checked=len(allowed_environments),
                environments_failed=len(failed_envs),
                total_servers=len(all_targets),
                correlation_id=correlation_id,
            )
        else:
            all_targets, total_available = self._list_targets(
                environment=None,
                search=search,
                target_type=target_type,
                page=1,
                page_size=MAX_TARGETS_FOR_RBAC_FILTER
            )
            rbac_truncated = total_available > MAX_TARGETS_FOR_RBAC_FILTER

            if total_available > MAX_TARGETS_FOR_RBAC_FILTER:
                logger.warning(
                    "rbac_filter_truncated",
                    total_available=total_available,
                    max_loaded=MAX_TARGETS_FOR_RBAC_FILTER,
                    user_id=user_id,
                    correlation_id=correlation_id,
                    message="Inventory too large for in-memory RBAC filtering. Results may be incomplete."
                )

        return all_targets, rbac_truncated
