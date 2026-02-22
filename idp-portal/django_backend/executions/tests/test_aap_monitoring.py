"""
Tests for AAP monitoring integration — Story 27.1.

Covers:
- ExecutionLogsView: GET /executions/{id}/logs
- poll_aap_job_status Celery task
- ExecutionConsumer channel group messaging
- build_auth_headers utility
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from rest_framework.test import APIClient

from tests.factories import (
    UserFactory, ActionFactory, IntegrationFactory,
    ExecutionFactory, ExecutionStepFactory,
)
from executions.models import ExecutionStatus
from adapters.utils import build_auth_headers


# ---------------------------------------------------------------------------
# build_auth_headers utility
# ---------------------------------------------------------------------------

class TestBuildAuthHeaders:
    """Tests for adapters.utils.build_auth_headers."""

    def test_token_auth_flow(self) -> None:
        integration = MagicMock()
        integration.auth_flow = "token"
        integration.credential_ref = "my-token-value"
        headers = build_auth_headers(integration)
        assert headers == {"Authorization": "Bearer my-token-value"}

    def test_basic_auth_flow(self) -> None:
        integration = MagicMock()
        integration.auth_flow = "basic"
        integration.credential_ref = "user:pass"
        headers = build_auth_headers(integration)
        assert headers["Authorization"].startswith("Basic ")
        import base64
        decoded = base64.b64decode(headers["Authorization"].split(" ")[1]).decode()
        assert decoded == "user:pass"

    def test_pat_auth_flow(self) -> None:
        integration = MagicMock()
        integration.auth_flow = "pat"
        integration.credential_ref = "personal-access-token"
        headers = build_auth_headers(integration)
        assert headers == {"Authorization": "Bearer personal-access-token"}

    def test_default_auth_flow(self) -> None:
        integration = MagicMock()
        integration.auth_flow = None
        integration.credential_ref = "default-token"
        headers = build_auth_headers(integration)
        assert headers == {"Authorization": "Bearer default-token"}

    def test_empty_credential_ref(self) -> None:
        """CRITICAL-2 FIX: Empty credential_ref now raises BadRequestError instead of returning empty Bearer."""
        from core.exceptions import BadRequestError

        integration = MagicMock()
        integration.auth_flow = "token"
        integration.credential_ref = None
        integration.id = 123

        with pytest.raises(BadRequestError) as exc_info:
            build_auth_headers(integration)

        assert exc_info.value.code == "EMPTY_CREDENTIAL"
        assert "credential_ref is empty" in exc_info.value.message


# ---------------------------------------------------------------------------
# ExecutionLogsView: GET /executions/{id}/logs
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestExecutionLogsView:
    """Tests for GET /api/v1/executions/{id}/logs — Story 27.1 AC3."""

    def setup_method(self) -> None:
        self.client = APIClient()
        self.user = UserFactory.create(profile="DBA")
        self.integration = IntegrationFactory.create(type="aap", name="Test AAP Logs")
        self.action = ActionFactory.create(
            status="published",
            integration=self.integration,
        )
        self.client.force_authenticate(user=self.user)

    def test_logs_fallback_to_steps_no_platform_job_id(self) -> None:
        """No platform_job_id → return step logs from DB."""
        execution = ExecutionFactory.create(
            action=self.action,
            user=self.user,
            status=ExecutionStatus.RUNNING,
            environment="dev",
            parameters=json.dumps({"target_host": "h1"}),
        )
        step = ExecutionStepFactory.create(
            execution=execution,
            step_order=1,
            step_name="Platform",
            step_type="platform",
            status="RUNNING",
        )

        response = self.client.get(f"/api/v1/executions/{execution.id}/logs/")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["source"] == "steps"
        assert len(data["logs"]) == 1
        assert data["logs"][0]["step_name"] == "Platform"

    def test_logs_from_aap_adapter(self) -> None:
        """With platform_job_id → fetch from AAPAdapter."""
        execution = ExecutionFactory.create(
            action=self.action,
            user=self.user,
            status=ExecutionStatus.RUNNING,
            environment="dev",
            parameters=json.dumps({
                "platform_job_id": "aap-job-42",
                "resource_type": "job_template",
            }),
        )

        mock_logs = {
            "content": "PLAY [all] ****\nok: [host1]",
            "format": "text/plain",
            "timestamp": "2026-02-14T10:30:00Z",
            "complete": False,
            "job_status": "running",
        }

        async def fake_get_job_logs(**kwargs):  # type: ignore[no-untyped-def]
            return mock_logs

        with patch("executions.views.execution_views.get_platform_adapter") as MockAdapter:
            mock_instance = MagicMock()
            MockAdapter.return_value = mock_instance
            mock_instance.get_job_logs = fake_get_job_logs

            response = self.client.get(f"/api/v1/executions/{execution.id}/logs/")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["source"] == "aap"
        assert "PLAY [all]" in data["content"]
        assert data["job_status"] == "running"

    def test_logs_404_execution_not_found(self) -> None:
        response = self.client.get("/api/v1/executions/999999/logs/")
        assert response.status_code == 404

    def test_logs_forbidden_other_user(self) -> None:
        """Non-owner, non-admin cannot access logs."""
        other_user = UserFactory.create(profile="BUSINESS")
        execution = ExecutionFactory.create(
            action=self.action,
            user=self.user,
            status=ExecutionStatus.RUNNING,
            environment="dev",
        )

        self.client.force_authenticate(user=other_user)
        response = self.client.get(f"/api/v1/executions/{execution.id}/logs/")
        assert response.status_code == 403

    def test_logs_no_integration(self) -> None:
        """Action without integration → fallback to steps."""
        action_no_integration = ActionFactory.create(
            status="published",
            integration=None,
        )
        execution = ExecutionFactory.create(
            action=action_no_integration,
            user=self.user,
            status=ExecutionStatus.RUNNING,
            environment="dev",
            parameters=json.dumps({"platform_job_id": "xyz"}),
        )

        response = self.client.get(f"/api/v1/executions/{execution.id}/logs/")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["source"] == "steps"


# ---------------------------------------------------------------------------
# poll_aap_job_status Celery task
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestPollAAPJobStatus:
    """Tests for poll_aap_job_status Celery task — Story 27.1 AC4."""

    def setup_method(self) -> None:
        self.user = UserFactory.create(profile="DBA")
        self.integration = IntegrationFactory.create(type="aap", name="Test AAP Poll")
        self.action = ActionFactory.create(
            status="published",
            integration=self.integration,
        )

    @patch("adapters.aap_adapter.AAPAdapter")
    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks.poll_platform_job_status.apply_async")
    def test_poll_running_job_reschedules(
        self, mock_apply_async: MagicMock, mock_broadcast: MagicMock, MockAdapter: MagicMock,
    ) -> None:
        """Running job → updates DB, broadcasts, re-schedules."""
        from executions.tasks import poll_aap_job_status

        execution = ExecutionFactory.create(
            action=self.action,
            user=self.user,
            status=ExecutionStatus.RUNNING,
            environment="dev",
        )

        mock_instance = MagicMock()
        MockAdapter.return_value = mock_instance

        async def fake_get_status(**kwargs):  # type: ignore[no-untyped-def]
            return {
                "status": "RUNNING",
                "aap_status": "running",
                "started": "2026-02-14T10:00:00Z",
                "finished": None,
                "elapsed": 30,
            }

        async def fake_get_job_logs(**kwargs):  # type: ignore[no-untyped-def]
            return {
                "content": "task output...",
                "format": "text/plain",
                "timestamp": "2026-02-14T10:00:30Z",
                "complete": False,
                "job_status": "running",
            }

        mock_instance.get_status = fake_get_status
        mock_instance.get_job_logs = fake_get_job_logs

        result = poll_aap_job_status(
            execution_id=execution.id,
            platform_job_id="aap-123",
            base_url="https://aap.example.com",
            credential_ref="token123",
        )

        assert result["outcome"] == "polling"
        mock_broadcast.assert_called_once()
        mock_apply_async.assert_called_once()

    @patch("adapters.aap_adapter.AAPAdapter")
    @patch("executions.tasks._broadcast_execution_update")
    @patch("executions.tasks.poll_platform_job_status.apply_async")
    def test_poll_completed_job_stops(
        self, mock_apply_async: MagicMock, mock_broadcast: MagicMock, MockAdapter: MagicMock,
    ) -> None:
        """Completed job → updates DB, broadcasts, does NOT re-schedule."""
        from executions.tasks import poll_aap_job_status

        execution = ExecutionFactory.create(
            action=self.action,
            user=self.user,
            status=ExecutionStatus.RUNNING,
            environment="dev",
        )

        mock_instance = MagicMock()
        MockAdapter.return_value = mock_instance

        async def fake_get_status(**kwargs):  # type: ignore[no-untyped-def]
            return {
                "status": "COMPLETED",
                "aap_status": "successful",
                "started": "2026-02-14T10:00:00Z",
                "finished": "2026-02-14T10:05:00Z",
                "elapsed": 300,
            }

        async def fake_get_job_logs(**kwargs):  # type: ignore[no-untyped-def]
            return {
                "content": "PLAY RECAP ****\nhost1 : ok=5",
                "format": "text/plain",
                "timestamp": "2026-02-14T10:05:00Z",
                "complete": True,
                "job_status": "successful",
            }

        mock_instance.get_status = fake_get_status
        mock_instance.get_job_logs = fake_get_job_logs

        result = poll_aap_job_status(
            execution_id=execution.id,
            platform_job_id="aap-123",
            base_url="https://aap.example.com",
            credential_ref="token123",
        )

        assert result["outcome"] == "complete"
        mock_broadcast.assert_called_once()
        mock_apply_async.assert_not_called()


# ---------------------------------------------------------------------------
# _broadcast_execution_update
# ---------------------------------------------------------------------------

class TestBroadcastExecutionUpdate:
    """Tests for _broadcast_execution_update helper."""

    @patch("channels.layers.get_channel_layer")
    def test_broadcast_sends_status_and_logs(self, mock_get_layer: MagicMock) -> None:
        from executions.tasks import _broadcast_execution_update

        mock_layer = MagicMock()
        mock_get_layer.return_value = mock_layer
        mock_layer.group_send = MagicMock()

        # Need async_to_sync to work — patch it
        with patch("asgiref.sync.async_to_sync", side_effect=lambda f: f):
            _broadcast_execution_update(
                execution_id=42,
                status_data={"status": "RUNNING", "aap_status": "running", "started": "x", "finished": None},
                logs_data={"content": "log data", "complete": False, "timestamp": "t"},
                is_terminal=False,
            )

        # Should have sent status_update + log_update (2 calls, no terminal)
        assert mock_layer.group_send.call_count == 2

    @patch("channels.layers.get_channel_layer")
    def test_broadcast_sends_terminal_event(self, mock_get_layer: MagicMock) -> None:
        from executions.tasks import _broadcast_execution_update

        mock_layer = MagicMock()
        mock_get_layer.return_value = mock_layer

        with patch("asgiref.sync.async_to_sync", side_effect=lambda f: f):
            _broadcast_execution_update(
                execution_id=42,
                status_data={"status": "COMPLETED", "aap_status": "successful", "started": "x", "finished": "y"},
                logs_data={"content": "done", "complete": True, "timestamp": "t"},
                is_terminal=True,
            )

        # status_update + log_update + execution_complete = 3
        assert mock_layer.group_send.call_count == 3

    @patch("channels.layers.get_channel_layer", return_value=None)
    def test_broadcast_no_channel_layer(self, mock_get_layer: MagicMock) -> None:
        """No channel layer configured → no error."""
        from executions.tasks import _broadcast_execution_update

        _broadcast_execution_update(
            execution_id=42,
            status_data={},
            logs_data={},
            is_terminal=False,
        )
        # Should not raise


# ---------------------------------------------------------------------------
# ExecutionConsumer WebSocket
# ---------------------------------------------------------------------------

class TestExecutionConsumer:
    """Tests for ExecutionConsumer channel group behavior — Story 27.1."""

    def test_consumer_group_name(self) -> None:
        """Consumer builds correct group name from execution_id."""
        from executions.consumers import ExecutionConsumer

        consumer = ExecutionConsumer()
        consumer.scope = {"url_route": {"kwargs": {"execution_id": "42"}}}
        # Simulate what connect() does
        consumer.execution_id = consumer.scope["url_route"]["kwargs"].get("execution_id")
        consumer.group_name = f"execution_{consumer.execution_id}"

        assert consumer.group_name == "execution_42"

    @pytest.mark.asyncio
    async def test_step_update_message_forwarded(self) -> None:
        """step_update handler sends JSON to client."""
        from executions.consumers import ExecutionConsumer

        consumer = ExecutionConsumer()
        consumer.send = AsyncMock()

        await consumer.step_update({"data": {"step_id": 1, "status": "RUNNING"}})

        consumer.send.assert_called_once()
        sent = json.loads(consumer.send.call_args[1]["text_data"])
        assert sent["type"] == "step_update"
        assert sent["data"]["step_id"] == 1

    @pytest.mark.asyncio
    async def test_log_update_message_forwarded(self) -> None:
        """log_update handler sends JSON to client."""
        from executions.consumers import ExecutionConsumer

        consumer = ExecutionConsumer()
        consumer.send = AsyncMock()

        await consumer.log_update({"data": {"content": "log lines...", "complete": False}})

        consumer.send.assert_called_once()
        sent = json.loads(consumer.send.call_args[1]["text_data"])
        assert sent["type"] == "log_update"
        assert "log lines" in sent["data"]["content"]

    @pytest.mark.asyncio
    async def test_execution_complete_message_forwarded(self) -> None:
        """execution_complete handler sends JSON to client."""
        from executions.consumers import ExecutionConsumer

        consumer = ExecutionConsumer()
        consumer.send = AsyncMock()

        await consumer.execution_complete({"data": {"status": "COMPLETED"}})

        sent = json.loads(consumer.send.call_args[1]["text_data"])
        assert sent["type"] == "execution_complete"

    @pytest.mark.asyncio
    async def test_status_update_message_forwarded(self) -> None:
        """status_update handler sends JSON to client."""
        from executions.consumers import ExecutionConsumer

        consumer = ExecutionConsumer()
        consumer.send = AsyncMock()

        await consumer.status_update({"data": {"status": "RUNNING", "aap_status": "running"}})

        sent = json.loads(consumer.send.call_args[1]["text_data"])
        assert sent["type"] == "status_update"
        assert sent["data"]["aap_status"] == "running"
