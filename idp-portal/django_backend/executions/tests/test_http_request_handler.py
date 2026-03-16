"""
Tests unitaires pour HttpRequestHandler (story 57.5 — ADR-007 §4c).

Couvre :
- AC#1 : GET HTTP → dict retourné
- AC#2 : hôte non dans ALLOWED_HTTP_REQUEST_HOSTS → ValueError
- AC#3 : IP privée bloquée / autorisée via allowlist
- AC#4 : HTTP en production (DEBUG=False) → ValueError
- AC#5 : erreur HTTP 4xx propagée
- AC#6 : POST avec resolved_params comme body JSON

Note : Pas de @pytest.mark.django_db — httpx et settings sont mockés.
"""

import pytest
from unittest.mock import patch, MagicMock

import httpx

from executions.step_handlers.http_request_handler import HttpRequestHandler, _is_private_ip_literal


class TestIsPrivateIpLiteral:
    """Tests unitaires de _is_private_ip_literal."""

    def test_private_10_x(self):
        assert _is_private_ip_literal('10.0.0.1') is True

    def test_private_172_16(self):
        assert _is_private_ip_literal('172.16.0.1') is True

    def test_private_192_168(self):
        assert _is_private_ip_literal('192.168.1.1') is True

    def test_private_127(self):
        assert _is_private_ip_literal('127.0.0.1') is True

    def test_link_local(self):
        assert _is_private_ip_literal('169.254.0.1') is True

    def test_public_ip(self):
        assert _is_private_ip_literal('8.8.8.8') is False

    def test_hostname_not_ip(self):
        assert _is_private_ip_literal('inventory.corp') is False

    def test_public_ip_8_8_4_4(self):
        assert _is_private_ip_literal('8.8.4.4') is False


class TestHttpRequestHandler:
    """Tests de HttpRequestHandler.execute() (story 57.5)."""

    def setup_method(self):
        self.handler = HttpRequestHandler()

    def _make_execution(self, exec_id=1):
        m = MagicMock()
        m.id = exec_id
        return m

    def _make_step_config(self, url='https://api.corp/data', method='GET',
                          headers=None, params=None, timeout=30):
        return {
            'step_type': 'http_request',
            'step_id': 'fetch-data',
            'name': 'Fetch Data',
            'config': {
                'url': url,
                'method': method,
                'headers': headers or {},
                'params': params or {},
                'timeout': timeout,
            },
        }

    @patch('executions.app.handlers.http_request_handler.settings')
    @patch('executions.app.handlers.http_request_handler.httpx.Client')
    def test_get_success_returns_json_dict(self, mock_client_class, mock_settings):
        """AC#1 : GET HTTP → dict retourné."""
        mock_settings.DEBUG = True
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = []

        mock_resp = MagicMock()
        mock_resp.json.return_value = {'databases': ['db1', 'db2']}
        mock_resp.raise_for_status.return_value = None
        mock_client_class.return_value.__enter__.return_value.get.return_value = mock_resp

        step_config = self._make_step_config()
        result = self.handler.execute(
            step_config=step_config,
            resolved_params={},
            execution=self._make_execution(),
            step=step_config,
            correlation_id='corr-123',
        )

        assert result == {'databases': ['db1', 'db2']}

    @patch('executions.app.handlers.http_request_handler.settings')
    @patch('executions.app.handlers.http_request_handler.httpx.Client')
    def test_post_uses_resolved_params_as_body(self, mock_client_class, mock_settings):
        """AC#6 : POST → resolved_params comme body JSON."""
        mock_settings.DEBUG = True
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = ['api.corp']

        mock_resp = MagicMock()
        mock_resp.json.return_value = {'created': True}
        mock_resp.raise_for_status.return_value = None
        mock_client = mock_client_class.return_value.__enter__.return_value
        mock_client.post.return_value = mock_resp

        step_config = self._make_step_config(url='https://api.corp/create', method='POST')
        resolved_params = {'name': 'test', 'env': 'production'}

        self.handler.execute(
            step_config=step_config,
            resolved_params=resolved_params,
            execution=self._make_execution(),
            step=step_config,
            correlation_id=None,
        )

        mock_client.post.assert_called_once_with(
            'https://api.corp/create',
            headers={},
            json=resolved_params,
        )

    @patch('executions.app.handlers.http_request_handler.settings')
    def test_host_not_in_allowlist_raises_value_error(self, mock_settings):
        """AC#2 : hôte non dans ALLOWED_HTTP_REQUEST_HOSTS → ValueError."""
        mock_settings.DEBUG = True
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = ['allowed.corp']

        step_config = self._make_step_config(url='https://evil.attacker.com/data')
        with pytest.raises(ValueError, match="not in ALLOWED_HTTP_REQUEST_HOSTS"):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )

    @patch('executions.app.handlers.http_request_handler.settings')
    def test_private_ip_blocked_by_default(self, mock_settings):
        """AC#3 : IP privée → ValueError si pas dans allowlist."""
        mock_settings.DEBUG = True
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = []

        step_config = self._make_step_config(url='http://192.168.1.100/api')
        with pytest.raises(ValueError, match="private IP"):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )

    @patch('executions.app.handlers.http_request_handler.settings')
    @patch('executions.app.handlers.http_request_handler.httpx.Client')
    def test_private_ip_allowed_via_allowlist(self, mock_client_class, mock_settings):
        """AC#3 : IP privée dans allowlist → autorisée."""
        mock_settings.DEBUG = True
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = ['192.168.1.100']

        mock_resp = MagicMock()
        mock_resp.json.return_value = {'status': 'ok'}
        mock_resp.raise_for_status.return_value = None
        mock_client_class.return_value.__enter__.return_value.get.return_value = mock_resp

        step_config = self._make_step_config(url='http://192.168.1.100/api')
        result = self.handler.execute(
            step_config=step_config,
            resolved_params={},
            execution=self._make_execution(),
            step=step_config,
            correlation_id=None,
        )
        assert result == {'status': 'ok'}

    @patch('executions.app.handlers.http_request_handler.settings')
    def test_http_rejected_in_production(self, mock_settings):
        """AC#4 : HTTP en production (DEBUG=False) → ValueError."""
        mock_settings.DEBUG = False
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = []

        step_config = self._make_step_config(url='http://api.corp/data')
        with pytest.raises(ValueError, match="HTTPS required in production"):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )

    @patch('executions.app.handlers.http_request_handler.settings')
    @patch('executions.app.handlers.http_request_handler.httpx.Client')
    def test_http_status_error_propagates(self, mock_client_class, mock_settings):
        """AC#5 : erreur HTTP 4xx propagée → _execute_handler_step marque step FAILED."""
        mock_settings.DEBUG = True
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = []

        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=MagicMock()
        )
        mock_client_class.return_value.__enter__.return_value.get.return_value = mock_resp

        step_config = self._make_step_config()
        with pytest.raises(httpx.HTTPStatusError):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )

    @patch('executions.app.handlers.http_request_handler.settings')
    def test_missing_url_raises_value_error(self, mock_settings):
        """URL manquante dans config → ValueError."""
        mock_settings.DEBUG = True
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = []

        step_config = {'step_type': 'http_request', 'config': {}}
        with pytest.raises(ValueError, match="requires 'config.url'"):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )

    @patch('executions.app.handlers.http_request_handler.settings')
    @patch('executions.app.handlers.http_request_handler.httpx.Client')
    def test_non_dict_response_normalized(self, mock_client_class, mock_settings):
        """Réponse non-dict normalisée en {'result': value}."""
        mock_settings.DEBUG = True
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = []

        mock_resp = MagicMock()
        mock_resp.json.return_value = ['item1', 'item2']
        mock_resp.raise_for_status.return_value = None
        mock_client_class.return_value.__enter__.return_value.get.return_value = mock_resp

        step_config = self._make_step_config()
        result = self.handler.execute(
            step_config=step_config,
            resolved_params={},
            execution=self._make_execution(),
            step=step_config,
            correlation_id=None,
        )

        assert result == {'result': ['item1', 'item2']}

    @patch('executions.app.handlers.http_request_handler.settings')
    @patch('executions.app.handlers.http_request_handler.httpx.Client')
    def test_network_error_propagates(self, mock_client_class, mock_settings):
        """Erreur réseau (RequestError) propagée."""
        mock_settings.DEBUG = True
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = []

        mock_client = mock_client_class.return_value.__enter__.return_value
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        step_config = self._make_step_config()
        with pytest.raises(httpx.RequestError):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )

    @patch('executions.app.handlers.http_request_handler.settings')
    @patch('executions.app.handlers.http_request_handler.httpx.Client')
    def test_https_allowed_in_production(self, mock_client_class, mock_settings):
        """AC#4 : HTTPS en production (DEBUG=False) → autorisé."""
        mock_settings.DEBUG = False
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = []

        mock_resp = MagicMock()
        mock_resp.json.return_value = {'ok': True}
        mock_resp.raise_for_status.return_value = None
        mock_client_class.return_value.__enter__.return_value.get.return_value = mock_resp

        step_config = self._make_step_config(url='https://api.corp/data')
        result = self.handler.execute(
            step_config=step_config,
            resolved_params={},
            execution=self._make_execution(),
            step=step_config,
            correlation_id=None,
        )

        assert result == {'ok': True}

    @patch('executions.app.handlers.http_request_handler.settings')
    def test_invalid_url_no_hostname(self, mock_settings):
        """URL sans hostname → ValueError."""
        mock_settings.DEBUG = True
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = []

        step_config = self._make_step_config(url='not-a-url')
        with pytest.raises(ValueError, match="Invalid URL"):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )

    @patch('executions.app.handlers.http_request_handler.settings')
    @patch('executions.app.handlers.http_request_handler.httpx.Client')
    def test_put_uses_resolved_params_as_body(self, mock_client_class, mock_settings):
        """PUT → resolved_params comme body JSON."""
        mock_settings.DEBUG = True
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = ['api.corp']

        mock_resp = MagicMock()
        mock_resp.json.return_value = {'updated': True}
        mock_resp.raise_for_status.return_value = None
        mock_client = mock_client_class.return_value.__enter__.return_value
        mock_client.put.return_value = mock_resp

        step_config = self._make_step_config(url='https://api.corp/resource/1', method='PUT')
        resolved_params = {'name': 'updated-name'}

        self.handler.execute(
            step_config=step_config,
            resolved_params=resolved_params,
            execution=self._make_execution(),
            step=step_config,
            correlation_id=None,
        )

        mock_client.put.assert_called_once_with(
            'https://api.corp/resource/1',
            headers={},
            json=resolved_params,
        )

    @patch('executions.app.handlers.http_request_handler.settings')
    @patch('executions.app.handlers.http_request_handler.httpx.Client')
    def test_patch_uses_resolved_params_as_body(self, mock_client_class, mock_settings):
        """PATCH → resolved_params comme body JSON."""
        mock_settings.DEBUG = True
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = ['api.corp']

        mock_resp = MagicMock()
        mock_resp.json.return_value = {'patched': True}
        mock_resp.raise_for_status.return_value = None
        mock_client = mock_client_class.return_value.__enter__.return_value
        mock_client.patch.return_value = mock_resp

        step_config = self._make_step_config(url='https://api.corp/resource/1', method='PATCH')
        resolved_params = {'status': 'active'}

        self.handler.execute(
            step_config=step_config,
            resolved_params=resolved_params,
            execution=self._make_execution(),
            step=step_config,
            correlation_id=None,
        )

        mock_client.patch.assert_called_once_with(
            'https://api.corp/resource/1',
            headers={},
            json=resolved_params,
        )

    @patch('executions.app.handlers.http_request_handler.settings')
    @patch('executions.app.handlers.http_request_handler.httpx.Client')
    def test_delete_success(self, mock_client_class, mock_settings):
        """DELETE → requête exécutée sans body."""
        mock_settings.DEBUG = True
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = ['api.corp']

        mock_resp = MagicMock()
        mock_resp.json.return_value = {'deleted': True}
        mock_resp.raise_for_status.return_value = None
        mock_client = mock_client_class.return_value.__enter__.return_value
        mock_client.delete.return_value = mock_resp

        step_config = self._make_step_config(url='https://api.corp/resource/1', method='DELETE')

        result = self.handler.execute(
            step_config=step_config,
            resolved_params={},
            execution=self._make_execution(),
            step=step_config,
            correlation_id=None,
        )

        mock_client.delete.assert_called_once_with(
            'https://api.corp/resource/1',
            headers={},
        )
        assert result == {'deleted': True}

    @patch('executions.app.handlers.http_request_handler.settings')
    @patch('executions.app.handlers.http_request_handler.httpx.Client')
    def test_non_json_text_response_returns_body_dict(self, mock_client_class, mock_settings):
        """Réponse texte non-JSON → {'body': text, 'status_code': code}."""
        mock_settings.DEBUG = True
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = []

        mock_resp = MagicMock()
        mock_resp.json.side_effect = ValueError("No JSON")
        mock_resp.text = "OK"
        mock_resp.status_code = 200
        mock_resp.raise_for_status.return_value = None
        mock_client_class.return_value.__enter__.return_value.get.return_value = mock_resp

        step_config = self._make_step_config()
        result = self.handler.execute(
            step_config=step_config,
            resolved_params={},
            execution=self._make_execution(),
            step=step_config,
            correlation_id=None,
        )

        assert result == {'body': 'OK', 'status_code': 200}

    @patch('executions.app.handlers.http_request_handler.settings')
    @patch('executions.app.handlers.http_request_handler.httpx.Client')
    def test_post_empty_resolved_params_falls_back_to_config_params(
        self, mock_client_class, mock_settings
    ):
        """POST avec resolved_params={} → fallback sur config.params comme body.

        Comportement documenté : resolved_params or params → si resolved_params est vide
        (aucun input_mapping), les params de la config sont utilisés comme body.
        """
        mock_settings.DEBUG = True
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = ['api.corp']

        mock_resp = MagicMock()
        mock_resp.json.return_value = {'queued': True}
        mock_resp.raise_for_status.return_value = None
        mock_client = mock_client_class.return_value.__enter__.return_value
        mock_client.post.return_value = mock_resp

        step_config = self._make_step_config(
            url='https://api.corp/action', method='POST', params={'action': 'restart'}
        )

        self.handler.execute(
            step_config=step_config,
            resolved_params={},  # vide → fallback sur config.params
            execution=self._make_execution(),
            step=step_config,
            correlation_id=None,
        )

        mock_client.post.assert_called_once_with(
            'https://api.corp/action',
            headers={},
            json={'action': 'restart'},
        )

    @patch('executions.app.handlers.http_request_handler.settings')
    def test_ipv6_loopback_blocked_by_default(self, mock_settings):
        """AC#3 : IPv6 loopback (::1) → ValueError si pas dans allowlist."""
        mock_settings.DEBUG = True
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = []

        step_config = self._make_step_config(url='http://[::1]/api')
        with pytest.raises(ValueError, match="private IP"):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )

    @patch('executions.app.handlers.http_request_handler.settings')
    def test_unsupported_http_method_raises(self, mock_settings):
        """Méthode HTTP non supportée (ex. HEAD) → ValueError."""
        mock_settings.DEBUG = True
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = ['api.corp']

        step_config = self._make_step_config(url='https://api.corp/data', method='HEAD')
        with pytest.raises(ValueError, match="Unsupported HTTP method"):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )

    @patch('executions.app.handlers.http_request_handler.settings')
    def test_allowlist_blocks_non_matching_host(self, mock_settings):
        """Allowlist configurée : hôte non listé → rejeté (même si allowlist a 'API.CORP')."""
        mock_settings.DEBUG = True
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = ['API.CORP']

        step_config = self._make_step_config(url='https://evil.attacker.com/data')
        with pytest.raises(ValueError, match="not in ALLOWED_HTTP_REQUEST_HOSTS"):
            self.handler.execute(
                step_config=step_config,
                resolved_params={},
                execution=self._make_execution(),
                step=step_config,
                correlation_id=None,
            )

    @patch('executions.app.handlers.http_request_handler.settings')
    @patch('executions.app.handlers.http_request_handler.httpx.Client')
    def test_allowlist_case_insensitive_positive(self, mock_client_class, mock_settings):
        """Allowlist insensible à la casse : 'API.CORP' dans allowlist → match 'api.corp' dans URL."""
        mock_settings.DEBUG = True
        mock_settings.ALLOWED_HTTP_REQUEST_HOSTS = ['API.CORP']

        mock_resp = MagicMock()
        mock_resp.json.return_value = {'ok': True}
        mock_resp.raise_for_status.return_value = None
        mock_client_class.return_value.__enter__.return_value.get.return_value = mock_resp

        step_config = self._make_step_config(url='https://api.corp/data')
        result = self.handler.execute(
            step_config=step_config,
            resolved_params={},
            execution=self._make_execution(),
            step=step_config,
            correlation_id=None,
        )
        assert result == {'ok': True}
