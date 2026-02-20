"""
Story 31.8: Tests unitaires du NotificationService.
Valide l'envoi vers chaque type de destination (avec mocks).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from services.notification_service import NotificationService


class TestSendEmail:
    """Tests pour send_email()."""

    def setup_method(self) -> None:
        self.service = NotificationService()

    @patch("services.notification_service.send_mail")
    def test_send_email_ok(self, mock_send_mail: MagicMock) -> None:
        """send_email appelle django send_mail avec les bons arguments."""
        self.service.send_email("test@example.com", "Sujet", "Corps")
        mock_send_mail.assert_called_once()
        call_kwargs = mock_send_mail.call_args
        assert call_kwargs.kwargs["subject"] == "Sujet"
        assert call_kwargs.kwargs["recipient_list"] == ["test@example.com"]

    @patch("services.notification_service.send_mail")
    def test_send_email_failure_non_blocking(self, mock_send_mail: MagicMock) -> None:
        """Une exception dans send_email ne doit pas se propager."""
        mock_send_mail.side_effect = Exception("SMTP error")
        # Ne lève pas d'exception
        self.service.send_email("test@example.com", "Sujet", "Corps")


class TestSendTeams:
    """Tests pour send_teams()."""

    def setup_method(self) -> None:
        self.service = NotificationService()

    @patch("services.notification_service.httpx.post")
    def test_send_teams_ok(self, mock_post: MagicMock) -> None:
        """send_teams envoie un MessageCard via httpx.post."""
        mock_response = MagicMock(status_code=200)
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        self.service.send_teams("http://webhook.example.com", "Test message")
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["@type"] == "MessageCard"

    @patch("services.notification_service.httpx.post")
    def test_send_teams_failure_non_blocking(self, mock_post: MagicMock) -> None:
        """Une exception dans send_teams ne doit pas se propager."""
        mock_post.side_effect = Exception("Connection error")
        self.service.send_teams("http://webhook.example.com", "Test message")


class TestSendPageIndividual:
    """Tests pour send_page_individual()."""

    def setup_method(self) -> None:
        self.service = NotificationService()

    @patch("services.notification_service.httpx.post")
    def test_send_page_individual_ok(self, mock_post: MagicMock) -> None:
        """send_page_individual appelle l'API avec le bon payload."""
        mock_response = MagicMock(status_code=200)
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        with patch("services.notification_service.settings") as mock_settings:
            mock_settings.PAGE_INDIVIDUAL_API_URL = "http://page-api/individual"
            self.service.send_page_individual(
                user_id="user1", user_name="User One",
                message="Alert", action_name="Test", execution_id=42,
            )
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        assert payload["user_id"] == "user1"
        assert payload["execution_id"] == 42

    @patch("services.notification_service.httpx.post")
    def test_send_page_individual_not_configured(self, mock_post: MagicMock) -> None:
        """Si PAGE_INDIVIDUAL_API_URL est vide, ne pas appeler."""
        with patch("services.notification_service.settings") as mock_settings:
            mock_settings.PAGE_INDIVIDUAL_API_URL = ""
            self.service.send_page_individual(
                user_id="user1", user_name="User One",
                message="Alert", action_name="Test", execution_id=42,
            )
        mock_post.assert_not_called()


class TestSendPageDba:
    """Tests pour send_page_dba()."""

    def setup_method(self) -> None:
        self.service = NotificationService()

    @patch("services.notification_service.httpx.post")
    def test_send_page_dba_ok(self, mock_post: MagicMock) -> None:
        """send_page_dba appelle l'API avec le bon payload."""
        mock_response = MagicMock(status_code=200)
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        self.service.send_page_dba(
            api_url="http://page-api/dba",
            message="DBA Alert", action_name="Test", execution_id=42, level="critical",
        )
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        assert payload["level"] == "critical"
        assert payload["execution_id"] == 42

    @patch("services.notification_service.httpx.post")
    def test_send_page_dba_not_configured(self, mock_post: MagicMock) -> None:
        """Si api_url est vide et PAGE_DBA_API_URL aussi, ne pas appeler."""
        with patch("services.notification_service.settings") as mock_settings:
            mock_settings.PAGE_DBA_API_URL = ""
            self.service.send_page_dba(
                api_url="",
                message="DBA Alert", action_name="Test", execution_id=42, level="critical",
            )
        mock_post.assert_not_called()


class TestNotifyExecutionEvent:
    """Tests pour notify_execution_event()."""

    def setup_method(self) -> None:
        self.service = NotificationService()

    def _make_execution(self, env: str = "prod") -> MagicMock:
        execution = MagicMock()
        execution.environment = env
        execution.id = 1
        execution.user.email = "user@example.com"
        return execution

    def _make_action(
        self,
        notification_config: dict | None = None,
        impact_level: str = "low",
        impact_rules: dict | None = None,
    ) -> MagicMock:
        action = MagicMock()
        action.notification_config = notification_config
        action.impact_rules = impact_rules or {}
        action.default_impact_level = impact_level
        action.name = "Test Action"
        return action

    def test_notify_execution_event_on_failure_email(self) -> None:
        """Les canaux on_failure sont appelés quand event=on_failure."""
        config = {
            "channels": [
                {"type": "email", "enabled": True, "conditions": ["on_failure"], "recipient": "requester"},
            ],
            "page_individual_enabled": False,
        }
        execution = self._make_execution()
        action = self._make_action(notification_config=config)

        with patch.object(self.service, "send_email") as mock_email:
            self.service.notify_execution_event(execution, action, "on_failure")
            mock_email.assert_called_once()

    def test_notify_execution_event_on_success_email(self) -> None:
        """Les canaux on_success sont appelés quand event=on_success."""
        config = {
            "channels": [
                {"type": "email", "enabled": True, "conditions": ["on_success"], "recipient": "requester"},
            ],
            "page_individual_enabled": False,
        }
        execution = self._make_execution()
        action = self._make_action(notification_config=config)

        with patch.object(self.service, "send_email") as mock_email:
            self.service.notify_execution_event(execution, action, "on_success")
            mock_email.assert_called_once()

    def test_notify_execution_event_email_not_on_success(self) -> None:
        """Un canal on_failure ne doit PAS être appelé quand event=on_success."""
        config = {
            "channels": [
                {"type": "email", "enabled": True, "conditions": ["on_failure"], "recipient": "requester"},
            ],
        }
        execution = self._make_execution()
        action = self._make_action(notification_config=config)

        with patch.object(self.service, "send_email") as mock_email:
            self.service.notify_execution_event(execution, action, "on_success")
            mock_email.assert_not_called()

    def test_page_only_in_prod_critical(self) -> None:
        """Page individuel NON envoyé si env != prod ou level != critical."""
        execution = self._make_execution(env="staging")
        action = self._make_action(
            notification_config={"channels": [], "page_individual_enabled": True},
            impact_level="critical",
            impact_rules={"staging": {"level": "critical"}},
        )

        with patch.object(self.service, "send_page_individual") as mock_page:
            self.service.notify_execution_event(
                execution, action, "on_failure",
                page_me=True, page_me_user_id="user1", page_me_user_name="User One",
            )
            mock_page.assert_not_called()  # env != prod

    def test_page_in_prod_critical(self) -> None:
        """Page envoyé si env == prod ET level == critical."""
        execution = self._make_execution(env="prod")
        action = self._make_action(
            notification_config={"channels": [], "page_individual_enabled": True},
            impact_level="critical",
            impact_rules={"prod": {"level": "critical"}},
        )

        with patch.object(self.service, "send_page_individual") as mock_page:
            self.service.notify_execution_event(
                execution, action, "on_failure",
                page_me=True, page_me_user_id="user1", page_me_user_name="User One",
            )
            mock_page.assert_called_once()

    def test_page_me_false_no_page_individual(self) -> None:
        """page_me=False → send_page_individual non appelé."""
        execution = self._make_execution(env="prod")
        action = self._make_action(
            notification_config={"channels": [], "page_individual_enabled": True},
            impact_level="critical",
            impact_rules={"prod": {"level": "critical"}},
        )

        with patch.object(self.service, "send_page_individual") as mock_page:
            self.service.notify_execution_event(
                execution, action, "on_failure",
                page_me=False,
            )
            mock_page.assert_not_called()

    def test_page_dba_in_prod_critical(self) -> None:
        """Page DBA envoyé si env == prod, level == critical, conditions match."""
        config = {
            "channels": [
                {"type": "page_dba", "enabled": True, "conditions": ["on_failure"],
                 "api_url": "http://page-api/dba"},
            ],
            "page_individual_enabled": False,
        }
        execution = self._make_execution(env="prod")
        action = self._make_action(
            notification_config=config,
            impact_level="critical",
            impact_rules={"prod": {"level": "critical"}},
        )

        with patch.object(self.service, "send_page_dba") as mock_dba:
            self.service.notify_execution_event(execution, action, "on_failure")
            mock_dba.assert_called_once()

    def test_page_dba_not_in_staging(self) -> None:
        """Page DBA NON envoyé si env != prod."""
        config = {
            "channels": [
                {"type": "page_dba", "enabled": True, "conditions": ["on_failure"],
                 "api_url": "http://page-api/dba"},
            ],
        }
        execution = self._make_execution(env="staging")
        action = self._make_action(
            notification_config=config,
            impact_level="critical",
            impact_rules={"staging": {"level": "critical"}},
        )

        with patch.object(self.service, "send_page_dba") as mock_dba:
            self.service.notify_execution_event(execution, action, "on_failure")
            mock_dba.assert_not_called()

    def test_teams_webhook_called(self) -> None:
        """Teams webhook appelé si conditions correspondent."""
        config = {
            "channels": [
                {"type": "teams", "enabled": True, "conditions": ["on_failure"],
                 "webhook_url_ref": "http://webhook.teams/hook"},
            ],
        }
        execution = self._make_execution()
        action = self._make_action(notification_config=config)

        with patch.object(self.service, "send_teams") as mock_teams:
            self.service.notify_execution_event(execution, action, "on_failure")
            mock_teams.assert_called_once()

    def test_teams_vault_ref_skipped(self) -> None:
        """Teams avec vault: ref est ignoré (hors scope v1)."""
        config = {
            "channels": [
                {"type": "teams", "enabled": True, "conditions": ["on_failure"],
                 "webhook_url_ref": "vault:secret/teams/webhook"},
            ],
        }
        execution = self._make_execution()
        action = self._make_action(notification_config=config)

        with patch.object(self.service, "send_teams") as mock_teams:
            self.service.notify_execution_event(execution, action, "on_failure")
            mock_teams.assert_not_called()

    def test_disabled_channel_skipped(self) -> None:
        """Un canal avec enabled=False ne doit pas être traité."""
        config = {
            "channels": [
                {"type": "email", "enabled": False, "conditions": ["on_failure"], "recipient": "requester"},
            ],
        }
        execution = self._make_execution()
        action = self._make_action(notification_config=config)

        with patch.object(self.service, "send_email") as mock_email:
            self.service.notify_execution_event(execution, action, "on_failure")
            mock_email.assert_not_called()

    def test_always_condition_sends(self) -> None:
        """Un canal avec condition 'always' envoie pour on_success et on_failure."""
        config = {
            "channels": [
                {"type": "email", "enabled": True, "conditions": ["always"], "recipient": "requester"},
            ],
        }
        execution = self._make_execution()
        action = self._make_action(notification_config=config)

        with patch.object(self.service, "send_email") as mock_email:
            self.service.notify_execution_event(execution, action, "on_success")
            mock_email.assert_called_once()

    def test_no_notification_config_noop(self) -> None:
        """Si notification_config est None, aucune notification n'est envoyée."""
        execution = self._make_execution()
        action = self._make_action(notification_config=None)

        with patch.object(self.service, "send_email") as mock_email:
            self.service.notify_execution_event(execution, action, "on_failure")
            mock_email.assert_not_called()

    def test_email_requester_uses_user_email(self) -> None:
        """recipient='requester' utilise execution.user.email."""
        config = {
            "channels": [
                {"type": "email", "enabled": True, "conditions": ["on_failure"], "recipient": "requester"},
            ],
        }
        execution = self._make_execution()
        execution.user.email = "requester@example.com"
        action = self._make_action(notification_config=config)

        with patch.object(self.service, "send_email") as mock_email:
            self.service.notify_execution_event(execution, action, "on_failure")
            mock_email.assert_called_once()
            assert mock_email.call_args.kwargs["recipient_email"] == "requester@example.com"


class TestNotify:
    """Tests pour la méthode dispatch notify()."""

    def setup_method(self) -> None:
        self.service = NotificationService()

    @patch("services.notification_service.send_mail")
    def test_notify_dispatches_email(self, mock_send_mail: MagicMock) -> None:
        """notify('email', ...) dispatche vers send_email."""
        self.service.notify("email", recipient_email="a@b.com", subject="S", body="B")
        mock_send_mail.assert_called_once()

    def test_notify_unknown_type(self) -> None:
        """notify avec type inconnu ne lève pas d'exception."""
        self.service.notify("unknown_type")


class TestServiceFactory:
    """Test que get_service_client('notification') fonctionne."""

    def test_notification_service_creation(self) -> None:
        """get_service_client('notification') retourne NotificationService."""
        from services import get_service_client
        svc = get_service_client("notification")
        assert isinstance(svc, NotificationService)
