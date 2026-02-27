"""
InventoryQueryExecutor: Executes config-driven SQL queries for inventory data.

Responsibility: Execute HOW to read inventory data (SQL queries, mapping, validation).
Story 26.1 - AC1, AC3: Separation of concerns + unification of _read_*_from_config methods.
"""
# Responsabilité : Exécution des requêtes SQL config-driven pour l'inventaire multi-table
# (Oracle) — volume justifié par l'unification _read_entity_from_config et la gestion
# exhaustive des cas multi-sources (Story 35.4 AC3 / Story 26.1 AC1).

from __future__ import annotations

import re
from typing import Any, Literal

import structlog
from django.db import DatabaseError, InterfaceError

from core.environment import EnvironmentHelper
from inventory.mapper import (
    SAFE_COLUMN_NAME_PATTERN,
    InventoryMapper,
    MapperValidationError,
    _validate_column_name,
)
from integrations.models import Integration, IntegrationType
from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)


def _get_connection() -> Any:
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
        except Exception as e:  # noqa: BLE001 — logged-and-wrapped: query error wrapped in InventoryServiceError
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
        *,
        column_mapping: dict[str, str] | None = None,
    ) -> tuple[list[dict], int]:
        """
        Read inventory from Oracle table or synonym.

        Args:
            table_or_synonym: Table name or synonym (e.g., 'DBOPS_INVENTORY')
            environment: Optional environment filter
            search: Optional search query
            target_type: Optional target type filter
            page: Page number
            page_size: Items per page
            column_mapping: Optional mapping of concept -> real column name.
                E.g. {'name': 'HOSTNAME', 'environment': 'ENV', 'type': 'TYPE'}.
                If omitted, defaults to NAME, ENVIRONMENT, TYPE.

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

        # Use config mapping or fallback to hardcoded defaults (NAME, ENVIRONMENT, TYPE)
        column_mapping = column_mapping or {}
        name_col = column_mapping.get('name', 'NAME')
        env_col = column_mapping.get('environment', 'ENVIRONMENT')
        type_col = column_mapping.get('type', 'TYPE')
        for col in (name_col, env_col, type_col):
            if not isinstance(col, str):
                raise InventoryServiceError(
                    f"Invalid column name in mapping: expected string, got {type(col).__name__}"
                )
            try:
                _validate_column_name(col)
            except (MapperValidationError, TypeError) as e:
                raise InventoryServiceError(
                    f"Invalid column name in mapping: '{col}'. Must be alphanumeric with underscore."
                ) from e

        if environment:
            conditions.append(f"UPPER({env_col}) = UPPER(:env)")  # nosec B608 - env_col validated above
            params['env'] = environment
        if search:
            conditions.append(f"UPPER({name_col}) LIKE UPPER(:search)")  # nosec B608 - name_col validated above
            params['search'] = f'%{search}%'
        if target_type:
            conditions.append(f"UPPER({type_col}) = UPPER(:ttype)")  # nosec B608 - type_col validated above
            params['ttype'] = target_type

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        # Count query
        count_sql = f"SELECT COUNT(*) FROM {table_or_synonym} {where_clause}"  # nosec B608 - table validated above

        # Data query with pagination (use mapped column names)
        offset = (page - 1) * page_size
        params['offset'] = offset  # type: ignore[assignment]
        params['limit'] = page_size  # type: ignore[assignment]

        data_sql = (
            f"SELECT {name_col}, {env_col}, {type_col} FROM {table_or_synonym} "  # nosec B608
            f"{where_clause} "
            f"ORDER BY {name_col} "
            "OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY"
        )

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
                # Story 26.7 AC4: Use EnvironmentHelper.normalize()
                raw_env = EnvironmentHelper.normalize(row[1])

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
        except Exception as e:  # noqa: BLE001 — logged-and-wrapped: Oracle DB errors wrapped in InventoryServiceError
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

    @staticmethod
    def _build_aliased_select(entity_cfg: dict, table_alias: str) -> str:
        """
        Build a table-aliased SELECT clause directly from entity config.

        Avoids str.replace fragility when column names share substrings.
        Validates id_column and all column names/concepts to prevent SQL injection.
        Example: entity_cfg with id_column="INST_ID", columns={"name": "INST_NAME"},
        alias="inst" → "inst.INST_ID AS id, inst.INST_NAME AS name"
        """
        parts = []
        id_col = entity_cfg.get('id_column')
        if id_col:
            _validate_column_name(id_col)
            parts.append(f"{table_alias}.{id_col} AS id")
        for concept, col in entity_cfg.get('columns', {}).items():
            if not SAFE_COLUMN_NAME_PATTERN.match(concept):
                raise MapperValidationError(
                    f"Invalid concept name: '{concept}'. "
                    "Must match pattern: [A-Za-z_][A-Za-z0-9_]*"
                )
            _validate_column_name(col)
            parts.append(f"{table_alias}.{col} AS {concept}")
        return ", ".join(parts)

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
                return self._read_databases_via_instances(mapper, environment, server_name, engine_type=engine_type)

            # Multi-server IN clause path (instances or databases)
            if server_names:
                return self._read_entity_multi_server(
                    mapper, entity_plural, environment or "", server_names, engine_type=engine_type
                )

            # Standard single-entity query
            table = mapper.get_table_name(entity_plural)

            # Story 37.1: Check if servers config available for env-from-server JOIN
            has_servers_config = mapper.get_entity_config('servers') is not None

            # Story 37.1/37.2 Task 1/5: Instances with environment or engine_type — derive from servers via JOIN
            # AC1, AC4: The local environment column on instances is ignored; use servers.env via JOIN.
            if entity_type == 'instance' and (environment or engine_type) and has_servers_config:
                srv_table = mapper.get_table_name('servers')
                srv_name_col = mapper.get_column('servers', 'name')
                inst_server_ref_col = mapper.get_column(entity_plural, 'server_ref')
                ref_join_id = mapper.refs_join_on_id(entity_plural)
                srv_join_col = mapper.get_id_column('servers') if ref_join_id else srv_name_col
                srv_join_on = f"inst.{inst_server_ref_col} = srv.{srv_join_col}" if ref_join_id else f"UPPER(inst.{inst_server_ref_col}) = UPPER(srv.{srv_name_col})"

                # Prefix instances columns with 'inst.' alias to avoid JOIN ambiguity
                entity_cfg = mapper.get_entity_config(entity_plural) or {}
                aliased_select = self._build_aliased_select(entity_cfg, 'inst')

                inst_conditions: list[str] = []
                inst_params: dict[str, Any] = {}

                if environment:
                    srv_env_col = mapper.get_column('servers', 'environment')
                    inst_conditions.append(f"UPPER(srv.{srv_env_col}) = UPPER(:p_environment)")  # nosec B608 - column validated by mapper
                    inst_params['p_environment'] = environment

                if engine_type:
                    try:
                        srv_engine_col = mapper.get_column('servers', 'engine_type')
                        inst_conditions.append(f"UPPER(srv.{srv_engine_col}) = UPPER(:p_engine_type)")  # nosec B608 - column validated by mapper
                        inst_params['p_engine_type'] = engine_type
                    except MapperValidationError:
                        logger.warning(
                            "engine_type_not_mapped_in_servers",
                            entity=entity_plural,
                            engine_type=engine_type,
                            correlation_id=correlation_id,
                        )

                if server_name:
                    if ref_join_id:
                        inst_conditions.append(f"UPPER(srv.{srv_name_col}) = UPPER(:p_server_ref)")
                    else:
                        inst_conditions.append(f"UPPER(inst.{inst_server_ref_col}) = UPPER(:p_server_ref)")
                    inst_params['p_server_ref'] = server_name

                where_str = ("WHERE " + " AND ".join(inst_conditions)) if inst_conditions else ""

                inst_name_col = mapper.get_column(entity_plural, 'name')
                inst_inner = (
                    f"SELECT {aliased_select} "  # nosec B608 - table/columns validated by mapper
                    f"FROM {table} inst "  # nosec B608 - table validated by mapper
                    f"INNER JOIN {srv_table} srv ON {srv_join_on} "  # nosec B608 - columns validated by mapper
                    f"{where_str} ORDER BY inst.{inst_name_col}"  # nosec B608 - where_str built from validated columns
                )
                inst_sql = f"SELECT * FROM ({inst_inner}) WHERE ROWNUM <= {MAX_MULTI_TABLE_RESULTS}"  # nosec B608

                logger.info(
                    "reading_instances_from_config",
                    table=table,
                    has_env_filter=bool(environment),
                    has_engine_filter=bool(engine_type),
                    has_server_filter=bool(server_name),
                    env_from_servers=True,
                    correlation_id=correlation_id,
                )
                return self.execute_mapped_query(inst_sql, inst_params)

            # Story 37.1/37.2 Task 2/6: Databases (no server_name, no server_names) with environment or engine_type
            # → derive from servers via JOIN databases → instances → servers (AC2, AC4).
            # The local environment column on databases is ignored when servers config is available.
            has_instances_config = mapper.get_entity_config('instances') is not None
            if entity_type == 'database' and (environment or engine_type) and has_servers_config and has_instances_config:
                db_table = mapper.get_table_name('databases')
                inst_table = mapper.get_table_name('instances')
                srv_table = mapper.get_table_name('servers')
                db_name_col = mapper.get_column('databases', 'name')
                inst_db_ref_col = mapper.get_column('instances', 'db_ref')
                inst_server_ref_col = mapper.get_column('instances', 'server_ref')
                srv_name_col = mapper.get_column('servers', 'name')
                ref_join_id = mapper.refs_join_on_id('instances')
                if ref_join_id:
                    db_id_col = mapper.get_id_column('databases')
                    srv_id_col = mapper.get_id_column('servers')
                    inst_db_join = f"i.{inst_db_ref_col} = d.{db_id_col}"
                    inst_srv_join = f"i.{inst_server_ref_col} = srv.{srv_id_col}"
                else:
                    inst_db_join = f"UPPER(i.{inst_db_ref_col}) = UPPER(d.{db_name_col})"
                    inst_srv_join = f"UPPER(i.{inst_server_ref_col}) = UPPER(srv.{srv_name_col})"

                # Prefix databases columns with 'd.' alias to avoid JOIN ambiguity
                db_entity_cfg = mapper.get_entity_config('databases') or {}
                aliased_db_select = self._build_aliased_select(db_entity_cfg, 'd')

                db_conditions: list[str] = []
                db_params: dict[str, Any] = {}

                if environment:
                    srv_env_col = mapper.get_column('servers', 'environment')
                    db_conditions.append(f"UPPER(srv.{srv_env_col}) = UPPER(:p_environment)")  # nosec B608 - column validated by mapper
                    db_params['p_environment'] = environment

                if engine_type:
                    try:
                        srv_engine_col = mapper.get_column('servers', 'engine_type')
                        db_conditions.append(f"UPPER(srv.{srv_engine_col}) = UPPER(:p_engine_type)")  # nosec B608 - column validated by mapper
                        db_params['p_engine_type'] = engine_type
                    except MapperValidationError:
                        logger.warning(
                            "engine_type_not_mapped_in_servers",
                            entity=entity_plural,
                            engine_type=engine_type,
                            correlation_id=correlation_id,
                        )

                where_db_str = ("WHERE " + " AND ".join(db_conditions)) if db_conditions else ""

                db_inner = (
                    f"SELECT DISTINCT {aliased_db_select} "  # nosec B608 - table/columns validated by mapper
                    f"FROM {db_table} d "  # nosec B608 - table validated by mapper
                    f"INNER JOIN {inst_table} i ON {inst_db_join} "  # nosec B608 - columns validated by mapper
                    f"INNER JOIN {srv_table} srv ON {inst_srv_join} "  # nosec B608 - columns validated by mapper
                    f"{where_db_str}"  # nosec B608 - where_db_str built from validated columns
                    f" ORDER BY d.{db_name_col}"  # nosec B608 - column validated by mapper
                )
                db_sql = f"SELECT * FROM ({db_inner}) WHERE ROWNUM <= {MAX_MULTI_TABLE_RESULTS}"  # nosec B608

                logger.info(
                    "reading_databases_from_config",
                    table=db_table,
                    has_env_filter=bool(environment),
                    has_engine_filter=bool(engine_type),
                    env_from_servers=True,
                    correlation_id=correlation_id,
                )
                return self.execute_mapped_query(db_sql, db_params)

            if entity_type == 'database' and environment and not (has_servers_config and has_instances_config):
                # Fallback: log warning, continue to local column filter below
                logger.warning(
                    "environment_filter_fallback_to_local_column",
                    entity=entity_plural,
                    reason="servers/instances entities not configured",
                    correlation_id=correlation_id,
                )

            if entity_type == 'instance' and (environment or engine_type) and not has_servers_config:
                # Fallback: log warning, continue to local column filter below (symmetric with databases)
                logger.warning(
                    "environment_filter_fallback_to_local_column",
                    entity=entity_plural,
                    reason="servers entity not configured",
                    correlation_id=correlation_id,
                )

            # Default path: servers always use their own env column;
            # instances/databases fallback here only when servers config is absent.
            filters = {}
            if environment:
                filters['environment'] = environment
            if engine_type and entity_type == 'server':
                filters['engine_type'] = engine_type
            # When ref_join_id, server_ref is FK; filter via JOIN srv.name, not inst.server_ref
            if server_name and entity_type in ('instance',) and not mapper.refs_join_on_id(entity_plural):
                filters['server_ref'] = server_name

            where_clause, params = mapper.build_where_clause(entity_plural, filters)

            name_col = mapper.get_column(entity_plural, 'name')
            table_alias = "inst" if entity_type == "instance" else "e"
            # Instance + server_name + ref_join_id: use aliased select to avoid column ambiguity with JOIN
            need_aliased_select = (
                server_name and entity_type == 'instance'
                and mapper.refs_join_on_id(entity_plural)
                and has_servers_config
            )
            if need_aliased_select:
                entity_cfg = mapper.get_entity_config(entity_plural) or {}
                select = self._build_aliased_select(entity_cfg, table_alias)
            else:
                select = mapper.build_select_clause(entity_plural)

            inner_sql = f"SELECT {select} FROM {table} {table_alias}"  # nosec B608 - table/columns validated by mapper

            # Instance + server_name + ref_join_id: need JOIN to filter by srv.name
            if need_aliased_select:
                srv_table = mapper.get_table_name('servers')
                inst_server_ref_col = mapper.get_column(entity_plural, 'server_ref')
                srv_id_col = mapper.get_id_column('servers')
                srv_name_col = mapper.get_column('servers', 'name')
                join_part = f" INNER JOIN {srv_table} srv ON {table_alias}.{inst_server_ref_col} = srv.{srv_id_col}"
                server_filter = f"UPPER(srv.{srv_name_col}) = UPPER(:p_server_ref)"
                params = dict(params, p_server_ref=server_name)
                inner_sql += join_part
                inner_sql += f" WHERE {server_filter}" if not where_clause else f" WHERE {where_clause} AND {server_filter}"
            elif where_clause:
                inner_sql += f" WHERE {where_clause}"
            inner_sql += f" ORDER BY {table_alias}.{name_col}"
            sql = f"SELECT * FROM ({inner_sql}) WHERE ROWNUM <= {MAX_MULTI_TABLE_RESULTS}"  # nosec B608 - MAX_MULTI_TABLE_RESULTS is a constant, inner_sql validated above

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
            raise
        except (DatabaseError, InterfaceError) as e:
            logger.error(
                f"read_{entity_plural}_from_config_db_error",
                error=str(e),
                error_type=type(e).__name__,
                correlation_id=correlation_id,
                exc_info=True,
            )
            raise InventoryServiceError(f"Database error reading {entity_plural}: {e}")
        except Exception as e:  # noqa: BLE001 — logged-and-wrapped: config read error wrapped in InventoryServiceError
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
        engine_type: str | None = None,
    ) -> list[dict]:
        """
        Read entities filtered by multiple server names using IN clause.

        Args:
            mapper: Configured InventoryMapper
            entity_plural: Entity name ('instances' or 'databases')
            environment: Target environment
            server_names: List of server names
            engine_type: Optional engine type filter

        Returns:
            List of entity dicts
        """
        correlation_id = get_correlation_id()

        if entity_plural == 'databases':
            return self._read_databases_multi_server(mapper, environment, server_names, engine_type=engine_type)

        # Instances multi-server path
        table = mapper.get_table_name(entity_plural)
        server_ref_col = mapper.get_column(entity_plural, 'server_ref')
        ref_join_id = mapper.refs_join_on_id(entity_plural)
        srv_table = mapper.get_table_name('servers')
        srv_name_col = mapper.get_column('servers', 'name')
        if ref_join_id:
            srv_id_col = mapper.get_id_column('servers')
            srv_join_col = srv_id_col
            srv_join_on = f"inst.{server_ref_col} = srv.{srv_join_col}"
        else:
            srv_join_col = srv_name_col
            srv_join_on = f"UPPER(inst.{server_ref_col}) = UPPER(srv.{srv_name_col})"
        server_filter_col = srv_name_col if ref_join_id else server_ref_col
        server_filter_alias = "srv" if ref_join_id else "inst"

        in_params = {f'p_server_{i}': sn for i, sn in enumerate(server_names)}
        in_placeholders = ', '.join(f":{key}" for key in in_params.keys())

        params: dict[str, Any] = {**in_params}

        # Story 37.1 Task 3: Derive environment from servers via JOIN (AC1, AC3)
        srv_env_col = mapper.get_column('servers', 'environment')

        # Prefix instances columns with 'inst.' alias to avoid JOIN ambiguity
        entity_cfg = mapper.get_entity_config(entity_plural) or {}
        aliased_select = self._build_aliased_select(entity_cfg, 'inst')
        inst_name_col = mapper.get_column(entity_plural, 'name')

        # Build WHERE conditions list for composable filtering (environment is optional)
        where_conditions = []
        if environment:
            where_conditions.append(f"UPPER(srv.{srv_env_col}) = UPPER(:p_environment)")  # nosec B608 - column validated by mapper
            params['p_environment'] = environment
        where_conditions.append(f"UPPER({server_filter_alias}.{server_filter_col}) IN ({in_placeholders})")  # nosec B608 - column validated by mapper

        # Story 37.2 Task 7.3: Add engine_type filter if provided
        if engine_type:
            try:
                srv_engine_col = mapper.get_column('servers', 'engine_type')
                where_conditions.append(f"UPPER(srv.{srv_engine_col}) = UPPER(:p_engine_type)")  # nosec B608 - column validated by mapper
                params['p_engine_type'] = engine_type
            except MapperValidationError:
                logger.warning(
                    "engine_type_not_mapped_in_servers",
                    entity=entity_plural,
                    engine_type=engine_type,
                    correlation_id=correlation_id,
                )

        where_str = "WHERE " + " AND ".join(where_conditions)  # always at least one condition (IN clause)

        inner_sql = (
            f"SELECT {aliased_select} "  # nosec B608 - table/columns validated by mapper
            f"FROM {table} inst "  # nosec B608 - table validated by mapper
            f"INNER JOIN {srv_table} srv ON {srv_join_on} "  # nosec B608 - columns validated by mapper
            f"{where_str} "  # nosec B608 - where_str built from validated columns
            f"ORDER BY inst.{inst_name_col}"
        )

        sql = f"SELECT * FROM ({inner_sql}) WHERE ROWNUM <= {MAX_MULTI_TABLE_RESULTS}"  # nosec B608

        logger.info(
            f"reading_{entity_plural}_from_config_multi",
            table=table,
            server_count=len(server_names),
            has_engine_filter=bool(engine_type),
            env_from_servers=True,
            correlation_id=correlation_id,
        )

        return self.execute_mapped_query(sql, params)

    def _read_databases_multi_server(
        self,
        mapper: InventoryMapper,
        environment: str,
        server_names: list[str],
        engine_type: str | None = None,
    ) -> list[dict]:
        """
        Read databases filtered by multiple servers via JOIN with instances.

        Args:
            mapper: Configured InventoryMapper
            environment: Target environment
            server_names: List of server names
            engine_type: Optional engine type filter

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
        inst_db_ref_col = mapper.get_column('instances', 'db_ref')
        inst_server_ref_col = mapper.get_column('instances', 'server_ref')
        ref_join_id = mapper.refs_join_on_id('instances')
        srv_table = mapper.get_table_name('servers')
        srv_name_col = mapper.get_column('servers', 'name')
        if ref_join_id:
            db_id_col = mapper.get_id_column('databases')
            srv_id_col = mapper.get_id_column('servers')
            inst_db_join = f"i.{inst_db_ref_col} = d.{db_id_col}"
            inst_srv_join = f"i.{inst_server_ref_col} = srv.{srv_id_col}"
        else:
            inst_db_join = f"UPPER(i.{inst_db_ref_col}) = UPPER(d.{db_name_col})"
            inst_srv_join = f"UPPER(i.{inst_server_ref_col}) = UPPER(srv.{srv_name_col})"
        server_filter_col = srv_name_col if ref_join_id else inst_server_ref_col
        server_filter_alias = "srv" if ref_join_id else "i"

        # Prefix DB columns with alias 'd'
        aliased_select = self._build_aliased_select(entity_config, 'd')

        in_params = {f'p_server_{i}': sn for i, sn in enumerate(server_names)}
        in_placeholders = ', '.join(f":{key}" for key in in_params.keys())

        params: dict[str, Any] = {**in_params}

        srv_env_col = mapper.get_column('servers', 'environment')

        # Build WHERE conditions list for composable filtering (environment is optional)
        where_conditions = []
        if environment:
            where_conditions.append(f"UPPER(srv.{srv_env_col}) = UPPER(:p_environment)")  # nosec B608 - column validated by mapper
            params['p_environment'] = environment
        where_conditions.append(f"UPPER({server_filter_alias}.{server_filter_col}) IN ({in_placeholders})")  # nosec B608 - column validated by mapper

        if engine_type:
            try:
                srv_engine_col = mapper.get_column('servers', 'engine_type')
                where_conditions.append(f"UPPER(srv.{srv_engine_col}) = UPPER(:p_engine_type)")  # nosec B608 - column validated by mapper
                params['p_engine_type'] = engine_type
            except MapperValidationError:
                logger.warning(
                    "engine_type_not_mapped_in_servers",
                    entity="databases",
                    engine_type=engine_type,
                    correlation_id=correlation_id,
                )

        where_str = "WHERE " + " AND ".join(where_conditions)  # always at least one condition (IN clause)

        inner_sql = (
            f"SELECT DISTINCT {aliased_select} "  # nosec B608 - table/columns validated by mapper
            f"FROM {db_table} d "  # nosec B608 - table validated by mapper
            f"INNER JOIN {inst_table} i ON {inst_db_join} "  # nosec B608 - columns validated by mapper
            f"INNER JOIN {srv_table} srv ON {inst_srv_join} "  # nosec B608 - columns validated by mapper
            f"{where_str} "  # nosec B608 - where_str built from validated columns
            f"ORDER BY d.{db_name_col}"  # nosec B608 - column validated by mapper
        )

        sql = f"SELECT * FROM ({inner_sql}) WHERE ROWNUM <= {MAX_MULTI_TABLE_RESULTS}"  # nosec B608

        logger.info(
            "reading_databases_from_config_multi",
            db_table=db_table,
            inst_table=inst_table,
            server_count=len(server_names),
            has_engine_filter=bool(engine_type),
            env_from_servers=True,
            correlation_id=correlation_id,
        )

        return self.execute_mapped_query(sql, params)

    def _read_databases_via_instances(
        self,
        mapper: InventoryMapper,
        environment: str | None,
        server_name: str,
        engine_type: str | None = None,
    ) -> list[dict]:
        """
        Read databases by joining through instances table.
        Uses instance.server_ref = server_name AND instance.db_ref = db.name.

        Args:
            mapper: Configured InventoryMapper
            environment: Optional environment filter
            server_name: Server name to filter by
            engine_type: Optional engine type filter

        Returns:
            List of database dicts
        """
        correlation_id = get_correlation_id()

        db_table = mapper.get_table_name('databases')
        inst_table = mapper.get_table_name('instances')
        db_name_col = mapper.get_column('databases', 'name')
        inst_db_ref_col = mapper.get_column('instances', 'db_ref')
        inst_server_ref_col = mapper.get_column('instances', 'server_ref')
        ref_join_id = mapper.refs_join_on_id('instances')
        srv_table = mapper.get_table_name('servers')
        srv_name_col = mapper.get_column('servers', 'name')
        if ref_join_id:
            db_id_col = mapper.get_id_column('databases')
            srv_id_col = mapper.get_id_column('servers')
            inst_db_join = f"i.{inst_db_ref_col} = d.{db_id_col}"
            inst_srv_join = f"i.{inst_server_ref_col} = srv.{srv_id_col}"
        else:
            inst_db_join = f"UPPER(i.{inst_db_ref_col}) = UPPER(d.{db_name_col})"
            inst_srv_join = f"UPPER(i.{inst_server_ref_col}) = UPPER(srv.{srv_name_col})"
        server_filter = f"UPPER(srv.{srv_name_col}) = UPPER(:p_server_name)" if ref_join_id else f"UPPER(i.{inst_server_ref_col}) = UPPER(:p_server_name)"

        entity_config = mapper.get_entity_config('databases') or {}

        # Prefix DB columns with alias 'd'
        aliased_select = self._build_aliased_select(entity_config, 'd')

        # Build base FROM clause (without WHERE — added below based on environment strategy)
        inner_sql_base = (
            f"SELECT DISTINCT {aliased_select} "  # nosec B608 - all identifiers validated by mapper
            f"FROM {db_table} d "  # nosec B608 - table validated by mapper
            f"INNER JOIN {inst_table} i ON {inst_db_join} "  # nosec B608 - columns validated by mapper
        )
        params: dict[str, Any] = {'p_server_name': server_name}

        has_servers_config = mapper.get_entity_config('servers') is not None

        if environment:
            if has_servers_config:
                srv_env_col = mapper.get_column('servers', 'environment')
                params['p_environment'] = environment

                engine_type_condition = ""
                if engine_type:
                    try:
                        srv_engine_col = mapper.get_column('servers', 'engine_type')
                        engine_type_condition = f" AND UPPER(srv.{srv_engine_col}) = UPPER(:p_engine_type)"  # nosec B608 - column validated by mapper
                        params['p_engine_type'] = engine_type
                    except MapperValidationError:
                        logger.warning(
                            "engine_type_not_mapped_in_servers",
                            entity="databases_via_instances",
                            engine_type=engine_type,
                            correlation_id=correlation_id,
                        )

                inner_sql = (
                    inner_sql_base +
                    f"INNER JOIN {srv_table} srv ON {inst_srv_join} "  # nosec B608 - columns validated by mapper
                    f"WHERE UPPER(srv.{srv_env_col}) = UPPER(:p_environment) "  # nosec B608 - column validated by mapper
                    f"AND {server_filter}"  # nosec B608 - server_filter built from validated columns
                    f"{engine_type_condition}"  # nosec B608 - engine_type_condition built from validated column
                )
            else:
                logger.warning(
                    "environment_filter_fallback_to_local_column",
                    entity="databases_via_instances",
                    reason="servers entity not configured",
                    correlation_id=correlation_id,
                )
                db_env_col = mapper.get_column('databases', 'environment')
                inner_sql = (
                    inner_sql_base +
                    f"INNER JOIN {srv_table} srv ON {inst_srv_join} "
                    f"WHERE {server_filter}"
                    f" AND UPPER(d.{db_env_col}) = UPPER(:p_environment)"
                )
                params['p_environment'] = environment
        elif engine_type and has_servers_config:
            try:
                srv_engine_col = mapper.get_column('servers', 'engine_type')
                params['p_engine_type'] = engine_type
                inner_sql = (
                    inner_sql_base +
                    f"INNER JOIN {srv_table} srv ON {inst_srv_join} "  # nosec B608 - columns validated by mapper
                    f"WHERE {server_filter} "  # nosec B608 - column validated by mapper
                    f"AND UPPER(srv.{srv_engine_col}) = UPPER(:p_engine_type)"  # nosec B608 - column validated by mapper
                )
            except MapperValidationError:
                logger.warning(
                    "engine_type_not_mapped_in_servers",
                    entity="databases_via_instances",
                    engine_type=engine_type,
                    correlation_id=correlation_id,
                )
                inner_sql = inner_sql_base + f"INNER JOIN {srv_table} srv ON {inst_srv_join} WHERE {server_filter}"
        else:
            # ref_join_id: need servers JOIN to filter by srv.name
            if ref_join_id:
                inner_sql = inner_sql_base + f"INNER JOIN {srv_table} srv ON {inst_srv_join} WHERE {server_filter}"
            else:
                inner_sql = inner_sql_base + f"WHERE {server_filter}"

        inner_sql += f" ORDER BY d.{db_name_col}"
        sql = f"SELECT * FROM ({inner_sql}) WHERE ROWNUM <= {MAX_MULTI_TABLE_RESULTS}"  # nosec B608

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
        engine_type: str | None = None,
    ) -> list[dict]:
        """
        Read instances from config-driven multi-table mapping.

        Args:
            environment: Optional environment filter
            server_name: Optional single server name filter
            server_names: Optional multiple server names for IN clause
            engine_type: Optional engine type filter

        Returns:
            List of instance dicts
        """
        return self._read_entity_from_config(
            'instance', environment=environment,
            server_name=server_name, server_names=server_names,
            engine_type=engine_type,
        )

    def read_databases(
        self,
        environment: str | None = None,
        server_name: str | None = None,
        server_names: list[str] | None = None,
        engine_type: str | None = None,
    ) -> list[dict]:
        """
        Read databases from config-driven multi-table mapping.

        Args:
            environment: Optional environment filter
            server_name: Optional single server name filter
            server_names: Optional multiple server names for IN clause
            engine_type: Optional engine type filter

        Returns:
            List of database dicts
        """
        return self._read_entity_from_config(
            'database', environment=environment,
            server_name=server_name, server_names=server_names,
            engine_type=engine_type,
        )
