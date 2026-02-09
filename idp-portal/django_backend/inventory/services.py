"""
InventoryService for inventory source resolution and target retrieval.
Story 13.1 - AC1,2: Source inventaire via intégration, fallback DBOPS_INVENTORY.
No local DB table - reads directly from external sources.
"""

import fnmatch
import re
import structlog
from cachetools import TTLCache

from django.db import connection

from integrations.models import Integration, IntegrationType
from inventory.models import Target, TargetEnvironment, TargetType
from profiles.models import Profile
from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)

# Cache for environments list (TTL 5 minutes to match catalog cache)
_environments_cache: TTLCache[str, list[str]] = TTLCache(maxsize=1, ttl=300)

# Maximum targets to load for in-memory RBAC filtering
MAX_TARGETS_FOR_RBAC_FILTER = 5000

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

        # Get targets from source for RBAC filtering
        # NOTE: RBAC filtering is done in-memory. For large inventories (>5000),
        # consider implementing server-side RBAC filtering in the SQL query.
        all_targets, total_available = self.list_targets(
            environment=None,  # We'll filter ourselves
            search=search,
            target_type=target_type,
            page=1,
            page_size=MAX_TARGETS_FOR_RBAC_FILTER
        )

        if total_available > MAX_TARGETS_FOR_RBAC_FILTER:
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
        rbac_truncated = total_available > MAX_TARGETS_FOR_RBAC_FILTER

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
