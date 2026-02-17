"""
Tests for health check endpoint.
Story M.8 - Task 10: Tests for extended health check.
"""

from unittest.mock import patch, MagicMock

from django.test import TestCase, Client, override_settings


class TestHealthCheckEndpoint(TestCase):
    """Tests for GET /api/v1/health endpoint."""

    def setUp(self):
        self.client = Client()
        self.url = '/api/v1/health/'

    @patch('core.views.connection')
    def test_health_check_all_services_up(self, mock_connection):
        """Test health check returns 200 when all services are healthy."""
        # Mock successful database connection
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = MagicMock(return_value=False)

        response = self.client.get(self.url)

        assert response.status_code == 200
        data = response.json()['data']
        assert data['status'] == 'healthy'
        assert data['oracle'] == 'connected'
        assert 'timestamp' in data

    @patch('core.views.connection')
    def test_health_check_oracle_down(self, mock_connection):
        """Test health check returns 503 when Oracle is disconnected."""
        # Mock database connection failure
        mock_connection.cursor.side_effect = Exception("ORA-12541: TNS:no listener")

        response = self.client.get(self.url)

        assert response.status_code == 503
        data = response.json()['data']
        assert data['status'] == 'degraded'
        assert data['oracle'] == 'disconnected'

    @patch('core.views.requests')
    @patch('core.views.connection')
    @override_settings(VAULT_ADDR='http://vault.example.com:8200')
    def test_health_check_vault_unreachable(self, mock_connection, mock_requests):
        """Test health check returns 503 when Vault is unreachable."""
        # Mock successful database connection
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Mock Vault failure
        mock_requests.get.side_effect = Exception("Connection refused")

        response = self.client.get(self.url)

        assert response.status_code == 503
        data = response.json()['data']
        assert data['status'] == 'degraded'
        assert data['oracle'] == 'connected'
        assert data['vault'] == 'unreachable'

    @patch('core.views.requests')
    @patch('core.views.connection')
    @override_settings(SERVICENOW_INSTANCE_URL='https://servicenow.example.com')
    def test_health_check_servicenow_unreachable(self, mock_connection, mock_requests):
        """Test health check returns 503 when ServiceNow is unreachable."""
        # Mock successful database connection
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Mock ServiceNow failure
        mock_requests.get.side_effect = Exception("Connection refused")

        response = self.client.get(self.url)

        assert response.status_code == 503
        data = response.json()['data']
        assert data['status'] == 'degraded'
        assert data['servicenow'] == 'unreachable'

    @patch('core.views.connection')
    def test_health_check_response_format(self, mock_connection):
        """Test health check response has correct format."""
        # Mock successful database connection
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = MagicMock(return_value=False)

        response = self.client.get(self.url)

        data = response.json()

        # Check envelope format
        assert 'data' in data
        health_data = data['data']

        # Check required fields
        assert 'status' in health_data
        assert 'timestamp' in health_data
        assert 'oracle' in health_data
        assert 'vault' in health_data
        assert 'servicenow' in health_data

        # Check status is one of valid values
        assert health_data['status'] in ('healthy', 'degraded')

        # Check timestamp is ISO8601 format with Z suffix
        assert health_data['timestamp'].endswith('Z')

    @patch('core.views.requests')
    @patch('core.views.connection')
    @override_settings(
        VAULT_ADDR='http://vault.example.com:8200',
        SERVICENOW_INSTANCE_URL='https://real-instance.service-now.com'
    )
    def test_health_check_all_external_services_reachable(self, mock_connection, mock_requests):
        """Test health check returns healthy when all external services respond."""
        # Mock successful database connection
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Mock successful external service calls
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_requests.get.return_value = mock_response

        response = self.client.get(self.url)

        assert response.status_code == 200
        data = response.json()['data']
        assert data['status'] == 'healthy'
        assert data['vault'] == 'reachable'
        assert data['servicenow'] == 'reachable'

    @patch('core.views.requests')
    @patch('core.views.connection')
    @override_settings(SERVICENOW_INSTANCE_URL='https://real-instance.service-now.com')
    def test_health_check_servicenow_401_is_reachable(self, mock_connection, mock_requests):
        """Test that ServiceNow returning 401 counts as reachable."""
        # Mock successful database connection
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Mock ServiceNow returning 401 (auth required but reachable)
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_requests.get.return_value = mock_response

        response = self.client.get(self.url)

        assert response.status_code == 200
        data = response.json()['data']
        assert data['servicenow'] == 'reachable'

    @patch('core.views.logger')
    @patch('core.views.connection')
    def test_health_check_logs_failures(self, mock_connection, mock_logger):
        """Test that health check failures are logged."""
        # Mock database connection failure
        mock_connection.cursor.side_effect = Exception("ORA-12541: TNS:no listener")

        self.client.get(self.url)

        # Check that error was logged
        assert mock_logger.error.called
        error_call = mock_logger.error.call_args
        assert error_call[0][0] == 'health_check_failed'
        assert error_call[1]['service'] == 'oracle'

    @patch('core.views.connection')
    def test_health_check_no_auth_required(self, mock_connection):
        """Test that health check does not require authentication."""
        # Mock successful database connection
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = MagicMock(return_value=False)

        response = self.client.get(self.url)

        # Should not return 401/403
        assert response.status_code in (200, 503)

    @patch('core.views.connection')
    def test_health_check_default_vault_config_marked_reachable(self, mock_connection):
        """Test that default localhost Vault config is marked reachable (not tested)."""
        # Mock successful database connection
        mock_cursor = MagicMock()
        mock_connection.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Default VAULT_ADDR is localhost - should not be tested
        response = self.client.get(self.url)

        data = response.json()['data']
        # Should be marked reachable without actually testing
        assert data['vault'] == 'reachable'
