"""
Tests for GitHub Actions webhook endpoint — Story 27.4.

Covers:
- HMAC SHA-256 signature validation (success, failure)
- Payload parsing: workflow_run events (requested, in_progress, completed)
- Execution status update from webhook
- WebSocket broadcast from webhook
- Edge cases: unknown run_id, malformed payload, missing fields
"""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from unittest.mock import MagicMock, patch

from rest_framework.test import APIClient

from executions.views.github_webhooks import _verify_github_signature


WEBHOOK_SECRET = "test-webhook-secret-123"
WEBHOOK_URL = "/api/v1/webhooks/github/workflow_run"


def _sign_payload(payload: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """Generate GitHub-style HMAC SHA-256 signature."""
    return "sha256=" + hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()


def _make_webhook_payload(
    action: str = "completed",
    run_id: int = 12345,
    status: str = "completed",
    conclusion: str | None = "success",
) -> dict:
    """Build a minimal workflow_run webhook payload."""
    return {
        "action": action,
        "workflow_run": {
            "id": run_id,
            "status": status,
            "conclusion": conclusion,
            "html_url": f"https://github.com/org/repo/actions/runs/{run_id}",
        },
        "repository": {"full_name": "org/repo"},
        "sender": {"login": "test-user"},
    }


# ---------------------------------------------------------------------------
# _verify_github_signature
# ---------------------------------------------------------------------------

class TestVerifyGitHubSignature:
    """Tests for HMAC SHA-256 validation."""

    def test_valid_signature(self) -> None:
        body = b'{"action": "completed"}'
        sig = _sign_payload(body)
        assert _verify_github_signature(body, sig, WEBHOOK_SECRET) is True

    def test_invalid_signature(self) -> None:
        body = b'{"action": "completed"}'
        assert _verify_github_signature(body, "sha256=invalid", WEBHOOK_SECRET) is False

    def test_missing_prefix(self) -> None:
        body = b'{"action": "completed"}'
        sig = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
        assert _verify_github_signature(body, sig, WEBHOOK_SECRET) is False

    def test_empty_signature(self) -> None:
        body = b'{"action": "completed"}'
        assert _verify_github_signature(body, "", WEBHOOK_SECRET) is False

    def test_wrong_secret(self) -> None:
        body = b'{"action": "completed"}'
        sig = _sign_payload(body, secret="wrong-secret")
        assert _verify_github_signature(body, sig, WEBHOOK_SECRET) is False


# ---------------------------------------------------------------------------
# Webhook endpoint integration tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGitHubWebhookEndpoint:
    """Tests for the webhook endpoint view."""

    @pytest.fixture(autouse=True)
    def _configure_secret(self, settings) -> None:
        settings.GITHUB_WEBHOOK_SECRET = WEBHOOK_SECRET

    def setup_method(self) -> None:
        self.client = APIClient()

    def _post_webhook(
        self,
        payload: dict | None = None,
        raw_body: bytes | None = None,
        sign: bool = True,
        secret: str = WEBHOOK_SECRET,
    ):
        """Send a webhook POST request with proper signature."""
        if raw_body is None:
            raw_body = json.dumps(payload or _make_webhook_payload()).encode()

        headers = {"content_type": "application/json"}
        if sign:
            headers["HTTP_X_HUB_SIGNATURE_256"] = _sign_payload(raw_body, secret)

        return self.client.post(
            WEBHOOK_URL,
            data=raw_body,
            **headers,
        )

    def test_invalid_signature_returns_401(self) -> None:
        """Invalid HMAC signature returns 401."""
        payload = _make_webhook_payload()
        raw_body = json.dumps(payload).encode()
        response = self.client.post(
            WEBHOOK_URL,
            data=raw_body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256="sha256=invalid",
        )
        assert response.status_code == 401

    def test_missing_signature_returns_401(self) -> None:
        """Missing signature returns 401."""
        payload = _make_webhook_payload()
        raw_body = json.dumps(payload).encode()
        response = self.client.post(
            WEBHOOK_URL,
            data=raw_body,
            content_type="application/json",
        )
        assert response.status_code == 401

    def test_valid_signature_no_matching_execution(self) -> None:
        """Valid signature, no matching execution returns 200 with no_matching_execution."""
        from executions.models import ExecutionStep
        with patch.object(
            ExecutionStep.objects, "filter"
        ) as mock_filter:
            mock_filter.return_value.select_related.return_value.first.return_value = None
            response = self._post_webhook(payload=_make_webhook_payload(run_id=99999))
        assert response.status_code == 200
        assert response.json()["status"] == "no_matching_execution"

    def test_invalid_json_returns_400(self) -> None:
        """Invalid JSON payload returns 400."""
        raw_body = b"not json"
        response = self._post_webhook(raw_body=raw_body)
        assert response.status_code == 400

    def test_missing_workflow_run_returns_400(self) -> None:
        """Payload without workflow_run returns 400."""
        payload = {"action": "completed"}
        response = self._post_webhook(payload=payload)
        assert response.status_code == 400

    def test_ignored_action_returns_200(self) -> None:
        """Non-processable action returns 200 with ignored status."""
        payload = {
            "action": "deleted",
            "workflow_run": {"id": 12345, "status": "completed", "conclusion": "success"},
        }
        response = self._post_webhook(payload=payload)
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"

    def test_missing_run_id_returns_400(self) -> None:
        """Payload with empty run ID returns 400."""
        payload = {
            "action": "completed",
            "workflow_run": {"status": "completed", "conclusion": "success"},
        }
        response = self._post_webhook(payload=payload)
        assert response.status_code == 400

    @patch("executions.views.github_webhooks._broadcast_webhook_update")
    def test_completed_event_updates_execution(self, mock_broadcast: MagicMock) -> None:
        """Completed event with matching execution updates status and broadcasts."""
        from executions.models import ExecutionStep

        mock_execution = MagicMock()
        mock_execution.id = 1
        mock_execution.status = "RUNNING"
        mock_execution.user_id = 42

        mock_step = MagicMock()
        mock_step.execution = mock_execution

        with patch.object(
            ExecutionStep.objects, "filter"
        ) as mock_filter:
            mock_filter.return_value.select_related.return_value.first.return_value = mock_step

            with patch("executions.services.ExecutionService") as mock_svc_cls:
                mock_svc = MagicMock()
                mock_svc_cls.return_value = mock_svc

                response = self._post_webhook(
                    payload=_make_webhook_payload(
                        action="completed",
                        run_id=12345,
                        status="completed",
                        conclusion="success",
                    )
                )

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        mock_svc.update_status.assert_called_once_with(1, "COMPLETED", "42")
        mock_broadcast.assert_called_once()

    @patch("executions.views.github_webhooks._broadcast_webhook_update")
    def test_in_progress_event_updates_execution(self, mock_broadcast: MagicMock) -> None:
        """In-progress event updates execution to RUNNING."""
        from executions.models import ExecutionStep

        mock_execution = MagicMock()
        mock_execution.id = 2
        mock_execution.status = "SUBMITTED"
        mock_execution.user_id = 42

        mock_step = MagicMock()
        mock_step.execution = mock_execution

        with patch.object(
            ExecutionStep.objects, "filter"
        ) as mock_filter:
            mock_filter.return_value.select_related.return_value.first.return_value = mock_step

            with patch("executions.services.ExecutionService") as mock_svc_cls:
                mock_svc = MagicMock()
                mock_svc_cls.return_value = mock_svc

                response = self._post_webhook(
                    payload=_make_webhook_payload(
                        action="in_progress",
                        run_id=12345,
                        status="in_progress",
                        conclusion=None,
                    )
                )

        assert response.status_code == 200
        mock_svc.update_status.assert_called_once_with(2, "RUNNING", "42")

    def test_no_webhook_secret_configured_returns_500(self, settings) -> None:
        """Missing webhook secret configuration returns 500."""
        settings.GITHUB_WEBHOOK_SECRET = ""
        payload = _make_webhook_payload()
        raw_body = json.dumps(payload).encode()
        response = self.client.post(
            WEBHOOK_URL,
            data=raw_body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=_sign_payload(raw_body),
        )
        assert response.status_code == 500
