"""
Tests for _find_workflows_referencing_action DB-side filtering optimization (Story 30.9, PERF-2).
Updated in Story 54.10 (MAINT-BE-5) to cover Oracle JSON_EXISTS branch and edge cases.

Verifies:
- DB-side pre-filter via execution_steps__contains (SQLite/non-Oracle path)
- Oracle JSON_EXISTS path via connection.vendor == 'oracle'
- Python-level exact match validation (no false positives)
- Edge cases: no matches, empty steps, non-matching action_id, prefix/suffix collisions

LIMITATION: These are unit tests with mocked ORM. They verify logic but NOT actual Oracle
DB compatibility with JSON_EXISTS on JSONField/CLOB. Integration testing
with real DB is required to validate Oracle-specific behavior.

TODO: Add integration test with real DB fixtures to verify Oracle JSONField __contains support.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock


from catalog.services import CatalogService


class TestFindWorkflowsReferencingActionOptimized:
    """Tests for _find_workflows_referencing_action DB-side filtering (PERF-2, MAINT-BE-5)."""

    def setup_method(self):
        self.service = CatalogService()

    @patch("catalog.services.connection")
    @patch("catalog.services.Action.objects")
    def test_uses_db_contains_filter_on_sqlite(self, mock_objects, mock_conn):
        """Verifies the queryset uses execution_steps__contains for DB-side filtering on non-Oracle."""
        mock_conn.vendor = 'sqlite'
        mock_base_qs = MagicMock()
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([]))
        mock_objects.filter.return_value = mock_base_qs
        mock_base_qs.filter.return_value = mock_qs

        self.service._find_workflows_referencing_action(42)

        mock_objects.filter.assert_called_once()
        mock_base_qs.filter.assert_called_once()
        call_kwargs = mock_base_qs.filter.call_args[1]
        assert call_kwargs.get("execution_steps__contains") == "42"

    @patch("catalog.services.connection")
    @patch("catalog.services.Action.objects")
    def test_matching_workflow_returned(self, mock_objects, mock_conn):
        """Workflow with matching referenced_action_id is returned."""
        mock_conn.vendor = 'sqlite'
        wf = MagicMock()
        wf.execution_steps = [{"referenced_action_id": 42, "name": "step1"}]

        mock_base_qs = MagicMock()
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([wf]))
        mock_objects.filter.return_value = mock_base_qs
        mock_base_qs.filter.return_value = mock_qs

        result = self.service._find_workflows_referencing_action(42)
        assert result == [wf]

    @patch("catalog.services.connection")
    @patch("catalog.services.Action.objects")
    def test_false_positive_filtered_out(self, mock_objects, mock_conn):
        """Workflow where "42" appears in multiple JSON fields but referenced_action_id is 421.

        Tests the compound false positive case: "42" present in both referenced_action_id
        (as part of 421) and in the step name. Python validation must filter both.
        See also: test_edge_case_42_does_not_match_421 for the single-field edge case (AC-4).
        """
        mock_conn.vendor = 'sqlite'
        wf = MagicMock()
        # "42" appears in text but referenced_action_id is 421 (false positive from text filter)
        wf.execution_steps = [{"referenced_action_id": 421, "name": "step with 42 in name"}]

        mock_base_qs = MagicMock()
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([wf]))
        mock_objects.filter.return_value = mock_base_qs
        mock_base_qs.filter.return_value = mock_qs

        result = self.service._find_workflows_referencing_action(42)
        assert result == []

    @patch("catalog.services.connection")
    @patch("catalog.services.Action.objects")
    def test_no_matching_workflows(self, mock_objects, mock_conn):
        """No workflows match the action_id."""
        mock_conn.vendor = 'sqlite'
        mock_base_qs = MagicMock()
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([]))
        mock_objects.filter.return_value = mock_base_qs
        mock_base_qs.filter.return_value = mock_qs

        result = self.service._find_workflows_referencing_action(99)
        assert result == []

    @patch("catalog.services.connection")
    @patch("catalog.services.Action.objects")
    def test_empty_execution_steps_skipped(self, mock_objects, mock_conn):
        """Workflow with None or empty execution_steps is skipped."""
        mock_conn.vendor = 'sqlite'
        wf1 = MagicMock()
        wf1.execution_steps = None
        wf2 = MagicMock()
        wf2.execution_steps = []

        mock_base_qs = MagicMock()
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([wf1, wf2]))
        mock_objects.filter.return_value = mock_base_qs
        mock_base_qs.filter.return_value = mock_qs

        result = self.service._find_workflows_referencing_action(42)
        assert result == []

    @patch("catalog.services.connection")
    @patch("catalog.services.Action.objects")
    def test_multiple_steps_one_matches(self, mock_objects, mock_conn):
        """Workflow with multiple steps where only one references the action_id."""
        mock_conn.vendor = 'sqlite'
        wf = MagicMock()
        wf.execution_steps = [
            {"referenced_action_id": 10, "name": "step1"},
            {"referenced_action_id": 42, "name": "step2"},
            {"referenced_action_id": 30, "name": "step3"},
        ]

        mock_base_qs = MagicMock()
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([wf]))
        mock_objects.filter.return_value = mock_base_qs
        mock_base_qs.filter.return_value = mock_qs

        result = self.service._find_workflows_referencing_action(42)
        assert result == [wf]

    @patch("catalog.services.connection")
    @patch("catalog.services.Action.objects")
    def test_does_not_load_all_workflows(self, mock_objects, mock_conn):
        """Verifies that filter is called with contains (not .all())."""
        mock_conn.vendor = 'sqlite'
        mock_base_qs = MagicMock()
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([]))
        mock_objects.filter.return_value = mock_base_qs
        mock_base_qs.filter.return_value = mock_qs

        self.service._find_workflows_referencing_action(42)

        # .all() should NOT be called
        mock_objects.all.assert_not_called()
        # .filter() should be called with execution_steps__contains on the base queryset
        assert mock_base_qs.filter.called

    # --- Oracle JSON_EXISTS path tests ---

    @patch("catalog.services.connection")
    @patch("catalog.services.Action.objects")
    def test_uses_json_exists_on_oracle(self, mock_objects, mock_conn):
        """Vérifie que JSON_EXISTS est utilisé sur Oracle."""
        mock_conn.vendor = 'oracle'
        mock_base_qs = MagicMock()
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([]))
        mock_objects.filter.return_value = mock_base_qs
        mock_base_qs.extra.return_value = mock_qs

        self.service._find_workflows_referencing_action(42)

        mock_base_qs.extra.assert_called_once()
        where_clause = mock_base_qs.extra.call_args[1]['where'][0]
        assert 'JSON_EXISTS' in where_clause
        # Verify the precise JSON path syntax including the filter expression
        assert "$[*]?(@.referenced_action_id == 42)" in where_clause

    @patch("catalog.services.connection")
    @patch("catalog.services.Action.objects")
    def test_oracle_path_does_not_use_text_filter(self, mock_objects, mock_conn):
        """Sur Oracle, le filtre texte (execution_steps__contains) n'est pas utilisé."""
        mock_conn.vendor = 'oracle'
        mock_base_qs = MagicMock()
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([]))
        mock_objects.filter.return_value = mock_base_qs
        mock_base_qs.extra.return_value = mock_qs

        self.service._find_workflows_referencing_action(42)

        # On Oracle, chained .filter(execution_steps__contains=...) must NOT be called
        mock_base_qs.filter.assert_not_called()

    @patch("catalog.services.connection")
    @patch("catalog.services.Action.objects")
    def test_oracle_matching_workflow_returned(self, mock_objects, mock_conn):
        """Sur Oracle, un workflow avec referenced_action_id correct est bien retourné."""
        mock_conn.vendor = 'oracle'
        wf = MagicMock()
        wf.execution_steps = [{"referenced_action_id": 42, "name": "step"}]

        mock_base_qs = MagicMock()
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([wf]))
        mock_objects.filter.return_value = mock_base_qs
        mock_base_qs.extra.return_value = mock_qs

        result = self.service._find_workflows_referencing_action(42)
        assert result == [wf]

    @patch("catalog.services.connection")
    @patch("catalog.services.Action.objects")
    def test_oracle_python_validation_still_applied(self, mock_objects, mock_conn):
        """Sur Oracle, la validation Python filtre toujours les mauvaises données."""
        mock_conn.vendor = 'oracle'
        wf = MagicMock()
        # Simule un résultat Oracle avec referenced_action_id incorrect (données malformées)
        wf.execution_steps = [{"referenced_action_id": 421, "name": "step"}]

        mock_base_qs = MagicMock()
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([wf]))
        mock_objects.filter.return_value = mock_base_qs
        mock_base_qs.extra.return_value = mock_qs

        result = self.service._find_workflows_referencing_action(42)
        assert result == []

    # --- Edge case tests (AC-4) ---

    @patch("catalog.services.connection")
    @patch("catalog.services.Action.objects")
    def test_edge_case_42_does_not_match_421(self, mock_objects, mock_conn):
        """action_id=42 ne doit pas matcher referenced_action_id=421 (prefix forward)."""
        mock_conn.vendor = 'sqlite'
        wf = MagicMock()
        wf.execution_steps = [{"referenced_action_id": 421, "name": "step"}]

        mock_base_qs = MagicMock()
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([wf]))
        mock_objects.filter.return_value = mock_base_qs
        mock_base_qs.filter.return_value = mock_qs

        result = self.service._find_workflows_referencing_action(42)
        assert result == []  # Python validation filtre le faux positif DB

    @patch("catalog.services.connection")
    @patch("catalog.services.Action.objects")
    def test_edge_case_4_does_not_match_42(self, mock_objects, mock_conn):
        """action_id=4 ne doit pas matcher referenced_action_id=42 (prefix forward avec DB filter actuel)."""
        mock_conn.vendor = 'sqlite'
        wf = MagicMock()
        wf.execution_steps = [{"referenced_action_id": 42, "name": "step"}]

        mock_base_qs = MagicMock()
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([wf]))
        mock_objects.filter.return_value = mock_base_qs
        mock_base_qs.filter.return_value = mock_qs

        result = self.service._find_workflows_referencing_action(4)
        assert result == []  # Python validation filtre le faux positif DB

    @patch("catalog.services.connection")
    @patch("catalog.services.Action.objects")
    def test_edge_case_42_does_not_match_142(self, mock_objects, mock_conn):
        """action_id=42 ne doit pas matcher referenced_action_id=142 (suffix match)."""
        mock_conn.vendor = 'sqlite'
        wf = MagicMock()
        wf.execution_steps = [{"referenced_action_id": 142, "name": "step"}]

        mock_base_qs = MagicMock()
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([wf]))
        mock_objects.filter.return_value = mock_base_qs
        mock_base_qs.filter.return_value = mock_qs

        result = self.service._find_workflows_referencing_action(42)
        assert result == []

    @patch("catalog.services.connection")
    @patch("catalog.services.Action.objects")
    def test_edge_case_42_does_not_match_420(self, mock_objects, mock_conn):
        """action_id=42 ne doit pas matcher referenced_action_id=420 (différence en suffixe)."""
        mock_conn.vendor = 'sqlite'
        wf = MagicMock()
        wf.execution_steps = [{"referenced_action_id": 420, "name": "step"}]

        mock_base_qs = MagicMock()
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([wf]))
        mock_objects.filter.return_value = mock_base_qs
        mock_base_qs.filter.return_value = mock_qs

        result = self.service._find_workflows_referencing_action(42)
        assert result == []

    @patch("catalog.services.connection")
    @patch("catalog.services.Action.objects")
    def test_step_without_referenced_action_id_key(self, mock_objects, mock_conn):
        """Step dict without referenced_action_id key is safely skipped (get() returns None)."""
        mock_conn.vendor = 'sqlite'
        wf = MagicMock()
        wf.execution_steps = [{"name": "step_without_ref_id", "type": "some_type"}]

        mock_base_qs = MagicMock()
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([wf]))
        mock_objects.filter.return_value = mock_base_qs
        mock_base_qs.filter.return_value = mock_qs

        result = self.service._find_workflows_referencing_action(42)
        assert result == []
