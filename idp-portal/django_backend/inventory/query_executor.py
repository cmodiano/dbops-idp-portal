"""
InventoryQueryExecutor: Thin orchestrator for config-driven inventory SQL queries.

Delegates SQL construction to InventoryQueryBuilder, pagination to ResultPaginator,
and identifier validation to MappingValidator. Keeps _get_connection() and
InventoryServiceError here as infrastructure patched by tests.

Story 26.1 - AC1, AC3; Story 54.14 - AC4 (MAINT-BE-3 decomposed).
"""
from __future__ import annotations

from typing import Any, Literal

import structlog
from django.db import DatabaseError, InterfaceError

from core.environment import EnvironmentHelper
from inventory.mapper import (
    InventoryMapper,
    MapperValidationError,  # re-exported for backward compat via services.py
)
from inventory.mapping_validator import MappingValidator
from inventory.result_paginator import (
    MAX_FLAT_TABLE_RESULTS as MAX_FLAT_TABLE_RESULTS,  # noqa: PLC0414 — explicit re-export for backward compat
    MAX_MULTI_TABLE_RESULTS as MAX_MULTI_TABLE_RESULTS,  # noqa: PLC0414 — explicit re-export for backward compat
    ResultPaginator,
)
from inventory.mapper import SAFE_TABLE_NAME_PATTERN as SAFE_TABLE_NAME_PATTERN  # noqa: PLC0414 — explicit re-export
from inventory.query_builder import InventoryQueryBuilder
from integrations.models import Integration, IntegrationType
from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)


def _get_connection() -> Any:
    """Get DB connection at call time so tests can patch 'inventory.services.connection'."""
    from django.db.backends.base.base import BaseDatabaseWrapper
    import inventory.services as svc_module
    conn: BaseDatabaseWrapper = svc_module.connection
    return conn


class InventoryServiceError(Exception):
    """Exception raised when inventory service encounters an error."""
    pass


class InventoryQueryExecutor:
    """Thin orchestrator: delegates to InventoryQueryBuilder, ResultPaginator, MappingValidator."""

    def __init__(self) -> None:
        self._validator = MappingValidator()
        self._paginator = ResultPaginator()

    def _get_inventory_mapper(self) -> InventoryMapper | None:
        """Get InventoryMapper from active inventory_db integration config."""
        integration = Integration.objects.get_by_type(IntegrationType.INVENTORY_DB)
        if not integration:
            return None
        return InventoryMapper(integration.get_config() or {})

    def _get_builder(self, mapper: InventoryMapper) -> InventoryQueryBuilder:
        return InventoryQueryBuilder(mapper, self._validator)

    def execute_mapped_query(self, sql: str, params: dict) -> list[dict]:
        """Execute a mapped SQL query and return results as list of dicts."""
        correlation_id = get_correlation_id()
        try:
            with _get_connection().cursor() as cursor:
                cursor.execute(sql, params)
                columns = [col[0].lower() for col in cursor.description]
                rows = cursor.fetchall()
            results = [dict(zip(columns, row)) for row in rows]
            logger.info("mapped_query_executed", result_count=len(results),
                        correlation_id=correlation_id)
            return results
        except InventoryServiceError:
            raise
        except Exception as e:  # noqa: BLE001 — logged-and-wrapped
            logger.error("mapped_query_execution_error", error=str(e),
                         error_type=type(e).__name__, correlation_id=correlation_id, exc_info=True)
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
        Read inventory from Oracle table or synonym with optional filters and pagination.

        Returns:
            Tuple of (list of target dicts, total count)

        Raises:
            InventoryServiceError: If table name is invalid or Oracle error occurs
        """
        from inventory.models import TargetType as TargetTypeEnum
        correlation_id = get_correlation_id()

        try:
            self._validator.validate_table_name(table_or_synonym)
        except ValueError as e:
            raise InventoryServiceError(str(e)) from e

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
                self._validator.validate_column_name(col)
            except (MapperValidationError, TypeError) as e:
                raise InventoryServiceError(
                    f"Invalid column name in mapping: '{col}'. Must be alphanumeric with underscore."
                ) from e

        conditions: list[str] = []
        params: dict[str, Any] = {}
        if environment:
            conditions.append(f"UPPER({env_col}) = UPPER(:env)")  # nosec B608
            params['env'] = environment
        if search:
            conditions.append(f"UPPER({name_col}) LIKE UPPER(:search)")  # nosec B608
            params['search'] = f'%{search}%'
        if target_type:
            conditions.append(f"UPPER({type_col}) = UPPER(:ttype)")  # nosec B608
            params['ttype'] = target_type

        count_sql, count_params, data_sql, data_params = ResultPaginator.build_flat_table_sql(
            table_or_synonym, name_col, env_col, type_col, conditions, params, page, page_size
        )

        try:
            with _get_connection().cursor() as cursor:
                rows, total_count = self._paginator.paginate_flat(
                    cursor, count_sql, count_params, data_sql, data_params
                )

            results = []
            for row in rows:
                raw_env = EnvironmentHelper.normalize(row[1])
                raw_type = (row[2] or '').lower().strip()
                normalized_type = raw_type if raw_type in TargetTypeEnum.VALUES else TargetTypeEnum.SERVER
                results.append({'name': row[0], 'environment': raw_env,
                                 'target_type': normalized_type, 'metadata': None})

            logger.info("oracle_inventory_read", source=table_or_synonym,
                        total=total_count, returned_count=len(results),
                        correlation_id=correlation_id)
            return results, total_count

        except InventoryServiceError:
            raise
        except Exception as e:  # noqa: BLE001 — logged-and-wrapped
            logger.error("oracle_inventory_read_error", source=table_or_synonym,
                         error=str(e), error_type=type(e).__name__,
                         correlation_id=correlation_id, exc_info=True)
            raise InventoryServiceError(f"Failed to read inventory from {table_or_synonym}: {str(e)}")

    def _read_entity_from_config(
        self,
        entity_type: Literal['server', 'instance', 'database'],
        environment: str | None = None,
        engine_type: str | None = None,
        server_name: str | None = None,
        server_names: list[str] | None = None,
    ) -> list[dict]:
        """
        Generic config-driven entity reader. Delegates SQL building to InventoryQueryBuilder.

        Raises:
            InventoryServiceError: If config invalid or query fails
        """
        correlation_id = get_correlation_id()
        entity_plural = f"{entity_type}s" if entity_type != 'database' else 'databases'

        if entity_type in ('instance', 'database') and not environment:
            environment = 'dev'
            logger.info("environment_defaulted_to_dev", entity=entity_plural,
                        correlation_id=correlation_id)

        mapper = self._get_inventory_mapper()

        if mapper is None or not mapper.is_multi_table:
            if entity_type == 'server':
                return self._read_servers_flat_fallback(environment)
            logger.info(f"{entity_plural}_flat_fallback", reason="no multi-table config",
                        correlation_id=correlation_id)
            return []

        entity_config = mapper.get_entity_config(entity_plural)
        if not entity_config:
            if entity_type == 'server':
                return self._read_servers_flat_fallback(environment)
            logger.info(f"{entity_plural}_entity_not_configured", correlation_id=correlation_id)
            return []

        try:
            builder = self._get_builder(mapper)
            sql, params = builder.build_entity_query(
                entity_type, entity_plural, environment, engine_type,
                server_name, server_names, correlation_id
            )
            if not sql:
                return []

            logger.info(
                f"reading_{entity_plural}_from_config",
                table=mapper.get_table_name(entity_plural),
                has_env_filter=bool(environment),
                has_engine_filter=bool(engine_type),
                has_server_filter=bool(server_name or server_names),
                correlation_id=correlation_id,
            )
            return self.execute_mapped_query(sql, params)

        except MapperValidationError as e:
            logger.error(f"{entity_type}_config_mapping_error", error=str(e),
                         correlation_id=correlation_id)
            raise InventoryServiceError(f"{entity_type.capitalize()} mapping config error: {e}")
        except InventoryServiceError:
            raise
        except (DatabaseError, InterfaceError) as e:
            logger.error(f"read_{entity_plural}_from_config_db_error", error=str(e),
                         error_type=type(e).__name__, correlation_id=correlation_id, exc_info=True)
            raise InventoryServiceError(f"Database error reading {entity_plural}: {e}")
        except Exception as e:  # noqa: BLE001 — logged-and-wrapped
            logger.error(f"read_{entity_plural}_from_config_error", error=str(e),
                         error_type=type(e).__name__, correlation_id=correlation_id, exc_info=True)
            raise InventoryServiceError(f"Failed to read {entity_plural}: {e}")

    def _read_servers_flat_fallback(self, environment: str | None = None) -> list[dict]:
        """Fallback: read servers from flat table (TYPE=server filter). Story 23.1 AC6."""
        logger.info("reading_servers_flat_fallback", correlation_id=get_correlation_id())
        targets, _ = self.read_oracle_inventory(
            'DBOPS_INVENTORY', environment=environment,
            target_type='server', page=1, page_size=MAX_FLAT_TABLE_RESULTS,
        )
        return [{'id': t.get('name', ''), 'name': t.get('name', ''),
                 'environment': t.get('environment', ''), 'engine_type': None}
                for t in targets]

    def _exec_env_query(self, sql: str, correlation_id: str | None, log_tag: str) -> list[str]:
        """Execute a SELECT DISTINCT environments query and return sorted deduplicated list."""
        with _get_connection().cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
        envs = [EnvironmentHelper.normalize(row[0]) for row in rows if row[0]]
        logger.info(f"read_distinct_environments_{log_tag}", count=len(envs),
                    correlation_id=correlation_id)
        return sorted(set(e for e in envs if e))

    def read_distinct_environments(self) -> list[str]:
        """
        Read distinct environment values directly from inventory.

        Returns:
            Sorted list of distinct environment strings.

        Raises:
            InventoryServiceError: If query fails.
        """
        correlation_id = get_correlation_id()
        mapper = self._get_inventory_mapper()

        try:
            if mapper and mapper.is_multi_table:
                srv_config = mapper.get_entity_config('servers')
                if srv_config:
                    table = mapper.get_table_name('servers')
                    env_col = mapper.get_column('servers', 'environment')
                    sql = (
                        f"SELECT DISTINCT {env_col} FROM {table} "  # nosec B608
                        f"WHERE {env_col} IS NOT NULL ORDER BY {env_col}"
                    )
                    return self._exec_env_query(sql, correlation_id, "multi_table")

            if mapper and mapper.is_flat_table:
                flat_cfg = mapper._flat_table or {}
                env_col = flat_cfg.get('columns', {}).get('environment', 'ENVIRONMENT')
                self._validator.validate_column_name(env_col)
                raw_table = flat_cfg.get('table', 'DBOPS_INVENTORY')
                schema = mapper._config.get('schema') or mapper._config.get('db_schema')
                flat_table = f"{schema}.{raw_table}" if schema and '.' not in raw_table else raw_table
                self._validator.validate_table_name(flat_table)
                sql = (
                    f"SELECT DISTINCT {env_col} FROM {flat_table} "  # nosec B608
                    f"WHERE {env_col} IS NOT NULL ORDER BY {env_col}"
                )
                return self._exec_env_query(sql, correlation_id, "flat_table")

            sql = (
                "SELECT DISTINCT ENVIRONMENT FROM DBOPS_INVENTORY "
                "WHERE ENVIRONMENT IS NOT NULL ORDER BY ENVIRONMENT"
            )
            return self._exec_env_query(sql, correlation_id, "fallback")

        except InventoryServiceError:
            raise
        except Exception as e:  # noqa: BLE001 — logged-and-wrapped
            logger.error("read_distinct_environments_error", error=str(e),
                         error_type=type(e).__name__, correlation_id=correlation_id, exc_info=True)
            raise InventoryServiceError(f"Failed to read distinct environments: {e}")

    def read_servers(
        self,
        environment: str | None = None,
        engine_type: str | None = None,
    ) -> list[dict]:
        """Read servers from config-driven multi-table or flat table fallback."""
        return self._read_entity_from_config('server', environment=environment, engine_type=engine_type)

    def read_instances(
        self,
        environment: str | None = None,
        server_name: str | None = None,
        server_names: list[str] | None = None,
        engine_type: str | None = None,
    ) -> list[dict]:
        """Read instances from config-driven multi-table mapping."""
        return self._read_entity_from_config(
            'instance', environment=environment,
            server_name=server_name, server_names=server_names, engine_type=engine_type,
        )

    def read_databases(
        self,
        environment: str | None = None,
        server_name: str | None = None,
        server_names: list[str] | None = None,
        engine_type: str | None = None,
    ) -> list[dict]:
        """Read databases from config-driven multi-table mapping."""
        return self._read_entity_from_config(
            'database', environment=environment,
            server_name=server_name, server_names=server_names, engine_type=engine_type,
        )
