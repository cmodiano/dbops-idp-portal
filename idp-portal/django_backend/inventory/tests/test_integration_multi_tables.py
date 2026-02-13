"""
Integration tests for multi-table inventory API.
Story 23.3 - AC8: Full HTTP → RBAC → InventoryService → JSON flow.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from inventory.services import InventoryServiceError


class InventoryMultiTableIntegrationTests(TestCase):
    """Integration tests: HTTP request → RBAC → service → JSON response. Task 9.2-9.7."""

    def setUp(self):
        self.client = APIClient()
        self.user = MagicMock()
        self.user.id = 42
        self.user.is_authenticated = True
        self.client.force_authenticate(user=self.user)

    @patch('inventory.views.get_correlation_id', return_value='int-test-001')
    @patch('inventory.views.get_user_ad_groups', return_value=['GRP-DBA'])
    @patch('inventory.views.InventoryService')
    def test_full_flow_servers(self, mock_service_cls, mock_ad_groups, mock_corr_id):
        """Task 9.2: Full flow - request → RBAC → list_servers → JSON."""
        mock_svc = mock_service_cls.return_value
        # RBAC: user has access to srv01 and srv02
        mock_svc.list_targets_for_user.return_value = (
            [
                {'name': 'srv01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
                {'name': 'srv02', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
            ],
            2,
            False,
        )
        mock_svc.list_servers.return_value = [
            {'id': 'srv01', 'name': 'srv01', 'environment': 'dev', 'engine_type': 'oracle'},
            {'id': 'srv02', 'name': 'srv02', 'environment': 'dev', 'engine_type': 'sqlserver'},
            {'id': 'srv03', 'name': 'srv03', 'environment': 'dev', 'engine_type': 'oracle'},
        ]

        response = self.client.get('/api/v1/inventory/servers/', {'environment': 'dev'})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        # RBAC filtered: only srv01, srv02 (not srv03)
        self.assertEqual(len(data['data']), 2)
        names = [s['name'] for s in data['data']]
        self.assertIn('srv01', names)
        self.assertIn('srv02', names)
        self.assertNotIn('srv03', names)

    @patch('inventory.views.get_correlation_id', return_value='int-test-002')
    @patch('inventory.views.get_user_ad_groups', return_value=['GRP-DBA'])
    @patch('inventory.views.InventoryService')
    def test_full_flow_instances_with_server_filter(self, mock_service_cls, mock_ad_groups, mock_corr_id):
        """Task 9.4: User with access to 2 servers loads instances."""
        mock_svc = mock_service_cls.return_value
        # RBAC allows srv01, srv02
        mock_svc.list_targets_for_user.return_value = (
            [
                {'name': 'srv01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
                {'name': 'srv02', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
            ],
            2,
            False,
        )
        mock_svc.list_instances.return_value = [
            {'id': 'INST01', 'name': 'INST01', 'environment': 'dev', 'server_ref': 'srv01', 'db_ref': 'DB01'},
            {'id': 'INST02', 'name': 'INST02', 'environment': 'dev', 'server_ref': 'srv01', 'db_ref': None},
        ]

        response = self.client.get('/api/v1/inventory/instances/', {
            'environment': 'dev',
            'server_name': 'srv01',
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['data']), 2)
        # Verify RBAC was checked
        mock_svc.list_targets_for_user.assert_called_once()
        # Verify service was called with validated server_name
        mock_svc.list_instances.assert_called_once_with(
            environment='dev', server_name='srv01', server_names=None,
        )

    @patch('inventory.views.get_correlation_id', return_value='int-test-003')
    @patch('inventory.views.get_user_ad_groups', return_value=['GRP-DBA'])
    @patch('inventory.views.InventoryService')
    def test_rbac_denial_flow(self, mock_service_cls, mock_ad_groups, mock_corr_id):
        """Task 9.5: User tries to access server outside profiles → 403."""
        mock_svc = mock_service_cls.return_value
        # RBAC allows only srv01
        mock_svc.list_targets_for_user.return_value = (
            [{'name': 'srv01', 'environment': 'dev', 'target_type': 'server', 'metadata': None}],
            1,
            False,
        )

        # Try to access srv99 which is NOT allowed
        response = self.client.get('/api/v1/inventory/instances/', {
            'environment': 'dev',
            'server_name': 'srv99',
        })

        self.assertEqual(response.status_code, 403)
        data = response.json()
        # Custom exception handler wraps in {"error": {"message": "..."}}
        self.assertIn('srv99', str(data))
        # Service should NOT have been called for instances
        mock_svc.list_instances.assert_not_called()

    @patch('inventory.views.get_correlation_id', return_value='int-test-004')
    @patch('inventory.views.get_user_ad_groups', return_value=['GRP-DBA'])
    @patch('inventory.views.InventoryService')
    def test_full_flow_databases_no_server_filter(self, mock_service_cls, mock_ad_groups, mock_corr_id):
        """Task 9.4: All databases for environment without server filter."""
        mock_svc = mock_service_cls.return_value
        mock_svc.list_databases.return_value = [
            {'id': 'DB01', 'name': 'DB01', 'environment': 'dev'},
            {'id': 'DB02', 'name': 'DB02', 'environment': 'dev'},
        ]

        response = self.client.get('/api/v1/inventory/databases/', {'environment': 'dev'})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['data']), 2)
        # No RBAC check when no server filter
        mock_svc.list_targets_for_user.assert_not_called()

    @patch('inventory.views.get_correlation_id', return_value='int-test-005')
    @patch('inventory.views.get_user_ad_groups', return_value=['GRP-DBA'])
    @patch('inventory.views.InventoryService')
    def test_json_structure_exact_format(self, mock_service_cls, mock_ad_groups, mock_corr_id):
        """Task 9.7: Verify exact JSON response structure { "data": [...] }."""
        mock_svc = mock_service_cls.return_value
        mock_svc.list_targets_for_user.return_value = (
            [{'name': 'srv01', 'environment': 'dev', 'target_type': 'server', 'metadata': None}],
            1,
            False,
        )
        mock_svc.list_servers.return_value = [
            {'id': 'srv01', 'name': 'srv01', 'environment': 'dev', 'engine_type': 'oracle'},
        ]

        response = self.client.get('/api/v1/inventory/servers/', {'environment': 'dev'})
        data = response.json()

        # Exact top-level key
        self.assertEqual(list(data.keys()), ['data'])
        # No pagination keys (AC4: pas de pagination pour inventaire)
        self.assertNotIn('pagination', data)
        self.assertNotIn('total', data)
        self.assertNotIn('page', data)

    @patch('inventory.views.get_correlation_id', return_value='int-test-006')
    @patch('inventory.views.get_user_ad_groups', return_value=['GRP-DBA'])
    @patch('inventory.views.InventoryService')
    def test_error_response_format(self, mock_service_cls, mock_ad_groups, mock_corr_id):
        """AC6: Error responses return { "detail": "..." }."""
        mock_svc = mock_service_cls.return_value
        mock_svc.list_targets_for_user.side_effect = InventoryServiceError("ORA-12541")

        response = self.client.get('/api/v1/inventory/servers/', {'environment': 'dev'})

        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertIn('detail', data)
        # Should NOT reveal internal error details
        self.assertNotIn('ORA-12541', data['detail'])

    def test_unauthenticated_request_401(self):
        """AC6: Unauthenticated requests return 401."""
        self.client.force_authenticate(user=None)

        for endpoint in ['/api/v1/inventory/servers/', '/api/v1/inventory/instances/', '/api/v1/inventory/databases/']:
            response = self.client.get(endpoint, {'environment': 'dev'})
            self.assertEqual(response.status_code, 401, f"Expected 401 for {endpoint}")

    @patch('inventory.views.get_correlation_id', return_value='int-test-008')
    @patch('inventory.views.get_user_ad_groups', return_value=['GRP-DBA'])
    @patch('inventory.views.InventoryService')
    def test_multi_server_names_query_param(self, mock_service_cls, mock_ad_groups, mock_corr_id):
        """Task 9.4: Multi-value server_names query param (srv01&srv02)."""
        mock_svc = mock_service_cls.return_value
        mock_svc.list_targets_for_user.return_value = (
            [
                {'name': 'srv01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
                {'name': 'srv02', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
            ],
            2,
            False,
        )
        mock_svc.list_instances.return_value = [
            {'id': 'INST01', 'name': 'INST01', 'environment': 'dev', 'server_ref': 'srv01', 'db_ref': None},
        ]

        response = self.client.get(
            '/api/v1/inventory/instances/?environment=dev&server_names=srv01&server_names=srv02'
        )

        self.assertEqual(response.status_code, 200)
        # Verify service called with server_names list
        mock_svc.list_instances.assert_called_once_with(
            environment='dev', server_name=None, server_names=['srv01', 'srv02'],
        )
