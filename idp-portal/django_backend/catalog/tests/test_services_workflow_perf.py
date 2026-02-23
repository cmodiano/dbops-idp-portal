"""
Tests for _find_workflows_referencing_action DB-side filtering optimization (Story 30.9, PERF-2).

Verifies:
- DB-side pre-filter via execution_steps__contains instead of loading all workflows
- Python-level exact match validation (no false positives)
- Edge cases: no matches, empty steps, non-matching action_id

LIMITATION: These are unit tests with mocked ORM. They verify logic but NOT actual Oracle
DB compatibility with execution_steps__contains on JSONField/CLOB. Integration testing
with real DB is required to validate Oracle-specific behavior.

TODO: Add integration test with real DB fixtures to verify Oracle JSONField __contains support.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock


from catalog.services import CatalogService


class TestFindWorkflowsReferencingActionOptimized:
    """Tests for _find_workflows_referencing_action DB-side filtering (PERF-2)."""

    def setup_method(self):
        self.service = CatalogService()

    @patch("catalog.services.Action.objects")
    def test_uses_db_contains_filter(self, mock_objects):
        """Verifies the queryset uses execution_steps__contains for DB-side filtering."""
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([]))
        mock_objects.filter.return_value = mock_qs

        self.service._find_workflows_referencing_action(42)

        mock_objects.filter.assert_called_once()
        call_kwargs = mock_objects.filter.call_args[1]
        assert call_kwargs.get("execution_steps__contains") == "42"

    @patch("catalog.services.Action.objects")
    def test_matching_workflow_returned(self, mock_objects):
        """Workflow with matching referenced_action_id is returned."""
        wf = MagicMock()
        wf.execution_steps = [{"referenced_action_id": 42, "name": "step1"}]

        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([wf]))
        mock_objects.filter.return_value = mock_qs

        result = self.service._find_workflows_referencing_action(42)
        assert result == [wf]

    @patch("catalog.services.Action.objects")
    def test_false_positive_filtered_out(self, mock_objects):
        """Workflow containing action_id string but not as referenced_action_id is excluded."""
        wf = MagicMock()
        # "42" appears in text but referenced_action_id is 421 (false positive from text filter)
        wf.execution_steps = [{"referenced_action_id": 421, "name": "step with 42 in name"}]

        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([wf]))
        mock_objects.filter.return_value = mock_qs

        result = self.service._find_workflows_referencing_action(42)
        assert result == []

    @patch("catalog.services.Action.objects")
    def test_no_matching_workflows(self, mock_objects):
        """No workflows match the action_id."""
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([]))
        mock_objects.filter.return_value = mock_qs

        result = self.service._find_workflows_referencing_action(99)
        assert result == []

    @patch("catalog.services.Action.objects")
    def test_empty_execution_steps_skipped(self, mock_objects):
        """Workflow with None or empty execution_steps is skipped."""
        wf1 = MagicMock()
        wf1.execution_steps = None
        wf2 = MagicMock()
        wf2.execution_steps = []

        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([wf1, wf2]))
        mock_objects.filter.return_value = mock_qs

        result = self.service._find_workflows_referencing_action(42)
        assert result == []

    @patch("catalog.services.Action.objects")
    def test_multiple_steps_one_matches(self, mock_objects):
        """Workflow with multiple steps where only one references the action_id."""
        wf = MagicMock()
        wf.execution_steps = [
            {"referenced_action_id": 10, "name": "step1"},
            {"referenced_action_id": 42, "name": "step2"},
            {"referenced_action_id": 30, "name": "step3"},
        ]

        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([wf]))
        mock_objects.filter.return_value = mock_qs

        result = self.service._find_workflows_referencing_action(42)
        assert result == [wf]

    @patch("catalog.services.Action.objects")
    def test_does_not_load_all_workflows(self, mock_objects):
        """Verifies that filter is called with contains (not .all())."""
        mock_qs = MagicMock()
        mock_qs.__iter__ = MagicMock(return_value=iter([]))
        mock_objects.filter.return_value = mock_qs

        self.service._find_workflows_referencing_action(42)

        # .all() should NOT be called
        mock_objects.all.assert_not_called()
        # .filter() should be called with execution_steps__contains
        assert mock_objects.filter.called
