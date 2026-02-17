"""
Tests for multi-table inventory API views.
Story 23.3 - AC8: Tests for /servers, /instances, /databases endpoints.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

from django.test import TestCase
from rest_framework.test import APIClient

from inventory.services import InventoryServiceError
from inventory.serializers import (
    ServerSerializer, InstanceSerializer, DatabaseSerializer,
    ServerFilterParamsSerializer, InstanceFilterParamsSerializer,
    DatabaseFilterParamsSerializer,
)


class SerializerTests(TestCase):
    """Tests for multi-table inventory serializers. Task 1.8."""

    # --- ServerSerializer ---

    def test_server_serializer_valid(self):
        data = {'id': 'srv01', 'name': 'srv01', 'environment': 'dev', 'engine_type': 'oracle'}
        s = ServerSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)
        self.assertEqual(s.validated_data['engine_type'], 'oracle')

    def test_server_serializer_without_engine_type(self):
        data = {'id': 'srv01', 'name': 'srv01', 'environment': 'dev'}
        s = ServerSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_server_serializer_missing_name(self):
        data = {'id': 'srv01', 'environment': 'dev'}
        s = ServerSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('name', s.errors)

    def test_server_serializer_output(self):
        """Verify output format matches AC4."""
        data = {'id': 'srv01', 'name': 'srv01', 'environment': 'dev', 'engine_type': 'oracle'}
        s = ServerSerializer(data)
        self.assertEqual(set(s.data.keys()), {'id', 'name', 'environment', 'engine_type'})

    # --- InstanceSerializer ---

    def test_instance_serializer_valid(self):
        data = {'id': 'INST01', 'name': 'INST01', 'environment': 'dev', 'server_ref': 'srv01', 'db_ref': 'DB01'}
        s = InstanceSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_instance_serializer_without_db_ref(self):
        data = {'id': 'INST01', 'name': 'INST01', 'environment': 'dev', 'server_ref': 'srv01'}
        s = InstanceSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_instance_serializer_without_server_ref(self):
        """server_ref is optional (nullable) after review fix HIGH-3."""
        data = {'id': 'INST01', 'name': 'INST01', 'environment': 'dev'}
        s = InstanceSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    # --- DatabaseSerializer ---

    def test_database_serializer_valid(self):
        data = {'id': 'DB01', 'name': 'DB01', 'environment': 'dev'}
        s = DatabaseSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_database_serializer_missing_environment(self):
        data = {'id': 'DB01', 'name': 'DB01'}
        s = DatabaseSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('environment', s.errors)

    # --- ServerFilterParamsSerializer ---

    def test_server_filter_valid(self):
        data = {'environment': 'dev', 'engine_type': 'oracle'}
        s = ServerFilterParamsSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_server_filter_missing_environment(self):
        data = {'engine_type': 'oracle'}
        s = ServerFilterParamsSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('environment', s.errors)

    def test_server_filter_environment_only(self):
        data = {'environment': 'prod'}
        s = ServerFilterParamsSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    # --- InstanceFilterParamsSerializer ---

    def test_instance_filter_valid_server_name(self):
        data = {'environment': 'dev', 'server_name': 'srv01'}
        s = InstanceFilterParamsSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_instance_filter_valid_server_names(self):
        data = {'environment': 'dev', 'server_names': ['srv01', 'srv02']}
        s = InstanceFilterParamsSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_instance_filter_missing_environment(self):
        data = {'server_name': 'srv01'}
        s = InstanceFilterParamsSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('environment', s.errors)

    def test_instance_filter_both_server_params_rejected(self):
        data = {'environment': 'dev', 'server_name': 'srv01', 'server_names': ['srv02']}
        s = InstanceFilterParamsSerializer(data=data)
        self.assertFalse(s.is_valid())
        self.assertIn('non_field_errors', s.errors)

    def test_instance_filter_no_server_filter(self):
        data = {'environment': 'dev'}
        s = InstanceFilterParamsSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    # --- DatabaseFilterParamsSerializer ---

    def test_database_filter_valid(self):
        data = {'environment': 'dev', 'server_name': 'srv01'}
        s = DatabaseFilterParamsSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_database_filter_both_server_params_rejected(self):
        data = {'environment': 'dev', 'server_name': 'srv01', 'server_names': ['srv02']}
        s = DatabaseFilterParamsSerializer(data=data)
        self.assertFalse(s.is_valid())


class BaseMultiTableViewTest(TestCase):
    """Base class for multi-table view tests."""

    def setUp(self):
        self.client = APIClient()
        self.user = MagicMock()
        self.user.id = 123
        self.user.is_authenticated = True
        self.client.force_authenticate(user=self.user)

        # Default mock for get_user_ad_groups
        self.ad_groups_patcher = patch('inventory.views.get_user_ad_groups', return_value=['GRP-DBA'])
        self.mock_ad_groups = self.ad_groups_patcher.start()

        # Default mock for get_correlation_id
        self.corr_id_patcher = patch('inventory.views.get_correlation_id', return_value='test-corr-id')
        self.mock_corr_id = self.corr_id_patcher.start()

    def tearDown(self):
        self.ad_groups_patcher.stop()
        self.corr_id_patcher.stop()


class ListServersViewTests(BaseMultiTableViewTest):
    """Tests for list_servers endpoint. Task 8.2."""

    @patch('inventory.views.InventoryService')
    def test_list_servers_success_200(self, mock_service_cls):
        """AC1: Success 200 with valid environment."""
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

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('data', data)
        self.assertEqual(len(data['data']), 1)
        self.assertEqual(data['data'][0]['name'], 'srv01')

    def test_list_servers_400_missing_environment(self):
        """AC1: 400 if environment missing."""
        response = self.client.get('/api/v1/inventory/servers/')
        self.assertEqual(response.status_code, 400)
        self.assertIn('detail', response.json())

    @patch('inventory.views.InventoryService')
    def test_list_servers_filter_engine_type(self, mock_service_cls):
        """AC1: engine_type filter works - verifies service receives the parameter."""
        mock_svc = mock_service_cls.return_value
        mock_svc.list_targets_for_user.return_value = (
            [
                {'name': 'srv01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
                {'name': 'srv02', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
            ],
            2,
            False,
        )
        # Service returns mixed engine types
        mock_svc.list_servers.return_value = [
            {'id': 'srv01', 'name': 'srv01', 'environment': 'dev', 'engine_type': 'oracle'},
            {'id': 'srv02', 'name': 'srv02', 'environment': 'dev', 'engine_type': 'postgres'},
        ]

        response = self.client.get('/api/v1/inventory/servers/', {
            'environment': 'dev',
            'engine_type': 'oracle',
        })

        self.assertEqual(response.status_code, 200)
        # Verify service called with engine_type parameter
        mock_svc.list_servers.assert_called_once_with(environment='dev', engine_type='oracle')
        # Note: actual filtering by engine_type is handled by InventoryService (story 23.2)
        # This test verifies the API layer passes the parameter correctly

    @patch('inventory.views.InventoryService')
    def test_list_servers_rbac_filters(self, mock_service_cls):
        """AC1: RBAC applied - only allowed servers returned."""
        mock_svc = mock_service_cls.return_value
        # User only has access to srv01
        mock_svc.list_targets_for_user.return_value = (
            [{'name': 'srv01', 'environment': 'dev', 'target_type': 'server', 'metadata': None}],
            1,
            False,
        )
        # Service returns srv01 and srv02
        mock_svc.list_servers.return_value = [
            {'id': 'srv01', 'name': 'srv01', 'environment': 'dev', 'engine_type': 'oracle'},
            {'id': 'srv02', 'name': 'srv02', 'environment': 'dev', 'engine_type': 'oracle'},
        ]

        response = self.client.get('/api/v1/inventory/servers/', {'environment': 'dev'})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['data']), 1)
        self.assertEqual(data['data'][0]['name'], 'srv01')

    @patch('inventory.views.InventoryService')
    def test_list_servers_500_service_error(self, mock_service_cls):
        """AC6: 500 on InventoryServiceError."""
        mock_svc = mock_service_cls.return_value
        mock_svc.list_targets_for_user.side_effect = InventoryServiceError("DB error")

        response = self.client.get('/api/v1/inventory/servers/', {'environment': 'dev'})

        self.assertEqual(response.status_code, 500)
        self.assertIn('detail', response.json())

    def test_list_servers_unauthenticated_401(self):
        """AC6: 401 if unauthenticated."""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/v1/inventory/servers/', {'environment': 'dev'})
        self.assertEqual(response.status_code, 401)

    @patch('inventory.views.InventoryService')
    def test_list_servers_logging(self, mock_service_cls):
        """AC6: Logging with correlation_id."""
        mock_svc = mock_service_cls.return_value
        mock_svc.list_targets_for_user.return_value = ([], 0, False)
        mock_svc.list_servers.return_value = []

        response = self.client.get('/api/v1/inventory/servers/', {'environment': 'dev'})
        self.assertEqual(response.status_code, 200)
        # Correlation ID was called
        self.mock_corr_id.assert_called()


class ListInstancesViewTests(BaseMultiTableViewTest):
    """Tests for list_instances endpoint. Task 8.3."""

    @patch('inventory.views.InventoryService')
    def test_list_instances_success_env_only(self, mock_service_cls):
        """AC2: Success 200 with environment only."""
        mock_svc = mock_service_cls.return_value
        mock_svc.list_instances.return_value = [
            {'id': 'INST01', 'name': 'INST01', 'environment': 'dev', 'server_ref': 'srv01', 'db_ref': None},
        ]

        response = self.client.get('/api/v1/inventory/instances/', {'environment': 'dev'})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('data', data)
        self.assertEqual(len(data['data']), 1)
        # No RBAC check since no server filter
        mock_svc.list_instances.assert_called_once_with(
            environment='dev', server_name=None, server_names=None,
        )

    @patch('inventory.views.InventoryService')
    @patch('inventory.views._validate_server_access')
    def test_list_instances_with_server_name_authorized(self, mock_validate, mock_service_cls):
        """AC2: Success 200 when server_name authorized."""
        mock_validate.return_value = ['srv01', 'srv02']
        mock_svc = mock_service_cls.return_value
        mock_svc.list_instances.return_value = [
            {'id': 'INST01', 'name': 'INST01', 'environment': 'dev', 'server_ref': 'srv01', 'db_ref': 'DB01'},
        ]

        response = self.client.get('/api/v1/inventory/instances/', {
            'environment': 'dev',
            'server_name': 'srv01',
        })

        self.assertEqual(response.status_code, 200)
        mock_validate.assert_called_once_with(self.user, 'dev', 'srv01', None)
        data = response.json()
        self.assertEqual(len(data['data']), 1)

    @patch('inventory.views._validate_server_access')
    def test_list_instances_server_name_unauthorized_403(self, mock_validate):
        """AC2: 403 when server_name not authorized."""
        from rest_framework.exceptions import PermissionDenied
        mock_validate.side_effect = PermissionDenied("Access denied to server: srv99")

        response = self.client.get('/api/v1/inventory/instances/', {
            'environment': 'dev',
            'server_name': 'srv99',
        })

        self.assertEqual(response.status_code, 403)
        data = response.json()
        # Custom exception handler wraps in {"error": {"message": "..."}}
        self.assertIn('srv99', str(data))

    @patch('inventory.views.InventoryService')
    @patch('inventory.views._validate_server_access')
    def test_list_instances_server_names_multi_value(self, mock_validate, mock_service_cls):
        """AC2: server_names multi-value works."""
        mock_validate.return_value = ['srv01', 'srv02']
        mock_svc = mock_service_cls.return_value
        mock_svc.list_instances.return_value = [
            {'id': 'INST01', 'name': 'INST01', 'environment': 'dev', 'server_ref': 'srv01', 'db_ref': None},
            {'id': 'INST02', 'name': 'INST02', 'environment': 'dev', 'server_ref': 'srv02', 'db_ref': None},
        ]

        response = self.client.get(
            '/api/v1/inventory/instances/?environment=dev&server_names=srv01&server_names=srv02'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['data']), 2)

    def test_list_instances_400_missing_environment(self):
        """AC2: 400 if environment missing."""
        response = self.client.get('/api/v1/inventory/instances/')
        self.assertEqual(response.status_code, 400)

    @patch('inventory.views.InventoryService')
    def test_list_instances_500_service_error(self, mock_service_cls):
        """AC6: 500 on InventoryServiceError."""
        mock_svc = mock_service_cls.return_value
        mock_svc.list_instances.side_effect = InventoryServiceError("DB error")

        response = self.client.get('/api/v1/inventory/instances/', {'environment': 'dev'})

        self.assertEqual(response.status_code, 500)
        self.assertIn('detail', response.json())


class ListDatabasesViewTests(BaseMultiTableViewTest):
    """Tests for list_databases endpoint. Task 8.4."""

    @patch('inventory.views.InventoryService')
    @patch('inventory.views._validate_server_access')
    def test_list_databases_with_server_name_authorized(self, mock_validate, mock_service_cls):
        """AC3: Success 200 with authorized server_name."""
        mock_validate.return_value = ['srv01']
        mock_svc = mock_service_cls.return_value
        mock_svc.list_databases.return_value = [
            {'id': 'DB01', 'name': 'DB01', 'environment': 'dev'},
        ]

        response = self.client.get('/api/v1/inventory/databases/', {
            'environment': 'dev',
            'server_name': 'srv01',
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('data', data)
        self.assertEqual(len(data['data']), 1)

    @patch('inventory.views._validate_server_access')
    def test_list_databases_server_name_unauthorized_403(self, mock_validate):
        """AC3: 403 when server_name not authorized."""
        from rest_framework.exceptions import PermissionDenied
        mock_validate.side_effect = PermissionDenied("Access denied to server: srv99")

        response = self.client.get('/api/v1/inventory/databases/', {
            'environment': 'dev',
            'server_name': 'srv99',
        })

        self.assertEqual(response.status_code, 403)

    @patch('inventory.views.InventoryService')
    @patch('inventory.views._validate_server_access')
    def test_list_databases_server_names_multi_value(self, mock_validate, mock_service_cls):
        """AC3: server_names list works."""
        mock_validate.return_value = ['srv01', 'srv02']
        mock_svc = mock_service_cls.return_value
        mock_svc.list_databases.return_value = [
            {'id': 'DB01', 'name': 'DB01', 'environment': 'dev'},
            {'id': 'DB02', 'name': 'DB02', 'environment': 'dev'},
        ]

        response = self.client.get(
            '/api/v1/inventory/databases/?environment=dev&server_names=srv01&server_names=srv02'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['data']), 2)

    @patch('inventory.views.InventoryService')
    def test_list_databases_no_server_filter(self, mock_service_cls):
        """AC3: Returns all databases for env without server filter."""
        mock_svc = mock_service_cls.return_value
        mock_svc.list_databases.return_value = [
            {'id': 'DB01', 'name': 'DB01', 'environment': 'dev'},
        ]

        response = self.client.get('/api/v1/inventory/databases/', {'environment': 'dev'})

        self.assertEqual(response.status_code, 200)
        mock_svc.list_databases.assert_called_once_with(
            environment='dev', server_name=None, server_names=None,
        )

    def test_list_databases_400_missing_environment(self):
        """AC3: 400 if environment missing."""
        response = self.client.get('/api/v1/inventory/databases/')
        self.assertEqual(response.status_code, 400)

    @patch('inventory.views.InventoryService')
    def test_list_databases_500_service_error(self, mock_service_cls):
        """AC6: 500 on InventoryServiceError."""
        mock_svc = mock_service_cls.return_value
        mock_svc.list_databases.side_effect = InventoryServiceError("DB error")

        response = self.client.get('/api/v1/inventory/databases/', {'environment': 'dev'})

        self.assertEqual(response.status_code, 500)


class ErrorHandlingTests(BaseMultiTableViewTest):
    """Tests for error handling across endpoints. Task 8.5."""

    @patch('inventory.views.InventoryService')
    def test_inventory_service_error_500_all_endpoints(self, mock_service_cls):
        """500 when InventoryService raises error - parameterized test for all endpoints."""
        test_cases = [
            {
                'endpoint': '/api/v1/inventory/servers/',
                'error_method': 'list_targets_for_user',
                'expected_detail': 'Failed to retrieve servers',
            },
            {
                'endpoint': '/api/v1/inventory/instances/',
                'error_method': 'list_instances',
                'expected_detail': 'Failed to retrieve instances',
            },
            {
                'endpoint': '/api/v1/inventory/databases/',
                'error_method': 'list_databases',
                'expected_detail': 'Failed to retrieve databases',
            },
        ]

        for case in test_cases:
            with self.subTest(endpoint=case['endpoint']):
                mock_svc = mock_service_cls.return_value
                # Reset all mocks
                mock_svc.reset_mock()

                # Set the specific method to raise error
                getattr(mock_svc, case['error_method']).side_effect = InventoryServiceError("Connection refused")

                response = self.client.get(case['endpoint'], {'environment': 'dev'})

                self.assertEqual(response.status_code, 500, f"Expected 500 for {case['endpoint']}")
                data = response.json()
                self.assertEqual(data['detail'], case['expected_detail'])
                # Error should NOT reveal SQL or config details
                self.assertNotIn('Connection refused', data['detail'])


class ValidateServerAccessTests(TestCase):
    """Tests for _validate_server_access helper. Task 8.6."""

    def setUp(self):
        self.user = MagicMock()
        self.user.id = 123

    @patch('inventory.views.get_correlation_id', return_value='test-corr-id')
    @patch('inventory.views.get_user_ad_groups', return_value=['GRP-DBA'])
    @patch('inventory.views.InventoryService')
    def test_server_authorized_passes(self, mock_service_cls, mock_ad_groups, mock_corr_id):
        """Authorized server_name passes without exception."""
        mock_svc = mock_service_cls.return_value
        mock_svc.list_targets_for_user.return_value = (
            [{'name': 'srv01', 'environment': 'dev', 'target_type': 'server', 'metadata': None}],
            1,
            False,
        )

        from inventory.views import _validate_server_access
        result = _validate_server_access(self.user, 'dev', server_name='srv01')
        self.assertIn('srv01', result)

    @patch('inventory.views.get_correlation_id', return_value='test-corr-id')
    @patch('inventory.views.get_user_ad_groups', return_value=['GRP-DBA'])
    @patch('inventory.views.InventoryService')
    def test_server_unauthorized_raises_403(self, mock_service_cls, mock_ad_groups, mock_corr_id):
        """Unauthorized server_name raises PermissionDenied."""
        mock_svc = mock_service_cls.return_value
        mock_svc.list_targets_for_user.return_value = (
            [{'name': 'srv01', 'environment': 'dev', 'target_type': 'server', 'metadata': None}],
            1,
            False,
        )

        from rest_framework.exceptions import PermissionDenied
        from inventory.views import _validate_server_access
        with self.assertRaises(PermissionDenied) as ctx:
            _validate_server_access(self.user, 'dev', server_name='srv99')
        self.assertIn('srv99', str(ctx.exception.detail))

    @patch('inventory.views.get_correlation_id', return_value='test-corr-id')
    @patch('inventory.views.get_user_ad_groups', return_value=['GRP-DBA'])
    @patch('inventory.views.InventoryService')
    def test_server_names_all_authorized(self, mock_service_cls, mock_ad_groups, mock_corr_id):
        """All server_names authorized passes."""
        mock_svc = mock_service_cls.return_value
        mock_svc.list_targets_for_user.return_value = (
            [
                {'name': 'srv01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
                {'name': 'srv02', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
            ],
            2,
            False,
        )

        from inventory.views import _validate_server_access
        result = _validate_server_access(self.user, 'dev', server_names=['srv01', 'srv02'])
        self.assertIn('srv01', result)
        self.assertIn('srv02', result)

    @patch('inventory.views.get_correlation_id', return_value='test-corr-id')
    @patch('inventory.views.get_user_ad_groups', return_value=['GRP-DBA'])
    @patch('inventory.views.InventoryService')
    def test_server_names_mixed_raises_403(self, mock_service_cls, mock_ad_groups, mock_corr_id):
        """Mixed server_names (some unauthorized) raises PermissionDenied."""
        mock_svc = mock_service_cls.return_value
        mock_svc.list_targets_for_user.return_value = (
            [{'name': 'srv01', 'environment': 'dev', 'target_type': 'server', 'metadata': None}],
            1,
            False,
        )

        from rest_framework.exceptions import PermissionDenied
        from inventory.views import _validate_server_access
        with self.assertRaises(PermissionDenied) as ctx:
            _validate_server_access(self.user, 'dev', server_names=['srv01', 'srv99'])
        self.assertIn('srv99', str(ctx.exception.detail))

    @patch('inventory.views.get_correlation_id', return_value='test-corr-id')
    @patch('inventory.views.get_user_ad_groups', return_value=['GRP-DBA'])
    @patch('inventory.views.InventoryService')
    def test_no_server_filter_returns_allowed(self, mock_service_cls, mock_ad_groups, mock_corr_id):
        """No server filter returns list of allowed servers."""
        mock_svc = mock_service_cls.return_value
        mock_svc.list_targets_for_user.return_value = (
            [{'name': 'srv01', 'environment': 'dev', 'target_type': 'server', 'metadata': None}],
            1,
            False,
        )

        from inventory.views import _validate_server_access
        result = _validate_server_access(self.user, 'dev')
        self.assertEqual(result, ['srv01'])


class ResponseFormatTests(BaseMultiTableViewTest):
    """Tests to verify JSON response format matches AC4."""

    @patch('inventory.views.InventoryService')
    def test_servers_response_format(self, mock_service_cls):
        """Response format: { "data": [...] } for servers."""
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

        self.assertEqual(set(data.keys()), {'data'})
        self.assertIsInstance(data['data'], list)
        self.assertEqual(set(data['data'][0].keys()), {'id', 'name', 'environment', 'engine_type'})

    @patch('inventory.views.InventoryService')
    def test_instances_response_format(self, mock_service_cls):
        """Response format: { "data": [...] } for instances."""
        mock_svc = mock_service_cls.return_value
        mock_svc.list_instances.return_value = [
            {'id': 'INST01', 'name': 'INST01', 'environment': 'dev', 'server_ref': 'srv01', 'db_ref': 'DB01'},
        ]

        response = self.client.get('/api/v1/inventory/instances/', {'environment': 'dev'})
        data = response.json()

        self.assertEqual(set(data.keys()), {'data'})
        self.assertIsInstance(data['data'], list)
        self.assertEqual(set(data['data'][0].keys()), {'id', 'name', 'environment', 'server_ref', 'db_ref'})

    @patch('inventory.views.InventoryService')
    def test_databases_response_format(self, mock_service_cls):
        """Response format: { "data": [...] } for databases."""
        mock_svc = mock_service_cls.return_value
        mock_svc.list_databases.return_value = [
            {'id': 'DB01', 'name': 'DB01', 'environment': 'dev'},
        ]

        response = self.client.get('/api/v1/inventory/databases/', {'environment': 'dev'})
        data = response.json()

        self.assertEqual(set(data.keys()), {'data'})
        self.assertIsInstance(data['data'], list)
        self.assertEqual(set(data['data'][0].keys()), {'id', 'name', 'environment'})
