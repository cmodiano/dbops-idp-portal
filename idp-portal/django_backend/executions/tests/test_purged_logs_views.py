"""
Tests for Splunk fallback in execution log views.

Covers _retrieve_purged_logs_from_splunk helper and
the Splunk fallback paths in ExecutionStepLogsView and ExecutionLogsView.
"""
from __future__ import annotations

from unittest.mock import patch, MagicMock



# ---------------------------------------------------------------------------
# _retrieve_purged_logs_from_splunk helper
# ---------------------------------------------------------------------------


class TestRetrievePurgedLogsFromSplunk:
    """Unit tests for the _retrieve_purged_logs_from_splunk helper."""

    @patch("services.splunk_utils.get_splunk_service")
    def test_returns_logs_from_splunk_when_available(self, mock_get_splunk):
        from executions.views.execution_views import _retrieve_purged_logs_from_splunk

        mock_splunk = MagicMock()
        mock_splunk.search_platform_logs = MagicMock()
        mock_get_splunk.return_value = mock_splunk

        # async_to_sync wraps the coroutine — mock the result directly
        with patch("asgiref.sync.async_to_sync", return_value=MagicMock(return_value="PLAY [all] ***\nok: [host1]")):
            output = {"logs_purged": True, "logs_purged_at": "2025-01-01T00:00:00", "other": "data"}
            result = _retrieve_purged_logs_from_splunk(output, execution_id=42)

        assert result["platform_logs"] == "PLAY [all] ***\nok: [host1]"
        assert result["logs_source"] == "splunk"
        assert result["other"] == "data"
        mock_get_splunk.assert_called_once()

    @patch("services.splunk_utils.get_splunk_service")
    def test_returns_output_unchanged_when_splunk_returns_none(self, mock_get_splunk):
        from executions.views.execution_views import _retrieve_purged_logs_from_splunk

        mock_splunk = MagicMock()
        mock_get_splunk.return_value = mock_splunk

        with patch("asgiref.sync.async_to_sync", return_value=MagicMock(return_value=None)):
            output = {"logs_purged": True, "logs_purged_at": "2025-01-01T00:00:00"}
            result = _retrieve_purged_logs_from_splunk(output, execution_id=42)

        assert "platform_logs" not in result
        assert "logs_source" not in result
        assert result["logs_purged"] is True

    @patch("services.splunk_utils.get_splunk_service")
    def test_returns_output_unchanged_when_no_splunk_service(self, mock_get_splunk):
        from executions.views.execution_views import _retrieve_purged_logs_from_splunk

        mock_get_splunk.return_value = None

        output = {"logs_purged": True}
        result = _retrieve_purged_logs_from_splunk(output, execution_id=42)

        assert result is output
        assert "platform_logs" not in result

    @patch("services.splunk_utils.get_splunk_service")
    def test_returns_output_unchanged_on_exception(self, mock_get_splunk):
        from executions.views.execution_views import _retrieve_purged_logs_from_splunk

        mock_get_splunk.side_effect = Exception("Splunk connection error")

        output = {"logs_purged": True}
        result = _retrieve_purged_logs_from_splunk(output, execution_id=42)

        assert result is output
        assert result["logs_purged"] is True


# ---------------------------------------------------------------------------
# ExecutionStepLogsView — Splunk fallback path
# ---------------------------------------------------------------------------


class TestExecutionStepLogsViewSplunkFallback:
    """Test that ExecutionStepLogsView calls Splunk when logs_purged=True."""

    @patch("executions.views.execution_views._retrieve_purged_logs_from_splunk")
    @patch("executions.views.execution_views._dba_permission")
    @patch("executions.models.ExecutionStep.objects")
    def test_calls_splunk_when_logs_purged(self, mock_step_objects, mock_perm, mock_retrieve):
        from executions.views.execution_views import ExecutionStepLogsView
        from rest_framework.test import APIRequestFactory

        mock_execution = MagicMock()
        mock_execution.id = 1
        mock_step = MagicMock()
        mock_step.id = 10
        mock_step.execution = mock_execution
        mock_step.execution_id = 1
        mock_step.error_message = None
        mock_step.started_at = None
        mock_step.completed_at = None
        mock_step.get_output.return_value = {"logs_purged": True, "logs_purged_at": "2025-01-01T00:00:00"}

        mock_step_objects.select_related.return_value.get.return_value = mock_step
        mock_perm.has_object_permission.return_value = True
        mock_retrieve.return_value = {
            "logs_purged": True,
            "logs_purged_at": "2025-01-01T00:00:00",
            "platform_logs": "retrieved from splunk",
            "logs_source": "splunk",
        }

        factory = APIRequestFactory()
        request = factory.get("/executions/1/steps/10/logs")
        request.user = MagicMock()

        view = ExecutionStepLogsView()
        response = view.get(request, execution_id=1, step_id=10)

        mock_retrieve.assert_called_once_with(
            {"logs_purged": True, "logs_purged_at": "2025-01-01T00:00:00"},
            1,
        )
        assert response.data["data"]["output"]["logs_source"] == "splunk"

    @patch("executions.views.execution_views._retrieve_purged_logs_from_splunk")
    @patch("executions.views.execution_views._dba_permission")
    @patch("executions.models.ExecutionStep.objects")
    def test_skips_splunk_when_not_purged(self, mock_step_objects, mock_perm, mock_retrieve):
        from executions.views.execution_views import ExecutionStepLogsView
        from rest_framework.test import APIRequestFactory

        mock_execution = MagicMock()
        mock_execution.id = 1
        mock_step = MagicMock()
        mock_step.id = 10
        mock_step.execution = mock_execution
        mock_step.execution_id = 1
        mock_step.error_message = None
        mock_step.started_at = None
        mock_step.completed_at = None
        mock_step.get_output.return_value = {"platform_logs": "still in DB"}

        mock_step_objects.select_related.return_value.get.return_value = mock_step
        mock_perm.has_object_permission.return_value = True

        factory = APIRequestFactory()
        request = factory.get("/executions/1/steps/10/logs")
        request.user = MagicMock()

        view = ExecutionStepLogsView()
        response = view.get(request, execution_id=1, step_id=10)

        mock_retrieve.assert_not_called()
        assert response.data["data"]["output"]["platform_logs"] == "still in DB"

    @patch("executions.views.execution_views._retrieve_purged_logs_from_splunk")
    @patch("executions.views.execution_views._dba_permission")
    @patch("executions.models.ExecutionStep.objects")
    def test_skips_splunk_when_output_is_none(self, mock_step_objects, mock_perm, mock_retrieve):
        from executions.views.execution_views import ExecutionStepLogsView
        from rest_framework.test import APIRequestFactory

        mock_execution = MagicMock()
        mock_execution.id = 1
        mock_step = MagicMock()
        mock_step.id = 10
        mock_step.execution = mock_execution
        mock_step.execution_id = 1
        mock_step.error_message = None
        mock_step.started_at = None
        mock_step.completed_at = None
        mock_step.get_output.return_value = None

        mock_step_objects.select_related.return_value.get.return_value = mock_step
        mock_perm.has_object_permission.return_value = True

        factory = APIRequestFactory()
        request = factory.get("/executions/1/steps/10/logs")
        request.user = MagicMock()

        view = ExecutionStepLogsView()
        response = view.get(request, execution_id=1, step_id=10)

        mock_retrieve.assert_not_called()
        assert response.data["data"]["output"] is None


# ---------------------------------------------------------------------------
# ExecutionLogsView — steps fallback path with Splunk
# ---------------------------------------------------------------------------


class TestExecutionLogsViewSplunkFallback:
    """Test that ExecutionLogsView steps fallback calls Splunk when logs_purged=True."""

    @patch("executions.views.execution_views._fetch_splunk_logs_for_execution")
    @patch("executions.views.execution_views.get_correlation_id", return_value="test-corr")
    @patch("executions.views.execution_views._dba_permission")
    @patch("executions.models.ExecutionStep.objects")
    @patch("executions.models.Execution.objects")
    def test_calls_splunk_once_for_purged_steps(
        self, mock_exec_objects, mock_step_objects, mock_perm, mock_corr, mock_fetch
    ):
        from executions.views.execution_views import ExecutionLogsView
        from rest_framework.test import APIRequestFactory

        # Setup execution without platform_job_id → falls back to steps path
        mock_execution = MagicMock()
        mock_execution.id = 1
        mock_execution.action = None  # no integration → steps fallback
        mock_execution.get_parameters.return_value = {}
        mock_exec_objects.select_related.return_value.get.return_value = mock_execution
        mock_perm.has_object_permission.return_value = True

        # Setup steps — one purged, one not
        step_purged = MagicMock()
        step_purged.id = 10
        step_purged.step_name = "platform_step"
        step_purged.step_order = 1
        step_purged.status = "COMPLETED"
        step_purged.error_message = None
        step_purged.get_output.return_value = {"logs_purged": True, "logs_purged_at": "2025-01-01"}

        step_normal = MagicMock()
        step_normal.id = 11
        step_normal.step_name = "another_step"
        step_normal.step_order = 2
        step_normal.status = "COMPLETED"
        step_normal.error_message = None
        step_normal.get_output.return_value = {"platform_logs": "still here"}

        mock_step_objects.filter.return_value.order_by.return_value = [step_purged, step_normal]

        mock_fetch.return_value = "from splunk"

        factory = APIRequestFactory()
        request = factory.get("/executions/1/logs")
        request.user = MagicMock()

        view = ExecutionLogsView()
        response = view.get(request, execution_id=1)

        # Splunk called exactly once for the whole execution (not per-step)
        mock_fetch.assert_called_once_with(1)
        assert response.data["data"]["source"] == "steps"
        assert response.data["data"]["logs"][0]["output"]["logs_source"] == "splunk"
        assert response.data["data"]["logs"][0]["output"]["platform_logs"] == "from splunk"
        assert response.data["data"]["logs"][1]["output"]["platform_logs"] == "still here"
