"""
Tests pour ServiceCallHandler — Story 16.9 : notification comme integration_type.

Couvre AC1-AC5 (backend) et la non-régression AC8.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from executions.step_handlers.service_call_handler import ServiceCallHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_execution(execution_id: int = 1) -> MagicMock:
    execution = MagicMock()
    execution.id = execution_id
    execution.action = MagicMock()
    return execution


def _make_handler() -> ServiceCallHandler:
    return ServiceCallHandler()


# ---------------------------------------------------------------------------
# AC1 — _ALLOWED_OPERATIONS : notification avec opérations autorisées
# ---------------------------------------------------------------------------

class TestAllowedOperations:
    def test_send_email_allowed(self):
        """AC1 : send_email est dans la liste autorisée pour notification."""
        handler = _make_handler()
        execution = _make_execution()

        with patch("executions.app.handlers.service_call_handler.get_service_client") as mock_gsc:
            mock_service = MagicMock()
            mock_service.send_email.return_value = None
            mock_gsc.return_value = mock_service

            result = handler.execute(
                step_config={"integration_type": "notification", "operation": "send_email"},
                resolved_params={"recipient_email": "a@b.com", "subject": "Test", "body": "Hello"},
                execution=execution,
                step={},
                correlation_id="corr-1",
            )
        assert result == {"result": None}

    def test_send_teams_allowed(self):
        """AC1 : send_teams est dans la liste autorisée pour notification."""
        handler = _make_handler()
        execution = _make_execution()

        with patch("executions.app.handlers.service_call_handler.get_service_client") as mock_gsc:
            mock_service = MagicMock()
            mock_service.send_teams.return_value = None
            mock_gsc.return_value = mock_service

            result = handler.execute(
                step_config={"integration_type": "notification", "operation": "send_teams"},
                resolved_params={"webhook_url": "https://hooks.example.com", "message": "Hello"},
                execution=execution,
                step={},
                correlation_id="corr-2",
            )
        assert result == {"result": None}

    def test_notify_execution_event_allowed(self):
        """AC1 : notify_execution_event est dans la liste autorisée pour notification."""
        handler = _make_handler()
        execution = _make_execution()

        with patch("executions.app.handlers.service_call_handler.get_service_client") as mock_gsc:
            mock_service = MagicMock()
            mock_service.notify_execution_event.return_value = None
            mock_gsc.return_value = mock_service

            result = handler.execute(
                step_config={"integration_type": "notification", "operation": "notify_execution_event"},
                resolved_params={"event": "on_success"},
                execution=execution,
                step={},
                correlation_id="corr-3",
            )
        assert result == {"result": None}

    def test_unauthorized_operation_raises_value_error(self):
        """AC1 : opération non autorisée lève ValueError."""
        handler = _make_handler()
        execution = _make_execution()

        with pytest.raises(ValueError, match="send_page_individual.*not in the allowed list.*notification"):
            handler.execute(
                step_config={"integration_type": "notification", "operation": "send_page_individual"},
                resolved_params={},
                execution=execution,
                step={},
                correlation_id="corr-4",
            )


# ---------------------------------------------------------------------------
# AC2 — Pas de lookup Integration en base pour notification
# ---------------------------------------------------------------------------

class TestCredentialFreeType:
    def test_no_db_lookup_for_notification(self):
        """AC2 : notification n'effectue pas de lookup Integration en DB."""
        handler = _make_handler()
        execution = _make_execution()

        with patch("executions.app.handlers.service_call_handler.get_service_client") as mock_gsc, \
             patch("executions.app.handlers.service_call_handler.IntegrationService") as mock_is:
            mock_service = MagicMock()
            mock_service.send_email.return_value = None
            mock_gsc.return_value = mock_service

            handler.execute(
                step_config={"integration_type": "notification", "operation": "send_email"},
                resolved_params={"recipient_email": "x@y.com", "subject": "S", "body": "B"},
                execution=execution,
                step={},
                correlation_id=None,
            )

        # IntegrationService ne doit pas être instancié pour notification
        mock_is.assert_not_called()

    def test_no_service_unavailable_error_without_integration_record(self):
        """AC2 : pas de ServiceUnavailableError même sans Integration en base."""
        handler = _make_handler()
        execution = _make_execution()

        with patch("executions.app.handlers.service_call_handler.get_service_client") as mock_gsc:
            mock_service = MagicMock()
            mock_service.send_email.return_value = None
            mock_gsc.return_value = mock_service

            # Ne doit pas lever ServiceUnavailableError
            result = handler.execute(
                step_config={"integration_type": "notification", "operation": "send_email"},
                resolved_params={"recipient_email": "x@y.com", "subject": "S", "body": "B"},
                execution=execution,
                step={},
                correlation_id=None,
            )
        assert result == {"result": None}

    def test_get_service_client_called_without_base_url(self):
        """AC2 : get_service_client('notification') appelé sans base_url ni auth_headers."""
        handler = _make_handler()
        execution = _make_execution()

        with patch("executions.app.handlers.service_call_handler.get_service_client") as mock_gsc:
            mock_service = MagicMock()
            mock_service.send_email.return_value = None
            mock_gsc.return_value = mock_service

            handler.execute(
                step_config={"integration_type": "notification", "operation": "send_email"},
                resolved_params={"recipient_email": "x@y.com", "subject": "S", "body": "B"},
                execution=execution,
                step={},
                correlation_id=None,
            )

        mock_gsc.assert_called_once_with("notification")


# ---------------------------------------------------------------------------
# AC3 — send_email exécutable via step service_call
# ---------------------------------------------------------------------------

class TestSendEmail:
    def test_send_email_called_with_correct_params(self):
        """AC3 : send_email appelé avec recipient_email, subject, body depuis resolved_params."""
        handler = _make_handler()
        execution = _make_execution()

        with patch("executions.app.handlers.service_call_handler.get_service_client") as mock_gsc:
            mock_service = MagicMock()
            mock_service.send_email.return_value = None
            mock_gsc.return_value = mock_service

            result = handler.execute(
                step_config={"integration_type": "notification", "operation": "send_email"},
                resolved_params={
                    "recipient_email": "test@example.com",
                    "subject": "Sujet test",
                    "body": "Corps du message",
                },
                execution=execution,
                step={},
                correlation_id="c-1",
            )

        mock_service.send_email.assert_called_once_with(
            recipient_email="test@example.com",
            subject="Sujet test",
            body="Corps du message",
        )
        assert result == {"result": None}

    def test_send_email_result_normalized_to_dict(self):
        """AC3 : résultat None normalisé en {'result': None}."""
        handler = _make_handler()
        execution = _make_execution()

        with patch("executions.app.handlers.service_call_handler.get_service_client") as mock_gsc:
            mock_service = MagicMock()
            mock_service.send_email.return_value = None
            mock_gsc.return_value = mock_service

            result = handler.execute(
                step_config={"integration_type": "notification", "operation": "send_email"},
                resolved_params={"recipient_email": "a@b.com", "subject": "S", "body": "B"},
                execution=execution,
                step={},
                correlation_id=None,
            )

        assert result == {"result": None}


# ---------------------------------------------------------------------------
# AC4 — send_teams exécutable via step service_call
# ---------------------------------------------------------------------------

class TestSendTeams:
    def test_send_teams_called_with_required_params(self):
        """AC4 : send_teams appelé avec webhook_url, message depuis resolved_params."""
        handler = _make_handler()
        execution = _make_execution()

        with patch("executions.app.handlers.service_call_handler.get_service_client") as mock_gsc:
            mock_service = MagicMock()
            mock_service.send_teams.return_value = None
            mock_gsc.return_value = mock_service

            result = handler.execute(
                step_config={"integration_type": "notification", "operation": "send_teams"},
                resolved_params={
                    "webhook_url": "https://hooks.teams.example.com/abc",
                    "message": "Déploiement réussi",
                },
                execution=execution,
                step={},
                correlation_id="c-2",
            )

        mock_service.send_teams.assert_called_once_with(
            webhook_url="https://hooks.teams.example.com/abc",
            message="Déploiement réussi",
        )
        assert result == {"result": None}

    def test_send_teams_with_optional_params(self):
        """AC4 : send_teams avec title et color optionnels."""
        handler = _make_handler()
        execution = _make_execution()

        with patch("executions.app.handlers.service_call_handler.get_service_client") as mock_gsc:
            mock_service = MagicMock()
            mock_service.send_teams.return_value = None
            mock_gsc.return_value = mock_service

            handler.execute(
                step_config={"integration_type": "notification", "operation": "send_teams"},
                resolved_params={
                    "webhook_url": "https://hooks.teams.example.com/abc",
                    "message": "Message",
                    "title": "Titre",
                    "color": "00FF00",
                },
                execution=execution,
                step={},
                correlation_id=None,
            )

        mock_service.send_teams.assert_called_once_with(
            webhook_url="https://hooks.teams.example.com/abc",
            message="Message",
            title="Titre",
            color="00FF00",
        )


# ---------------------------------------------------------------------------
# AC5 — notify_execution_event avec injection auto de execution et action
# ---------------------------------------------------------------------------

class TestNotifyExecutionEvent:
    def test_execution_and_action_injected_automatically(self):
        """AC5 : execution et action injectés depuis le contexte handler, event depuis resolved_params."""
        handler = _make_handler()
        execution = _make_execution()
        action = execution.action

        with patch("executions.app.handlers.service_call_handler.get_service_client") as mock_gsc:
            mock_service = MagicMock()
            mock_service.notify_execution_event.return_value = None
            mock_gsc.return_value = mock_service

            result = handler.execute(
                step_config={"integration_type": "notification", "operation": "notify_execution_event"},
                resolved_params={"event": "on_success"},
                execution=execution,
                step={},
                correlation_id="c-3",
            )

        mock_service.notify_execution_event.assert_called_once_with(
            execution=execution,
            action=action,
            correlation_id="c-3",
            event="on_success",
        )
        assert result == {"result": None}

    def test_resolved_params_override_context_kwargs_for_event(self):
        """AC5 : event dans resolved_params est transmis correctement."""
        handler = _make_handler()
        execution = _make_execution()

        with patch("executions.app.handlers.service_call_handler.get_service_client") as mock_gsc:
            mock_service = MagicMock()
            mock_service.notify_execution_event.return_value = None
            mock_gsc.return_value = mock_service

            handler.execute(
                step_config={"integration_type": "notification", "operation": "notify_execution_event"},
                resolved_params={"event": "on_failure", "page_me": True},
                execution=execution,
                step={},
                correlation_id=None,
            )

        call_kwargs = mock_service.notify_execution_event.call_args[1]
        assert call_kwargs["event"] == "on_failure"
        assert call_kwargs["page_me"] is True
        assert call_kwargs["execution"] is execution
        assert call_kwargs["action"] is execution.action

    def test_notify_execution_event_result_normalized(self):
        """AC5 : résultat None normalisé en {'result': None}."""
        handler = _make_handler()
        execution = _make_execution()

        with patch("executions.app.handlers.service_call_handler.get_service_client") as mock_gsc:
            mock_service = MagicMock()
            mock_service.notify_execution_event.return_value = None
            mock_gsc.return_value = mock_service

            result = handler.execute(
                step_config={"integration_type": "notification", "operation": "notify_execution_event"},
                resolved_params={"event": "on_success"},
                execution=execution,
                step={},
                correlation_id=None,
            )

        assert result == {"result": None}

    def test_context_kwargs_not_overrideable_by_resolved_params(self):
        """Sécurité : execution/action/correlation_id ne peuvent pas être surchargés via resolved_params."""
        handler = _make_handler()
        execution = _make_execution()
        fake_execution = MagicMock()
        fake_execution.id = 999
        fake_action = MagicMock()

        with patch("executions.app.handlers.service_call_handler.get_service_client") as mock_gsc:
            mock_service = MagicMock()
            mock_service.notify_execution_event.return_value = None
            mock_gsc.return_value = mock_service

            handler.execute(
                step_config={"integration_type": "notification", "operation": "notify_execution_event"},
                resolved_params={
                    "event": "on_success",
                    "execution": fake_execution,   # tentative d'injection via input_mapping
                    "action": fake_action,          # tentative d'injection via input_mapping
                    "correlation_id": "injected",   # tentative d'injection via input_mapping
                },
                execution=execution,
                step={},
                correlation_id="real-corr",
            )

        call_kwargs = mock_service.notify_execution_event.call_args[1]
        # Les objets contextuels doivent être ceux du handler, pas ceux de resolved_params
        assert call_kwargs["execution"] is execution, "execution ne doit pas être surchargé par resolved_params"
        assert call_kwargs["execution"] is not fake_execution
        assert call_kwargs["action"] is execution.action, "action ne doit pas être surchargé par resolved_params"
        assert call_kwargs["action"] is not fake_action
        assert call_kwargs["correlation_id"] == "real-corr", "correlation_id ne doit pas être surchargé"
        # event reste accessible (non protégé)
        assert call_kwargs["event"] == "on_success"


# ---------------------------------------------------------------------------
# AC8 — Non-régression : servicenow, vault, jira inchangés
# ---------------------------------------------------------------------------

class TestNonRegression:
    def test_unknown_integration_type_raises_value_error(self):
        """AC8 : type d'intégration inconnu lève ValueError."""
        handler = _make_handler()
        execution = _make_execution()

        with pytest.raises(ValueError, match="Unknown integration_type: 'unknown_type'"):
            handler.execute(
                step_config={"integration_type": "unknown_type", "operation": "do_something"},
                resolved_params={},
                execution=execution,
                step={},
                correlation_id=None,
            )

    def test_servicenow_still_requires_integration_db_record(self):
        """AC8 : servicenow effectue toujours le lookup Integration en DB."""
        handler = _make_handler()
        execution = _make_execution()

        with patch("executions.app.handlers.service_call_handler.IntegrationService") as mock_is:
            mock_integration_service = MagicMock()
            mock_is.return_value = mock_integration_service
            mock_integration_service.get_by_id.return_value = None
            mock_integration_service.get_by_type.return_value = None

            from core.exceptions import ServiceUnavailableError

            with pytest.raises(ServiceUnavailableError):
                handler.execute(
                    step_config={"integration_type": "servicenow", "operation": "create_change"},
                    resolved_params={},
                    execution=execution,
                    step={},
                    correlation_id=None,
                )

        mock_is.assert_called_once()

    def test_missing_integration_type_raises_value_error(self):
        """AC8 : integration_type manquant lève ValueError."""
        handler = _make_handler()
        execution = _make_execution()

        with pytest.raises(ValueError, match="requires 'integration_type'"):
            handler.execute(
                step_config={},
                resolved_params={},
                execution=execution,
                step={},
                correlation_id=None,
            )

    def test_missing_operation_raises_value_error(self):
        """AC8 : operation manquante lève ValueError."""
        handler = _make_handler()
        execution = _make_execution()

        with pytest.raises(ValueError, match="requires 'operation'"):
            handler.execute(
                step_config={"integration_type": "notification"},
                resolved_params={},
                execution=execution,
                step={},
                correlation_id=None,
            )

    def test_private_method_blocked(self):
        """AC8 : méthodes privées (_*) toujours bloquées."""
        handler = _make_handler()
        execution = _make_execution()

        with pytest.raises(ValueError, match="private methods cannot be called"):
            handler.execute(
                step_config={"integration_type": "notification", "operation": "_internal"},
                resolved_params={},
                execution=execution,
                step={},
                correlation_id=None,
            )
