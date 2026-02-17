"""
Tests for Terraform Cloud webhook endpoint — Story 27.5.

Covers:
- HMAC SHA-512 signature verification (success, failure)
- Payload parsing (valid, invalid JSON, missing fields)
- Execution lookup and status update
- WebSocket broadcast
- Edge cases (unknown run_id, malformed payload)
"""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from unittest.mock import MagicMock, patch

from rest_framework.test import APIClient

from executions.views.terraform_webhooks import _verify_terraform_signature


WEBHOOK_SECRET = "test-terraform-webhook-secret"
WEBHOOK_URL = "/api/v1/webhooks/terraform/run"


def _sign_payload(payload: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """Generate Terraform Cloud HMAC SHA-512 signature."""
    return hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha512,
    ).hexdigest()


def _make_terraform_payload(
    run_id: str = "run-abc123",
    run_status: str = "planning",
    trigger: str = "run:planning",
    workspace_name: str = "my-workspace",
    organization_name: str = "my-org",
) -> dict:
    """Build a Terraform Cloud webhook notification payload."""
    return {
        "notification_configuration_id": "nc-test",
        "run_url": f"https://app.terraform.io/app/{organization_name}/{workspace_name}/runs/{run_id}",
        "run_id": run_id,
        "run_message": "Triggered via IDP Portal",
        "run_created_at": "2026-02-14T10:00:00Z",
        "run_created_by": "user@example.com",
        "workspace_id": "ws-test",
        "workspace_name": workspace_name,
        "organization_name": organization_name,
        "notifications": [
            {
                "message": f"Run {run_status}",
                "trigger": trigger,
                "run_status": run_status,
                "run_updated_at": "2026-02-14T10:01:00Z",
            }
        ],
    }


# ---------------------------------------------------------------------------
# _verify_terraform_signature
# ---------------------------------------------------------------------------

class TestVerifyTerraformSignature:
    """Tests for HMAC SHA-512 validation."""

    def test_valid_signature(self) -> None:
        body = b'{"run_id": "run-abc"}'
        sig = _sign_payload(body)
        assert _verify_terraform_signature(body, sig, WEBHOOK_SECRET) is True

    def test_invalid_signature(self) -> None:
        body = b'{"run_id": "run-abc"}'
        assert _verify_terraform_signature(body, "invalid-signature", WEBHOOK_SECRET) is False

    def test_empty_signature(self) -> None:
        assert _verify_terraform_signature(b"body", "", "secret") is False

    def test_wrong_secret(self) -> None:
        body = b'{"run_id": "run-abc"}'
        sig = _sign_payload(body, secret="wrong-secret")
        assert _verify_terraform_signature(body, sig, WEBHOOK_SECRET) is False


# ---------------------------------------------------------------------------
# Webhook endpoint integration tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTerraformWebhookEndpoint:
    """Tests for the webhook endpoint view."""

    @pytest.fixture(autouse=True)
    def _configure_secret(self, settings) -> None:  # type: ignore[no-untyped-def]
        settings.TERRAFORM_WEBHOOK_SECRET = WEBHOOK_SECRET

    def setup_method(self) -> None:
        self.client = APIClient()

    def _post_webhook(
        self,
        payload: dict | None = None,
        raw_body: bytes | None = None,
        sign: bool = True,
        secret: str = WEBHOOK_SECRET,
    ):  # type: ignore[no-untyped-def]
        """Send a webhook POST with proper HMAC SHA-512 signature."""
        if raw_body is None:
            raw_body = json.dumps(payload or _make_terraform_payload()).encode()

        headers = {"content_type": "application/json"}
        if sign:
            headers["HTTP_X_TFE_NOTIFICATION_SIGNATURE"] = _sign_payload(raw_body, secret)

        return self.client.post(
            WEBHOOK_URL,
            data=raw_body,
            **headers,
        )

    def test_no_secret_configured(self, settings) -> None:  # type: ignore[no-untyped-def]
        """No webhook secret → 500."""
        settings.TERRAFORM_WEBHOOK_SECRET = ""
        response = self._post_webhook()
        assert response.status_code == 500

    def test_invalid_signature_rejected(self) -> None:
        """Invalid HMAC signature → 401."""
        payload = _make_terraform_payload()
        raw_body = json.dumps(payload).encode()
        response = self.client.post(
            WEBHOOK_URL,
            data=raw_body,
            content_type="application/json",
            HTTP_X_TFE_NOTIFICATION_SIGNATURE="bad-signature",
        )
        assert response.status_code == 401

    def test_missing_signature(self) -> None:
        """No signature header → 401."""
        response = self._post_webhook(sign=False)
        assert response.status_code == 401

    def test_invalid_json_payload(self) -> None:
        """Invalid JSON → 400."""
        response = self._post_webhook(raw_body=b"not-valid-json{")
        assert response.status_code == 400

    def test_missing_run_id(self) -> None:
        """Missing run_id → 400."""
        payload = _make_terraform_payload()
        del payload["run_id"]
        response = self._post_webhook(payload=payload)
        assert response.status_code == 400

    def test_missing_notifications(self) -> None:
        """Empty notifications → 400."""
        payload = _make_terraform_payload()
        payload["notifications"] = []
        response = self._post_webhook(payload=payload)
        assert response.status_code == 400

    def test_missing_run_status_in_notification(self) -> None:
        """Notification without run_status → 400."""
        payload = _make_terraform_payload()
        payload["notifications"] = [
            {
                "message": "Run is planning",
                "trigger": "run:planning",
                # Missing "run_status" field
                "run_updated_at": "2026-02-14T10:01:00Z",
            }
        ]
        response = self._post_webhook(payload=payload)
        assert response.status_code == 400
        assert "run_status" in response.json()["error"].lower()

    @patch("executions.views.terraform_webhooks.ExecutionStep")
    @patch("executions.views.terraform_webhooks._broadcast_terraform_webhook_update")
    def test_execution_not_found(
        self,
        mock_broadcast: MagicMock,
        mock_step_model: MagicMock,
    ) -> None:
        """Unknown run_id → 200 with no_matching_execution."""
        mock_step_model.objects.filter.return_value.select_related.return_value.first.return_value = None

        response = self._post_webhook(
            payload=_make_terraform_payload(run_id="run-unknown")
        )
        assert response.status_code == 200
        assert response.json()["status"] == "no_matching_execution"
        mock_broadcast.assert_not_called()

    @patch("executions.views.terraform_webhooks.ExecutionStep")
    @patch("executions.views.terraform_webhooks._broadcast_terraform_webhook_update")
    def test_status_update_and_broadcast(
        self,
        mock_broadcast: MagicMock,
        mock_step_model: MagicMock,
    ) -> None:
        """Valid webhook → updates execution and broadcasts."""
        mock_execution = MagicMock()
        mock_execution.id = 42
        mock_execution.status = "SUBMITTED"
        mock_execution.user_id = 1

        mock_step = MagicMock()
        mock_step.execution = mock_execution
        mock_step_model.objects.filter.return_value.select_related.return_value.first.return_value = mock_step

        with patch("executions.services.ExecutionService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc_cls.return_value = mock_svc

            response = self._post_webhook(
                payload=_make_terraform_payload(
                    run_status="applying", trigger="run:applying"
                )
            )

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        mock_broadcast.assert_called_once()

    @patch("executions.views.terraform_webhooks.ExecutionStep")
    @patch("executions.views.terraform_webhooks._broadcast_terraform_webhook_update")
    def test_terminal_status_applied(
        self,
        mock_broadcast: MagicMock,
        mock_step_model: MagicMock,
    ) -> None:
        """Applied status triggers terminal broadcast."""
        mock_execution = MagicMock()
        mock_execution.id = 42
        mock_execution.status = "RUNNING"
        mock_execution.user_id = 1

        mock_step = MagicMock()
        mock_step.execution = mock_execution
        mock_step_model.objects.filter.return_value.select_related.return_value.first.return_value = mock_step

        with patch("executions.services.ExecutionService"):
            response = self._post_webhook(
                payload=_make_terraform_payload(
                    run_status="applied", trigger="run:completed"
                )
            )

        assert response.status_code == 200
        mock_broadcast.assert_called_once()
        call_kwargs = mock_broadcast.call_args.kwargs
        assert call_kwargs["is_terminal"] is True
        assert call_kwargs["idp_status"] == "COMPLETED"

    @patch("executions.views.terraform_webhooks.ExecutionStep")
    @patch("executions.views.terraform_webhooks._broadcast_terraform_webhook_update")
    def test_errored_status(
        self,
        mock_broadcast: MagicMock,
        mock_step_model: MagicMock,
    ) -> None:
        """Errored status → FAILED, terminal."""
        mock_execution = MagicMock()
        mock_execution.id = 42
        mock_execution.status = "RUNNING"
        mock_execution.user_id = 1

        mock_step = MagicMock()
        mock_step.execution = mock_execution
        mock_step_model.objects.filter.return_value.select_related.return_value.first.return_value = mock_step

        with patch("executions.services.ExecutionService"):
            response = self._post_webhook(
                payload=_make_terraform_payload(
                    run_status="errored", trigger="run:errored"
                )
            )

        assert response.status_code == 200
        call_kwargs = mock_broadcast.call_args.kwargs
        assert call_kwargs["is_terminal"] is True
        assert call_kwargs["idp_status"] == "FAILED"
