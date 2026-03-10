"""
InventoryQueryBuilder: Builds Oracle SQL queries for inventory entities.

Responsibility: Construct SQL strings and bind-parameter dicts. No DB access.
Story 54.14 - AC1: Extracted from InventoryQueryExecutor (MAINT-BE-3).
"""
from __future__ import annotations

from typing import Any, Literal

import structlog

from inventory.mapper import (
    SAFE_COLUMN_NAME_PATTERN,
    InventoryMapper,
    MapperValidationError,
    validate_column_name,  # INV-LOW-01: use public name instead of private _validate_column_name
)
from inventory.mapping_validator import MappingValidator
from inventory.result_paginator import ResultPaginator

logger = structlog.get_logger(__name__)


class InventoryQueryBuilder:
    """
    Builds Oracle SQL queries for multi-table inventory reads. No DB access.
    Story 54.14 - AC1.
    """

    def __init__(self, mapper: InventoryMapper, validator: MappingValidator) -> None:
        self._mapper = mapper
        self._validator = validator

    @staticmethod
    def _build_aliased_select(entity_cfg: dict, table_alias: str) -> str:
        """Build table-aliased SELECT clause from entity config. Validates all identifiers."""
        parts = []
        id_col = entity_cfg.get('id_column')
        if id_col:
            validate_column_name(id_col)
            parts.append(f"{table_alias}.{id_col} AS id")
        for concept, col in entity_cfg.get('columns', {}).items():
            if not SAFE_COLUMN_NAME_PATTERN.match(concept):
                raise MapperValidationError(
                    f"Invalid concept name: '{concept}'. "
                    "Must match pattern: [A-Za-z_][A-Za-z0-9_]*"
                )
            validate_column_name(col)
            parts.append(f"{table_alias}.{col} AS {concept}")
        return ", ".join(parts)

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def build_entity_query(
        self,
        entity_type: Literal['server', 'instance', 'database'],
        entity_plural: str,
        environment: str | None,
        engine_type: str | None,
        server_name: str | None,
        server_names: list[str] | None,
        correlation_id: str | None,
    ) -> tuple[str, dict]:
        """
        Return (sql, params) for an entity query on the multi-table path.

        Raises:
            MapperValidationError: If mapper config is invalid.
        """
        mapper = self._mapper

        # databases filtered by single server_name → join via instances
        if entity_type == 'database' and server_name and mapper.get_entity_config('instances'):
            return self._build_databases_via_instances_query(
                environment, server_name, engine_type, correlation_id
            )

        # multi-server IN clause
        if server_names:
            return self._build_entity_multi_server_query(
                entity_plural, environment or "", server_names, engine_type, correlation_id
            )

        table = mapper.get_table_name(entity_plural)
        has_servers_config = mapper.get_entity_config('servers') is not None

        # instances: derive environment from servers via JOIN
        if entity_type == 'instance' and (environment or engine_type) and has_servers_config:
            return self._build_instance_join_query(
                entity_plural, table, environment, engine_type, server_name, correlation_id
            )

        # databases: derive environment via JOIN db→inst→srv
        has_instances_config = mapper.get_entity_config('instances') is not None
        if (
            entity_type == 'database'
            and (environment or engine_type)
            and has_servers_config
            and has_instances_config
        ):
            return self._build_database_join_query(table, environment, engine_type, correlation_id)

        if entity_type == 'database' and environment and not (has_servers_config and has_instances_config):
            logger.warning(
                "environment_filter_fallback_to_local_column",
                entity=entity_plural, reason="servers/instances entities not configured",
                correlation_id=correlation_id,
            )
        if entity_type == 'instance' and (environment or engine_type) and not has_servers_config:
            logger.warning(
                "environment_filter_fallback_to_local_column",
                entity=entity_plural, reason="servers entity not configured",
                correlation_id=correlation_id,
            )

        return self._build_simple_entity_query(
            entity_type, entity_plural, table, environment, engine_type,
            server_name, has_servers_config, correlation_id
        )

    # ------------------------------------------------------------------
    # Private SQL builders
    # ------------------------------------------------------------------

    def _build_instance_join_query(
        self,
        entity_plural: str,
        table: str,
        environment: str | None,
        engine_type: str | None,
        server_name: str | None,
        correlation_id: str | None,
    ) -> tuple[str, dict]:
        mapper = self._mapper
        srv_table = mapper.get_table_name('servers')
        srv_name_col = mapper.get_column('servers', 'name')
        inst_sref_col = mapper.get_column(entity_plural, 'server_ref')
        ref_join_id = mapper.refs_join_on_id(entity_plural)
        srv_join_col = mapper.get_id_column('servers') if ref_join_id else srv_name_col
        srv_join_on = (
            f"inst.{inst_sref_col} = srv.{srv_join_col}" if ref_join_id
            else f"UPPER(inst.{inst_sref_col}) = UPPER(srv.{srv_name_col})"
        )
        aliased = self._build_aliased_select(mapper.get_entity_config(entity_plural) or {}, 'inst')
        name_col = mapper.get_column(entity_plural, 'name')

        conds: list[str] = []
        params: dict[str, Any] = {}
        if environment:
            env_col = mapper.get_column('servers', 'environment')
            conds.append(f"UPPER(srv.{env_col}) = UPPER(:p_environment)")  # nosec B608
            params['p_environment'] = environment
        if engine_type:
            try:
                eng_col = mapper.get_column('servers', 'engine_type')
                conds.append(f"UPPER(srv.{eng_col}) = UPPER(:p_engine_type)")  # nosec B608
                params['p_engine_type'] = engine_type
            except MapperValidationError:
                logger.warning("engine_type_not_mapped_in_servers", entity=entity_plural,
                               engine_type=engine_type, correlation_id=correlation_id)
        if server_name:
            if ref_join_id:
                conds.append(f"UPPER(srv.{srv_name_col}) = UPPER(:p_server_ref)")
            else:
                conds.append(f"UPPER(inst.{inst_sref_col}) = UPPER(:p_server_ref)")
            params['p_server_ref'] = server_name

        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        inner = (
            f"SELECT {aliased} FROM {table} inst "  # nosec B608
            f"INNER JOIN {srv_table} srv ON {srv_join_on} "  # nosec B608
            f"{where} ORDER BY inst.{name_col}"  # nosec B608
        )
        return ResultPaginator.apply_rownum_limit(inner), params

    def _build_database_join_query(
        self,
        db_table: str,
        environment: str | None,
        engine_type: str | None,
        correlation_id: str | None,
    ) -> tuple[str, dict]:
        mapper = self._mapper
        inst_table = mapper.get_table_name('instances')
        srv_table = mapper.get_table_name('servers')
        db_name_col = mapper.get_column('databases', 'name')
        inst_db_ref = mapper.get_column('instances', 'db_ref')
        inst_srv_ref = mapper.get_column('instances', 'server_ref')
        ref_join_id = mapper.refs_join_on_id('instances')
        srv_name_col = mapper.get_column('servers', 'name')

        if ref_join_id:
            db_id_col = mapper.get_id_column('databases')
            srv_id_col = mapper.get_id_column('servers')
            db_join = f"i.{inst_db_ref} = d.{db_id_col}"
            srv_join = f"i.{inst_srv_ref} = srv.{srv_id_col}"
        else:
            db_join = f"UPPER(i.{inst_db_ref}) = UPPER(d.{db_name_col})"
            srv_join = f"UPPER(i.{inst_srv_ref}) = UPPER(srv.{srv_name_col})"

        aliased = self._build_aliased_select(mapper.get_entity_config('databases') or {}, 'd')
        conds: list[str] = []
        params: dict[str, Any] = {}

        if environment:
            env_col = mapper.get_column('servers', 'environment')
            conds.append(f"UPPER(srv.{env_col}) = UPPER(:p_environment)")  # nosec B608
            params['p_environment'] = environment
        if engine_type:
            try:
                eng_col = mapper.get_column('servers', 'engine_type')
                conds.append(f"UPPER(srv.{eng_col}) = UPPER(:p_engine_type)")  # nosec B608
                params['p_engine_type'] = engine_type
            except MapperValidationError:
                logger.warning("engine_type_not_mapped_in_servers", entity="databases",
                               engine_type=engine_type, correlation_id=correlation_id)

        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        inner = (
            f"SELECT DISTINCT {aliased} FROM {db_table} d "  # nosec B608
            f"INNER JOIN {inst_table} i ON {db_join} "  # nosec B608
            f"INNER JOIN {srv_table} srv ON {srv_join} "  # nosec B608
            f"{where} ORDER BY d.{db_name_col}"  # nosec B608
        )
        return ResultPaginator.apply_rownum_limit(inner), params

    def _build_simple_entity_query(
        self,
        entity_type: str,
        entity_plural: str,
        table: str,
        environment: str | None,
        engine_type: str | None,
        server_name: str | None,
        has_servers_config: bool,
        correlation_id: str | None,
    ) -> tuple[str, dict]:
        mapper = self._mapper
        filters: dict[str, Any] = {}
        if environment:
            filters['environment'] = environment
        if engine_type and entity_type == 'server':
            filters['engine_type'] = engine_type
        if server_name and entity_type == 'instance' and not mapper.refs_join_on_id(entity_plural):
            filters['server_ref'] = server_name

        where_clause, params = mapper.build_where_clause(entity_plural, filters)
        name_col = mapper.get_column(entity_plural, 'name')
        alias = "inst" if entity_type == "instance" else "e"

        need_join = (
            server_name and entity_type == 'instance'
            and mapper.refs_join_on_id(entity_plural)
            and has_servers_config
        )

        if need_join:
            select = self._build_aliased_select(mapper.get_entity_config(entity_plural) or {}, alias)
        else:
            select = mapper.build_select_clause(entity_plural)

        inner = f"SELECT {select} FROM {table} {alias}"  # nosec B608

        if need_join:
            srv_table = mapper.get_table_name('servers')
            sref_col = mapper.get_column(entity_plural, 'server_ref')
            srv_id_col = mapper.get_id_column('servers')
            srv_name_col = mapper.get_column('servers', 'name')
            join = f" INNER JOIN {srv_table} srv ON {alias}.{sref_col} = srv.{srv_id_col}"
            srv_filter = f"UPPER(srv.{srv_name_col}) = UPPER(:p_server_ref)"
            params = dict(params, p_server_ref=server_name)
            inner += join
            inner += (
                f" WHERE {srv_filter}" if not where_clause
                else f" WHERE {where_clause} AND {srv_filter}"
            )
        elif where_clause:
            inner += f" WHERE {where_clause}"

        inner += f" ORDER BY {alias}.{name_col}"
        return ResultPaginator.apply_rownum_limit(inner), params

    def _build_entity_multi_server_query(
        self,
        entity_plural: str,
        environment: str,
        server_names: list[str],
        engine_type: str | None,
        correlation_id: str | None,
    ) -> tuple[str, dict]:
        if entity_plural == 'databases':
            return self._build_databases_multi_server_query(
                environment, server_names, engine_type, correlation_id
            )

        mapper = self._mapper
        table = mapper.get_table_name(entity_plural)
        sref_col = mapper.get_column(entity_plural, 'server_ref')
        ref_join_id = mapper.refs_join_on_id(entity_plural)
        srv_table = mapper.get_table_name('servers')
        srv_name_col = mapper.get_column('servers', 'name')

        if ref_join_id:
            srv_id_col = mapper.get_id_column('servers')
            srv_join = f"inst.{sref_col} = srv.{srv_id_col}"
            filter_alias, filter_col = "srv", srv_name_col
        else:
            srv_join = f"UPPER(inst.{sref_col}) = UPPER(srv.{srv_name_col})"
            filter_alias, filter_col = "inst", sref_col

        in_params = {f'p_server_{i}': sn for i, sn in enumerate(server_names)}
        in_ph = ', '.join(f"UPPER(:{k})" for k in in_params)
        params: dict[str, Any] = {**in_params}

        aliased = self._build_aliased_select(mapper.get_entity_config(entity_plural) or {}, 'inst')
        name_col = mapper.get_column(entity_plural, 'name')
        srv_env_col = mapper.get_column('servers', 'environment')

        conds: list[str] = []
        if environment:
            conds.append(f"UPPER(srv.{srv_env_col}) = UPPER(:p_environment)")  # nosec B608
            params['p_environment'] = environment
        conds.append(f"UPPER({filter_alias}.{filter_col}) IN ({in_ph})")  # nosec B608
        if engine_type:
            try:
                eng_col = mapper.get_column('servers', 'engine_type')
                conds.append(f"UPPER(srv.{eng_col}) = UPPER(:p_engine_type)")  # nosec B608
                params['p_engine_type'] = engine_type
            except MapperValidationError:
                logger.warning("engine_type_not_mapped_in_servers", entity=entity_plural,
                               engine_type=engine_type, correlation_id=correlation_id)

        where = "WHERE " + " AND ".join(conds)
        inner = (
            f"SELECT {aliased} FROM {table} inst "  # nosec B608
            f"INNER JOIN {srv_table} srv ON {srv_join} "  # nosec B608
            f"{where} ORDER BY inst.{name_col}"
        )
        return ResultPaginator.apply_rownum_limit(inner), params

    def _build_databases_multi_server_query(
        self,
        environment: str,
        server_names: list[str],
        engine_type: str | None,
        correlation_id: str | None,
    ) -> tuple[str, dict]:
        mapper = self._mapper
        entity_config = mapper.get_entity_config('databases')
        if not entity_config or not mapper.get_entity_config('instances'):
            return "", {}

        db_table = mapper.get_table_name('databases')
        inst_table = mapper.get_table_name('instances')
        db_name_col = mapper.get_column('databases', 'name')
        inst_db_ref = mapper.get_column('instances', 'db_ref')
        inst_srv_ref = mapper.get_column('instances', 'server_ref')
        ref_join_id = mapper.refs_join_on_id('instances')
        srv_table = mapper.get_table_name('servers')
        srv_name_col = mapper.get_column('servers', 'name')

        if ref_join_id:
            db_id_col = mapper.get_id_column('databases')
            srv_id_col = mapper.get_id_column('servers')
            db_join = f"i.{inst_db_ref} = d.{db_id_col}"
            srv_join = f"i.{inst_srv_ref} = srv.{srv_id_col}"
            filter_alias, filter_col = "srv", srv_name_col
        else:
            db_join = f"UPPER(i.{inst_db_ref}) = UPPER(d.{db_name_col})"
            srv_join = f"UPPER(i.{inst_srv_ref}) = UPPER(srv.{srv_name_col})"
            filter_alias, filter_col = "i", inst_srv_ref

        aliased = self._build_aliased_select(entity_config, 'd')
        in_params = {f'p_server_{i}': sn for i, sn in enumerate(server_names)}
        in_ph = ', '.join(f"UPPER(:{k})" for k in in_params)
        params: dict[str, Any] = {**in_params}
        srv_env_col = mapper.get_column('servers', 'environment')

        conds: list[str] = []
        if environment:
            conds.append(f"UPPER(srv.{srv_env_col}) = UPPER(:p_environment)")  # nosec B608
            params['p_environment'] = environment
        conds.append(f"UPPER({filter_alias}.{filter_col}) IN ({in_ph})")  # nosec B608
        if engine_type:
            try:
                eng_col = mapper.get_column('servers', 'engine_type')
                conds.append(f"UPPER(srv.{eng_col}) = UPPER(:p_engine_type)")  # nosec B608
                params['p_engine_type'] = engine_type
            except MapperValidationError:
                logger.warning("engine_type_not_mapped_in_servers", entity="databases",
                               engine_type=engine_type, correlation_id=correlation_id)

        where = "WHERE " + " AND ".join(conds)
        inner = (
            f"SELECT DISTINCT {aliased} FROM {db_table} d "  # nosec B608
            f"INNER JOIN {inst_table} i ON {db_join} "  # nosec B608
            f"INNER JOIN {srv_table} srv ON {srv_join} "  # nosec B608
            f"{where} ORDER BY d.{db_name_col}"  # nosec B608
        )
        return ResultPaginator.apply_rownum_limit(inner), params

    def _build_databases_via_instances_query(
        self,
        environment: str | None,
        server_name: str,
        engine_type: str | None,
        correlation_id: str | None,
    ) -> tuple[str, dict]:
        """Build database query filtered by server_name via JOIN databases→instances→servers."""
        mapper = self._mapper
        db_table = mapper.get_table_name('databases')
        inst_table = mapper.get_table_name('instances')
        db_name_col = mapper.get_column('databases', 'name')
        inst_db_ref = mapper.get_column('instances', 'db_ref')
        inst_srv_ref = mapper.get_column('instances', 'server_ref')
        ref_join_id = mapper.refs_join_on_id('instances')
        srv_table = mapper.get_table_name('servers')
        srv_name_col = mapper.get_column('servers', 'name')

        if ref_join_id:
            db_id_col = mapper.get_id_column('databases')
            srv_id_col = mapper.get_id_column('servers')
            db_join = f"i.{inst_db_ref} = d.{db_id_col}"
            srv_join = f"i.{inst_srv_ref} = srv.{srv_id_col}"
            server_filter = f"UPPER(srv.{srv_name_col}) = UPPER(:p_server_name)"
        else:
            db_join = f"UPPER(i.{inst_db_ref}) = UPPER(d.{db_name_col})"
            srv_join = f"UPPER(i.{inst_srv_ref}) = UPPER(srv.{srv_name_col})"
            server_filter = f"UPPER(i.{inst_srv_ref}) = UPPER(:p_server_name)"

        aliased = self._build_aliased_select(mapper.get_entity_config('databases') or {}, 'd')
        base = (
            f"SELECT DISTINCT {aliased} FROM {db_table} d "  # nosec B608
            f"INNER JOIN {inst_table} i ON {db_join} "  # nosec B608
        )
        params: dict[str, Any] = {'p_server_name': server_name}
        has_srv = mapper.get_entity_config('servers') is not None

        inner = self._apply_dvi_where(
            base, params, environment, engine_type, server_filter,
            srv_table, srv_join, srv_name_col, ref_join_id, has_srv, correlation_id
        )
        inner += f" ORDER BY d.{db_name_col}"
        return ResultPaginator.apply_rownum_limit(inner), params

    def _apply_dvi_where(
        self,
        base: str,
        params: dict[str, Any],
        environment: str | None,
        engine_type: str | None,
        server_filter: str,
        srv_table: str,
        srv_join: str,
        srv_name_col: str,
        ref_join_id: bool,
        has_srv: bool,
        correlation_id: str | None,
    ) -> str:
        """Attach WHERE/JOIN clause for _build_databases_via_instances_query."""
        mapper = self._mapper

        if environment:
            if has_srv:
                env_col = mapper.get_column('servers', 'environment')
                params['p_environment'] = environment
                eng_cond = ""
                if engine_type:
                    try:
                        eng_col = mapper.get_column('servers', 'engine_type')
                        eng_cond = f" AND UPPER(srv.{eng_col}) = UPPER(:p_engine_type)"  # nosec B608
                        params['p_engine_type'] = engine_type
                    except MapperValidationError:
                        logger.warning("engine_type_not_mapped_in_servers",
                                       entity="databases_via_instances",
                                       engine_type=engine_type, correlation_id=correlation_id)
                return (
                    base
                    + f"INNER JOIN {srv_table} srv ON {srv_join} "  # nosec B608
                    + f"WHERE UPPER(srv.{env_col}) = UPPER(:p_environment) "  # nosec B608
                    + f"AND {server_filter}{eng_cond}"  # nosec B608
                )
            else:
                logger.warning("environment_filter_fallback_to_local_column",
                               entity="databases_via_instances",
                               reason="servers entity not configured",
                               correlation_id=correlation_id)
                try:
                    db_env_col = mapper.get_column('databases', 'environment')
                    params['p_environment'] = environment
                    return (
                        base
                        + f"INNER JOIN {srv_table} srv ON {srv_join} "
                        + f"WHERE {server_filter} AND UPPER(d.{db_env_col}) = UPPER(:p_environment)"
                    )
                except MapperValidationError:
                    logger.warning("databases_environment_column_not_mapped",
                                   entity="databases_via_instances",
                                   reason="environment column not mapped, skipping filter",
                                   correlation_id=correlation_id)
                    srv_part = f"INNER JOIN {srv_table} srv ON {srv_join} " if ref_join_id else ""
                    return base + srv_part + f"WHERE {server_filter}"

        elif engine_type and has_srv:
            try:
                eng_col = mapper.get_column('servers', 'engine_type')
                params['p_engine_type'] = engine_type
                return (
                    base
                    + f"INNER JOIN {srv_table} srv ON {srv_join} "  # nosec B608
                    + f"WHERE {server_filter} AND UPPER(srv.{eng_col}) = UPPER(:p_engine_type)"  # nosec B608
                )
            except MapperValidationError:
                logger.warning("engine_type_not_mapped_in_servers",
                               entity="databases_via_instances",
                               engine_type=engine_type, correlation_id=correlation_id)
                return base + f"INNER JOIN {srv_table} srv ON {srv_join} WHERE {server_filter}"
        else:
            if ref_join_id:
                return base + f"INNER JOIN {srv_table} srv ON {srv_join} WHERE {server_filter}"
            return base + f"WHERE {server_filter}"
