"""
InventoryQueryExecutor: Executes config-driven SQL queries for inventory data.

Responsibility: Execute HOW to read inventory data (SQL queries, mapping, validation).
Story 26.1 - AC1, AC3: Separation of concerns + unification of _read_*_from_config methods.
"""

from __future__ import annotations

import re
from typing import Literal

import structlog
from django.db import DatabaseError, InterfaceError

from inventory.mapper import InventoryMapper, MapperValidationError
from integrations.models import Integration, IntegrationType
from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)


def _get_connection():
    """
    Get the Django DB connection, resolving at call time to support test patching.

    Tests patch 'inventory.services.connection', so we access connection through
    the services module when available, falling back to django.db.connection.
    This ensures backward compatibility with existing test infrastructure.

    Returns:
        Django database connection instance.
    """
    from django.db.backends.base.base import BaseDatabaseWrapper
    import inventory.services as svc_module
    conn: BaseDatabaseWrapper = svc_module.connection
    return conn

# Maximum results from multi-table config queries (prevent DoS via unbounded queries)
# Story 23.1 code review fix: prevent out-of-memory from million-row tables
MAX_MULTI_TABLE_RESULTS = 10000

# Maximum results from flat table fallback
MAX_FLAT_TABLE_RESULTS = 10000

# Whitelist of allowed table/synonym names pattern (alphanumeric, underscore, dot for schema.table)
SAFE_TABLE_NAME_PATTERN = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$')


class InventoryServiceError(Exception):
    """Exception raised when inventory service encounters an error."""
    pass


class InventoryQueryExecutor:
    """
    Executes config-driven SQL queries for inventory entities.

    Handles:
    - Multi-table config-driven queries (servers, instances, databases)
    - Flat table fallback (DBOPS_INVENTORY)
    - SQL query construction, validation, and execution
    - Column mapping via InventoryMapper

    Story 26.1 - AC1, AC3: Extracted from InventoryService, unified _read_*_from_config methods.
    """

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

    def execute_mapped_query(self, sql: str, params: dict) -> list[dict]:
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
            with _get_connection().cursor() as cursor:
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

    def read_oracle_inventory(
        self,
        table_or_synonym: str,
        environment: str | None = None,
        search: str | None = None,
        target_type: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> tuple[list[dict], int]:
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
        from inventory.models import TargetType as TargetTypeEnum

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
            with _get_connection().cursor() as cursor:
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
                raw_env = (row[1] or '').lower().strip()

                # Normalize target type (unchanged)
                raw_type = (row[2] or '').lower().strip()
                normalized_type = raw_type if raw_type in TargetTypeEnum.VALUES else TargetTypeEnum.SERVER

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

    def _read_entity_from_config(
        self,
        entity_type: Literal['server', 'instance', 'database'],
        environment: str | None = None,
        engine_type: str | None = None,
        server_name: str | None = None,
        server_names: list[str] | None = None,
    ) -> list[dict]:
        """
        Generic config-driven entity reader. Unifies the 6 former _read_*_from_config methods.

        Reads entities (servers, instances, databases) from multi-table inventory config
        using InventoryMapper for column mapping and SQL generation.

        Args:
            entity_type: Type of entity to read ('server', 'instance', 'database')
            environment: Optional environment filter
            engine_type: Optional engine type filter (servers only)
            server_name: Optional single server name filter (instances/databases)
            server_names: Optional multiple server names for IN clause (instances/databases)

        Returns:
            List of dicts mapped by InventoryMapper

        Raises:
            InventoryServiceError: If config invalid or query fails

        Story 26.1 - AC3: Unifies _read_servers/instances/databases_from_config[_multi].
        """
        correlation_id = get_correlation_id()
        entity_plural = f"{entity_type}s" if entity_type != 'database' else 'databases'
        mapper = self._get_inventory_mapper()

        if mapper is None or not mapper.is_multi_table:
            if entity_type == 'server':
                return self._read_servers_flat_fallback(environment)
            logger.info(
                f"{entity_plural}_flat_fallback",
                reason="no multi-table config",
                correlation_id=correlation_id,
            )
            return []

        entity_config = mapper.get_entity_config(entity_plural)
        if not entity_config:
            if entity_type == 'server':
                return self._read_servers_flat_fallback(environment)
            logger.info(
                f"{entity_plural}_entity_not_configured",
                correlation_id=correlation_id,
            )
            return []

        try:
            # Database with server_name filter: join via instances
            if entity_type == 'database' and server_name and mapper.get_entity_config('instances'):
                return self._read_databases_via_instances(mapper, environment, server_name)

            # Multi-server IN clause path (instances or databases)
            if server_names:
                return self._read_entity_multi_server(
                    mapper, entity_plural, environment, server_names
                )

            # Standard single-entity query
            table = mapper.get_table_name(entity_plural)
            select = mapper.build_select_clause(entity_plural)

            filters = {}
            if environment:
                filters['environment'] = environment
            if engine_type and entity_type == 'server':
                filters['engine_type'] = engine_type
            if server_name and entity_type in ('instance',):
                filters['server_ref'] = server_name

            where_clause, params = mapper.build_where_clause(entity_plural, filters)

            # nosec B608 - table/columns validated by mapper
            inner_sql = f"SELECT {select} FROM {table}"
            if where_clause:
                inner_sql += f" WHERE {where_clause}"
            inner_sql += " ORDER BY name"
            sql = f"SELECT * FROM ({inner_sql}) WHERE ROWNUM <= {MAX_MULTI_TABLE_RESULTS}"

            logger.info(
                f"reading_{entity_plural}_from_config",
                table=table,
                has_env_filter=bool(environment),
                has_engine_filter=bool(engine_type),
                has_server_filter=bool(server_name),
                correlation_id=correlation_id,
            )

            return self.execute_mapped_query(sql, params)

        except MapperValidationError as e:
            logger.error(
                f"{entity_type}_config_mapping_error",
                error=str(e),
                correlation_id=correlation_id,
            )
            raise InventoryServiceError(f"{entity_type.capitalize()} mapping config error: {e}")
        except InventoryServiceError:
            raise InventoryServiceError(
                f"Failed to read {entity_plural} from {mapper.get_table_name(entity_plural)}"
            )
        except (DatabaseError, InterfaceError) as e:
            logger.error(
                f"read_{entity_plural}_from_config_db_error",
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
                exc_info=True,
            )
            raise InventoryServiceError(f"Database error reading {entity_plural}: {e}")
        except Exception as e:
            logger.error(
                f"read_{entity_plural}_from_config_error",
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
                exc_info=True,
            )
            raise InventoryServiceError(f"Failed to read {entity_plural}: {e}")

    def _read_entity_multi_server(
        self,
        mapper: InventoryMapper,
        entity_plural: str,
        environment: str,
        server_names: list[str],
    ) -> list[dict]:
        """
        Read entities filtered by multiple server names using IN clause.

        Args:
            mapper: Configured InventoryMapper
            entity_plural: Entity name ('instances' or 'databases')
            environment: Target environment
            server_names: List of server names

        Returns:
            List of entity dicts
        """
        correlation_id = get_correlation_id()

        if entity_plural == 'databases':
            return self._read_databases_multi_server(mapper, environment, server_names)

        # Instances multi-server path
        table = mapper.get_table_name(entity_plural)
        select = mapper.build_select_clause(entity_plural)
        server_ref_col = mapper.get_column(entity_plural, 'server_ref')
        env_col = mapper.get_column(entity_plural, 'environment')

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
            f"reading_{entity_plural}_from_config_multi",
            table=table,
            server_count=len(server_names),
            correlation_id=correlation_id,
        )

        return self.execute_mapped_query(sql, params)

    def _read_databases_multi_server(
        self,
        mapper: InventoryMapper,
        environment: str,
        server_names: list[str],
    ) -> list[dict]:
        """
        Read databases filtered by multiple servers via JOIN with instances.

        Args:
            mapper: Configured InventoryMapper
            environment: Target environment
            server_names: List of server names

        Returns:
            List of database dicts
        """
        correlation_id = get_correlation_id()

        entity_config = mapper.get_entity_config('databases')
        if not entity_config or not mapper.get_entity_config('instances'):
            return []

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

        return self.execute_mapped_query(sql, params)

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

        entity_config = mapper.get_entity_config('databases') or {}

        # Prefix DB columns with alias 'd'
        aliased_select = db_select.replace(
            mapper.get_column('databases', 'name'),
            f"d.{mapper.get_column('databases', 'name')}",
            1,
        )
        for concept, col in entity_config.get('columns', {}).items():
            aliased_select = aliased_select.replace(col, f"d.{col}")
        id_col = entity_config.get('id_column')
        if id_col:
            aliased_select = aliased_select.replace(id_col, f"d.{id_col}")

        # nosec B608 - all identifiers validated by mapper
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

        return self.execute_mapped_query(sql, params)

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

        targets, _ = self.read_oracle_inventory(
            'DBOPS_INVENTORY',
            environment=environment,
            target_type='server',
            page=1,
            page_size=MAX_FLAT_TABLE_RESULTS,
        )
        return [
            {
                'id': t.get('name', ''),
                'name': t.get('name', ''),
                'environment': t.get('environment', ''),
                'engine_type': None,
            }
            for t in targets
        ]

    # --- Public convenience methods ---

    def read_servers(
        self,
        environment: str | None = None,
        engine_type: str | None = None,
    ) -> list[dict]:
        """
        Read servers from config-driven multi-table or flat table fallback.

        Args:
            environment: Optional environment filter
            engine_type: Optional engine type filter

        Returns:
            List of server dicts
        """
        return self._read_entity_from_config('server', environment=environment, engine_type=engine_type)

    def read_instances(
        self,
        environment: str | None = None,
        server_name: str | None = None,
        server_names: list[str] | None = None,
    ) -> list[dict]:
        """
        Read instances from config-driven multi-table mapping.

        Args:
            environment: Optional environment filter
            server_name: Optional single server name filter
            server_names: Optional multiple server names for IN clause

        Returns:
            List of instance dicts
        """
        return self._read_entity_from_config(
            'instance', environment=environment,
            server_name=server_name, server_names=server_names,
        )

    def read_databases(
        self,
        environment: str | None = None,
        server_name: str | None = None,
        server_names: list[str] | None = None,
    ) -> list[dict]:
        """
        Read databases from config-driven multi-table mapping.

        Args:
            environment: Optional environment filter
            server_name: Optional single server name filter
            server_names: Optional multiple server names for IN clause

        Returns:
            List of database dicts
        """
        return self._read_entity_from_config(
            'database', environment=environment,
            server_name=server_name, server_names=server_names,
        )
