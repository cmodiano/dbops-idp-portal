"""
ResultPaginator: Handles Oracle pagination for inventory queries.

Responsibility: Encapsulate OFFSET/FETCH NEXT and ROWNUM limit logic.
Story 54.14 - AC3: Extracted from InventoryQueryExecutor (MAINT-BE-3).
"""
from __future__ import annotations

from typing import Any

# Maximum results from multi-table config queries (prevent DoS via unbounded queries)
# Story 23.1 code review fix: prevent out-of-memory from million-row tables
MAX_MULTI_TABLE_RESULTS = 10000

# Maximum results from flat table fallback
MAX_FLAT_TABLE_RESULTS = 10000


class ResultPaginator:
    """
    Handles Oracle pagination with OFFSET/FETCH NEXT and ROWNUM limiting.

    Executes pre-built count and data queries using a caller-provided cursor,
    keeping all connection management in the calling orchestrator.
    Story 54.14 - AC3.
    """

    def paginate_flat(
        self,
        cursor: Any,
        count_sql: str,
        count_params: dict,
        data_sql: str,
        data_params: dict,
    ) -> tuple[list[tuple], int]:
        """
        Execute COUNT and paginated data queries using the provided cursor.

        Args:
            cursor: Active Oracle cursor (opened by caller).
            count_sql: COUNT(*) query string.
            count_params: Bind parameters for the count query.
            data_sql: Paginated SELECT query (OFFSET/FETCH NEXT).
            data_params: Bind parameters for the data query (includes offset/limit).

        Returns:
            Tuple of (raw rows as tuples, total row count).
        """
        cursor.execute(count_sql, count_params)
        total_count = cursor.fetchone()[0]
        cursor.execute(data_sql, data_params)
        rows = cursor.fetchall()
        return rows, total_count

    @staticmethod
    def apply_rownum_limit(sql: str, limit: int = MAX_MULTI_TABLE_RESULTS) -> str:
        """Wrap SQL in ROWNUM <= limit subquery for DoS prevention."""
        return f"SELECT * FROM ({sql}) WHERE ROWNUM <= {limit}"  # nosec B608 — limit is an integer constant

    @staticmethod
    def build_flat_table_sql(
        table: str,
        name_col: str,
        env_col: str,
        type_col: str,
        conditions: list[str],
        filter_params: dict,
        page: int,
        page_size: int,
    ) -> tuple[str, dict, str, dict]:
        """
        Build count and paginated SELECT queries for a flat Oracle table.

        Returns:
            (count_sql, count_params, data_sql, data_params)
        """
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        count_sql = f"SELECT COUNT(*) FROM {table} {where}"  # nosec B608 — table validated by caller
        offset = (page - 1) * page_size
        data_params = dict(filter_params, offset=offset, limit=page_size)
        data_sql = (
            f"SELECT {name_col}, {env_col}, {type_col} FROM {table} "  # nosec B608 — identifiers validated by caller
            f"{where} ORDER BY {name_col} "
            "OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY"
        )
        return count_sql, filter_params, data_sql, data_params
