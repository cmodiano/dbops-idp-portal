"""
Tests for purge_old_platform_logs cleanup task.
"""
from __future__ import annotations

import json
from unittest.mock import patch, MagicMock



def _make_step(output_dict: dict | None, step_id: int = 1):
    """Create a mock ExecutionStep with get_output/set_output."""
    step = MagicMock()
    step.id = step_id
    step._output = json.dumps(output_dict) if output_dict is not None else None

    def get_output():
        if step._output is None:
            return None
        return json.loads(step._output)

    def set_output(val):
        step._output = json.dumps(val) if val is not None else None

    step.get_output = get_output
    step.set_output = set_output
    step.save = MagicMock()
    return step


def _build_queryset_mock(step_ids_batches, steps_by_batch):
    """Build a mock ExecutionStep.objects that simulates batched queryset.

    Args:
        step_ids_batches: list of lists of IDs returned by successive values_list calls
        steps_by_batch: list of lists of step objects returned by successive filter(id__in=) calls
    """
    qs = MagicMock()

    # Chain: filter().exclude().exclude().only() → qs itself
    qs.filter.return_value = qs
    qs.exclude.return_value = qs
    qs.only.return_value = qs

    # values_list()[:BATCH] returns batches then empty
    batch_iter = iter(step_ids_batches)
    vl = MagicMock()
    vl.__getitem__ = MagicMock(side_effect=lambda _: next(batch_iter))
    qs.values_list.return_value = vl

    # filter(id__in=...).only() returns step objects
    steps_iter = iter(steps_by_batch)

    def filter_side_effect(**kwargs):
        if "id__in" in kwargs:
            id_qs = MagicMock()
            id_qs.only.return_value = next(steps_iter)
            return id_qs
        return qs

    qs.filter.side_effect = filter_side_effect

    return qs


class TestPurgeOldPlatformLogs:

    @patch("executions.models.ExecutionStep.objects")
    def test_purges_old_terminal_logs(self, mock_objects):
        from executions.tasks.cleanup import purge_old_platform_logs

        step = _make_step({"platform_logs": "long log content", "other_key": "value"})
        mock_objects.filter.return_value = mock_objects
        mock_objects.exclude.return_value = mock_objects
        mock_objects.only.return_value = mock_objects

        batch_iter = iter([[1], []])
        vl = MagicMock()
        vl.__getitem__ = MagicMock(side_effect=lambda _: next(batch_iter))
        mock_objects.values_list.return_value = vl

        id_qs = MagicMock()
        id_qs.only.return_value = [step]
        mock_objects.filter.side_effect = lambda **kw: id_qs if "id__in" in kw else mock_objects

        result = purge_old_platform_logs()

        assert result["purged"] == 1
        assert result["errors"] == 0
        output = step.get_output()
        assert "platform_logs" not in output
        assert output["logs_purged"] is True
        assert "logs_purged_at" in output
        assert output["other_key"] == "value"
        step.save.assert_called_once()

    @patch("executions.models.ExecutionStep.objects")
    def test_skips_step_without_platform_logs(self, mock_objects):
        from executions.tasks.cleanup import purge_old_platform_logs

        step = _make_step({"some_other_key": "value"})
        mock_objects.filter.return_value = mock_objects
        mock_objects.exclude.return_value = mock_objects
        mock_objects.only.return_value = mock_objects

        batch_iter = iter([[1], []])
        vl = MagicMock()
        vl.__getitem__ = MagicMock(side_effect=lambda _: next(batch_iter))
        mock_objects.values_list.return_value = vl

        id_qs = MagicMock()
        id_qs.only.return_value = [step]
        mock_objects.filter.side_effect = lambda **kw: id_qs if "id__in" in kw else mock_objects

        result = purge_old_platform_logs()

        assert result["purged"] == 0
        step.save.assert_not_called()

    @patch("executions.models.ExecutionStep.objects")
    def test_handles_step_error_gracefully(self, mock_objects):
        from executions.tasks.cleanup import purge_old_platform_logs

        step = MagicMock()
        step.id = 1
        step.get_output = MagicMock(side_effect=Exception("DB error"))

        mock_objects.filter.return_value = mock_objects
        mock_objects.exclude.return_value = mock_objects
        mock_objects.only.return_value = mock_objects

        batch_iter = iter([[1], []])
        vl = MagicMock()
        vl.__getitem__ = MagicMock(side_effect=lambda _: next(batch_iter))
        mock_objects.values_list.return_value = vl

        id_qs = MagicMock()
        id_qs.only.return_value = [step]
        mock_objects.filter.side_effect = lambda **kw: id_qs if "id__in" in kw else mock_objects

        result = purge_old_platform_logs()

        assert result["purged"] == 0
        assert result["errors"] == 1

    @patch("executions.models.ExecutionStep.objects")
    def test_empty_queryset_returns_zero(self, mock_objects):
        from executions.tasks.cleanup import purge_old_platform_logs

        mock_objects.filter.return_value = mock_objects
        mock_objects.exclude.return_value = mock_objects
        mock_objects.only.return_value = mock_objects

        vl = MagicMock()
        vl.__getitem__ = MagicMock(return_value=[])
        mock_objects.values_list.return_value = vl

        result = purge_old_platform_logs()

        assert result["purged"] == 0
        assert result["errors"] == 0

    @patch("executions.tasks.cleanup.LOG_RETENTION_DAYS", 3)
    @patch("executions.models.ExecutionStep.objects")
    def test_configurable_retention_days(self, mock_objects):
        from executions.tasks.cleanup import purge_old_platform_logs

        mock_objects.filter.return_value = mock_objects
        mock_objects.exclude.return_value = mock_objects
        mock_objects.only.return_value = mock_objects

        vl = MagicMock()
        vl.__getitem__ = MagicMock(return_value=[])
        mock_objects.values_list.return_value = vl

        result = purge_old_platform_logs()
        assert result == {"purged": 0, "errors": 0}

    @patch("executions.models.ExecutionStep.objects")
    def test_multiple_steps_purged(self, mock_objects):
        from executions.tasks.cleanup import purge_old_platform_logs

        step1 = _make_step({"platform_logs": "log1", "k": "v1"}, step_id=1)
        step2 = _make_step({"platform_logs": "log2", "k": "v2"}, step_id=2)

        mock_objects.filter.return_value = mock_objects
        mock_objects.exclude.return_value = mock_objects
        mock_objects.only.return_value = mock_objects

        batch_iter = iter([[1, 2], []])
        vl = MagicMock()
        vl.__getitem__ = MagicMock(side_effect=lambda _: next(batch_iter))
        mock_objects.values_list.return_value = vl

        id_qs = MagicMock()
        id_qs.only.return_value = [step1, step2]
        mock_objects.filter.side_effect = lambda **kw: id_qs if "id__in" in kw else mock_objects

        result = purge_old_platform_logs()

        assert result["purged"] == 2
        assert result["errors"] == 0
        assert step1.get_output()["logs_purged"] is True
        assert step2.get_output()["logs_purged"] is True
