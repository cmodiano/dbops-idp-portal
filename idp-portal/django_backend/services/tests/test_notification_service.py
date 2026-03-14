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

    @patch("services.notification_service.settings")
    @patch("services.notification_service.EmailMessage")
    def test_send_email_ok(self, mock_email_class: MagicMock, mock_settings: MagicMock) -> None:
        """send_email appelle EmailMessage avec les bons arguments."""
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@idp.test"
        mock_instance = mock_email_class.return_value
        mock_instance.send.return_value = None
        self.service.send_email("test@example.com", "Sujet", "Corps")
        mock_email_class.assert_called_once_with(
            subject="Sujet",
            body="Corps",
            from_email="noreply@idp.test",
            to=["test@example.com"],
            cc=[],
        )
        mock_instance.send.assert_called_once()

    @patch("services.notification_service.EmailMessage")
    def test_send_email_failure_non_blocking(self, mock_email_class: MagicMock) -> None:
        """Une exception dans send_email ne doit pas se propager."""
        mock_instance = mock_email_class.return_value
        mock_instance.send.side_effect = Exception("SMTP error")
        # Ne lève pas d'exception
        self.service.send_email("test@example.com", "Sujet", "Corps")

    @patch("services.notification_service.settings")
    @patch("services.notification_service.EmailMessage")
    def test_send_email_with_cc(self, mock_email_class: MagicMock, mock_settings: MagicMock) -> None:
        """AC4 (story 79.2) : send_email avec cc → EmailMessage appelé avec cc=[...] correctement parsé."""
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@idp.test"
        mock_instance = mock_email_class.return_value
        mock_instance.send.return_value = None
        self.service.send_email(
            recipient_email="dba@company.com",
            subject="Patch Oracle terminé",
            body="L'exécution s'est terminée avec succès.",
            cc="admin@company.com,team@company.com",
        )
        mock_email_class.assert_called_once_with(
            subject="Patch Oracle terminé",
            body="L'exécution s'est terminée avec succès.",
            from_email="noreply@idp.test",
            to=["dba@company.com"],
            cc=["admin@company.com", "team@company.com"],
        )
        mock_instance.send.assert_called_once()

    @patch("services.notification_service.settings")
    @patch("services.notification_service.EmailMessage")
    def test_send_email_with_cc_spaces_trimmed(self, mock_email_class: MagicMock, mock_settings: MagicMock) -> None:
        """CC avec espaces autour des adresses → parsé et trimmé correctement."""
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@idp.test"
        mock_instance = mock_email_class.return_value
        mock_instance.send.return_value = None
        self.service.send_email(
            recipient_email="dba@company.com",
            subject="Test",
            body="Body",
            cc=" admin@company.com , team@company.com ",
        )
        _, kwargs = mock_email_class.call_args
        assert kwargs["cc"] == ["admin@company.com", "team@company.com"]

    @patch("services.notification_service.settings")
    @patch("services.notification_service.EmailMessage")
    def test_send_email_without_cc_unchanged(self, mock_email_class: MagicMock, mock_settings: MagicMock) -> None:
        """AC4 (story 79.2) : send_email sans cc → comportement inchangé (rétrocompatibilité)."""
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@idp.test"
        mock_instance = mock_email_class.return_value
        mock_instance.send.return_value = None
        self.service.send_email(
            recipient_email="dba@company.com",
            subject="Sujet",
            body="Corps",
        )
        _, kwargs = mock_email_class.call_args
        assert kwargs["to"] == ["dba@company.com"]
        assert kwargs["cc"] == []
        mock_instance.send.assert_called_once()

    @patch("services.notification_service.settings")
    @patch("services.notification_service.EmailMessage")
    def test_send_email_with_cc_none_treated_as_no_cc(self, mock_email_class: MagicMock, mock_settings: MagicMock) -> None:
        """cc=None explicite → cc_list=[] (équivalent à pas de cc)."""
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@idp.test"
        mock_instance = mock_email_class.return_value
        mock_instance.send.return_value = None
        self.service.send_email("dba@company.com", "Sujet", "Corps", cc=None)
        _, kwargs = mock_email_class.call_args
        assert kwargs["cc"] == []

    @patch("services.notification_service.settings")
    @patch("services.notification_service.EmailMessage")
    def test_send_email_with_cc_empty_string_treated_as_no_cc(self, mock_email_class: MagicMock, mock_settings: MagicMock) -> None:
        """cc='' (chaîne vide) → cc_list=[] (comportement identique à None)."""
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@idp.test"
        mock_instance = mock_email_class.return_value
        mock_instance.send.return_value = None
        self.service.send_email("dba@company.com", "Sujet", "Corps", cc="")
        _, kwargs = mock_email_class.call_args
        assert kwargs["cc"] == []

    @patch("services.notification_service.settings")
    @patch("services.notification_service.EmailMessage")
    def test_send_email_with_cc_single_address(self, mock_email_class: MagicMock, mock_settings: MagicMock) -> None:
        """cc avec une seule adresse (sans virgule) → liste d'un élément."""
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@idp.test"
        mock_instance = mock_email_class.return_value
        mock_instance.send.return_value = None
        self.service.send_email("dba@company.com", "Sujet", "Corps", cc="admin@company.com")
        _, kwargs = mock_email_class.call_args
        assert kwargs["cc"] == ["admin@company.com"]

    @patch("services.notification_service.settings")
    @patch("services.notification_service.EmailMessage")
    def test_send_email_with_cc_whitespace_only_treated_as_no_cc(self, mock_email_class: MagicMock, mock_settings: MagicMock) -> None:
        """cc=' ' (espaces seuls) → cc_list=[] (cas limite : truthy mais vide après strip)."""
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@idp.test"
        mock_instance = mock_email_class.return_value
        mock_instance.send.return_value = None
        self.service.send_email("dba@company.com", "Sujet", "Corps", cc="   ")
        _, kwargs = mock_email_class.call_args
        assert kwargs["cc"] == []

    @patch("services.notification_service.settings")
    @patch("services.notification_service.EmailMessage")
    def test_send_email_with_cc_only_separators_treated_as_no_cc(self, mock_email_class: MagicMock, mock_settings: MagicMock) -> None:
        """cc=',,' (séparateurs seuls) → cc_list=[] (filtre les segments vides après strip)."""
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@idp.test"
        mock_instance = mock_email_class.return_value
        mock_instance.send.return_value = None
        self.service.send_email("dba@company.com", "Sujet", "Corps", cc=",,")
        _, kwargs = mock_email_class.call_args
        assert kwargs["cc"] == []


class TestSendEmailAttachments:
    """Tests pour send_email() avec pièces jointes (Story 79.3 AC1, AC4, AC6)."""

    def setup_method(self) -> None:
        self.service = NotificationService()

    @patch("services.notification_service.settings")
    @patch("services.notification_service.os")
    @patch("services.notification_service.EmailMessage")
    def test_send_email_with_attachment(
        self, mock_email_class: MagicMock, mock_os: MagicMock, mock_settings: MagicMock
    ) -> None:
        """AC6 : send_email avec chemin valide → attach_file appelé avec le bon chemin."""
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@idp.test"
        mock_settings.EMAIL_ATTACHMENT_MAX_SIZE_BYTES = 10 * 1024 * 1024
        mock_os.path.exists.return_value = True
        mock_os.path.getsize.return_value = 1024  # 1 KB
        mock_instance = mock_email_class.return_value
        mock_instance.send.return_value = None

        self.service.send_email(
            recipient_email="user@company.com",
            subject="Rapport",
            body="Voici le rapport.",
            attachments="/data/report.txt",
        )

        mock_email_class.assert_called_once_with(
            subject="Rapport",
            body="Voici le rapport.",
            from_email="noreply@idp.test",
            to=["user@company.com"],
            cc=[],
        )
        mock_instance.attach_file.assert_called_once_with("/data/report.txt")
        mock_instance.send.assert_called_once()

    @patch("services.notification_service.settings")
    @patch("services.notification_service.os")
    @patch("services.notification_service.EmailMessage")
    def test_send_email_with_multiple_attachments(
        self, mock_email_class: MagicMock, mock_os: MagicMock, mock_settings: MagicMock
    ) -> None:
        """AC6 : send_email avec deux chemins → attach_file appelé deux fois."""
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@idp.test"
        mock_settings.EMAIL_ATTACHMENT_MAX_SIZE_BYTES = 10 * 1024 * 1024
        mock_os.path.exists.return_value = True
        mock_os.path.getsize.return_value = 512
        mock_instance = mock_email_class.return_value
        mock_instance.send.return_value = None

        self.service.send_email(
            recipient_email="user@company.com",
            subject="Rapports",
            body="Deux pièces jointes.",
            attachments=["/data/report1.txt", "/data/report2.pdf"],
        )

        assert mock_instance.attach_file.call_count == 2
        mock_instance.attach_file.assert_any_call("/data/report1.txt")
        mock_instance.attach_file.assert_any_call("/data/report2.pdf")
        mock_instance.send.assert_called_once()

    @patch("services.notification_service.settings")
    @patch("services.notification_service.os")
    @patch("services.notification_service.EmailMessage")
    def test_send_email_attachment_too_large_skipped(
        self, mock_email_class: MagicMock, mock_os: MagicMock, mock_settings: MagicMock
    ) -> None:
        """AC4 : fichier dépassant la limite → skip + log warning, email envoyé quand même."""
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@idp.test"
        mock_settings.EMAIL_ATTACHMENT_MAX_SIZE_BYTES = 1024
        mock_os.path.exists.return_value = True
        mock_os.path.getsize.return_value = 2048  # Dépasse 1024 bytes
        mock_instance = mock_email_class.return_value
        mock_instance.send.return_value = None

        with patch("services.notification_service.logger") as mock_logger:
            self.service.send_email(
                recipient_email="user@company.com",
                subject="Rapport",
                body="Corps.",
                attachments="/data/big_file.pdf",
            )
            mock_logger.warning.assert_any_call(
                "attachment_size_exceeded",
                path="/data/big_file.pdf",
                size_bytes=2048,
                max_bytes=1024,
                correlation_id=None,
            )

        mock_instance.attach_file.assert_not_called()  # Attachement skippé
        mock_instance.send.assert_called_once()          # Email envoyé quand même

    @patch("services.notification_service.settings")
    @patch("services.notification_service.os")
    @patch("services.notification_service.EmailMessage")
    def test_send_email_attachment_not_found_skipped(
        self, mock_email_class: MagicMock, mock_os: MagicMock, mock_settings: MagicMock
    ) -> None:
        """AC4/AC6 : fichier inexistant → skip + log warning, email envoyé quand même."""
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@idp.test"
        mock_settings.EMAIL_ATTACHMENT_MAX_SIZE_BYTES = 10 * 1024 * 1024
        mock_os.path.exists.return_value = False
        mock_instance = mock_email_class.return_value
        mock_instance.send.return_value = None

        with patch("services.notification_service.logger") as mock_logger:
            self.service.send_email(
                recipient_email="user@company.com",
                subject="Rapport",
                body="Corps.",
                attachments="/data/nonexistent.txt",
            )
            mock_logger.warning.assert_any_call(
                "attachment_not_found",
                path="/data/nonexistent.txt",
                correlation_id=None,
            )

        mock_instance.attach_file.assert_not_called()
        mock_instance.send.assert_called_once()

    @patch("services.notification_service.settings")
    @patch("services.notification_service.os")
    @patch("services.notification_service.EmailMessage")
    def test_send_email_with_attachment_logs_has_attachments_true(
        self, mock_email_class: MagicMock, mock_os: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Task 1.7 : log notification_sent contient has_attachments=True si pièce jointe valide."""
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@idp.test"
        mock_settings.EMAIL_ATTACHMENT_MAX_SIZE_BYTES = 10 * 1024 * 1024
        mock_os.path.exists.return_value = True
        mock_os.path.getsize.return_value = 512
        mock_instance = mock_email_class.return_value
        mock_instance.send.return_value = None

        with patch("services.notification_service.logger") as mock_logger:
            self.service.send_email(
                recipient_email="user@company.com",
                subject="Rapport",
                body="Corps.",
                attachments="/data/report.txt",
            )
            mock_logger.info.assert_called_once_with(
                "notification_sent",
                destination_type="email",
                recipient_domain="company.com",
                has_cc=False,
                has_attachments=True,
                correlation_id=None,
            )

    @patch("services.notification_service.settings")
    @patch("services.notification_service.EmailMessage")
    def test_send_email_without_attachments_logs_has_attachments_false(
        self, mock_email_class: MagicMock, mock_settings: MagicMock
    ) -> None:
        """Task 1.7 : log notification_sent contient has_attachments=False sans pièce jointe."""
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@idp.test"
        mock_instance = mock_email_class.return_value
        mock_instance.send.return_value = None

        with patch("services.notification_service.logger") as mock_logger:
            self.service.send_email(
                recipient_email="user@company.com",
                subject="Sujet",
                body="Corps.",
            )
            mock_logger.info.assert_called_once_with(
                "notification_sent",
                destination_type="email",
                recipient_domain="company.com",
                has_cc=False,
                has_attachments=False,
                correlation_id=None,
            )

    @patch("services.notification_service.settings")
    @patch("services.notification_service.EmailMessage")
    def test_send_email_without_attachments_unchanged(
        self, mock_email_class: MagicMock, mock_settings: MagicMock
    ) -> None:
        """AC1 : appel sans attachments → comportement inchangé (rétrocompatibilité totale)."""
        mock_settings.DEFAULT_FROM_EMAIL = "noreply@idp.test"
        mock_instance = mock_email_class.return_value
        mock_instance.send.return_value = None

        self.service.send_email(
            recipient_email="user@company.com",
            subject="Sujet",
            body="Corps.",
        )

        mock_email_class.assert_called_once_with(
            subject="Sujet",
            body="Corps.",
            from_email="noreply@idp.test",
            to=["user@company.com"],
            cc=[],
        )
        mock_instance.attach_file.assert_not_called()
        mock_instance.send.assert_called_once()


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

    @patch("services.notification_service.httpx.post")
    def test_send_teams_different_webhooks_per_step(self, mock_post: MagicMock) -> None:
        """AC4 : deux send_teams avec webhooks distincts → httpx.post appelé sur les bonnes URLs."""
        mock_response = MagicMock(status_code=200)
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        # Step 1 — channel ops
        self.service.send_teams(
            webhook_url="https://teams.example.com/webhook/ops",
            message="Déploiement terminé",
            title="Ops Alert",
        )
        # Step 2 — channel sécurité
        self.service.send_teams(
            webhook_url="https://teams.example.com/webhook/security",
            message="Audit de sécurité complété",
            title="Sec Alert",
        )

        assert mock_post.call_count == 2
        call_urls = [call.args[0] for call in mock_post.call_args_list]
        assert "https://teams.example.com/webhook/ops" in call_urls
        assert "https://teams.example.com/webhook/security" in call_urls


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
        """PAGE_ONCALL_API_URL utilisé quand api_url non fourni."""
        mock_response = MagicMock(status_code=200)
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        with patch("services.notification_service.settings") as mock_settings:
            mock_settings.PAGE_ONCALL_API_URL = "http://page-oncall-api/alert"
            self.service.send_page_oncall(
                api_url="",
                message="Alert", action_name="Test", execution_id=42, level="critical",
            )

        mock_post.assert_called_once()
        call_url = mock_post.call_args.args[0]
        assert call_url == "http://page-oncall-api/alert"

    @patch("services.notification_service.httpx.post")
    def test_send_page_oncall_not_configured(self, mock_post: MagicMock) -> None:
        """Aucun URL configuré → pas d'appel httpx."""
        with patch("services.notification_service.settings") as mock_settings:
            mock_settings.PAGE_ONCALL_API_URL = ""
            self.service.send_page_oncall(
                api_url="",
                message="Alert", action_name="Test", execution_id=42, level="critical",
            )
        mock_post.assert_not_called()

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

    def test_on_approval_required_params_list_does_not_raise(self) -> None:
        """Robustness: get_parameters() returning a list must not raise."""
        config = {
            "channels": [
                {"type": "email", "enabled": True, "conditions": ["on_approval_required"], "recipient": "dba@corp.com"},
            ],
        }
        execution = self._make_approval_execution(params={}, targets=[])
        execution.get_parameters.return_value = ["item1", "item2"]
        action = self._make_action(notification_config=config)

        with patch.object(self.service, "send_email") as mock_send:
            self.service.notify_execution_event(execution, action, "on_approval_required")
            mock_send.assert_called_once()
            body = mock_send.call_args.kwargs["body"]
            assert "approbation requise" in body.lower() or "approbation" in body.lower()

    def test_on_approval_required_params_string_does_not_raise(self) -> None:
        """Robustness: get_parameters() returning a string must not raise."""
        config = {
            "channels": [
                {"type": "email", "enabled": True, "conditions": ["on_approval_required"], "recipient": "dba@corp.com"},
            ],
        }
        execution = self._make_approval_execution(params={}, targets=[])
        execution.get_parameters.return_value = "raw_string"
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

    @patch("services.notification_service.EmailMessage")
    def test_notify_dispatches_email(self, mock_email_class: MagicMock) -> None:
        """notify('email', ...) dispatche vers send_email."""
        mock_instance = mock_email_class.return_value
        mock_instance.send.return_value = None
        self.service.notify("email", recipient_email="a@b.com", subject="S", body="B")
        mock_instance.send.assert_called_once()

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


class TestServiceFactory:
    """Test que get_service_client('notification') fonctionne."""

    def test_notification_service_creation(self) -> None:
        """get_service_client('notification') retourne NotificationService."""
        from services import get_service_client
        svc = get_service_client("notification")
        assert isinstance(svc, NotificationService)
