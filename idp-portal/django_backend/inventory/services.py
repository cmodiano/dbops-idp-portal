"""
InventoryService for inventory source resolution and target retrieval.
Story 13.1 - AC1,2: Source inventaire via intégration, fallback DBOPS_INVENTORY.
Story 23.1 - Config-driven multi-table mapping (servers, instances, databases).
No local DB table - reads directly from external sources.
"""

from __future__ import annotations

import fnmatch
import re
import structlog
from cachetools import TTLCache

from django.db import connection

from integrations.models import Integration, IntegrationType
from inventory.mapper import InventoryMapper, MapperValidationError
from inventory.models import Target, TargetEnvironment, TargetType
from profiles.models import Profile
from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)

# Cache for environments list (TTL 5 minutes to match catalog cache)
_environments_cache: TTLCache[str, list[str]] = TTLCache(maxsize=1, ttl=300)

# Maximum targets to load for in-memory RBAC filtering
MAX_TARGETS_FOR_RBAC_FILTER = 5000

# Maximum results from multi-table config queries (防止 DoS via unbounded queries)
# Story 23.1 code review fix: prevent out-of-memory from million-row tables
MAX_MULTI_TABLE_RESULTS = 10000

# Maximum results from flat table fallback
MAX_FLAT_TABLE_RESULTS = 10000

# Whitelist of allowed table/synonym names pattern (alphanumeric, underscore, dot for schema.table)
SAFE_TABLE_NAME_PATTERN = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$')


class InventoryServiceError(Exception):
    """Exception raised when inventory service encounters an error."""
    pass


class InventoryService:
    """
    Service for inventory source resolution and target retrieval.
    Reads from integration (API or DB schema) or fallback DBOPS_INVENTORY.
    No local persistence - acts as a proxy with RBAC filtering.
    """

    def get_active_inventory_integration(self) -> Integration | None:
        """
        Get the active inventory integration.
        Looks for integration of type 'inventory' (API) or 'inventory_db' (schema).

        Returns:
            Integration instance or None if no inventory integration configured
        """
        correlation_id = get_correlation_id()

        # Try API inventory first, then DB inventory
        integration = Integration.objects.get_by_type(IntegrationType.INVENTORY)
        if integration:
            logger.info(
                "inventory_integration_found",
                integration_id=integration.id,
                integration_type=IntegrationType.INVENTORY,
                correlation_id=correlation_id
            )
            return integration

        integration = Integration.objects.get_by_type(IntegrationType.INVENTORY_DB)
        if integration:
            logger.info(
                "inventory_integration_found",
                integration_id=integration.id,
                integration_type=IntegrationType.INVENTORY_DB,
                correlation_id=correlation_id
            )
            return integration

        logger.info(
            "no_inventory_integration_configured",
            correlation_id=correlation_id
        )
        return None

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
        integration = self.get_active_inventory_integration()

        if integration:
            if integration.type == IntegrationType.INVENTORY:
                # API-based inventory
                return self._list_targets_from_api(
                    integration, environment, search, target_type, page, page_size
                )
            elif integration.type == IntegrationType.INVENTORY_DB:
                # DB schema-based inventory
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

    def _list_targets_from_api(self, integration: Integration,
                               environment: str | None = None,
                               search: str | None = None,
                               target_type: str | None = None,
                               page: int = 1,
                               page_size: int = 25) -> tuple[list[dict], int]:
        """
        List targets from external API inventory.

        TODO: Implement HTTP client with VaultService for credentials.
        For now, returns empty list as placeholder.

        Args:
            integration: Integration instance with base_url and credential_ref
            environment: Optional environment filter
            search: Optional search query
            target_type: Optional target type filter
            page: Page number
            page_size: Items per page

        Returns:
            Tuple of (list of target dicts, total count)
        """
        correlation_id = get_correlation_id()

        # TODO: Implement HTTP client call to integration.base_url
        # - Get credentials from VaultService using integration.credential_ref
        # - Call API with filters
        # - Parse response
        logger.warning(
            "api_inventory_not_yet_implemented",
            integration_id=integration.id,
            base_url=integration.base_url,
            correlation_id=correlation_id
        )

        return [], 0

    def _list_targets_from_db_schema(self, integration: Integration,
                                     environment: str | None = None,
                                     search: str | None = None,
                                     target_type: str | None = None,
                                     page: int = 1,
                                     page_size: int = 25) -> tuple[list[dict], int]:
        """
        List targets from DB schema inventory (configured via integration config).

        Args:
            integration: Integration instance with schema config
            environment: Optional environment filter
            search: Optional search query
            target_type: Optional target type filter
            page: Page number
            page_size: Items per page

        Returns:
            Tuple of (list of target dicts, total count)
        """
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

        return self._read_oracle_inventory(
            f"{schema_name}.{table_name}",
            environment, search, target_type, page, page_size
        )

    def _list_targets_from_fallback(self, environment: str | None = None,
                                    search: str | None = None,
                                    target_type: str | None = None,
                                    page: int = 1,
                                    page_size: int = 25) -> tuple[list[dict], int]:
        """
        List targets from DBOPS_INVENTORY fallback (synonym).

        Args:
            environment: Optional environment filter
            search: Optional search query
            target_type: Optional target type filter
            page: Page number
            page_size: Items per page

        Returns:
            Tuple of (list of target dicts, total count)
        """
        return self._read_oracle_inventory(
            'DBOPS_INVENTORY',
            environment, search, target_type, page, page_size
        )

    def _read_oracle_inventory(self, table_or_synonym: str,
                               environment: str | None = None,
                               search: str | None = None,
                               target_type: str | None = None,
                               page: int = 1,
                               page_size: int = 25) -> tuple[list[dict], int]:
        """
        Read inventory from Oracle table or synonym.
        Expected columns: NAME, ENVIRONMENT, TYPE.

        Args:
            table_or_synonym: Table name or synonym (e.g., 'DBOPS_INVENTORY')
            environment: Optional environment filter
            search: Optional search query
            target_type: Optional target type filter
            page: Page number
            page_size: Items per page

        Returns:
            Tuple of (list of target dicts, total count)

        Raises:
            InventoryServiceError: If table name is invalid or Oracle error occurs
        """
        correlation_id = get_correlation_id()

        # SECURITY: Validate table/synonym name to prevent SQL injection
        if not SAFE_TABLE_NAME_PATTERN.match(table_or_synonym):
            logger.error(
                "invalid_table_name_rejected",
                table_name=table_or_synonym,
                correlation_id=correlation_id
            )
            raise InventoryServiceError(
                f"Invalid table/synonym name: {table_or_synonym}. "
                "Must be alphanumeric with optional schema prefix."
            )

        # Build WHERE clause with named parameters
        conditions = []
        params = {}

        if environment:
            conditions.append("UPPER(ENVIRONMENT) = UPPER(:env)")
            params['env'] = environment
        if search:
            conditions.append("UPPER(NAME) LIKE UPPER(:search)")
            params['search'] = f'%{search}%'
        if target_type:
            conditions.append("UPPER(TYPE) = UPPER(:ttype)")
            params['ttype'] = target_type

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        # Count query
        # nosec B608 - table_or_synonym validated by SAFE_TABLE_NAME_PATTERN above
        count_sql = f"SELECT COUNT(*) FROM {table_or_synonym} {where_clause}"

        # Data query with pagination
        offset = (page - 1) * page_size
        params['offset'] = offset
        params['limit'] = page_size

        # nosec B608 - table_or_synonym validated by SAFE_TABLE_NAME_PATTERN above
        data_sql = f"""
            SELECT NAME, ENVIRONMENT, TYPE
            FROM {table_or_synonym}
            {where_clause}
            ORDER BY NAME
            OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
        """

        try:
            with connection.cursor() as cursor:
                # Get count (without pagination params)
                count_params = {k: v for k, v in params.items() if k not in ('offset', 'limit')}
                cursor.execute(count_sql, count_params)
                total_count = cursor.fetchone()[0]

                # Get data
                cursor.execute(data_sql, params)
                rows = cursor.fetchall()

            results = []
            for row in rows:
                # Story 21.1: Use raw environment values - inventory is source of truth
                # MEDIUM-1 FIX: Removed confusing "Oracle recursion" comment - no recursion here
                # Normalization moved to RBAC layer (Story 21.2) for case-insensitive matching
                raw_env = (row[1] or '').lower().strip()

                # Normalize target type (unchanged)
                raw_type = (row[2] or '').lower().strip()
                normalized_type = raw_type if raw_type in TargetType.VALUES else TargetType.SERVER

                results.append({
                    'name': row[0],
                    'environment': raw_env,
                    'target_type': normalized_type,
                    'metadata': None,
                })

            logger.info(
                "oracle_inventory_read",
                source=table_or_synonym,
                total=total_count,
                returned_count=len(results),
                correlation_id=correlation_id
            )

            return results, total_count

        except InventoryServiceError:
            # Re-raise our own exceptions
            raise
        except Exception as e:
            # Story 17.6: Justified broad catch - Oracle DB can raise various exceptions
            logger.error(
                "oracle_inventory_read_error",
                source=table_or_synonym,
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
                exc_info=True,
            )
            raise InventoryServiceError(
                f"Failed to read inventory from {table_or_synonym}: {str(e)}"
            )

    def list_targets_for_user(self, user_id: int, ad_groups: list[str],
                              environment: str | None = None,
                              search: str | None = None,
                              target_type: str | None = None,
                              page: int = 1,
                              page_size: int = 25) -> tuple[list[dict], int, bool]:
        """
        List targets filtered by user permissions (RBAC).
        Implements RM2-RM6 from business rules.

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
            rbac_truncated is True when inventory exceeds MAX_TARGETS_FOR_RBAC_FILTER (results may be incomplete).
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

        # Aggregate permissions from all profiles (RM6: cumul multi-profils)
        allowed_environments: set[str] = set()
        target_restrictions: list[tuple[str, list[str] | None]] = []
        has_all_access = False

        for profile in profiles:
            is_admin = getattr(profile, 'is_admin', 0) == 1

            # Story 21.2, Task 1.1: Build allowed_environments with both raw and normalized values
            # This allows matching targets with raw values (e.g., certif) against profiles with aliases
            action_perm = getattr(profile, 'profileactionpermission', None)
            if action_perm:
                envs = action_perm.get_environments()
                if envs:
                    for e in envs:
                        if isinstance(e, str):
                            raw_env = (e or '').strip().lower()
                            normalized_env = self._normalize_environment(e)
                            
                            # Add normalized value (for alias handling: certif -> staging)
                            allowed_environments.add(normalized_env)
                            
                            # Also add raw value to match targets with raw environments
                            # Example: profile has "certif" -> adds both "staging" and "certif"
                            if raw_env and raw_env != normalized_env:
                                allowed_environments.add(raw_env)
            elif is_admin:
                # Admin profiles without ProfileActionPermission: full environment access
                # Story 13.7: Get environments from inventory instead of hardcoded list
                try:
                    allowed_environments.update(self.list_environments())
                except InventoryServiceError:
                    # Fallback to default environments if inventory unavailable
                    allowed_environments.update(self.get_default_environments())

            # Get target permissions
            target_perm = getattr(profile, 'profiletargetpermission', None)
            if target_perm:
                perm_type = target_perm.permission_type
                if perm_type == 'ALL':
                    has_all_access = True
                elif perm_type == 'PATTERN':
                    patterns = target_perm.get_target_patterns()
                    if patterns:
                        target_restrictions.append(('PATTERN', patterns))
                elif perm_type == 'LIST':
                    names = target_perm.get_target_names()
                    if names:
                        target_restrictions.append(('LIST', names))
            elif is_admin:
                # Admin profiles without ProfileTargetPermission: full target access
                has_all_access = True

        # When admin profiles have actions_type=ALL but empty environments
        if not allowed_environments and any(getattr(p, 'is_admin', 0) == 1 for p in profiles):
            # Story 13.7: Get environments from inventory instead of hardcoded list
            try:
                allowed_environments = set(self.list_environments())
            except InventoryServiceError:
                # Fallback to default environments if inventory unavailable
                allowed_environments = set(self.get_default_environments())

        # Story 21.2, Task 1.3: Apply environment filter with case-insensitive matching
        if environment:
            env_lower = (environment or '').strip().lower()
            # Check if user has access to this environment (case-insensitive)
            allowed_lower = {e.lower() for e in allowed_environments}
            if env_lower not in allowed_lower:
                # User doesn't have access to this environment
                return [], 0, False
            # Filter to only this environment (keep case-insensitive matching)
            allowed_environments = {e for e in allowed_environments if e.lower() == env_lower}

        if not allowed_environments:
            logger.info(
                "no_allowed_environments",
                user_id=user_id,
                correlation_id=correlation_id
            )
            return [], 0, False

        # Story 23.2 AC4: Detect multi-table config and use list_servers if active
        mapper = self._get_inventory_mapper()
        use_multi_table = mapper is not None and mapper.is_multi_table

        if use_multi_table:
            # Multi-table path: use list_servers (no pagination, returns all for env)
            # We pass environment=None equivalent by loading all servers then filtering
            all_targets = []
            failed_envs = []
            for env in allowed_environments:
                try:
                    servers = self.list_servers(environment=env)
                    # Normalize to Target-like dicts for compatibility
                    for s in servers:
                        all_targets.append({
                            'name': s.get('name', ''),
                            'environment': s.get('environment', ''),
                            'target_type': 'server',
                            'metadata': None,
                        })
                except InventoryServiceError as e:
                    # Log and track failed environments
                    failed_envs.append(env)
                    logger.warning(
                        "list_servers_failed_for_env",
                        environment=env,
                        user_id=user_id,
                        error=str(e),
                        correlation_id=correlation_id,
                    )

            # If ALL environments failed, raise error instead of silent empty result
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

            total_available = len(all_targets)
            rbac_truncated = False

            logger.info(
                "rbac_using_multi_table_servers",
                user_id=user_id,
                environments_checked=len(allowed_environments),
                environments_failed=len(failed_envs),
                total_servers=total_available,
                correlation_id=correlation_id,
            )
        else:
            # Get targets from source for RBAC filtering (legacy path)
            # NOTE: RBAC filtering is done in-memory. For large inventories (>5000),
            # consider implementing server-side RBAC filtering in the SQL query.
            all_targets, total_available = self.list_targets(
                environment=None,  # We'll filter ourselves
                search=search,
                target_type=target_type,
                page=1,
                page_size=MAX_TARGETS_FOR_RBAC_FILTER
            )
            rbac_truncated = total_available > MAX_TARGETS_FOR_RBAC_FILTER

        if total_available > MAX_TARGETS_FOR_RBAC_FILTER and not use_multi_table:
            logger.warning(
                "rbac_filter_truncated",
                total_available=total_available,
                max_loaded=MAX_TARGETS_FOR_RBAC_FILTER,
                user_id=user_id,
                correlation_id=correlation_id,
                message="Inventory too large for in-memory RBAC filtering. Results may be incomplete."
            )

        # Story 21.2, Task 1.2: Filter by environment with case-insensitive comparison
        allowed_environments_lower = {e.lower() for e in allowed_environments}
        filtered_targets = [
            t for t in all_targets
            if (t.get('environment') or '').lower() in allowed_environments_lower
        ]
        env_filtered_count = len(filtered_targets)

        # Filter by target restrictions (union of all profile permissions)
        restriction_type = 'ALL' if has_all_access else (
            'MIXED' if target_restrictions else 'NONE'
        )
        if not has_all_access and target_restrictions:
            filtered_targets = self._apply_target_restrictions(
                filtered_targets, target_restrictions
            )

        # Pagination (Story 22.6: renamed total_count → total)
        total = len(filtered_targets)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        page_results = filtered_targets[start_index:end_index]
        # rbac_truncated already set above (multi-table: always False, legacy: based on count)

        # RBAC traceability log (Story 13.3, Subtask 1.5) - single consolidated log
        logger.info(
            "rbac_targets_filtered",
            user_id=user_id,
            allowed_environments=sorted(allowed_environments),
            restriction_type=restriction_type,
            restriction_count=len(target_restrictions) if target_restrictions else 0,
            has_all_access=has_all_access,
            total_before_filter=len(all_targets),
            after_env_filter=env_filtered_count,
            after_target_filter=len(filtered_targets),
            total=total,
            returned_count=len(page_results),
            rbac_truncated=rbac_truncated,
            correlation_id=correlation_id
        )

        return page_results, total, rbac_truncated

    def _apply_target_restrictions(self, targets: list[dict],
                                   restrictions: list[tuple[str, list[str] | None]]) -> list[dict]:
        """
        Apply target restrictions (union of patterns and lists).

        Args:
            targets: List of target dicts
            restrictions: List of (type, values) tuples

        Returns:
            Filtered list of targets matching any restriction
        """
        result = []
        for target in targets:
            target_name = target['name']
            matches = False

            for perm_type, values in restrictions:
                if values is None:
                    continue

                if perm_type == 'LIST':
                    # Case-insensitive match for consistency with PATTERN (AC3)
                    values_lower = [v.lower() for v in values if isinstance(v, str)]
                    if target_name.lower() in values_lower:
                        matches = True
                        break
                elif perm_type == 'PATTERN':
                    for pattern in values:
                        if fnmatch.fnmatch(target_name.lower(), pattern.lower()):
                            matches = True
                            break
                    if matches:
                        break

            if matches:
                result.append(target)

        return result

    def _normalize_environment(self, raw_env: str) -> str:
        """
        Normalize environment value from external sources.
        Handles legacy aliases like 'certif' -> 'staging'.
        
        Story 21.1: Simplified to only apply aliases without recursion.
        Inventory is the source of truth - unknown values are returned as-is.

        Args:
            raw_env: Raw environment string

        Returns:
            Normalized environment value (alias applied or raw value)
        """
        # Environment aliases mapping (legacy compatibility)
        env_aliases = {
            'certif': 'staging',
            'certification': 'staging',
            'stg': 'staging',
            'development': 'dev',
            'production': 'prod',
        }

        # Normalize input
        normalized = (raw_env or '').strip().lower()
        
        # Apply alias if exists
        if normalized in env_aliases:
            return env_aliases[normalized]
        
        # Return raw value - inventory is source of truth
        return normalized

    def get_allowed_environments_for_user(self, ad_groups: list[str]) -> set[str]:
        """
        Get allowed environments for a user based on their profiles.
        
        Story 21.2, Task 2.1: Returns both raw and normalized values for consistency
        with list_targets_for_user RBAC filtering.
        
        MEDIUM-2 FIX: This method returns a set that may contain both the normalized
        form and raw form of aliased environments. For example, a profile with
        ["certif"] will return {"staging", "certif"} because certif normalizes to staging.

        Args:
            ad_groups: User's AD groups

        Returns:
            Set of allowed environment values (includes both raw and normalized).
            Example: profile with ["certif", "lab"] returns {"staging", "certif", "lab"}
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
                            raw_env = (e or '').strip().lower()
                            normalized_env = self._normalize_environment(e)
                            
                            # Add normalized value (for alias handling)
                            allowed_environments.add(normalized_env)
                            
                            # Also add raw value for consistency with RBAC filtering
                            if raw_env and raw_env != normalized_env:
                                allowed_environments.add(raw_env)

        return allowed_environments

    def list_environments(self) -> list[str]:
        """
        List distinct environments from inventory.
        Story 21.1: Returns raw environment values from inventory (e.g., dev, lab, staging, prod, certif).
        Story 13.7 - AC2: Source of truth for environments is inventory.
        Uses cache to prevent duplicate Oracle queries.

        Returns:
            List of distinct environment values (raw, not normalized)
        """
        correlation_id = get_correlation_id()
        
        # Check cache first
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
        
        integration = self.get_active_inventory_integration()

        # Get targets without filters to extract all environments
        targets, _ = self.list_targets(
            environment=None,
            search=None,
            target_type=None,
            page=1,
            page_size=10000  # Large page size to get all targets
        )

        # Extract distinct environments (normalized)
        environments = set()
        for target in targets:
            env = target.get('environment')
            if env:
                environments.add(env)

        # Sort for consistent ordering
        result = sorted(environments)

        # Cache result
        _environments_cache[cache_key] = result

        logger.info(
            "environments_listed",
            count=len(result),
            environments=result,
            correlation_id=correlation_id
        )

        return result

    def get_default_environments(self) -> list[str]:
        """
        Get default environment values as fallback when inventory is unavailable.
        Story 13.7 - Fallback to standard values if inventory service fails.

        Returns:
            List of default environment values (dev, staging, prod)
        """
        return ['dev', 'staging', 'prod']

    # --- Story 23.2: Public multi-table inventory methods ---

    def list_servers(
        self,
        environment: str,
        engine_type: str | None = None,
    ) -> list[dict]:
        """
        List servers from multi-table inventory or flat table fallback.

        Performance Note:
            Results are limited to MAX_MULTI_TABLE_RESULTS (10000).
            A warning is logged if this limit is reached.

        Args:
            environment: Target environment (required)
            engine_type: Optional filter by engine type (oracle, sqlserver, etc.)

        Returns:
            List of server dicts: [{ id, name, environment, engine_type? }]

        Raises:
            InventoryServiceError: If inventory source is unreachable or config invalid
            ValueError: If environment is empty
        """
        if not environment or not environment.strip():
            raise ValueError("environment is required")

        correlation_id = get_correlation_id()

        try:
            servers = self._read_servers_from_config(environment, engine_type)

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

        except (InventoryServiceError, ValueError):
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

        Security Note:
            This method does NOT apply RBAC filtering. The caller (API layer)
            is responsible for:
            1. Validating that user has access to specified server_name(s)
            2. Only passing server_name(s) from the user's allowed servers list
            3. Calling list_targets_for_user first to get allowed servers

        Performance Note:
            Results are limited to MAX_MULTI_TABLE_RESULTS (10000) per query.
            A warning is logged if this limit is reached.

        Args:
            environment: Target environment (required)
            server_name: Filter by single server (exclusive with server_names)
            server_names: Filter by multiple servers (exclusive with server_name)

        Returns:
            List of instance dicts: [{ id, name, environment, server_ref, db_ref? }]

        Raises:
            InventoryServiceError: If inventory source is unreachable or config invalid
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
                # Multiple server filter: use optimized IN clause via _read_instances_from_config_multi
                result = self._read_instances_from_config_multi(environment, server_names)
            else:
                result = self._read_instances_from_config(environment, server_name=server_name)

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

        except (InventoryServiceError, ValueError):
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

        Security Note:
            This method does NOT apply RBAC filtering. The caller (API layer)
            is responsible for:
            1. Validating that user has access to specified server_name(s)
            2. Only passing server_name(s) from the user's allowed servers list
            3. Calling list_targets_for_user first to get allowed servers

        Performance Note:
            Results are limited to MAX_MULTI_TABLE_RESULTS (10000) per query.
            A warning is logged if this limit is reached.

        Args:
            environment: Target environment (required)
            server_name: Filter by single server (exclusive with server_names)
            server_names: Filter by multiple servers (exclusive with server_name)

        Returns:
            List of database dicts: [{ id, name, environment }]

        Raises:
            InventoryServiceError: If inventory source is unreachable or config invalid
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
                # Multiple server filter: use optimized IN clause via _read_databases_from_config_multi
                result = self._read_databases_from_config_multi(environment, server_names)
            else:
                result = self._read_databases_from_config(environment, server_name=server_name)

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

        except (InventoryServiceError, ValueError):
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

    # --- Story 23.1: Config-driven multi-table entity reading ---

    def _get_inventory_mapper(self) -> InventoryMapper | None:
        """
        Get InventoryMapper from active inventory_db integration config.

        Returns:
            InventoryMapper instance or None if no inventory_db integration
        """
        integration = Integration.objects.get_by_type(IntegrationType.INVENTORY_DB)
        if not integration:
            return None
        config = integration.get_config() or {}
        return InventoryMapper(config)

    def _read_servers_from_config(
        self,
        environment: str | None = None,
        engine_type: str | None = None,
    ) -> list[dict]:
        """
        Read servers from config-driven multi-table or flat table fallback.
        Story 23.1 AC3: Uses mapped table/columns for servers entity.

        Args:
            environment: Optional environment filter
            engine_type: Optional engine type filter (Oracle, SQL Server, etc.)

        Returns:
            List of dicts with standardized keys (id, name, environment, engine_type)
        """
        correlation_id = get_correlation_id()
        mapper = self._get_inventory_mapper()

        if mapper is None or not mapper.is_multi_table:
            # AC6 Fallback: use flat table with TYPE=server filter
            return self._read_servers_flat_fallback(environment)

        try:
            table = mapper.get_table_name('servers')
            select = mapper.build_select_clause('servers')

            filters = {}
            if environment:
                filters['environment'] = environment
            if engine_type:
                filters['engine_type'] = engine_type

            where_clause, params = mapper.build_where_clause('servers', filters)

            # nosec B608 - table/columns validated by mapper via _validate_table_name/_validate_column_name
            # Oracle subquery pattern to combine ORDER BY + ROWNUM limit (防止 DoS)
            inner_sql = f"SELECT {select} FROM {table}"
            if where_clause:
                inner_sql += f" WHERE {where_clause}"
            inner_sql += " ORDER BY name"
            sql = f"SELECT * FROM ({inner_sql}) WHERE ROWNUM <= {MAX_MULTI_TABLE_RESULTS}"

            logger.info(
                "reading_servers_from_config",
                table=table,
                has_env_filter=bool(environment),
                has_engine_filter=bool(engine_type),
                correlation_id=correlation_id,
            )

            return self._execute_mapped_query(sql, params)

        except MapperValidationError as e:
            logger.error(
                "server_config_mapping_error",
                error=str(e),
                correlation_id=correlation_id,
            )
            raise InventoryServiceError(f"Server mapping config error: {e}")
        except Exception as e:
            logger.error(
                "read_servers_from_config_error",
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
                exc_info=True,
            )
            raise InventoryServiceError(f"Failed to read servers: {e}")

    def _read_instances_from_config(
        self,
        environment: str | None = None,
        server_name: str | None = None,
    ) -> list[dict]:
        """
        Read instances from config-driven multi-table mapping.
        Story 23.1 AC4: Filters on server_ref column if server_name provided.

        Args:
            environment: Optional environment filter
            server_name: Optional server name to filter instances by

        Returns:
            List of dicts with standardized keys (id, name, environment, server_ref, db_ref)
        """
        correlation_id = get_correlation_id()
        mapper = self._get_inventory_mapper()

        if mapper is None or not mapper.is_multi_table:
            # AC6 Fallback: flat table mode - no instance concept
            logger.info(
                "instances_flat_fallback",
                reason="no multi-table config",
                correlation_id=correlation_id,
            )
            return []

        entity_config = mapper.get_entity_config('instances')
        if not entity_config:
            logger.info(
                "instances_entity_not_configured",
                correlation_id=correlation_id,
            )
            return []

        try:
            table = mapper.get_table_name('instances')
            select = mapper.build_select_clause('instances')

            filters = {}
            if environment:
                filters['environment'] = environment
            if server_name:
                filters['server_ref'] = server_name

            where_clause, params = mapper.build_where_clause('instances', filters)

            # nosec B608 - table/columns validated by mapper via _validate_table_name/_validate_column_name
            # Oracle subquery pattern to combine ORDER BY + ROWNUM limit (防止 DoS)
            inner_sql = f"SELECT {select} FROM {table}"
            if where_clause:
                inner_sql += f" WHERE {where_clause}"
            inner_sql += " ORDER BY name"
            sql = f"SELECT * FROM ({inner_sql}) WHERE ROWNUM <= {MAX_MULTI_TABLE_RESULTS}"

            logger.info(
                "reading_instances_from_config",
                table=table,
                has_env_filter=bool(environment),
                has_server_filter=bool(server_name),
                correlation_id=correlation_id,
            )

            return self._execute_mapped_query(sql, params)

        except MapperValidationError as e:
            logger.error(
                "instance_config_mapping_error",
                error=str(e),
                correlation_id=correlation_id,
            )
            raise InventoryServiceError(f"Instance mapping config error: {e}")
        except Exception as e:
            logger.error(
                "read_instances_from_config_error",
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
                exc_info=True,
            )
            raise InventoryServiceError(f"Failed to read instances: {e}")

    def _read_instances_from_config_multi(
        self,
        environment: str,
        server_names: list[str],
    ) -> list[dict]:
        """
        Read instances from multi-table config filtered by multiple servers using IN clause.
        Optimized version of _read_instances_from_config for server_names parameter.

        Args:
            environment: Target environment (required)
            server_names: List of server names to filter by (non-empty)

        Returns:
            List of instance dicts (deduplicated by id+name)
        """
        correlation_id = get_correlation_id()
        mapper = self._get_inventory_mapper()

        if mapper is None or not mapper.is_multi_table:
            return []

        entity_config = mapper.get_entity_config('instances')
        if not entity_config:
            return []

        try:
            table = mapper.get_table_name('instances')
            select = mapper.build_select_clause('instances')
            server_ref_col = mapper.get_column('instances', 'server_ref')
            env_col = mapper.get_column('instances', 'environment')

            # Build IN clause with bind parameters
            in_params = {f'p_server_{i}': sn for i, sn in enumerate(server_names)}
            in_placeholders = ', '.join(f":{key}" for key in in_params.keys())

            params = {**in_params, 'p_environment': environment}

            # nosec B608 - table/columns validated by mapper
            inner_sql = (
                f"SELECT {select} FROM {table} "
                f"WHERE UPPER({env_col}) = UPPER(:p_environment) "
                f"AND UPPER({server_ref_col}) IN ({in_placeholders}) "
                f"ORDER BY name"
            )
            sql = f"SELECT * FROM ({inner_sql}) WHERE ROWNUM <= {MAX_MULTI_TABLE_RESULTS}"

            logger.info(
                "reading_instances_from_config_multi",
                table=table,
                server_count=len(server_names),
                correlation_id=correlation_id,
            )

            return self._execute_mapped_query(sql, params)

        except MapperValidationError as e:
            logger.error(
                "instance_config_mapping_error",
                error=str(e),
                correlation_id=correlation_id,
            )
            raise InventoryServiceError(f"Instance mapping config error: {e}")
        except Exception as e:
            logger.error(
                "read_instances_from_config_multi_error",
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
                exc_info=True,
            )
            raise InventoryServiceError(f"Failed to read instances: {e}")

    def _read_databases_from_config(
        self,
        environment: str | None = None,
        server_name: str | None = None,
    ) -> list[dict]:
        """
        Read databases from config-driven multi-table mapping.
        Story 23.1 AC5: If server_name provided, joins via instances to find related DBs.

        Args:
            environment: Optional environment filter
            server_name: Optional server name to filter databases via instance relations

        Returns:
            List of dicts with standardized keys (id, name, environment)
        """
        correlation_id = get_correlation_id()
        mapper = self._get_inventory_mapper()

        if mapper is None or not mapper.is_multi_table:
            # AC6 Fallback: flat table mode - no database entity concept
            logger.info(
                "databases_flat_fallback",
                reason="no multi-table config",
                correlation_id=correlation_id,
            )
            return []

        entity_config = mapper.get_entity_config('databases')
        if not entity_config:
            logger.info(
                "databases_entity_not_configured",
                correlation_id=correlation_id,
            )
            return []

        try:
            db_table = mapper.get_table_name('databases')
            db_select = mapper.build_select_clause('databases')

            if server_name and mapper.get_entity_config('instances'):
                # AC5: Join via instances to find DBs related to server
                return self._read_databases_via_instances(
                    mapper, environment, server_name
                )

            # Simple query without server filter
            filters = {}
            if environment:
                filters['environment'] = environment

            where_clause, params = mapper.build_where_clause('databases', filters)

            # nosec B608 - table/columns validated by mapper via _validate_table_name/_validate_column_name
            # Oracle subquery pattern to combine ORDER BY + ROWNUM limit (防止 DoS)
            inner_sql = f"SELECT {db_select} FROM {db_table}"
            if where_clause:
                inner_sql += f" WHERE {where_clause}"
            inner_sql += " ORDER BY name"
            sql = f"SELECT * FROM ({inner_sql}) WHERE ROWNUM <= {MAX_MULTI_TABLE_RESULTS}"

            logger.info(
                "reading_databases_from_config",
                table=db_table,
                has_env_filter=bool(environment),
                correlation_id=correlation_id,
            )

            return self._execute_mapped_query(sql, params)

        except MapperValidationError as e:
            logger.error(
                "database_config_mapping_error",
                error=str(e),
                correlation_id=correlation_id,
            )
            raise InventoryServiceError(f"Database mapping config error: {e}")
        except Exception as e:
            logger.error(
                "read_databases_from_config_error",
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
                exc_info=True,
            )
            raise InventoryServiceError(f"Failed to read databases: {e}")

    def _read_databases_via_instances(
        self,
        mapper: InventoryMapper,
        environment: str | None,
        server_name: str,
    ) -> list[dict]:
        """
        Read databases by joining through instances table.
        Uses instance.server_ref = server_name AND instance.db_ref = db.name.

        Args:
            mapper: Configured InventoryMapper
            environment: Optional environment filter
            server_name: Server name to filter by

        Returns:
            List of database dicts
        """
        correlation_id = get_correlation_id()

        db_table = mapper.get_table_name('databases')
        inst_table = mapper.get_table_name('instances')
        db_name_col = mapper.get_column('databases', 'name')
        inst_db_ref_col = mapper.get_column('instances', 'db_ref')
        inst_server_ref_col = mapper.get_column('instances', 'server_ref')
        db_select = mapper.build_select_clause('databases')

        # Prefix DB columns with alias 'd'
        aliased_select = db_select.replace(
            mapper.get_column('databases', 'name'),
            f"d.{mapper.get_column('databases', 'name')}",
            1,
        )
        # Replace other DB columns with 'd.' prefix
        for concept, col in (mapper.get_entity_config('databases') or {}).get('columns', {}).items():
            aliased_select = aliased_select.replace(col, f"d.{col}")
        id_col = (mapper.get_entity_config('databases') or {}).get('id_column')
        if id_col:
            aliased_select = aliased_select.replace(id_col, f"d.{id_col}")

        # nosec B608 - all identifiers validated by mapper via _validate_table_name/_validate_column_name
        # Oracle subquery pattern to combine ORDER BY + ROWNUM limit (防止 DoS)
        inner_sql = (
            f"SELECT DISTINCT {aliased_select} "
            f"FROM {db_table} d "
            f"INNER JOIN {inst_table} i ON UPPER(i.{inst_db_ref_col}) = UPPER(d.{db_name_col}) "
            f"WHERE UPPER(i.{inst_server_ref_col}) = UPPER(:p_server_name)"
        )
        params = {'p_server_name': server_name}

        if environment:
            db_env_col = mapper.get_column('databases', 'environment')
            inner_sql += f" AND UPPER(d.{db_env_col}) = UPPER(:p_environment)"
            params['p_environment'] = environment

        inner_sql += f" ORDER BY d.{db_name_col}"
        sql = f"SELECT * FROM ({inner_sql}) WHERE ROWNUM <= {MAX_MULTI_TABLE_RESULTS}"

        logger.info(
            "reading_databases_via_instances",
            db_table=db_table,
            inst_table=inst_table,
            server_name=server_name,
            has_env_filter=bool(environment),
            correlation_id=correlation_id,
        )

        return self._execute_mapped_query(sql, params)

    def _read_databases_from_config_multi(
        self,
        environment: str,
        server_names: list[str],
    ) -> list[dict]:
        """
        Read databases from multi-table config filtered by multiple servers using IN clause.
        Optimized version using JOIN with instances + IN for server_names.

        Args:
            environment: Target environment (required)
            server_names: List of server names to filter by (non-empty)

        Returns:
            List of database dicts (deduplicated by id+name)
        """
        correlation_id = get_correlation_id()
        mapper = self._get_inventory_mapper()

        if mapper is None or not mapper.is_multi_table:
            return []

        entity_config = mapper.get_entity_config('databases')
        if not entity_config or not mapper.get_entity_config('instances'):
            return []

        try:
            db_table = mapper.get_table_name('databases')
            inst_table = mapper.get_table_name('instances')
            db_name_col = mapper.get_column('databases', 'name')
            db_env_col = mapper.get_column('databases', 'environment')
            inst_db_ref_col = mapper.get_column('instances', 'db_ref')
            inst_server_ref_col = mapper.get_column('instances', 'server_ref')
            db_select = mapper.build_select_clause('databases')

            # Prefix DB columns with alias 'd'
            aliased_select = db_select
            for concept, col in entity_config.get('columns', {}).items():
                aliased_select = aliased_select.replace(col, f"d.{col}")
            id_col = entity_config.get('id_column')
            if id_col:
                aliased_select = aliased_select.replace(id_col, f"d.{id_col}")

            # Build IN clause with bind parameters
            in_params = {f'p_server_{i}': sn for i, sn in enumerate(server_names)}
            in_placeholders = ', '.join(f":{key}" for key in in_params.keys())

            params = {**in_params, 'p_environment': environment}

            # nosec B608 - table/columns validated by mapper
            inner_sql = (
                f"SELECT DISTINCT {aliased_select} "
                f"FROM {db_table} d "
                f"INNER JOIN {inst_table} i ON UPPER(i.{inst_db_ref_col}) = UPPER(d.{db_name_col}) "
                f"WHERE UPPER(d.{db_env_col}) = UPPER(:p_environment) "
                f"AND UPPER(i.{inst_server_ref_col}) IN ({in_placeholders}) "
                f"ORDER BY d.{db_name_col}"
            )
            sql = f"SELECT * FROM ({inner_sql}) WHERE ROWNUM <= {MAX_MULTI_TABLE_RESULTS}"

            logger.info(
                "reading_databases_from_config_multi",
                db_table=db_table,
                inst_table=inst_table,
                server_count=len(server_names),
                correlation_id=correlation_id,
            )

            return self._execute_mapped_query(sql, params)

        except MapperValidationError as e:
            logger.error(
                "database_config_mapping_error",
                error=str(e),
                correlation_id=correlation_id,
            )
            raise InventoryServiceError(f"Database mapping config error: {e}")
        except Exception as e:
            logger.error(
                "read_databases_from_config_multi_error",
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
                exc_info=True,
            )
            raise InventoryServiceError(f"Failed to read databases: {e}")

    def _read_servers_flat_fallback(self, environment: str | None = None) -> list[dict]:
        """
        Fallback: read servers from flat table (TYPE=server filter).
        Story 23.1 AC6.

        Args:
            environment: Optional environment filter

        Returns:
            List of server dicts with standardized keys
        """
        correlation_id = get_correlation_id()

        logger.info(
            "reading_servers_flat_fallback",
            correlation_id=correlation_id,
        )

        targets, _ = self._read_oracle_inventory(
            'DBOPS_INVENTORY',
            environment=environment,
            target_type='server',
            page=1,
            page_size=MAX_FLAT_TABLE_RESULTS,
        )
        # Map flat results to standardized format
        return [
            {
                'id': t.get('name', ''),
                'name': t.get('name', ''),
                'environment': t.get('environment', ''),
                'engine_type': None,
            }
            for t in targets
        ]

    def _execute_mapped_query(self, sql: str, params: dict) -> list[dict]:
        """
        Execute a mapped SQL query and return results as list of dicts.
        Column aliases from SELECT clause become dict keys.

        Args:
            sql: SQL query string with named bind parameters
            params: Bind parameter dict

        Returns:
            List of dicts with column alias as keys
        """
        correlation_id = get_correlation_id()

        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                columns = [col[0].lower() for col in cursor.description]
                rows = cursor.fetchall()

            results = [dict(zip(columns, row)) for row in rows]

            logger.info(
                "mapped_query_executed",
                result_count=len(results),
                correlation_id=correlation_id,
            )

            return results

        except InventoryServiceError:
            raise
        except Exception as e:
            logger.error(
                "mapped_query_execution_error",
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
                exc_info=True,
            )
            raise InventoryServiceError(f"Query execution failed: {e}")
