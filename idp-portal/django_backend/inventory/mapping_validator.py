"""
MappingValidator: Validates SQL identifiers and mapper column configurations.

Responsibility: Centralise SQL injection prevention for table/column names.
Story 54.14 - AC2: Extracted from InventoryQueryExecutor (MAINT-BE-3).
"""
from __future__ import annotations

from inventory.mapper import (
    SAFE_COLUMN_NAME_PATTERN,
    SAFE_TABLE_NAME_PATTERN,
    InventoryMapper,
    MapperValidationError,
    validate_column_name,  # INV-LOW-01: use public name instead of private _validate_column_name
)


class MappingValidator:
    """
    Validates table names, column names, and mapper configurations against SQL injection.

    Encapsulates all identifier-safety checks previously scattered in InventoryQueryExecutor.
    Story 54.14 - AC2.
    """

    def validate_table_name(self, name: str) -> str:
        """
        Validate a table/synonym name against SAFE_TABLE_NAME_PATTERN.

        Args:
            name: Table or synonym name to validate.

        Returns:
            The validated name (unchanged).

        Raises:
            ValueError: If name is unsafe (potential SQL injection).
                Callers (orchestrator) are responsible for wrapping as InventoryServiceError.
        """
        if not name or not SAFE_TABLE_NAME_PATTERN.match(name):
            raise ValueError(
                f"Invalid table/synonym name: {name}. "
                "Must be alphanumeric with optional schema prefix."
            )
        return name

    def validate_column_name(self, name: str) -> str:
        """
        Validate a SQL column name against SAFE_COLUMN_NAME_PATTERN.

        Args:
            name: Column name to validate.

        Returns:
            The validated name (unchanged).

        Raises:
            MapperValidationError: If name is invalid.
        """
        validate_column_name(name)
        return name

    def validate_mapper_columns(self, mapper: InventoryMapper, entity_name: str) -> None:
        """
        Verify all column names mapped for a given entity are safe SQL identifiers.

        Args:
            mapper: Configured InventoryMapper instance.
            entity_name: Entity name to validate (e.g. 'servers', 'instances', 'databases').

        Raises:
            MapperValidationError: If any column name is invalid.
        """
        entity = mapper.get_entity_config(entity_name)
        if not entity:
            return

        id_col = entity.get('id_column')
        if id_col:
            validate_column_name(id_col)

        for concept, col in entity.get('columns', {}).items():
            if not SAFE_COLUMN_NAME_PATTERN.match(concept):
                raise MapperValidationError(
                    f"Invalid concept name: '{concept}'. "
                    "Must match pattern: [A-Za-z_][A-Za-z0-9_]*"
                )
            validate_column_name(col)
