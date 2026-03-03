"""
Story 31.8: Tests unitaires du NotificationService.
Valide l'envoi vers chaque type de destination (avec mocks).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


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


class TestSendPageOncall:
    """Tests pour send_page_oncall() — Epic 56 (ex-send_page_dba)."""

    def setup_method(self) -> None:
        self.service = NotificationService()

    @patch("services.notification_service.httpx.post")
    def test_send_page_oncall_ok(self, mock_post: MagicMock) -> None:
        """AC2 : send_page_oncall appelle l'API avec le bon payload."""
        mock_response = MagicMock(status_code=200)
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        self.service.send_page_oncall(
            api_url="http://page-api/oncall",
            message="Oncall Alert", action_name="Test", execution_id=42, level="critical",
        )
        mock_post.assert_called_once()
        call_url = mock_post.call_args.args[0]
        assert call_url == "http://page-api/oncall"
        payload = mock_post.call_args.kwargs["json"]
        assert payload["level"] == "critical"
        assert payload["execution_id"] == 42

    @patch("services.notification_service.httpx.post")
    def test_send_page_oncall_uses_page_oncall_url_setting(self, mock_post: MagicMock) -> None:
        """AC3 : PAGE_ONCALL_API_URL est prioritaire sur PAGE_DBA_API_URL."""
        mock_response = MagicMock(status_code=200)
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        with patch("services.notification_service.settings") as mock_settings:
            mock_settings.PAGE_ONCALL_API_URL = "http://page-oncall-api/alert"
            mock_settings.PAGE_DBA_API_URL = "http://page-dba-api/alert"
            self.service.send_page_oncall(
                api_url="",
                message="Alert", action_name="Test", execution_id=42, level="critical",
            )

        mock_post.assert_called_once()
        call_url = mock_post.call_args.args[0]
        assert call_url == "http://page-oncall-api/alert"

    @patch("services.notification_service.httpx.post")
    def test_send_page_oncall_falls_back_to_page_dba_url(self, mock_post: MagicMock) -> None:
        """AC4 : PAGE_DBA_API_URL utilisé si PAGE_ONCALL_API_URL est vide."""
        mock_response = MagicMock(status_code=200)
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        with patch("services.notification_service.settings") as mock_settings:
            mock_settings.PAGE_ONCALL_API_URL = ""
            mock_settings.PAGE_DBA_API_URL = "http://page-dba-api/alert"
            self.service.send_page_oncall(
                api_url="",
                message="Alert", action_name="Test", execution_id=42, level="critical",
            )

        mock_post.assert_called_once()
        call_url = mock_post.call_args.args[0]
        assert call_url == "http://page-dba-api/alert"

    @patch("services.notification_service.httpx.post")
    def test_send_page_oncall_not_configured(self, mock_post: MagicMock) -> None:
        """AC3/4 : Aucun URL configuré → pas d'appel httpx."""
        with patch("services.notification_service.settings") as mock_settings:
            mock_settings.PAGE_ONCALL_API_URL = ""
            mock_settings.PAGE_DBA_API_URL = ""
            self.service.send_page_oncall(
                api_url="",
                message="Alert", action_name="Test", execution_id=42, level="critical",
            )
        mock_post.assert_not_called()

    def test_send_page_dba_alias_works(self) -> None:
        """AC5 : send_page_dba() est un alias de send_page_oncall() — même fonction sous-jacente."""
        assert self.service.send_page_dba.__func__ is self.service.send_page_oncall.__func__

    @patch("services.notification_service.httpx.post")
    def test_send_page_oncall_failure_non_blocking(self, mock_post: MagicMock) -> None:
        """Une exception dans send_page_oncall ne doit pas se propager."""
        mock_post.side_effect = Exception("Connection error")
        # Ne lève pas d'exception
        self.service.send_page_oncall(
            api_url="http://page-api/oncall",
            message="Alert", action_name="Test", execution_id=42, level="critical",
        )


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
        """AC1 : Page DBA envoyé si env == prod, level == critical, conditions match."""
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

        with patch.object(self.service, "send_page_oncall") as mock_oncall:
            self.service.notify_execution_event(execution, action, "on_failure")
            mock_oncall.assert_called_once()

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

        with patch.object(self.service, "send_page_oncall") as mock_oncall:
            self.service.notify_execution_event(execution, action, "on_failure")
            mock_oncall.assert_not_called()

    def test_page_oncall_channel_type_dispatches(self) -> None:
        """AC2 : type page_oncall → send_page_oncall appelé."""
        config = {
            "channels": [
                {"type": "page_oncall", "enabled": True, "conditions": ["on_failure"],
                 "api_url": "http://oncall-api"},
            ],
            "page_individual_enabled": False,
        }
        execution = self._make_execution(env="prod")
        action = self._make_action(
            notification_config=config,
            impact_level="critical",
            impact_rules={"prod": {"level": "critical"}},
        )

        with patch.object(self.service, "send_page_oncall") as mock_oncall:
            self.service.notify_execution_event(execution, action, "on_failure")
        mock_oncall.assert_called_once()

    def test_page_dba_channel_type_still_dispatches(self) -> None:
        """AC1 : type page_dba → send_page_oncall appelé (alias rétrocompatible)."""
        config = {
            "channels": [
                {"type": "page_dba", "enabled": True, "conditions": ["on_failure"],
                 "api_url": "http://dba-api"},
            ],
            "page_individual_enabled": False,
        }
        execution = self._make_execution(env="prod")
        action = self._make_action(
            notification_config=config,
            impact_level="critical",
            impact_rules={"prod": {"level": "critical"}},
        )

        with patch.object(self.service, "send_page_oncall") as mock_oncall:
            self.service.notify_execution_event(execution, action, "on_failure")
        mock_oncall.assert_called_once()

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

    # ─── Story 58.2: on_approval_required enrichment ──────────────────────────

    def _make_approval_execution(self, params: dict | None = None, targets: list | None = None) -> MagicMock:
        """Exécution mock avec parameters et targets pour on_approval_required."""
        execution = self._make_execution(env="prod")
        execution.get_parameters.return_value = params or {}
        mock_targets = [MagicMock(target_name=t["target_name"], target_id=t["target_id"]) for t in (targets or [])]
        execution.targets.all.return_value = mock_targets
        return execution

    def test_on_approval_required_email_includes_parameters(self) -> None:
        """Story 58.2 AC6: email pour on_approval_required inclut les paramètres."""
        config = {
            "channels": [
                {"type": "email", "enabled": True, "conditions": ["on_approval_required"], "recipient": "dba@corp.com"},
            ],
        }
        execution = self._make_approval_execution(params={"pdb_name": "TESTDB"})
        action = self._make_action(notification_config=config)

        with patch.object(self.service, "send_email") as mock_send:
            self.service.notify_execution_event(execution, action, "on_approval_required")
            mock_send.assert_called_once()
            body = mock_send.call_args.kwargs["body"]
            assert "pdb_name=TESTDB" in body

    def test_on_approval_required_email_includes_targets(self) -> None:
        """Story 58.2 AC6: email pour on_approval_required inclut les targets."""
        config = {
            "channels": [
                {"type": "email", "enabled": True, "conditions": ["on_approval_required"], "recipient": "dba@corp.com"},
            ],
        }
        execution = self._make_approval_execution(
            params={},
            targets=[{"target_name": "oracle-prod-01", "target_id": "srv-01"}],
        )
        action = self._make_action(notification_config=config)

        with patch.object(self.service, "send_email") as mock_send:
            self.service.notify_execution_event(execution, action, "on_approval_required")
            body = mock_send.call_args.kwargs["body"]
            assert "oracle-prod-01" in body

    def test_on_approval_required_email_no_params_no_context(self) -> None:
        """Story 58.2 AC3/AC6: email sans paramètres ni targets — pas de crash."""
        config = {
            "channels": [
                {"type": "email", "enabled": True, "conditions": ["on_approval_required"], "recipient": "dba@corp.com"},
            ],
        }
        execution = self._make_approval_execution(params={}, targets=[])
        action = self._make_action(notification_config=config)

        with patch.object(self.service, "send_email") as mock_send:
            self.service.notify_execution_event(execution, action, "on_approval_required")
            mock_send.assert_called_once()
            body = mock_send.call_args.kwargs["body"]
            assert "approbation requise" in body.lower() or "approbation" in body.lower()

    def test_on_approval_required_teams_includes_parameters(self) -> None:
        """Story 58.2 AC6: Teams pour on_approval_required inclut les paramètres."""
        config = {
            "channels": [
                {"type": "teams", "enabled": True, "conditions": ["on_approval_required"],
                 "webhook_url_ref": "http://teams.webhook/hook"},
            ],
        }
        execution = self._make_approval_execution(params={"pdb_name": "TESTDB"})
        action = self._make_action(notification_config=config)

        with patch.object(self.service, "send_teams") as mock_teams:
            self.service.notify_execution_event(execution, action, "on_approval_required")
            mock_teams.assert_called_once()
            message = mock_teams.call_args.kwargs["message"]
            assert "pdb_name" in message or "TESTDB" in message

    def test_on_approval_required_teams_includes_targets(self) -> None:
        """Story 58.2 AC6: Teams pour on_approval_required inclut les targets."""
        config = {
            "channels": [
                {"type": "teams", "enabled": True, "conditions": ["on_approval_required"],
                 "webhook_url_ref": "http://teams.webhook/hook"},
            ],
        }
        execution = self._make_approval_execution(
            targets=[{"target_name": "oracle-prod-01", "target_id": "srv-01"}],
        )
        action = self._make_action(notification_config=config)

        with patch.object(self.service, "send_teams") as mock_teams:
            self.service.notify_execution_event(execution, action, "on_approval_required")
            message = mock_teams.call_args.kwargs["message"]
            assert "oracle-prod-01" in message

    def test_on_success_email_body_not_modified(self) -> None:
        """Story 58.2: le corps email pour on_success n'est PAS enrichi avec params/targets."""
        config = {
            "channels": [
                {"type": "email", "enabled": True, "conditions": ["on_success"], "recipient": "dba@corp.com"},
            ],
        }
        execution = self._make_approval_execution(params={"pdb_name": "TESTDB"})
        action = self._make_action(notification_config=config)

        with patch.object(self.service, "send_email") as mock_send:
            self.service.notify_execution_event(execution, action, "on_success")
            body = mock_send.call_args.kwargs["body"]
            # Body ne contient pas le format enrichi avec "approbation requise"
            assert "approbation requise" not in body.lower()


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

    @patch("services.notification_service.httpx.post")
    def test_notify_dispatches_page_oncall(self, mock_post: MagicMock) -> None:
        """notify('page_oncall', ...) dispatche vers send_page_oncall."""
        mock_response = MagicMock(status_code=200)
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        self.service.notify(
            "page_oncall",
            api_url="http://api/oncall", message="Alert", action_name="Test",
            execution_id=1, level="critical",
        )
        mock_post.assert_called_once()

    @patch("services.notification_service.httpx.post")
    def test_notify_dispatches_page_dba(self, mock_post: MagicMock) -> None:
        """notify('page_dba', ...) dispatche vers send_page_oncall (backward compat — Epic 56)."""
        mock_response = MagicMock(status_code=200)
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        self.service.notify(
            "page_dba",
            api_url="http://api/dba", message="Alert", action_name="Test",
            execution_id=1, level="critical",
        )
        mock_post.assert_called_once()


class TestServiceFactory:
    """Test que get_service_client('notification') fonctionne."""

    def test_notification_service_creation(self) -> None:
        """get_service_client('notification') retourne NotificationService."""
        from services import get_service_client
        svc = get_service_client("notification")
        assert isinstance(svc, NotificationService)
