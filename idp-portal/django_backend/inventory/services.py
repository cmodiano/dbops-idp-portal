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

import re  # noqa: F401 — backward compat for tests importing SAFE_TABLE_NAME_PATTERN

import structlog
from cachetools import TTLCache
from django.db import connection  # noqa: F401 — backward compat for tests patching inventory.services.connection

from integrations.models import IntegrationType
from inventory.mapper import InventoryMapper, MapperValidationError
from inventory.source_resolver import InventorySourceResolver
from inventory.query_executor import (
    InventoryQueryExecutor,
    InventoryServiceError,
    MAX_MULTI_TABLE_RESULTS,
    MAX_FLAT_TABLE_RESULTS,
)
from inventory.rbac_filter import (
    InventoryRBACFilter,
    MAX_TARGETS_FOR_RBAC_FILTER,
)
from profiles.models import Profile
from core.environment import EnvironmentHelper
from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)

# Cache for environments list (TTL 5 minutes to match catalog cache)
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

    # --- Backward compatibility delegations ---

    def get_active_inventory_integration(self):
        """Delegate to source_resolver."""
        return self.source_resolver.get_active_inventory_integration()

    def _get_inventory_mapper(self) -> InventoryMapper | None:
        """Delegate to query_executor."""
        return self.query_executor._get_inventory_mapper()

    def _execute_mapped_query(self, sql: str, params: dict) -> list[dict]:
        """Delegate to query_executor."""
        return self.query_executor.execute_mapped_query(sql, params)

    def _read_oracle_inventory(self, table_or_synonym: str,
                               environment=None, search=None, target_type=None,
                               page: int = 1, page_size: int = 25):
        """Delegate to query_executor."""
        return self.query_executor.read_oracle_inventory(
            table_or_synonym, environment, search, target_type, page, page_size
        )

    def _read_servers_from_config(self, environment=None, engine_type=None):
        """Delegate to query_executor.read_servers (backward compat)."""
        return self.query_executor.read_servers(environment, engine_type)

    def _read_instances_from_config(self, environment=None, server_name=None, server_names=None):
        """Delegate to query_executor.read_instances (backward compat)."""
        return self.query_executor.read_instances(environment, server_name, server_names)

    def _read_databases_from_config(self, environment=None, server_name=None, server_names=None):
        """Delegate to query_executor.read_databases (backward compat)."""
        return self.query_executor.read_databases(environment, server_name, server_names)

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
                return self._list_targets_from_api(
                    integration, environment, search, target_type, page, page_size
                )
            elif integration.type == IntegrationType.INVENTORY_DB:
                return self._list_targets_from_db_schema(
                    integration, environment, search, target_type, page, page_size
                )

        # Fallback: DBOPS_INVENTORY synonym
        logger.info(
            "using_fallback_inventory",
            fallback="DBOPS_INVENTORY",
            correlation_id=correlation_id
        )
        return self._list_targets_from_fallback(
            environment, search, target_type, page, page_size
        )

    def _list_targets_from_api(self, integration, environment=None, search=None,
                                target_type=None, page=1, page_size=25):
        """List targets from external API inventory (placeholder)."""
        correlation_id = get_correlation_id()
        logger.warning(
            "api_inventory_not_yet_implemented",
            integration_id=integration.id,
            base_url=integration.base_url,
            correlation_id=correlation_id
        )
        return [], 0

    def _list_targets_from_db_schema(self, integration, environment=None, search=None,
                                      target_type=None, page=1, page_size=25):
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

    def _list_targets_from_fallback(self, environment=None, search=None,
                                     target_type=None, page=1, page_size=25):
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
        server_name: str | None = None,
        server_names: list[str] | None = None,
    ) -> list[dict]:
        """
        List instances from multi-table inventory.

        NO RBAC FILTERING - caller must validate server_name against user's allowed servers.

        Args:
            environment: Target environment (required)
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
                    environment, server_names=server_names
                )
            else:
                result = self.query_executor.read_instances(
                    environment, server_name=server_name
                )

            server_filter = server_name or (f"[{len(server_names)} servers]" if server_names else None)
            logger.info(
                "inventory_list_instances",
                environment=environment,
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
        server_name: str | None = None,
        server_names: list[str] | None = None,
    ) -> list[dict]:
        """
        List databases from multi-table inventory.

        NO RBAC FILTERING - caller must validate server_name against user's allowed servers.

        Args:
            environment: Target environment (required)
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
                    environment, server_names=server_names
                )
            else:
                result = self.query_executor.read_databases(
                    environment, server_name=server_name
                )

            server_filter = server_name or (f"[{len(server_names)} servers]" if server_names else None)
            logger.info(
                "inventory_list_databases",
                environment=environment,
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
        permissions = self._aggregate_profile_permissions(profiles, environment, correlation_id)
        if permissions is None:
            return [], 0, False

        allowed_environments = permissions['allowed_environments']

        # Step 2: Load targets
        all_targets, rbac_truncated = self._load_targets(
            permissions, allowed_environments, search, target_type, user_id, correlation_id
        )

        # Step 3: Apply RBAC chain
        filtered_targets = self._apply_rbac_chain_for_user(
            all_targets, allowed_environments, permissions, user_id, correlation_id
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
        self, profiles, environment: str | None, correlation_id: str
    ) -> dict | None:
        """
        Aggregate permissions from all user profiles.

        Args:
            profiles: QuerySet of user's Profile objects
            environment: Optional environment filter
            correlation_id: Correlation ID for logging

        Returns:
            Dict with keys: has_all_access, target_restrictions, attribute_filters,
            all_access_attribute_filters, exclusion_patterns, allowed_environments.
            Returns None if no environments are allowed.

        Story 26.1 - AC4: Step 1 of list_targets_for_user pipeline.
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
                    for e in envs:
                        if isinstance(e, str):
                            raw_env = EnvironmentHelper.normalize(e)
                            normalized_env = self._normalize_environment(e)
                            allowed_environments.add(normalized_env)
                            if raw_env and raw_env != normalized_env:
                                allowed_environments.add(raw_env)
            elif is_admin:
                try:
                    allowed_environments.update(self.list_environments())
                except InventoryServiceError:
                    allowed_environments.update(self.get_default_environments())

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
                allowed_environments = set(self.list_environments())
            except InventoryServiceError:
                allowed_environments = set(self.get_default_environments())

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

    def _load_targets(
        self, permissions: dict, allowed_environments: set[str],
        search: str | None, target_type: str | None,
        user_id: int, correlation_id: str,
    ) -> tuple[list[dict], bool]:
        """
        Load targets from inventory source.

        Args:
            permissions: Aggregated permissions dict
            allowed_environments: Set of allowed environment values
            search: Optional search query
            target_type: Optional target type filter
            user_id: User ID for logging
            correlation_id: Correlation ID for logging

        Returns:
            Tuple of (all_targets list, rbac_truncated bool)

        Story 26.1 - AC4: Step 2 of list_targets_for_user pipeline.
        """
        mapper = self._get_inventory_mapper()
        use_multi_table = mapper is not None and mapper.is_multi_table

        if use_multi_table:
            all_targets = []
            failed_envs = []
            for env in allowed_environments:
                try:
                    servers = self.list_servers(environment=env)
                    for s in servers:
                        target = {
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
            all_targets, total_available = self.list_targets(
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
        Normalize environment value from external sources.
        Handles legacy aliases like 'certif' -> 'staging'.

        Args:
            raw_env: Raw environment string

        Returns:
            Normalized environment value
        """
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

    def get_allowed_environments_for_user(self, ad_groups: list[str]) -> set[str]:
        """
        Get allowed environments for a user based on their profiles.

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
                    for e in envs:
                        if isinstance(e, str):
                            raw_env = EnvironmentHelper.normalize(e)
                            normalized_env = self._normalize_environment(e)
                            allowed_environments.add(normalized_env)
                            if raw_env and raw_env != normalized_env:
                                allowed_environments.add(raw_env)

        return allowed_environments

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
