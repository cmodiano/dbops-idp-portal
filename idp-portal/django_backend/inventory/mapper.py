"""
InventoryMapper: Configuration-driven inventory column mapping and SQL query building.
Story 23.1 — Translates business concepts to real column names via declarative config.

Config format (stored in Integration.config JSON):
  Multi-tables:
    {
      "entities": {
        "servers": {
          "table": "SERVER",
          "id_column": "ID",
          "columns": {"name": "NAME", "environment": "ENVIRONMENT", "engine_type": "ENGINE_TYPE"}
        },
        "instances": {
          "table": "INSTANCE",
          "id_column": "ID",
          "columns": {"name": "NAME", "server_ref": "SERVER_ID", "db_ref": "DB_ID"},
          "ref_join": "id"
        },
        "databases": {
          "table": "DB",
          "id_column": "ID",
          "columns": {"name": "NAME"}
        }
      }
    }

  ref_join: When "id", server_ref/db_ref are FK columns (e.g. SERVER_ID, DB_ID).
    Joins use inst.server_ref = srv.id_column instead of inst.server_ref = srv.name.
    Omit or use "name" for legacy name-based refs.

  Note on environment filtering (Story 37.1):
    When the 'servers' entity is configured, the environment filter for instances and
    databases is derived from the servers table via JOIN, not from the local 'environment'
    column on instances/databases. The local 'environment' column on instances/databases
    is optional in "env-from-server" mode; it may be mapped but will be ignored for
    environment filtering purposes.

  Flat table (fallback):
    {
      "flat_table": {
        "table": "DBOPS_INVENTORY",
        "columns": {"name": "NAME", "environment": "ENVIRONMENT", "type": "TYPE"}
      }
    }
"""

from __future__ import annotations

import re
from typing import Any, cast
import structlog

from core.middleware import get_correlation_id

logger = structlog.get_logger(__name__)

# Security: strict patterns for SQL identifiers — alphanumeric + underscore, starts with letter/underscore
# Reuses the same philosophy as SAFE_TABLE_NAME_PATTERN in services.py, extended for schema.table
SAFE_TABLE_NAME_PATTERN = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$')
SAFE_COLUMN_NAME_PATTERN = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


class MapperValidationError(Exception):
    """Raised when config validation or SQL identifier validation fails."""
    pass


class InventoryMapper:
    """
    Translates business concepts (name, environment, engine_type) to real DB columns
    based on a declarative configuration. Builds safe SQL fragments.
    """

    def __init__(self, config: dict):
        """
        Initialize mapper with integration config.

        Args:
            config: Integration config dict containing 'entities' or 'flat_table'
        """
        self._config = config or {}
        self._entities = self._config.get('entities') or {}
        self._flat_table = self._config.get('flat_table')

    @property
    def is_multi_table(self) -> bool:
        """True if config defines multi-table entities (servers, instances, databases)."""
        return bool(self._entities.get('servers'))

    @property
    def is_flat_table(self) -> bool:
        """True if config only defines a flat table (fallback mode)."""
        return not self.is_multi_table and self._flat_table is not None

    def get_entity_config(self, entity_name: str) -> dict[str, Any] | None:
        """
        Get configuration for a specific entity.

        Args:
            entity_name: Entity name (servers, instances, databases)

        Returns:
            Entity config dict or None if not defined
        """
        return self._entities.get(entity_name)

    def get_table_name(self, entity_name: str) -> str:
        """
        Get and validate the table name for an entity.
        Prepends config.schema when table has no schema prefix (no dot).

        Args:
            entity_name: Entity name (servers, instances, databases)

        Returns:
            Validated table name (schema.table if schema configured and table has no dot)

        Raises:
            MapperValidationError: If entity not configured or table name invalid
        """
        entity = self.get_entity_config(entity_name)
        if not entity:
            raise MapperValidationError(
                f"Entity '{entity_name}' not configured in mapping"
            )
        table = entity.get('table')
        if not table:
            raise MapperValidationError(
                f"Entity '{entity_name}' missing 'table' in config"
            )
        _validate_table_name(table)
        # Prepend schema if table has no schema prefix and config has schema
        schema = self._config.get('schema') or self._config.get('db_schema')
        if schema and '.' not in table:
            full_name = f"{schema}.{table}"
            _validate_table_name(full_name)
            return full_name
        return cast(str, table)

    def get_column(self, entity_name: str, concept: str) -> str:
        """
        Get the real column name for a business concept.

        Args:
            entity_name: Entity name (servers, instances, databases)
            concept: Business concept (name, environment, engine_type, server_ref, etc.)

        Returns:
            Real column name

        Raises:
            MapperValidationError: If entity/concept not found or column name invalid
        """
        entity = self.get_entity_config(entity_name)
        if not entity:
            raise MapperValidationError(
                f"Entity '{entity_name}' not configured in mapping"
            )
        columns = entity.get('columns', {})
        col = columns.get(concept)
        if not col:
            raise MapperValidationError(
                f"Column concept '{concept}' not mapped for entity '{entity_name}'"
            )
        _validate_column_name(col)
        return cast(str, col)

    def get_id_column(self, entity_name: str) -> str:
        """
        Get the ID column for an entity.

        Args:
            entity_name: Entity name

        Returns:
            ID column name

        Raises:
            MapperValidationError: If entity not found or id_column not configured
        """
        entity = self.get_entity_config(entity_name)
        if not entity:
            raise MapperValidationError(
                f"Entity '{entity_name}' not configured in mapping"
            )
        id_col = entity.get('id_column')
        if not id_col:
            raise MapperValidationError(
                f"Entity '{entity_name}' missing 'id_column' in config"
            )
        _validate_column_name(id_col)
        return cast(str, id_col)

    def refs_join_on_id(self, entity_name: str) -> bool:
        """
        True if server_ref/db_ref columns are FK IDs (join on target id_column).
        When False, refs hold names (join on target name column).

        Args:
            entity_name: Entity name (e.g. 'instances')

        Returns:
            True if ref_join is 'id', else False
        """
        entity = self.get_entity_config(entity_name)
        if not entity:
            return False
        return (entity.get('ref_join') or '').lower() == 'id'

    def build_select_clause(self, entity_name: str) -> str:
        """
        Build SELECT clause with aliased columns for an entity.
        Example: "HOSTNAME AS name, ENV AS environment, ENGINE AS engine_type"

        Args:
            entity_name: Entity name

        Returns:
            SQL SELECT clause string (without SELECT keyword)

        Raises:
            MapperValidationError: If entity not configured or columns invalid
        """
        entity = self.get_entity_config(entity_name)
        if not entity:
            raise MapperValidationError(
                f"Entity '{entity_name}' not configured in mapping"
            )
        columns = entity.get('columns', {})
        if not columns:
            raise MapperValidationError(
                f"Entity '{entity_name}' has no columns mapped"
            )

        id_col = entity.get('id_column')
        parts = []

        # Include id_column first if defined
        if id_col:
            _validate_column_name(id_col)
            parts.append(f"{id_col} AS id")

        # Add mapped columns
        for concept, real_col in columns.items():
            _validate_column_name(real_col)
            parts.append(f"{real_col} AS {concept}")

        return ", ".join(parts)

    def build_where_clause(self, entity_name: str, filters: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """
        Build WHERE clause using mapped columns.
        Filter keys are business concepts; values are filter values.

        Args:
            entity_name: Entity name
            filters: Dict of {concept: value} to filter on

        Returns:
            Tuple of (WHERE clause string without WHERE keyword, bind params dict)
            Empty string and empty dict if no filters.

        Raises:
            MapperValidationError: If column concept not found or name invalid
        """
        if not filters:
            return "", {}

        conditions = []
        params = {}
        for concept, value in filters.items():
            if value is None:
                continue
            # Security: validate concept name to prevent SQL injection via param names
            # Concept names must match column pattern (alphanumeric + underscore)
            if not SAFE_COLUMN_NAME_PATTERN.match(concept):
                correlation_id = get_correlation_id()
                logger.warning(
                    "invalid_filter_concept",
                    concept=concept,
                    correlation_id=correlation_id,
                )
                raise MapperValidationError(
                    f"Invalid filter concept name: '{concept}'. "
                    "Must match pattern: [A-Za-z_][A-Za-z0-9_]*"
                )
            real_col = self.get_column(entity_name, concept)
            param_name = f"p_{concept}"
            conditions.append(f"UPPER({real_col}) = UPPER(:{param_name})")
            params[param_name] = value

        if not conditions:
            return "", {}

        return " AND ".join(conditions), params

    @staticmethod
    def get_available_concepts(entity_name: str = 'servers') -> list[str]:
        """
        Get available concept keys for the specified entity type.

        Concept keys are stable attribute names defined in the inventory mapping config,
        independent of actual Oracle column names. Used for RBAC filter validation (Story 23.4).

        Performance Note:
            Instantiates InventoryService internally, which queries the Integration DB.
            Avoid calling repeatedly in loops - cache result if needed.

        Args:
            entity_name: Entity type ('servers', 'instances', 'databases')

        Returns:
            List of concept keys (e.g., ['name', 'environment', 'engine_type', ...])

        Story 23.4 - AC5.
        """
        from inventory.services import InventoryService

        service = InventoryService()
        mapper = service._get_inventory_mapper()

        if mapper and mapper.is_multi_table:
            # Code review fix: validate config before reading to prevent SQL injection via malicious config
            errors = mapper.validate_config()
            if errors:
                correlation_id = get_correlation_id()
                logger.error(
                    "inventory_mapper_config_invalid_in_get_available_concepts",
                    entity_name=entity_name,
                    validation_errors=errors,
                    correlation_id=correlation_id,
                )
                # Fallback to safe defaults if config is invalid
                return ['name', 'environment', 'type']

            entity = mapper.get_entity_config(entity_name)
            if entity:
                columns = entity.get('columns', {})
                if columns:
                    return list(columns.keys())

        # Fallback: default concepts for flat table mode
        return ['name', 'environment', 'type']

    def validate_config(self) -> list[str]:
        """
        Validate the entire mapping configuration.
        Returns a list of error messages (empty if valid).

        Returns:
            List of validation error messages
        """
        errors = []

        if not self._entities and not self._flat_table:
            errors.append("Config must define 'entities' or 'flat_table'")
            return errors

        # Validate entities
        for entity_name, entity_config in self._entities.items():
            if not isinstance(entity_config, dict):
                errors.append(f"Entity '{entity_name}' must be a dict")
                continue

            table = entity_config.get('table')
            if not table:
                errors.append(f"Entity '{entity_name}' missing 'table'")
            else:
                try:
                    _validate_table_name(table)
                except MapperValidationError as e:
                    errors.append(str(e))

            columns = entity_config.get('columns', {})
            if not columns:
                errors.append(f"Entity '{entity_name}' has no 'columns' mapping")
            else:
                for concept, col_name in columns.items():
                    try:
                        _validate_column_name(col_name)
                    except MapperValidationError as e:
                        errors.append(f"Entity '{entity_name}', concept '{concept}': {e}")

            id_col = entity_config.get('id_column')
            if id_col:
                try:
                    _validate_column_name(id_col)
                except MapperValidationError as e:
                    errors.append(f"Entity '{entity_name}' id_column: {e}")

        # Validate flat_table
        if self._flat_table:
            if not isinstance(self._flat_table, dict):
                errors.append("'flat_table' must be a dict")
            else:
                table = self._flat_table.get('table')
                if not table:
                    errors.append("flat_table missing 'table'")
                else:
                    try:
                        _validate_table_name(table)
                    except MapperValidationError as e:
                        errors.append(str(e))

                columns = self._flat_table.get('columns', {})
                if not columns:
                    errors.append("flat_table has no 'columns' mapping")
                else:
                    for concept, col_name in columns.items():
                        try:
                            _validate_column_name(col_name)
                        except MapperValidationError as e:
                            errors.append(f"flat_table concept '{concept}': {e}")

        return errors


def _validate_table_name(name: str) -> None:
    """
    Validate a SQL table/view name against safe pattern and Oracle length limits.

    Args:
        name: Table or view name to validate

    Raises:
        MapperValidationError: If name doesn't match safe pattern or exceeds Oracle limits
    """
    if not name or not SAFE_TABLE_NAME_PATTERN.match(name):
        correlation_id = get_correlation_id()
        logger.warning(
            "invalid_table_name",
            table_name=name,
            correlation_id=correlation_id,
        )
        raise MapperValidationError(
            f"Invalid table name: '{name}'. "
            "Must match pattern: [A-Za-z_][A-Za-z0-9_]*(.[A-Za-z_][A-Za-z0-9_]*)?"
        )

    # Oracle identifier length limit: 30 chars (< 12.2) or 128 chars (>= 12.2)
    # Use conservative 30 char limit per identifier part
    parts = name.split('.')
    for part in parts:
        if len(part) > 30:
            correlation_id = get_correlation_id()
            logger.warning(
                "table_name_too_long",
                table_name=name,
                part=part,
                length=len(part),
                correlation_id=correlation_id,
            )
            raise MapperValidationError(
                f"Table name part '{part}' exceeds Oracle 30 character limit (length: {len(part)})"
            )


def _validate_column_name(name: str) -> None:
    """
    Validate a SQL column name against safe pattern and Oracle length limits.

    Args:
        name: Column name to validate

    Raises:
        MapperValidationError: If name doesn't match safe pattern or exceeds Oracle limits
    """
    if not name or not SAFE_COLUMN_NAME_PATTERN.match(name):
        correlation_id = get_correlation_id()
        logger.warning(
            "invalid_column_name",
            column_name=name,
            correlation_id=correlation_id,
        )
        raise MapperValidationError(
            f"Invalid column name: '{name}'. "
            "Must match pattern: [A-Za-z_][A-Za-z0-9_]*"
        )

    # Oracle identifier length limit: 30 chars (conservative limit)
    if len(name) > 30:
        correlation_id = get_correlation_id()
        logger.warning(
            "column_name_too_long",
            column_name=name,
            length=len(name),
            correlation_id=correlation_id,
        )
        raise MapperValidationError(
            f"Column name '{name}' exceeds Oracle 30 character limit (length: {len(name)})"
        )
