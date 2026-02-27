"""
Tests unitaires pour LDAPService (Story 49.1).

Couvre :
- AC1 : bind réussi → (True, groups, display_name)
- AC2 : credentials invalides (LDAPBindError) → (False, [], None)
- AC3 : récupération des groupes memberOf
- AC5 : LDAP indisponible → LDAPUnavailableError
- AC4/AC8 : LDAP_URI manquante → LDAPUnavailableError
- AC6 : mot de passe absent des logs
"""
from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest
from django.test import TestCase, override_settings
from ldap3.core.exceptions import LDAPBindError, LDAPException

from idp_auth.ldap_service import LDAPService, LDAPUnavailableError


LDAP_SETTINGS = dict(
    LDAP_URI="ldap://dc.example.com:389",
    LDAP_BASE_DN="DC=example,DC=com",
    LDAP_USER_DN_TEMPLATE="{username}@example.com",
)


def _make_entry(groups: list[str], display_name: str | None) -> MagicMock:
    """Construit un mock d'entrée LDAP avec memberOf et displayName."""
    entry = MagicMock()
    entry.__contains__ = lambda self, key: key in ("memberOf", "displayName")

    member_of_attr = MagicMock()
    member_of_attr.values = groups
    entry.__getitem__ = lambda self, key: (
        member_of_attr if key == "memberOf" else _make_dn_attr(display_name)
    )
    return entry


def _make_dn_attr(value: str | None) -> MagicMock:
    attr = MagicMock()
    attr.value = value
    return attr


@override_settings(**LDAP_SETTINGS)
class TestLDAPServiceAuthenticate(TestCase):
    """Tests de la méthode LDAPService.authenticate()."""

    def setUp(self) -> None:
        self.service = LDAPService()

    # ------------------------------------------------------------------
    # AC1 + AC3 — Bind réussi, récupération des groupes et displayName
    # ------------------------------------------------------------------

    @patch("idp_auth.ldap_service.Connection")
    @patch("idp_auth.ldap_service.Server")
    def test_authenticate_success_returns_true_with_groups(
        self, mock_server_cls: MagicMock, mock_conn_cls: MagicMock
    ) -> None:
        """AC1+AC3 : bind réussi retourne (True, groups, display_name)."""
        groups = [
            "CN=GRP-IDP-DBOPS,OU=Groups,DC=example,DC=com",
            "CN=GRP-IDP-READERS,OU=Groups,DC=example,DC=com",
        ]
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn
        mock_conn.search.return_value = True
        mock_conn.entries = [_make_entry(groups, "John Doe")]

        success, ad_groups, display_name = self.service.authenticate("svc-ci", "secret")

        assert success is True
        assert ad_groups == groups
        assert display_name == "John Doe"
        mock_conn.unbind.assert_called_once()

    @patch("idp_auth.ldap_service.Connection")
    @patch("idp_auth.ldap_service.Server")
    def test_authenticate_success_no_entries(
        self, mock_server_cls: MagicMock, mock_conn_cls: MagicMock
    ) -> None:
        """Bind réussi mais aucune entrée LDAP → False (silent failure évité)."""
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn
        mock_conn.search.return_value = True
        mock_conn.entries = []

        success, ad_groups, display_name = self.service.authenticate("svc-ci", "secret")

        assert success is False
        assert ad_groups == []
        assert display_name is None

    # ------------------------------------------------------------------
    # AC2 — Credentials invalides
    # ------------------------------------------------------------------

    @patch("idp_auth.ldap_service.Connection")
    @patch("idp_auth.ldap_service.Server")
    def test_authenticate_invalid_credentials_returns_false(
        self, mock_server_cls: MagicMock, mock_conn_cls: MagicMock
    ) -> None:
        """AC2 : LDAPBindError → (False, [], None)."""
        mock_conn_cls.side_effect = LDAPBindError("Invalid credentials")

        success, ad_groups, display_name = self.service.authenticate("svc-ci", "wrong")

        assert success is False
        assert ad_groups == []
        assert display_name is None

    # ------------------------------------------------------------------
    # AC5 — LDAP indisponible (erreur réseau)
    # ------------------------------------------------------------------

    @patch("idp_auth.ldap_service.Connection")
    @patch("idp_auth.ldap_service.Server")
    def test_authenticate_ldap_network_error_raises_unavailable(
        self, mock_server_cls: MagicMock, mock_conn_cls: MagicMock
    ) -> None:
        """AC5 : LDAPException réseau → LDAPUnavailableError."""
        mock_conn_cls.side_effect = LDAPException("Connection refused")

        with pytest.raises(LDAPUnavailableError):
            self.service.authenticate("svc-ci", "secret")

    @patch("idp_auth.ldap_service.Connection")
    @patch("idp_auth.ldap_service.Server")
    def test_authenticate_ldap_search_error_raises_unavailable(
        self, mock_server_cls: MagicMock, mock_conn_cls: MagicMock
    ) -> None:
        """AC5 : LDAPException lors du search → LDAPUnavailableError."""
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn
        mock_conn.search.side_effect = LDAPException("Search timeout")

        with pytest.raises(LDAPUnavailableError):
            self.service.authenticate("svc-ci", "secret")

        mock_conn.unbind.assert_called_once()

    # ------------------------------------------------------------------
    # AC4 / AC8 — LDAP_URI manquante → LDAPUnavailableError
    # ------------------------------------------------------------------

    @override_settings(LDAP_URI="")
    def test_authenticate_missing_ldap_uri_raises_unavailable(self) -> None:
        """AC4 : LDAP_URI vide → LDAPUnavailableError avec message clair."""
        with pytest.raises(LDAPUnavailableError, match="LDAP_URI non configuré"):
            self.service.authenticate("svc-ci", "secret")

    @override_settings(LDAP_BASE_DN="")
    def test_authenticate_missing_ldap_base_dn_raises_unavailable(self) -> None:
        """AC4 : LDAP_BASE_DN vide → LDAPUnavailableError avec message clair."""
        with pytest.raises(LDAPUnavailableError, match="LDAP_BASE_DN non configuré"):
            self.service.authenticate("svc-ci", "secret")

    @override_settings(LDAP_USER_DN_TEMPLATE="{user}@example.com")
    def test_authenticate_malformed_dn_template_raises_unavailable(self) -> None:
        """Template DN mal configuré (placeholder incorrect) → LDAPUnavailableError."""
        with pytest.raises(LDAPUnavailableError, match="Template DN mal configuré"):
            self.service.authenticate("svc-ci", "secret")

    # ------------------------------------------------------------------
    # Vérification du DN template
    # ------------------------------------------------------------------

    @override_settings(LDAP_USER_DN_TEMPLATE="CN={username},OU=SA,DC=example,DC=com")
    @patch("idp_auth.ldap_service.Connection")
    @patch("idp_auth.ldap_service.Server")
    def test_dn_template_full_dn_format(
        self, mock_server_cls: MagicMock, mock_conn_cls: MagicMock
    ) -> None:
        """Le template DN complet (format CN=...) est correctement résolu."""
        mock_conn = MagicMock()
        mock_conn_cls.return_value = mock_conn
        mock_conn.search.return_value = True
        mock_conn.entries = []

        self.service.authenticate("svc-ci", "secret")

        call_kwargs = mock_conn_cls.call_args
        assert call_kwargs is not None
        # Le user DN doit être le DN complet résolu
        assert "svc-ci" in call_kwargs.kwargs.get("user", "") or (
            len(call_kwargs.args) > 1 and "svc-ci" in str(call_kwargs.args[1])
        )


# ============================================================================
# AC6 — Tests mot de passe absent des logs (fonctions pytest standalone)
# Les fixtures pytest (caplog) ne s'injectent pas dans unittest.TestCase + @patch.
# ============================================================================


@pytest.mark.django_db
@override_settings(**LDAP_SETTINGS)
@patch("idp_auth.ldap_service.Connection")
@patch("idp_auth.ldap_service.Server")
def test_password_not_logged_on_success(
    mock_server_cls: MagicMock, mock_conn_cls: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """AC6 : le mot de passe ne figure jamais dans les logs (cas succès)."""
    caplog.set_level(logging.INFO, logger="idp_auth.ldap_service")
    mock_conn = MagicMock()
    mock_conn_cls.return_value = mock_conn
    mock_conn.search.return_value = True
    mock_conn.entries = [_make_entry([], "Test User")]

    LDAPService().authenticate("svc-ci", "super_secret_password")

    for record in caplog.records:
        assert "super_secret_password" not in record.getMessage()


@pytest.mark.django_db
@override_settings(**LDAP_SETTINGS)
@patch("idp_auth.ldap_service.Connection")
@patch("idp_auth.ldap_service.Server")
def test_password_not_logged_on_bind_error(
    mock_server_cls: MagicMock, mock_conn_cls: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """AC6 : le mot de passe ne figure jamais dans les logs (cas bind raté)."""
    caplog.set_level(logging.INFO, logger="idp_auth.ldap_service")
    mock_conn_cls.side_effect = LDAPBindError("Invalid credentials")

    LDAPService().authenticate("svc-ci", "super_secret_password")

    for record in caplog.records:
        assert "super_secret_password" not in record.getMessage()


@pytest.mark.django_db
@override_settings(**LDAP_SETTINGS)
@patch("idp_auth.ldap_service.Connection")
@patch("idp_auth.ldap_service.Server")
def test_password_not_logged_on_ldap_error(
    mock_server_cls: MagicMock, mock_conn_cls: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """AC6 : le mot de passe ne figure jamais dans les logs (cas LDAP indisponible)."""
    caplog.set_level(logging.INFO, logger="idp_auth.ldap_service")
    mock_conn_cls.side_effect = LDAPException("Connection refused")

    with pytest.raises(LDAPUnavailableError):
        LDAPService().authenticate("svc-ci", "super_secret_password")

    for record in caplog.records:
        assert "super_secret_password" not in record.getMessage()
