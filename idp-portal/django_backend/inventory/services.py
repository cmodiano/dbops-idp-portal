"""
InventoryService: Orchestrator for inventory operations.

Delegates to:
- InventorySourceResolver: WHERE to read (API/DB/fallback)
- InventoryQueryExecutor: HOW to read (SQL queries, mapping)
- InventoryRBACFilter: WHAT to filter (permissions, attributes, exclusions)

Story 26.1 - AC2: Thin orchestrator pattern replacing God Service.
Story 13.1 - AC1,2: Source inventaire via intégration, fallback DBOPS_INVENTORY.
Story 23.1 - Config-driven multi-table mapping (servers, instances, databases).
"""

from __future__ import annotations

from typing import Any, cast

import structlog
from cachetools import TTLCache
from django.db import connection  # noqa: F401 — backward compat: 90+ tests patch inventory.services.connection
from django.db.models import QuerySet

from integrations.models import IntegrationType
from inventory.mapper import InventoryMapper, MapperValidationError
from inventory.source_resolver import InventorySourceResolver
from inventory.query_executor import (
    InventoryQueryExecutor,
    InventoryServiceError,
    MAX_MULTI_TABLE_RESULTS,
    MAX_FLAT_TABLE_RESULTS,
    SAFE_TABLE_NAME_PATTERN,  # noqa: F401 — backward compat: tests import from inventory.services
)
from inventory.rbac_filter import (
    InventoryRBACFilter,
    MAX_TARGETS_FOR_RBAC_FILTER,
)
from inventory.permission_aggregator import RBACPermissionAggregator
from inventory.target_loader import TargetLoader
from profiles.models import Profile
from core.environment import EnvironmentHelper
from core.middleware import get_correlation_id

__all__ = [
    "InventoryService",
    "InventoryServiceError",
    "MAX_TARGETS_FOR_RBAC_FILTER",
    "connection",
    "MapperValidationError",
    "MAX_MULTI_TABLE_RESULTS",
    "MAX_FLAT_TABLE_RESULTS",
    "SAFE_TABLE_NAME_PATTERN",
]

logger = structlog.get_logger(__name__)

# Cache for environments list (TTL 5 minutes to match catalog cache)
# Story 30.7 (RACE-3): Per-worker cache — see docs/architecture/caching-strategy.md
_environments_cache: TTLCache[str, list[str]] = TTLCache(maxsize=1, ttl=300)


class InventoryService:
    """
    Orchestrator for inventory source resolution and target retrieval.
    Delegates to InventorySourceResolver, InventoryQueryExecutor, and InventoryRBACFilter.

    Story 26.1 - AC2: Thin orchestrator replacing God Service.
    """

    def __init__(self) -> None:
        self.source_resolver = InventorySourceResolver()
        self.query_executor = InventoryQueryExecutor()
        self.rbac_filter = InventoryRBACFilter()
        # Story 34.8 - AC3: DI collaborators instantiated after base components.
        # Lambdas used so monkey-patching in tests (self.service.list_x = mock) is honoured
        # at call time (Python resolves self.list_x via instance __dict__ first).
        self.permission_aggregator = RBACPermissionAggregator(
            list_environments_fn=lambda: self.list_environments(),
            get_default_environments_fn=lambda: self.get_default_environments(),
        )
        self.target_loader = TargetLoader(
            query_executor=self.query_executor,
            list_targets_fn=lambda *args, **kwargs: self.list_targets(*args, **kwargs),
            list_servers_fn=lambda *args, **kwargs: self.list_servers(*args, **kwargs),
            get_mapper_fn=lambda: self._get_inventory_mapper(),
        )

    # --- Backward compatibility delegations ---

    def get_active_inventory_integration(self) -> Any:
        """Delegate to source_resolver."""
        return self.source_resolver.get_active_inventory_integration()

    def _get_inventory_mapper(self) -> InventoryMapper | None:
        """Delegate to query_executor."""
        return self.query_executor._get_inventory_mapper()

    def _execute_mapped_query(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        """Delegate to query_executor."""
        return self.query_executor.execute_mapped_query(sql, params)

    def _read_oracle_inventory(self, table_or_synonym: str,
                               environment: str | None = None, search: str | None = None,
                               target_type: str | None = None,
                               page: int = 1, page_size: int = 25) -> tuple[list[dict[str, Any]], int]:
        """Delegate to query_executor."""
        return self.query_executor.read_oracle_inventory(
            table_or_synonym, environment, search, target_type, page, page_size
        )

    def _read_servers_from_config(self, environment: str | None = None,
                                   engine_type: str | None = None) -> list[dict[str, Any]]:
        """Delegate to query_executor.read_servers (backward compat)."""
        return self.query_executor.read_servers(environment, engine_type)

    def _read_instances_from_config(self, environment: str | None = None,
                                     server_name: str | None = None,
                                     server_names: list[str] | None = None,
                                     engine_type: str | None = None) -> list[dict[str, Any]]:
        """Delegate to query_executor.read_instances (backward compat)."""
        return self.query_executor.read_instances(environment, server_name, server_names, engine_type=engine_type)

    def _read_databases_from_config(self, environment: str | None = None,
                                     server_name: str | None = None,
                                     server_names: list[str] | None = None,
                                     engine_type: str | None = None) -> list[dict[str, Any]]:
        """Delegate to query_executor.read_databases (backward compat)."""
        return self.query_executor.read_databases(environment, server_name, server_names, engine_type=engine_type)

    # --- Public API methods (orchestration) ---

    def list_targets(self, environment: str | None = None,
                     search: str | None = None,
                     target_type: str | None = None,
                     page: int = 1,
                     page_size: int = 25) -> tuple[list[dict], int]:
        """
        List targets from the configured source.
        AC1: Uses integration if configured, AC2: Falls back to DBOPS_INVENTORY.

        Args:
            environment: Optional environment filter (dev, staging, prod)
            search: Optional search query for name
            target_type: Optional target type filter
            page: Page number (1-based)
            page_size: Number of items per page

        Returns:
            Tuple of (list of target dicts, total count)
        """
        correlation_id = get_correlation_id()
        integration = self.source_resolver.get_active_inventory_integration()

        if integration:
            if integration.type == IntegrationType.INVENTORY:
                result = self._list_targets_from_api(
                    integration, environment, search, target_type, page, page_size
                )
                return cast("tuple[list[dict], int]", result)
            elif integration.type == IntegrationType.INVENTORY_DB:
                result = self._list_targets_from_db_schema(
                    integration, environment, search, target_type, page, page_size
                )
                return cast("tuple[list[dict], int]", result)

        # Fallback: DBOPS_INVENTORY synonym
        logger.info(
            "using_fallback_inventory",
            fallback="DBOPS_INVENTORY",
            correlation_id=correlation_id
        )
        return cast("tuple[list[dict], int]", self._list_targets_from_fallback(
            environment, search, target_type, page, page_size
        ))

    def _list_targets_from_api(self, integration: Any, environment: str | None = None,
                                search: str | None = None, target_type: str | None = None,
                                page: int = 1, page_size: int = 25) -> tuple[list[dict[str, Any]], int]:
        """List targets from external API inventory (placeholder)."""
        correlation_id = get_correlation_id()
        logger.warning(
            "api_inventory_not_yet_implemented",
            integration_id=integration.id,
            base_url=integration.base_url,
            correlation_id=correlation_id
        )
        return [], 0

    def _list_targets_from_db_schema(self, integration: Any, environment: str | None = None,
                                      search: str | None = None, target_type: str | None = None,
                                      page: int = 1, page_size: int = 25) -> tuple[list[dict[str, Any]], int]:
        """List targets from DB schema inventory."""
        correlation_id = get_correlation_id()
        config = integration.get_config() or {}
        schema_name = config.get('schema') or config.get('db_schema') or 'DBOPS_INVENTORY'
        table_name = config.get('table') or config.get('table_view') or 'INVENTORY_TABLE'

        logger.info(
            "reading_db_schema_inventory",
            schema=schema_name,
            table=table_name,
            correlation_id=correlation_id
        )

        return self.query_executor.read_oracle_inventory(
            f"{schema_name}.{table_name}",
            environment, search, target_type, page, page_size
        )

    def _list_targets_from_fallback(self, environment: str | None = None,
                                     search: str | None = None, target_type: str | None = None,
                                     page: int = 1, page_size: int = 25) -> tuple[list[dict[str, Any]], int]:
        """List targets from DBOPS_INVENTORY fallback."""
        return self.query_executor.read_oracle_inventory(
            'DBOPS_INVENTORY',
            environment, search, target_type, page, page_size
        )

    # --- Multi-table public methods ---

    def list_servers(
        self,
        environment: str,
        engine_type: str | None = None,
    ) -> list[dict]:
        """
        List servers from multi-table inventory or flat table fallback.

        Args:
            environment: Target environment (required)
            engine_type: Optional filter by engine type

        Returns:
            List of server dicts

        Raises:
            InventoryServiceError: If inventory source unreachable or config invalid
            ValueError: If environment is empty
        """
        if not environment or not environment.strip():
            raise ValueError("environment is required")

        correlation_id = get_correlation_id()

        try:
            servers = self.query_executor.read_servers(environment, engine_type)

            logger.info(
                "inventory_list_servers",
                environment=environment,
                engine_type=engine_type,
                nb_results=len(servers),
                correlation_id=correlation_id,
            )

            if len(servers) >= MAX_MULTI_TABLE_RESULTS:
                logger.warning(
                    "inventory_result_limit_reached",
                    entity="servers",
                    limit=MAX_MULTI_TABLE_RESULTS,
                    correlation_id=correlation_id,
                )

            return servers

        except ValueError:
            raise
        except InventoryServiceError:
            logger.error(
                "inventory_list_servers_failed",
                environment=environment,
                correlation_id=correlation_id,
            )
            raise
        except MapperValidationError as e:
            logger.error(
                "inventory_config_validation_failed",
                entity="servers",
                environment=environment,
                error=str(e),
                correlation_id=correlation_id,
            )
            raise InventoryServiceError("Invalid inventory configuration") from e
        except Exception as e:
            logger.error(
                "inventory_list_servers_failed",
                environment=environment,
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
            )
            raise InventoryServiceError("Failed to list servers") from e

    def list_instances(
        self,
        environment: str,
        engine_type: str | None = None,
        server_name: str | None = None,
        server_names: list[str] | None = None,
    ) -> list[dict]:
        """
        List instances from multi-table inventory.

        NO RBAC FILTERING - caller must validate server_name against user's allowed servers.

        Args:
            environment: Target environment (required)
            engine_type: Optional filter by engine type
            server_name: Filter by single server
            server_names: Filter by multiple servers

        Returns:
            List of instance dicts

        Raises:
            InventoryServiceError: If inventory source unreachable or config invalid
            ValueError: If environment is empty or both server_name and server_names provided
        """
        if not environment or not environment.strip():
            raise ValueError("environment is required")
        if server_name and server_names:
            raise ValueError("Cannot specify both server_name and server_names")
        if server_names is not None and not server_names:
            raise ValueError("server_names cannot be empty list")

        correlation_id = get_correlation_id()

        try:
            if server_names:
                result = self.query_executor.read_instances(
                    environment, server_names=server_names, engine_type=engine_type
                )
            else:
                result = self.query_executor.read_instances(
                    environment, server_name=server_name, engine_type=engine_type
                )

            server_filter = server_name or (f"[{len(server_names)} servers]" if server_names else None)
            logger.info(
                "inventory_list_instances",
                environment=environment,
                engine_type=engine_type,
                server_filter=server_filter,
                nb_results=len(result),
                correlation_id=correlation_id,
            )

            if len(result) >= MAX_MULTI_TABLE_RESULTS:
                logger.warning(
                    "inventory_result_limit_reached",
                    entity="instances",
                    limit=MAX_MULTI_TABLE_RESULTS,
                    correlation_id=correlation_id,
                )

            return result

        except ValueError:
            raise
        except InventoryServiceError:
            logger.error(
                "inventory_list_instances_failed",
                environment=environment,
                correlation_id=correlation_id,
            )
            raise
        except MapperValidationError as e:
            logger.error(
                "inventory_config_validation_failed",
                entity="instances",
                environment=environment,
                error=str(e),
                correlation_id=correlation_id,
            )
            raise InventoryServiceError("Invalid inventory configuration") from e
        except Exception as e:
            logger.error(
                "inventory_list_instances_failed",
                environment=environment,
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
            )
            raise InventoryServiceError("Failed to list instances") from e

    def list_databases(
        self,
        environment: str,
        engine_type: str | None = None,
        server_name: str | None = None,
        server_names: list[str] | None = None,
    ) -> list[dict]:
        """
        List databases from multi-table inventory.

        NO RBAC FILTERING - caller must validate server_name against user's allowed servers.

        Args:
            environment: Target environment (required)
            engine_type: Optional filter by engine type
            server_name: Filter by single server
            server_names: Filter by multiple servers

        Returns:
            List of database dicts

        Raises:
            InventoryServiceError: If inventory source unreachable or config invalid
            ValueError: If environment is empty or both server_name and server_names provided
        """
        if not environment or not environment.strip():
            raise ValueError("environment is required")
        if server_name and server_names:
            raise ValueError("Cannot specify both server_name and server_names")
        if server_names is not None and not server_names:
            raise ValueError("server_names cannot be empty list")

        correlation_id = get_correlation_id()

        try:
            if server_names:
                result = self.query_executor.read_databases(
                    environment, server_names=server_names, engine_type=engine_type
                )
            else:
                result = self.query_executor.read_databases(
                    environment, server_name=server_name, engine_type=engine_type
                )

            server_filter = server_name or (f"[{len(server_names)} servers]" if server_names else None)
            logger.info(
                "inventory_list_databases",
                environment=environment,
                engine_type=engine_type,
                server_filter=server_filter,
                nb_results=len(result),
                correlation_id=correlation_id,
            )

            if len(result) >= MAX_MULTI_TABLE_RESULTS:
                logger.warning(
                    "inventory_result_limit_reached",
                    entity="databases",
                    limit=MAX_MULTI_TABLE_RESULTS,
                    correlation_id=correlation_id,
                )

            return result

        except ValueError:
            raise
        except InventoryServiceError:
            logger.error(
                "inventory_list_databases_failed",
                environment=environment,
                correlation_id=correlation_id,
            )
            raise
        except MapperValidationError as e:
            logger.error(
                "inventory_config_validation_failed",
                entity="databases",
                environment=environment,
                error=str(e),
                correlation_id=correlation_id,
            )
            raise InventoryServiceError("Invalid inventory configuration") from e
        except Exception as e:
            logger.error(
                "inventory_list_databases_failed",
                environment=environment,
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
            )
            raise InventoryServiceError("Failed to list databases") from e

    # --- RBAC-filtered user methods ---

    def list_targets_for_user(self, user_id: int, ad_groups: list[str],
                              environment: str | None = None,
                              search: str | None = None,
                              target_type: str | None = None,
                              page: int = 1,
                              page_size: int = 25) -> tuple[list[dict], int, bool]:
        """
        List targets filtered by user permissions (RBAC).
        Implements RM2-RM6 from business rules.

        Pipeline:
        1. _aggregate_profile_permissions() → collect permissions from profiles
        2. _load_targets() → load targets from inventory source
        3. _apply_rbac_chain() → apply RBAC multi-layer filtering
        4. _paginate() → apply pagination

        Args:
            user_id: User ID
            ad_groups: User's AD groups
            environment: Optional environment filter
            search: Optional search query
            target_type: Optional target type filter
            page: Page number
            page_size: Items per page

        Returns:
            Tuple of (list of target dicts, total count, rbac_truncated).

        Story 26.1 - AC4: Decomposed into named steps.
        """
        correlation_id = get_correlation_id()

        # Get user's profiles
        profiles = Profile.objects.find_by_ad_groups(ad_groups).prefetch_related(
            'profileactionpermission', 'profiletargetpermission'
        )

        if not profiles.exists():
            logger.info(
                "no_profiles_for_user",
                user_id=user_id,
                correlation_id=correlation_id
            )
            return [], 0, False

        # Step 1: Aggregate permissions
        permissions = self.permission_aggregator.aggregate(profiles, environment, correlation_id or "")
        if permissions is None:
            return [], 0, False

        allowed_environments = permissions['allowed_environments']

        # Step 2: Load targets
        all_targets, rbac_truncated = self.target_loader.load(
            permissions, allowed_environments, search, target_type, user_id, correlation_id or ""
        )

        # Step 3: Apply RBAC chain
        filtered_targets = self._apply_rbac_chain_for_user(
            all_targets, allowed_environments, permissions, user_id, correlation_id or ""
        )

        # Step 4: Paginate
        page_results, total = self._paginate(filtered_targets, page, page_size)

        # RBAC traceability log
        logger.info(
            "rbac_targets_filtered",
            user_id=user_id,
            allowed_environments=sorted(allowed_environments),
            restriction_type='ALL' if permissions['has_all_access'] else (
                'MIXED' if permissions['target_restrictions'] else 'NONE'
            ),
            restriction_count=len(permissions['target_restrictions']),
            has_all_access=permissions['has_all_access'],
            exclusion_patterns_count=len(permissions['exclusion_patterns']),
            total_before_filter=len(all_targets),
            total=total,
            returned_count=len(page_results),
            rbac_truncated=rbac_truncated,
            correlation_id=correlation_id
        )

        return page_results, total, rbac_truncated

    def _aggregate_profile_permissions(
        self, profiles: QuerySet[Profile], environment: str | None, correlation_id: str
    ) -> dict[str, Any] | None:
        """Backward-compat delegation to permission_aggregator.aggregate (Story 34.8 - AC3)."""
        return self.permission_aggregator.aggregate(profiles, environment, correlation_id)

    def _load_targets(
        self, permissions: dict, allowed_environments: set[str],
        search: str | None, target_type: str | None,
        user_id: int, correlation_id: str,
    ) -> tuple[list[dict], bool]:
        """Backward-compat delegation to target_loader.load (Story 34.8 - AC3)."""
        return self.target_loader.load(
            permissions, allowed_environments, search, target_type, user_id, correlation_id
        )

    def _apply_rbac_chain_for_user(
        self, all_targets: list[dict], allowed_environments: set[str],
        permissions: dict, user_id: int, correlation_id: str,
    ) -> list[dict]:
        """
        Apply RBAC filtering chain to loaded targets.

        Args:
            all_targets: Raw targets from inventory
            allowed_environments: Set of allowed environment values
            permissions: Aggregated permissions dict
            user_id: User ID for logging
            correlation_id: Correlation ID for logging

        Returns:
            Filtered list of targets

        Story 26.1 - AC4: Step 3 of list_targets_for_user pipeline.
        """
        # Filter by environment (Story 26.7 AC4: using EnvironmentHelper)
        filtered_targets = [
            t for t in all_targets
            if EnvironmentHelper.is_in(t.get('environment'), list(allowed_environments))
        ]

        # Delegate to RBACFilter
        filtered_targets = self.rbac_filter.apply_rbac_chain(filtered_targets, permissions)

        return filtered_targets

    def _paginate(
        self, targets: list[dict], page: int, page_size: int
    ) -> tuple[list[dict], int]:
        """
        Apply pagination to filtered results.

        Args:
            targets: Filtered targets list
            page: Page number (1-based)
            page_size: Items per page

        Returns:
            Tuple of (page results, total count)

        Story 26.1 - AC4: Step 4 of list_targets_for_user pipeline.
        """
        total = len(targets)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        return targets[start_index:end_index], total

    # --- Utility methods (kept in InventoryService) ---

    def _normalize_environment(self, raw_env: str) -> str:
        """
        Backward-compat delegation to permission_aggregator._normalize_environment.

        Story 34.8 - AC3: tests call self.service._normalize_environment() directly.
        """
        return self.permission_aggregator._normalize_environment(raw_env)

    def get_allowed_environments_for_user(self, ad_groups: list[str]) -> set[str]:
        """
        Backward-compat delegation to permission_aggregator.get_allowed_environments.

        Story 34.8 - AC3: tests call self.service.get_allowed_environments_for_user() directly.
        """
        return self.permission_aggregator.get_allowed_environments(ad_groups)

    def list_environments(self) -> list[str]:
        """
        List distinct environments from inventory.

        Returns:
            List of distinct environment values
        """
        correlation_id = get_correlation_id()

        cache_key = 'environments_list'
        if cache_key in _environments_cache:
            cached_result = _environments_cache[cache_key]
            logger.info(
                "environments_listed_cached",
                count=len(cached_result),
                environments=cached_result,
                correlation_id=correlation_id
            )
            return cached_result

        self.source_resolver.get_active_inventory_integration()

        targets, _ = self.list_targets(
            environment=None,
            search=None,
            target_type=None,
            page=1,
            page_size=MAX_FLAT_TABLE_RESULTS
        )

        environments = set()
        for target in targets:
            env = target.get('environment')
            if env:
                environments.add(env)

        result = sorted(environments)
        _environments_cache[cache_key] = result

        logger.info(
            "environments_listed",
            count=len(result),
            environments=result,
            correlation_id=correlation_id
        )

        return result

    def get_default_environments(self) -> list[str]:
        """Get default environment values as fallback."""
        return ['dev', 'staging', 'prod']

    # --- Maintenance window ---

    def get_next_maintenance_window(self, target_id: str) -> dict | None:
        """
        Get the next maintenance window for a target.

        Args:
            target_id: Opaque target ID in the inventory

        Returns:
            Maintenance window dict or None
        """
        correlation_id = get_correlation_id()
        logger.info(
            "get_next_maintenance_window",
            target_id=target_id,
            correlation_id=correlation_id,
        )
        return None
