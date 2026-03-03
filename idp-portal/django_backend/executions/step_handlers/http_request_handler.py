"""
HttpRequestHandler — implémentation story 57.5

Handler pour les steps de type http_request (ADR-007 §4c).
Validation SSRF : allowlist ALLOWED_HTTP_REQUEST_HOSTS + blocklist IPs privées.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

import httpx
import structlog
from django.conf import settings

from executions.models import Execution

logger = structlog.get_logger(__name__)

# Réseaux privés bloqués par défaut (SSRF protection — ADR-007 §Sécurité)
_PRIVATE_NETWORKS = (
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('127.0.0.0/8'),
    ipaddress.ip_network('169.254.0.0/16'),   # link-local
    ipaddress.ip_network('::1/128'),
    ipaddress.ip_network('fc00::/7'),
)


def _is_private_ip_literal(hostname: str) -> bool:
    """Returns True if hostname is an IP literal in a private range."""
    try:
        ip = ipaddress.ip_address(hostname)
        return any(ip in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        return False  # Not an IP literal — hostname, skip IP check


class HttpRequestHandler:
    """Handler pour les steps de type http_request (ADR-007 §4c).

    Exécute des appels HTTP bruts (inventaire, CMDB) avec validation SSRF :
    - Allowlist configurable via settings.ALLOWED_HTTP_REQUEST_HOSTS
    - Blocklist IPs privées par défaut
    - HTTPS obligatoire en production (DEBUG=False)
    """

    def execute(
        self,
        step_config: dict,
        resolved_params: dict,
        execution: Execution,
        step: dict,
        correlation_id: str | None,
    ) -> dict:
        config = step_config.get('config', {})
        url = config.get('url')
        if not url:
            raise ValueError("http_request step requires 'config.url'")

        method = config.get('method', 'GET').upper()
        headers = config.get('headers', {})
        params = config.get('params', {})
        timeout = config.get('timeout', 30)

        logger.info(
            "http_request_handler_start",
            url=url,
            method=method,
            execution_id=execution.id,
            correlation_id=correlation_id,
        )

        # Validation SSRF avant tout appel réseau
        try:
            self._validate_url(url)
        except ValueError:
            logger.warning(
                "http_request_handler_validation_blocked",
                url=url,
                method=method,
                execution_id=execution.id,
                correlation_id=correlation_id,
            )
            raise

        try:
            with httpx.Client(timeout=timeout) as client:
                if method == 'GET':
                    resp = client.get(url, headers=headers, params=params)
                elif method == 'POST':
                    resp = client.post(url, headers=headers, json=resolved_params or params)
                elif method == 'PUT':
                    resp = client.put(url, headers=headers, json=resolved_params or params)
                elif method == 'PATCH':
                    resp = client.patch(url, headers=headers, json=resolved_params or params)
                elif method == 'DELETE':
                    resp = client.delete(url, headers=headers)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method!r}")

                resp.raise_for_status()

                try:
                    result = resp.json()
                except (ValueError, UnicodeDecodeError):
                    result = {"body": resp.text, "status_code": resp.status_code}

        except (httpx.HTTPStatusError, httpx.RequestError):
            logger.error(
                "http_request_handler_error",
                url=url,
                method=method,
                execution_id=execution.id,
                correlation_id=correlation_id,
            )
            raise

        if not isinstance(result, dict):
            result = {"result": result}

        logger.info(
            "http_request_handler_success",
            url=url,
            method=method,
            execution_id=execution.id,
            correlation_id=correlation_id,
        )

        return result

    def _validate_url(self, url: str) -> None:
        """Validation SSRF de l'URL (ADR-007 §Sécurité).

        Raises:
            ValueError: si l'URL viole une règle SSRF.
        """
        parsed = urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            raise ValueError(f"Invalid URL: no hostname in {url!r}")

        # Règle 1 : HTTPS obligatoire en production
        if not settings.DEBUG and parsed.scheme != 'https':
            raise ValueError(
                f"HTTPS required in production (DEBUG=False). Got scheme: {parsed.scheme!r}"
            )

        # Règle 2 : Allowlist (si configurée)
        # urlparse().hostname retourne du lowercase ; normaliser l'allowlist également
        allowed_hosts: list[str] = getattr(settings, 'ALLOWED_HTTP_REQUEST_HOSTS', [])
        if allowed_hosts:
            if hostname not in [h.lower() for h in allowed_hosts]:
                raise ValueError(
                    f"Host {hostname!r} is not in ALLOWED_HTTP_REQUEST_HOSTS. "
                    f"Allowed: {allowed_hosts}"
                )
            # Hôte explicitement autorisé → bypass blocklist privée
            return

        # Règle 3 : Blocklist IPs privées (uniquement si pas d'allowlist configurée)
        if _is_private_ip_literal(hostname):
            raise ValueError(
                f"Requests to private IP ranges are not allowed: {hostname!r}. "
                "Add to settings.ALLOWED_HTTP_REQUEST_HOSTS to explicitly allow."
            )
