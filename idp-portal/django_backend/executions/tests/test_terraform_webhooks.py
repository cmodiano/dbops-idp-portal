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

    def teardown_method(self) -> None:
        from core.di import reset_services
        reset_services()

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

        from core.di import override_service
        mock_svc = MagicMock()
        override_service("execution_service", lambda: mock_svc)

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

        from core.di import override_service
        override_service("execution_service", lambda: MagicMock())

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

        from core.di import override_service
        override_service("execution_service", lambda: MagicMock())

        response = self._post_webhook(
            payload=_make_terraform_payload(
                run_status="errored", trigger="run:errored"
            )
        )

        assert response.status_code == 200
        call_kwargs = mock_broadcast.call_args.kwargs
        assert call_kwargs["is_terminal"] is True
        assert call_kwargs["idp_status"] == "FAILED"

# ---------------------------------------------------------------------------
# Story 39.5 — Branches manquantes (5.1 - 5.11)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestTerraformWebhookBranchesExtra:
    """5.1-5.5 branches supplémentaires du endpoint terraform_webhook_run."""

    @pytest.fixture(autouse=True)
    def _configure_secret(self, settings) -> None:
        settings.TERRAFORM_WEBHOOK_SECRET = WEBHOOK_SECRET

    def setup_method(self) -> None:
        self.client = APIClient()
        from core.di import reset_services
        reset_services()

    def teardown_method(self) -> None:
        from core.di import reset_services
        reset_services()

    def _post_webhook(self, payload=None, raw_body=None):
        if raw_body is None:
            raw_body = json.dumps(payload or _make_terraform_payload()).encode()
        headers = {
            "content_type": "application/json",
            "HTTP_X_TFE_NOTIFICATION_SIGNATURE": _sign_payload(raw_body),
        }
        return self.client.post(WEBHOOK_URL, data=raw_body, **headers)

    @patch("executions.views.terraform_webhooks.ExecutionStep")
    @patch("executions.views.terraform_webhooks._broadcast_terraform_webhook_update")
    def test_step_without_execution_returns_no_match(self, mock_broadcast, mock_step_model):
        """5.1 step existe mais step.execution=None → no_matching_execution."""
        # Créer un mock sans attribut 'execution' mais avec 'id' pour le logging
        class _StepWithoutExecution:
            id = 999

        mock_step = _StepWithoutExecution()
        mock_step_model.objects.filter.return_value.select_related.return_value.first.return_value = mock_step

        response = self._post_webhook()
        assert response.status_code == 200
        assert response.json()["status"] == "no_matching_execution"
        mock_broadcast.assert_not_called()

    @patch("executions.views.terraform_webhooks.ExecutionStep")
    def test_db_error_returns_500(self, mock_step_model):
        """5.2 DatabaseError lors du lookup → 500."""
        from django.db import DatabaseError
        mock_step_model.objects.filter.return_value.select_related.return_value.first.side_effect = DatabaseError("DB error")
        response = self._post_webhook()
        assert response.status_code == 500

    @patch("executions.views.terraform_webhooks.ExecutionStep")
    @patch("executions.views.terraform_webhooks._broadcast_terraform_webhook_update")
    def test_terminal_execution_skips_status_update(self, mock_broadcast, mock_step_model):
        """5.3 execution déjà terminale → pas d'appel update_status."""
        from core.di import override_service
        mock_execution = MagicMock()
        mock_execution.id = 20
        mock_execution.status = "COMPLETED"  # already terminal
        mock_execution.user_id = 1
        mock_step = MagicMock()
        mock_step.execution = mock_execution
        mock_step_model.objects.filter.return_value.select_related.return_value.first.return_value = mock_step

        mock_svc = MagicMock()
        override_service("execution_service", lambda: mock_svc)

        response = self._post_webhook(payload=_make_terraform_payload(run_status="applied", trigger="run:completed"))
        assert response.status_code == 200
        mock_svc.update_status.assert_not_called()

    @patch("executions.views.terraform_webhooks.ExecutionStep")
    @patch("executions.views.terraform_webhooks._broadcast_terraform_webhook_update")
    def test_status_unchanged_skips_update(self, mock_broadcast, mock_step_model):
        """5.4 status inchangé → pas d'appel update_status."""
        from core.di import override_service
        mock_execution = MagicMock()
        mock_execution.id = 21
        mock_execution.status = "RUNNING"
        mock_execution.user_id = 1
        mock_step = MagicMock()
        mock_step.execution = mock_execution
        mock_step_model.objects.filter.return_value.select_related.return_value.first.return_value = mock_step

        mock_svc = MagicMock()
        override_service("execution_service", lambda: mock_svc)

        # planning → RUNNING (même statut)
        response = self._post_webhook(payload=_make_terraform_payload(run_status="planning", trigger="run:planning"))
        assert response.status_code == 200
        mock_svc.update_status.assert_not_called()

    @patch("executions.views.terraform_webhooks.ExecutionStep")
    @patch("executions.views.terraform_webhooks._broadcast_terraform_webhook_update")
    def test_value_error_in_update_status_logs_warning(self, mock_broadcast, mock_step_model):
        """5.5 ValueError dans update_status → log warning, pas d'exception."""
        from core.di import override_service
        mock_execution = MagicMock()
        mock_execution.id = 22
        mock_execution.status = "SUBMITTED"
        mock_execution.user_id = 1
        mock_step = MagicMock()
        mock_step.execution = mock_execution
        mock_step_model.objects.filter.return_value.select_related.return_value.first.return_value = mock_step

        mock_svc = MagicMock()
        mock_svc.update_status.side_effect = ValueError("Invalid transition")
        override_service("execution_service", lambda: mock_svc)

        response = self._post_webhook(payload=_make_terraform_payload(run_status="applied", trigger="run:completed"))
        # Doit retourner 200 sans exception
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests directs de _broadcast_terraform_webhook_update (5.6 - 5.11)
# ---------------------------------------------------------------------------

class TestBroadcastTerraformWebhookUpdateDirect:
    """Tests directs de _broadcast_terraform_webhook_update.

    Note : get_channel_layer et async_to_sync sont importés lazily dans le try block.
    Patcher via channels.layers et asgiref.sync.
    """

    def test_no_channel_layer_returns_silently(self):
        """5.6 channel_layer=None → warning, return silencieux."""
        from executions.views.terraform_webhooks import _broadcast_terraform_webhook_update
        with patch("channels.layers.get_channel_layer", return_value=None):
            _broadcast_terraform_webhook_update(
                execution_id=1,
                idp_status="RUNNING",
                tc_status="planning",
                is_terminal=False,
            )

    def test_channel_layer_without_group_send_returns(self):
        """5.7 channel_layer sans group_send → log error, return silencieux."""
        from executions.views.terraform_webhooks import _broadcast_terraform_webhook_update
        mock_layer = MagicMock(spec=[])  # pas de group_send
        with patch("channels.layers.get_channel_layer", return_value=mock_layer):
            with patch("asgiref.sync.async_to_sync") as mock_a2s:
                _broadcast_terraform_webhook_update(
                    execution_id=1,
                    idp_status="RUNNING",
                    tc_status="planning",
                    is_terminal=False,
                )
        mock_a2s.assert_not_called()

    def test_terminal_completed_sends_execution_complete(self):
        """5.8 terminal + COMPLETED → event_type='execution_complete'."""
        from executions.views.terraform_webhooks import _broadcast_terraform_webhook_update
        mock_layer = MagicMock()
        with patch("channels.layers.get_channel_layer", return_value=mock_layer):
            with patch("asgiref.sync.async_to_sync") as mock_a2s:
                mock_a2s.return_value = MagicMock()
                _broadcast_terraform_webhook_update(
                    execution_id=5,
                    idp_status="COMPLETED",
                    tc_status="applied",
                    is_terminal=True,
                )
        # 2 appels : status_update + execution_complete
        assert mock_a2s.call_count == 2

    def test_terminal_failed_sends_execution_failed(self):
        """5.9 terminal + FAILED → event_type='execution_failed'."""
        from executions.views.terraform_webhooks import _broadcast_terraform_webhook_update
        mock_layer = MagicMock()
        with patch("channels.layers.get_channel_layer", return_value=mock_layer):
            with patch("asgiref.sync.async_to_sync") as mock_a2s:
                mock_a2s.return_value = MagicMock()
                _broadcast_terraform_webhook_update(
                    execution_id=6,
                    idp_status="FAILED",
                    tc_status="errored",
                    is_terminal=True,
                )
        # 2 appels : status_update + execution_failed
        assert mock_a2s.call_count == 2

    def test_import_error_logs_error_no_raise(self):
        """5.10 ImportError → log error, pas d'exception."""
        from executions.views.terraform_webhooks import _broadcast_terraform_webhook_update
        with patch("channels.layers.get_channel_layer", side_effect=ImportError("channels not installed")):
            _broadcast_terraform_webhook_update(
                execution_id=1,
                idp_status="RUNNING",
                tc_status="planning",
                is_terminal=False,
            )

    def test_generic_exception_logs_error_no_raise(self):
        """5.11 exception générique → log error, pas d'exception."""
        from executions.views.terraform_webhooks import _broadcast_terraform_webhook_update
        with patch("channels.layers.get_channel_layer", side_effect=RuntimeError("unexpected")):
            _broadcast_terraform_webhook_update(
                execution_id=1,
                idp_status="RUNNING",
                tc_status="planning",
                is_terminal=False,
            )
