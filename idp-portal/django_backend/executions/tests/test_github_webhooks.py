"""
Tests pour le webhook GitHub Actions (executions) — Story 34.4 (SOLID-BE-9).

Couvre :
- Vérification signature HMAC SHA-256
- Parsing payload / actions ignorées
- DI via override_service (AC2)
- Status update + broadcast
- Edge cases : run_id inconnu, payload invalide
"""
from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from unittest.mock import MagicMock, patch

from rest_framework.test import APIClient

from executions.views.github_webhooks import _verify_github_signature


WEBHOOK_SECRET = "test-github-webhook-secret"
WEBHOOK_URL = "/api/v1/webhooks/github/workflow_run"


def _sign_payload(payload: bytes, secret: str = WEBHOOK_SECRET) -> str:
    """Génère une signature HMAC SHA-256 GitHub-style."""
    return (
        "sha256="
        + hmac.new(
            secret.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()
    )


def _make_github_payload(
    action: str = "completed",
    run_id: int = 123456,
    status: str = "completed",
    conclusion: str | None = "success",
) -> dict:
    """Construit un payload workflow_run GitHub."""
    return {
        "action": action,
        "workflow_run": {
            "id": run_id,
            "status": status,
            "conclusion": conclusion,
            "name": "CI",
            "html_url": f"https://github.com/org/repo/actions/runs/{run_id}",
        },
        "repository": {"full_name": "org/repo"},
    }


# ---------------------------------------------------------------------------
# _verify_github_signature
# ---------------------------------------------------------------------------

class TestVerifyGithubSignature:
    def test_valid_signature(self) -> None:
        body = b'{"action": "completed"}'
        sig = _sign_payload(body)
        assert _verify_github_signature(body, sig, WEBHOOK_SECRET) is True

    def test_invalid_signature(self) -> None:
        body = b'{"action": "completed"}'
        assert _verify_github_signature(body, "sha256=badhex", WEBHOOK_SECRET) is False

    def test_missing_sha256_prefix(self) -> None:
        body = b'{"action": "completed"}'
        raw_sig = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
        assert _verify_github_signature(body, raw_sig, WEBHOOK_SECRET) is False

    def test_empty_signature(self) -> None:
        assert _verify_github_signature(b"body", "", "secret") is False

    def test_wrong_secret(self) -> None:
        body = b'{"action": "completed"}'
        sig = _sign_payload(body, secret="wrong-secret")
        assert _verify_github_signature(body, sig, WEBHOOK_SECRET) is False


# ---------------------------------------------------------------------------
# Endpoint integration tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGithubWebhookEndpoint:
    """Tests du webhook GitHub Actions."""

    @pytest.fixture(autouse=True)
    def _configure_secret(self, settings) -> None:  # type: ignore[no-untyped-def]
        settings.GITHUB_WEBHOOK_SECRET = WEBHOOK_SECRET

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
        """Envoie un POST webhook avec signature HMAC SHA-256."""
        if raw_body is None:
            raw_body = json.dumps(payload or _make_github_payload()).encode()

        headers: dict = {"content_type": "application/json"}
        if sign:
            headers["HTTP_X_HUB_SIGNATURE_256"] = _sign_payload(raw_body, secret)

        return self.client.post(WEBHOOK_URL, data=raw_body, **headers)

    def test_no_secret_configured(self, settings) -> None:  # type: ignore[no-untyped-def]
        settings.GITHUB_WEBHOOK_SECRET = ""
        response = self._post_webhook()
        assert response.status_code == 500

    def test_invalid_signature_rejected(self) -> None:
        raw_body = json.dumps(_make_github_payload()).encode()
        response = self.client.post(
            WEBHOOK_URL,
            data=raw_body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256="sha256=badhex",
        )
        assert response.status_code == 401

    def test_missing_signature(self) -> None:
        response = self._post_webhook(sign=False)
        assert response.status_code == 401

    def test_invalid_json(self) -> None:
        response = self._post_webhook(raw_body=b"not{json")
        assert response.status_code == 400

    def test_action_ignored(self) -> None:
        """Actions non-processables → 200 ignored."""
        response = self._post_webhook(payload=_make_github_payload(action="rerequested"))
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"

    def test_missing_workflow_run(self) -> None:
        payload = {"action": "completed"}  # no workflow_run key
        response = self._post_webhook(payload=payload)
        assert response.status_code == 400

    @patch("executions.views.github_webhooks.ExecutionStep")
    @patch("executions.views.github_webhooks._broadcast_webhook_update")
    def test_execution_not_found(
        self,
        mock_broadcast: MagicMock,
        mock_step_model: MagicMock,
    ) -> None:
        """Run_id inconnu → 200 no_matching_execution."""
        mock_step_model.objects.filter.return_value.select_related.return_value.first.return_value = None

        response = self._post_webhook(payload=_make_github_payload(run_id=99999))
        assert response.status_code == 200
        assert response.json()["status"] == "no_matching_execution"
        mock_broadcast.assert_not_called()

    @patch("executions.views.github_webhooks.ExecutionStep")
    @patch("executions.views.github_webhooks._broadcast_webhook_update")
    def test_webhook_di_override_service(
        self,
        mock_broadcast: MagicMock,
        mock_step_model: MagicMock,
    ) -> None:
        """AC2 : le service d'exécution est injecté via override_service (DI propre)."""
        from core.di import override_service

        mock_execution = MagicMock()
        mock_execution.id = 42
        mock_execution.status = "SUBMITTED"
        mock_execution.user_id = 1

        mock_step = MagicMock()
        mock_step.execution = mock_execution
        mock_step_model.objects.filter.return_value.select_related.return_value.first.return_value = mock_step

        mock_svc = MagicMock()
        override_service("execution_service", lambda: mock_svc)

        response = self._post_webhook(
            payload=_make_github_payload(
                action="completed", status="completed", conclusion="success"
            )
        )

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        mock_svc.update_status.assert_called_once()
        mock_broadcast.assert_called_once()

    @patch("executions.views.github_webhooks.ExecutionStep")
    @patch("executions.views.github_webhooks._broadcast_webhook_update")
    def test_terminal_status_broadcast(
        self,
        mock_broadcast: MagicMock,
        mock_step_model: MagicMock,
    ) -> None:
        """Status terminal 'completed/success' → broadcast avec is_terminal=True."""
        from core.di import override_service

        mock_execution = MagicMock()
        mock_execution.id = 7
        mock_execution.status = "RUNNING"
        mock_execution.user_id = 2

        mock_step = MagicMock()
        mock_step.execution = mock_execution
        mock_step_model.objects.filter.return_value.select_related.return_value.first.return_value = mock_step

        override_service("execution_service", lambda: MagicMock())

        response = self._post_webhook(
            payload=_make_github_payload(
                action="completed", status="completed", conclusion="success"
            )
        )

        assert response.status_code == 200
        call_kwargs = mock_broadcast.call_args.kwargs
        assert call_kwargs["is_terminal"] is True
        assert call_kwargs["idp_status"] == "COMPLETED"

# ---------------------------------------------------------------------------
# Story 39.5 — Branches manquantes (4.1 - 4.11)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestGithubWebhookMissingRunId:
    """4.1 run_id absent dans workflow_run → 400."""

    @pytest.fixture(autouse=True)
    def _configure_secret(self, settings):
        settings.GITHUB_WEBHOOK_SECRET = WEBHOOK_SECRET

    def setup_method(self):
        self.client = APIClient()

    def _post_webhook(self, payload):
        raw_body = json.dumps(payload).encode()
        sig = _sign_payload(raw_body)
        return self.client.post(
            WEBHOOK_URL,
            data=raw_body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=sig,
        )

    def test_empty_run_id_returns_400(self):
        payload = _make_github_payload()
        payload["workflow_run"]["id"] = ""  # run_id vide → str("") après conversion
        response = self._post_webhook(payload)
        assert response.status_code == 400


@pytest.mark.django_db
class TestGithubWebhookDatabaseError:
    """4.2 DatabaseError lors du lookup → 500."""

    @pytest.fixture(autouse=True)
    def _configure_secret(self, settings):
        settings.GITHUB_WEBHOOK_SECRET = WEBHOOK_SECRET

    def setup_method(self):
        self.client = APIClient()

    def _post_webhook(self, payload=None):
        raw_body = json.dumps(payload or _make_github_payload()).encode()
        sig = _sign_payload(raw_body)
        return self.client.post(
            WEBHOOK_URL,
            data=raw_body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=sig,
        )

    @patch("executions.views.github_webhooks.ExecutionStep")
    def test_db_error_returns_500(self, mock_step_model):
        from django.db import DatabaseError
        mock_step_model.objects.filter.return_value.select_related.return_value.first.side_effect = DatabaseError("DB down")
        response = self._post_webhook()
        assert response.status_code == 500


@pytest.mark.django_db
class TestGithubWebhookTerminalAndUnchangedStatus:
    """4.3 execution déjà terminale → pas d'appel update_status.
       4.4 status inchangé → pas d'appel update_status.
       4.5 ValueError dans update_status → log warning, pas d'exception.
    """

    @pytest.fixture(autouse=True)
    def _configure_secret(self, settings):
        settings.GITHUB_WEBHOOK_SECRET = WEBHOOK_SECRET

    def setup_method(self):
        self.client = APIClient()
        from core.di import reset_services
        reset_services()

    def teardown_method(self):
        from core.di import reset_services
        reset_services()

    def _post_webhook(self, payload=None):
        raw_body = json.dumps(payload or _make_github_payload()).encode()
        sig = _sign_payload(raw_body)
        return self.client.post(
            WEBHOOK_URL,
            data=raw_body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=sig,
        )

    @patch("executions.views.github_webhooks.ExecutionStep")
    @patch("executions.views.github_webhooks._broadcast_webhook_update")
    def test_terminal_execution_skips_status_update(self, mock_broadcast, mock_step_model):
        """4.3 execution déjà terminale → pas d'appel update_status."""
        from core.di import override_service
        mock_execution = MagicMock()
        mock_execution.id = 10
        mock_execution.status = "COMPLETED"  # already terminal
        mock_execution.user_id = 1
        mock_step = MagicMock()
        mock_step.execution = mock_execution
        mock_step_model.objects.filter.return_value.select_related.return_value.first.return_value = mock_step

        mock_svc = MagicMock()
        override_service("execution_service", lambda: mock_svc)

        response = self._post_webhook(payload=_make_github_payload(status="completed", conclusion="success"))
        assert response.status_code == 200
        mock_svc.update_status.assert_not_called()

    @patch("executions.views.github_webhooks.ExecutionStep")
    @patch("executions.views.github_webhooks._broadcast_webhook_update")
    def test_status_unchanged_skips_update(self, mock_broadcast, mock_step_model):
        """4.4 status inchangé (idp_status == execution.status) → pas d'appel update_status."""
        from core.di import override_service
        # RUNNING maps to same IDP status
        mock_execution = MagicMock()
        mock_execution.id = 11
        mock_execution.status = "RUNNING"
        mock_execution.user_id = 1
        mock_step = MagicMock()
        mock_step.execution = mock_execution
        mock_step_model.objects.filter.return_value.select_related.return_value.first.return_value = mock_step

        mock_svc = MagicMock()
        override_service("execution_service", lambda: mock_svc)

        # status=in_progress → RUNNING (same as current)
        response = self._post_webhook(payload=_make_github_payload(action="in_progress", status="in_progress", conclusion=None))
        assert response.status_code == 200
        mock_svc.update_status.assert_not_called()

    @patch("executions.views.github_webhooks.ExecutionStep")
    @patch("executions.views.github_webhooks._broadcast_webhook_update")
    def test_value_error_in_update_status_logs_warning(self, mock_broadcast, mock_step_model):
        """4.5 ValueError dans update_status → log warning, pas d'exception."""
        from core.di import override_service
        mock_execution = MagicMock()
        mock_execution.id = 12
        mock_execution.status = "SUBMITTED"
        mock_execution.user_id = 1
        mock_step = MagicMock()
        mock_step.execution = mock_execution
        mock_step_model.objects.filter.return_value.select_related.return_value.first.return_value = mock_step

        mock_svc = MagicMock()
        mock_svc.update_status.side_effect = ValueError("Invalid transition")
        override_service("execution_service", lambda: mock_svc)

        response = self._post_webhook(payload=_make_github_payload(status="completed", conclusion="success"))
        # Doit retourner 200 sans exception
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests directs de _broadcast_webhook_update (4.6 - 4.11)
# ---------------------------------------------------------------------------

class TestBroadcastWebhookUpdateDirect:
    """Tests directs de la fonction _broadcast_webhook_update.

    Note : get_channel_layer et async_to_sync sont importés lazily dans le bloc try
    de _broadcast_webhook_update. On doit donc patcher via channels.layers et asgiref.sync.
    """

    def test_no_channel_layer_returns_silently(self):
        """4.6 channel_layer=None → warning, return silencieux."""
        from executions.views.github_webhooks import _broadcast_webhook_update
        with patch("channels.layers.get_channel_layer", return_value=None):
            _broadcast_webhook_update(
                execution_id=1,
                idp_status="RUNNING",
                gh_status="in_progress",
                gh_conclusion=None,
                is_terminal=False,
                correlation_id="test",
            )

    def test_terminal_completed_sends_execution_complete(self):
        """4.7 terminal + COMPLETED → event_type='execution_complete'."""
        from executions.views.github_webhooks import _broadcast_webhook_update
        mock_layer = MagicMock()
        with patch("channels.layers.get_channel_layer", return_value=mock_layer):
            with patch("asgiref.sync.async_to_sync") as mock_a2s:
                mock_a2s.return_value = MagicMock()
                _broadcast_webhook_update(
                    execution_id=42,
                    idp_status="COMPLETED",
                    gh_status="completed",
                    gh_conclusion="success",
                    is_terminal=True,
                )
        # 2 appels : status_update + execution_complete
        assert mock_a2s.call_count == 2

    def test_terminal_failed_sends_execution_failed(self):
        """4.8 terminal + FAILED → event_type='execution_failed'."""
        from executions.views.github_webhooks import _broadcast_webhook_update
        mock_layer = MagicMock()
        with patch("channels.layers.get_channel_layer", return_value=mock_layer):
            with patch("asgiref.sync.async_to_sync") as mock_a2s:
                mock_a2s.return_value = MagicMock()
                _broadcast_webhook_update(
                    execution_id=43,
                    idp_status="FAILED",
                    gh_status="completed",
                    gh_conclusion="failure",
                    is_terminal=True,
                )
        # 2 appels : status_update + execution_failed
        assert mock_a2s.call_count == 2

    def test_non_terminal_sends_single_status_update(self):
        """4.9 non-terminal → un seul group_send (status_update)."""
        from executions.views.github_webhooks import _broadcast_webhook_update
        mock_layer = MagicMock()
        with patch("channels.layers.get_channel_layer", return_value=mock_layer):
            with patch("asgiref.sync.async_to_sync") as mock_a2s:
                mock_a2s.return_value = MagicMock()
                _broadcast_webhook_update(
                    execution_id=44,
                    idp_status="RUNNING",
                    gh_status="in_progress",
                    gh_conclusion=None,
                    is_terminal=False,
                )
        # 1 seul appel async_to_sync (status_update uniquement)
        assert mock_a2s.call_count == 1

    def test_import_error_channels_logs_error_no_raise(self):
        """4.10 ImportError channels → log error, pas d'exception."""
        from executions.views.github_webhooks import _broadcast_webhook_update
        with patch("channels.layers.get_channel_layer", side_effect=ImportError("channels not installed")):
            _broadcast_webhook_update(
                execution_id=1,
                idp_status="RUNNING",
                gh_status="in_progress",
                gh_conclusion=None,
                is_terminal=False,
            )

    def test_generic_exception_logs_error_no_raise(self):
        """4.11 exception générique → log error, pas d'exception."""
        from executions.views.github_webhooks import _broadcast_webhook_update
        with patch("channels.layers.get_channel_layer", side_effect=RuntimeError("unexpected error")):
            _broadcast_webhook_update(
                execution_id=1,
                idp_status="RUNNING",
                gh_status="in_progress",
                gh_conclusion=None,
                is_terminal=False,
            )
