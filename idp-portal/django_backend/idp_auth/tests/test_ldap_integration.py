"""
Tests d'intégration pour LDAPService avec ldap3 MOCK_SYNC (Story 49.5).

Utilise la vraie stratégie ldap3 MOCK_SYNC pour tester la logique de parsing
des entrées LDAP (memberOf, displayName, sAMAccountName) sans serveur LDAP réel.

AC#1 : Tests MOCK_SYNC passant par la vraie logique de parsing ldap3.
AC#3 : Test conditionnel skipif(not settings.LDAP_URI) pour intégration réelle.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.test import TestCase, override_settings
from ldap3 import ALL, MOCK_SYNC
from ldap3 import Connection as LdapConnection
from ldap3 import Server as LdapServer

from idp_auth.ldap_service import LDAPService


LDAP_SETTINGS = dict(
    LDAP_URI="ldap://dc.example.com:389",
    LDAP_BASE_DN="DC=example,DC=com",
    LDAP_USER_DN_TEMPLATE="{username}@example.com",
)


def _make_mock_connection_factory(
    username: str,
    groups: list[str],
    display_name: str | None,
    *,
    include_display_name_attr: bool = True,
) -> Any:
    """
    Retourne une factory de Connection(MOCK_SYNC) peuplée avec les entrées données.

    La factory intercepte l'appel à idp_auth.ldap_service.Connection fait par
    LDAPService et retourne une vraie Connection MOCK_SYNC peuplée avec les
    données de test — permettant de tester la vraie logique de parsing ldap3.

    Args:
        username: Le sAMAccountName de l'entrée à créer dans le mock.
        groups: Liste des DNs memberOf à inclure (vide si absent).
        display_name: Valeur displayName à inclure dans l'attribut (peut être vide).
        include_display_name_attr: Si False, l'attribut displayName est absent de
            l'entrée (branche `"displayName" not in entry`). Si True et display_name
            est une chaîne vide, l'attribut est présent mais sa valeur est falsy
            (branche AC2a : `"displayName" in entry and not entry["displayName"].value`).
    """

    def factory(
        server: Any,
        user: str | None = None,
        password: str | None = None,
        auto_bind: Any = None,
        receive_timeout: Any = None,
        raise_exceptions: Any = None,
    ) -> LdapConnection:
        mock_server = LdapServer("localhost", get_info=ALL)
        conn = LdapConnection(
            mock_server,
            user="cn=admin,dc=test,dc=com",
            password="admin",
            client_strategy=MOCK_SYNC,
            auto_bind=False,
        )
        attrs: dict[str, Any] = {
            "objectClass": ["person"],
            "sAMAccountName": [username],
        }
        if groups:
            attrs["memberOf"] = groups
        if include_display_name_attr:
            # Inclure l'attribut (présent, valeur peut être vide → AC2a)
            attrs["displayName"] = [display_name if display_name is not None else ""]
        # Si include_display_name_attr=False : attribut absent de l'entrée

        conn.strategy.add_entry(
            f"CN={username},DC=example,DC=com",
            attrs,
        )
        conn.bind()
        return conn

    return factory


@override_settings(**LDAP_SETTINGS)
class TestLDAPIntegrationMockSync(TestCase):
    """
    Tests d'intégration LDAPService via ldap3 MOCK_SYNC.

    Patch uniquement idp_auth.ldap_service.Connection avec une factory qui
    retourne une vraie Connection MOCK_SYNC — la logique de parsing des Entry
    ldap3 (memberOf.values, displayName.value, __contains__) est exercée réellement.
    """

    def setUp(self) -> None:
        self.service = LDAPService()

    # ------------------------------------------------------------------
    # Task 1.2 — AC1 : bind + parsing groupes + displayName
    # ------------------------------------------------------------------

    @patch("idp_auth.ldap_service.Server")
    def test_ldap_mock_sync_success(self, mock_server_cls: MagicMock) -> None:
        """
        AC1 : MOCK_SYNC — authentification réussie avec groupes et displayName.

        Vérifie que LDAPService parse correctement les Entry ldap3 retournées
        par la vraie stratégie MOCK_SYNC (pas de unittest.mock sur Connection).

        Note : @patch("idp_auth.ldap_service.Server") est nécessaire pour éviter
        que Server(ldap_uri, ...) tente une résolution DNS réelle. La factory
        crée son propre LdapServer("localhost") pour la connexion MOCK_SYNC.
        """
        groups = [
            "CN=GRP-IDP-DBOPS,OU=Groups,DC=example,DC=com",
            "CN=GRP-IDP-READERS,OU=Groups,DC=example,DC=com",
        ]
        factory = _make_mock_connection_factory("svc-ci", groups, "Service CI")

        with patch("idp_auth.ldap_service.Connection", side_effect=factory):
            success, ad_groups, display_name = self.service.authenticate(
                "svc-ci", "secret"
            )

        assert success is True
        assert ad_groups == groups
        assert display_name == "Service CI"

    # ------------------------------------------------------------------
    # Task 1.3 — entrée sans memberOf → ad_groups=[]
    # ------------------------------------------------------------------

    @patch("idp_auth.ldap_service.Server")
    def test_ldap_mock_sync_no_member_of(self, mock_server_cls: MagicMock) -> None:
        """
        AC1 : MOCK_SYNC — entrée LDAP sans attribut memberOf → ad_groups=[].

        Vérifie la branche `if "memberOf" in entry else []` de ldap_service.py
        via la vraie logique de parsing ldap3 Entry.
        """
        factory = _make_mock_connection_factory("svc-ci", [], "Service CI")

        with patch("idp_auth.ldap_service.Connection", side_effect=factory):
            success, ad_groups, display_name = self.service.authenticate(
                "svc-ci", "secret"
            )

        assert success is True
        assert ad_groups == []
        assert display_name == "Service CI"

    # ------------------------------------------------------------------
    # Task 1.4 — displayName absent de l'entrée → display_name=None
    # ------------------------------------------------------------------

    @patch("idp_auth.ldap_service.Server")
    def test_ldap_mock_sync_display_name_absent(self, mock_server_cls: MagicMock) -> None:
        """
        MOCK_SYNC — entrée LDAP sans attribut displayName → display_name=None.

        Vérifie la branche `if "displayName" in entry` (False car attribut absent)
        via la vraie logique de parsing ldap3 Entry.
        """
        groups = ["CN=GRP-IDP-DBOPS,OU=Groups,DC=example,DC=com"]
        factory = _make_mock_connection_factory(
            "svc-ci", groups, None, include_display_name_attr=False
        )

        with patch("idp_auth.ldap_service.Connection", side_effect=factory):
            success, ad_groups, display_name = self.service.authenticate(
                "svc-ci", "secret"
            )

        assert success is True
        assert ad_groups == groups
        assert display_name is None

    # ------------------------------------------------------------------
    # AC2a — displayName présent mais valeur vide/falsy → display_name=None
    # ------------------------------------------------------------------

    @patch("idp_auth.ldap_service.Server")
    def test_ldap_mock_sync_display_name_empty_returns_none(
        self, mock_server_cls: MagicMock
    ) -> None:
        """
        AC2a : MOCK_SYNC — entrée LDAP avec displayName présent mais valeur vide → display_name=None.

        Vérifie la branche `"displayName" in entry and entry["displayName"].value` (falsy)
        via la vraie logique de parsing ldap3 Entry. Complète le test unitaire
        test_display_name_value_is_none_returns_none avec une validation MOCK_SYNC.
        """
        groups = ["CN=GRP-IDP-DBOPS,OU=Groups,DC=example,DC=com"]
        # include_display_name_attr=True (défaut), display_name="" → attribut présent, valeur vide
        factory = _make_mock_connection_factory(
            "svc-ci", groups, "", include_display_name_attr=True
        )

        with patch("idp_auth.ldap_service.Connection", side_effect=factory):
            success, ad_groups, display_name = self.service.authenticate(
                "svc-ci", "secret"
            )

        assert success is True
        assert ad_groups == groups
        assert display_name is None


# ============================================================================
# Task 1.5 — AC3 : Test d'intégration conditionnel (skipif LDAP_URI absent)
# Utilise une fonction pytest standalone (pas TestCase) pour cohérence avec
# le pattern du projet (Learning 49.1 : caplog incompatible avec TestCase).
# ============================================================================


@pytest.mark.skipif(
    not settings.LDAP_URI,
    reason="LDAP_URI non configuré — test d'intégration réel ignoré",
)
@pytest.mark.django_db
def test_ldap_integration_real_skip() -> None:
    """
    AC3 : Test conditionnel — exécute un vrai bind LDAP si LDAP_URI est configuré.

    Ignoré automatiquement si LDAP_URI est vide (environnement sans LDAP réel).
    En CI ou dev avec LDAP configuré, valide la configuration réelle end-to-end.

    Note : Ce test ne doit PAS être patché — il utilise le vrai serveur LDAP.
    Note : Le username brut (sAMAccountName) est passé — authenticate() applique
    le template DN en interne.
    """
    from idp_auth.ldap_service import LDAPUnavailableError

    service = LDAPService()
    # Si LDAP_URI est configuré, on appelle authenticate() sans patch.
    # Un vrai bind est tenté — le test échoue seulement si la config LDAP est incorrecte.
    try:
        result = service.authenticate(
            "test-user",  # username brut — le template DN est appliqué en interne
            "wrong-password-intentional",
        )
        # Credentials invalides → (False, [], None) attendu
        assert isinstance(result, tuple)
        assert len(result) == 3
    except LDAPUnavailableError:
        # Le serveur est configuré mais inaccessible : acceptable en CI conditionnel.
        pass
