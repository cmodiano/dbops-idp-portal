"""
Service LDAP pour l'authentification des comptes de service via Active Directory.

Story 49.1 — Backend: Service LDAP (bind, fetch groups) et configuration.
Utilisé par la story 49.2 (ServiceLoginView) via import direct.
"""
from __future__ import annotations

import structlog
from django.conf import settings
from ldap3 import Connection, Server  # type: ignore[import-untyped]
from ldap3.core.exceptions import LDAPBindError, LDAPException  # type: ignore[import-untyped]
from ldap3.utils.conv import escape_filter_chars  # type: ignore[import-untyped]

logger = structlog.get_logger(__name__)


class LDAPUnavailableError(Exception):
    """Levée quand le serveur LDAP est inaccessible ou non configuré."""


class LDAPService:
    """Service d'authentification LDAP pour comptes de service AD."""

    def authenticate(
        self, username: str, password: str
    ) -> tuple[bool, list[str], str | None]:
        """
        Valide les credentials d'un compte de service contre l'Active Directory via LDAP bind,
        puis récupère ses groupes AD (memberOf) et son displayName.

        Returns:
            (True, ad_groups, display_name) si le bind réussit.
            (False, [], None) si les credentials sont invalides (LDAPBindError).

        Raises:
            LDAPUnavailableError: si LDAP_URI n'est pas configuré ou si le serveur est inaccessible.

        Note:
            Le mot de passe n'est jamais inclus dans les logs (AC6).
        """
        ldap_uri = settings.LDAP_URI
        base_dn = settings.LDAP_BASE_DN
        dn_template = settings.LDAP_USER_DN_TEMPLATE

        if not ldap_uri:
            logger.error("ldap_uri_not_configured")
            raise LDAPUnavailableError("LDAP_URI non configuré")

        if not base_dn:
            logger.error("ldap_base_dn_not_configured")
            raise LDAPUnavailableError("LDAP_BASE_DN non configuré")

        try:
            user_dn = dn_template.format(username=username)
        except KeyError as exc:
            logger.error("ldap_dn_template_error", error=str(exc))
            raise LDAPUnavailableError(f"Template DN mal configuré : {exc}") from exc
        log = logger.bind(ldap_username=username, ldap_uri=ldap_uri)

        try:
            server = Server(ldap_uri, get_info=None)
            conn = Connection(server, user=user_dn, password=password, auto_bind=True)
        except LDAPBindError:
            log.warning("ldap_bind_failed")
            return False, [], None
        except LDAPException as exc:
            log.error("ldap_unavailable", error=str(exc))
            raise LDAPUnavailableError(f"LDAP indisponible : {exc}") from exc

        try:
            conn.search(
                search_base=base_dn,
                search_filter=f"(sAMAccountName={escape_filter_chars(username)})",
                attributes=["memberOf", "displayName"],
            )
            ad_groups: list[str] = []
            display_name: str | None = None
            if conn.entries:
                entry = conn.entries[0]
                raw_groups = entry["memberOf"].values if "memberOf" in entry else []
                ad_groups = [str(g) for g in raw_groups]
                display_name = (
                    str(entry["displayName"].value)
                    if "displayName" in entry and entry["displayName"].value
                    else None
                )
            log.info("ldap_authenticate_success", groups_count=len(ad_groups))
            return True, ad_groups, display_name
        except LDAPException as exc:
            log.error("ldap_search_failed", error=str(exc))
            raise LDAPUnavailableError(f"Recherche LDAP échouée : {exc}") from exc
        finally:
            conn.unbind()
