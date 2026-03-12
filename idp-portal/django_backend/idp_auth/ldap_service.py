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

        Deux modes de connexion :
        - Avec compte de bind (LDAP_BIND_DN + LDAP_BIND_PASSWORD) : bind technique → recherche
          utilisateur → re-bind avec DN trouvé pour vérifier le mot de passe.
        - Sans compte de bind : bind direct avec DN construit via LDAP_USER_DN_TEMPLATE.

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
        bind_dn = getattr(settings, "LDAP_BIND_DN", "") or ""
        bind_password = getattr(settings, "LDAP_BIND_PASSWORD", "") or ""
        dn_template = settings.LDAP_USER_DN_TEMPLATE
        connect_timeout = settings.LDAP_CONNECT_TIMEOUT
        receive_timeout = settings.LDAP_RECEIVE_TIMEOUT

        if not ldap_uri:
            logger.error("ldap_uri_not_configured")
            raise LDAPUnavailableError("LDAP_URI non configuré")

        if not base_dn:
            logger.error("ldap_base_dn_not_configured")
            raise LDAPUnavailableError("LDAP_BASE_DN non configuré")

        use_bind_account = bool(bind_dn and bind_password)
        log = logger.bind(ldap_username=username, ldap_uri=ldap_uri)

        if use_bind_account:
            return self._authenticate_with_bind_account(
                username=username,
                password=password,
                ldap_uri=ldap_uri,
                base_dn=base_dn,
                bind_dn=bind_dn,
                bind_password=bind_password,
                connect_timeout=connect_timeout,
                receive_timeout=receive_timeout,
                log=log,
            )
        return self._authenticate_direct_bind(
            username=username,
            password=password,
            ldap_uri=ldap_uri,
            base_dn=base_dn,
            dn_template=dn_template,
            connect_timeout=connect_timeout,
            receive_timeout=receive_timeout,
            log=log,
        )

    def _authenticate_with_bind_account(
        self,
        username: str,
        password: str,
        ldap_uri: str,
        base_dn: str,
        bind_dn: str,
        bind_password: str,
        connect_timeout: int,
        receive_timeout: int,
        log: structlog.BoundLogger,
    ) -> tuple[bool, list[str], str | None]:
        """Connexion via compte de bind technique : recherche utilisateur puis re-bind pour vérifier le mot de passe."""
        server = Server(ldap_uri, get_info=None, connect_timeout=connect_timeout)
        conn = None
        try:
            conn = Connection(
                server,
                user=bind_dn,
                password=bind_password,
                auto_bind=True,
                receive_timeout=receive_timeout,
                raise_exceptions=True,
            )
        except LDAPBindError:
            log.warning("ldap_bind_account_failed")
            raise LDAPUnavailableError("Échec du bind avec le compte technique LDAP") from None
        except LDAPException as exc:
            log.error("ldap_unavailable", error=str(exc))
            raise LDAPUnavailableError(f"LDAP indisponible : {exc}") from exc

        try:
            search_ok = conn.search(
                search_base=base_dn,
                search_filter=f"(sAMAccountName={escape_filter_chars(username)})",
                attributes=["memberOf", "displayName"],
            )
            if not search_ok or not conn.entries:
                log.warning(
                    "ldap_search_no_results",
                    search_ok=search_ok,
                    entries_count=len(conn.entries) if conn.entries else 0,
                )
                return False, [], None
            entry = conn.entries[0]
            user_dn = entry.entry_dn
        except LDAPException as exc:
            log.error("ldap_search_failed", error=str(exc))
            raise LDAPUnavailableError(f"Recherche LDAP échouée : {exc}") from exc
        finally:
            if conn:
                conn.unbind()

        # Re-bind avec le DN de l'utilisateur pour vérifier le mot de passe
        try:
            conn = Connection(
                server,
                user=user_dn,
                password=password,
                auto_bind=True,
                receive_timeout=receive_timeout,
                raise_exceptions=True,
            )
        except LDAPBindError:
            log.warning("ldap_bind_failed")
            return False, [], None
        except LDAPException as exc:
            log.error("ldap_unavailable", error=str(exc))
            raise LDAPUnavailableError(f"LDAP indisponible : {exc}") from exc

        try:
            raw_groups = entry["memberOf"].values if "memberOf" in entry else []
            ad_groups = [str(g) for g in raw_groups]
            display_name = (
                str(entry["displayName"].value)
                if "displayName" in entry and entry["displayName"].value
                else None
            )
            log.info("ldap_authenticate_success", groups_count=len(ad_groups))
            return True, ad_groups, display_name
        finally:
            conn.unbind()

    def _authenticate_direct_bind(
        self,
        username: str,
        password: str,
        ldap_uri: str,
        base_dn: str,
        dn_template: str,
        connect_timeout: int,
        receive_timeout: int,
        log: structlog.BoundLogger,
    ) -> tuple[bool, list[str], str | None]:
        """Connexion directe avec les credentials utilisateur (DN construit via template)."""
        try:
            user_dn = dn_template.format(username=username)
        except (KeyError, ValueError) as exc:
            logger.error("ldap_dn_template_error", error=str(exc))
            raise LDAPUnavailableError(f"Template DN mal configuré : {exc}") from exc

        try:
            server = Server(ldap_uri, get_info=None, connect_timeout=connect_timeout)
            conn = Connection(
                server,
                user=user_dn,
                password=password,
                auto_bind=True,
                receive_timeout=receive_timeout,
                raise_exceptions=True,
            )
        except LDAPBindError:
            log.warning("ldap_bind_failed")
            return False, [], None
        except LDAPException as exc:
            log.error("ldap_unavailable", error=str(exc))
            raise LDAPUnavailableError(f"LDAP indisponible : {exc}") from exc

        try:
            search_ok = conn.search(
                search_base=base_dn,
                search_filter=f"(sAMAccountName={escape_filter_chars(username)})",
                attributes=["memberOf", "displayName"],
            )
            if not search_ok or not conn.entries:
                log.warning(
                    "ldap_search_no_results",
                    search_ok=search_ok,
                    entries_count=len(conn.entries) if conn.entries else 0,
                )
                return False, [], None
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
