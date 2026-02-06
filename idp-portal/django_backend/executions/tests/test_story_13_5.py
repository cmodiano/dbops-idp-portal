"""
Story 13.5: API self-service standalone — déclencher une exécution via API sans frontend

Tests for:
- AC1: Authentification par jeton Bearer (API standalone)
- AC2: Refus explicite pour targets non autorisés ou payload invalide
- AC3: Visibilité portail des exécutions API (GET /executions shows API-created executions)
- AC4: Traçabilité audit SOC1 pour exécutions API (source, ip_address, correlation_id)
"""
import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock

from idp_auth.models import User
from idp_auth.jwt_utils import create_access_token
from catalog.models import Action
from executions.models import Execution
from core.models import AuditLog


@pytest.mark.django_db
class APIStandaloneExecutionTests(TestCase):
    """
    Story 13.5: Tests for API standalone execution without frontend.
    """

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create(
            username='api_test_user',
            profile='DBA'
        )

        # Create a published action requiring targets
        self.action = Action.objects.create(
            name='API Test Action',
            category='Provisioning',
            engine='Oracle',
            platform='AAP',
            status='published',
            requires_target=True
        )
        self.action.set_change_type_config({
            'DEV': {'required': False, 'change_model_code': None},
        })
        self.action.set_impact_rules({
            'DEV': {'level': 'low'},
        })
        self.action.save()

        # Action not requiring targets
        self.action_no_target = Action.objects.create(
            name='API Test Action No Target',
            category='Monitoring',
            engine='Oracle',
            platform='AAP',
            status='published',
            requires_target=False
        )

    def _get_valid_token(self, user=None):
        """Generate a valid JWT token for the given user."""
        user = user or self.user
        token_data = {
            'sub': str(user.id),
            'username': user.username,
            'profile': user.profile,
            'ad_groups': [user.profile],
        }
        return create_access_token(token_data)

    def _mock_inventory_service(self, allowed_targets):
        """Create a mock for InventoryService.list_targets_for_user."""
        mock_instance = MagicMock()
        mock_instance.list_targets_for_user.return_value = (allowed_targets, len(allowed_targets), False)
        return mock_instance

    # =========================================================================
    # AC1: Authentification par jeton Bearer (API standalone)
    # =========================================================================

    def test_api_execution_with_bearer_token_success(self):
        """
        Subtask 5.1: POST /executions with Authorization Bearer → 201
        Verifies execution_id is returned in response.
        """
        token = self._get_valid_token()
        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]

        with patch('executions.views.InventoryService') as MockInventoryService:
            MockInventoryService.return_value = self._mock_inventory_service(allowed_targets)

            response = self.client.post(
                '/api/v1/executions',
                {
                    'action_id': self.action.id,
                    'target_names': ['srv-dev-01'],
                },
                format='json',
                HTTP_AUTHORIZATION=f'Bearer {token}',
                HTTP_X_IDP_REQUEST_ID='test-correlation-id-001',
            )

        self.assertEqual(response.status_code, 201)
        self.assertIn('data', response.data)
        self.assertIn('execution_id', response.data['data'])
        self.assertEqual(response.data['data']['status'], 'SUBMITTED')

        # Verify execution exists in database
        execution = Execution.objects.get(id=response.data['data']['execution_id'])
        self.assertEqual(execution.user_id, self.user.id)
        self.assertEqual(execution.action_id, self.action.id)

    def test_api_execution_without_auth_returns_401(self):
        """
        Subtask 5.2: POST /executions without Authorization header → 401
        """
        response = self.client.post(
            '/api/v1/executions',
            {
                'action_id': self.action.id,
                'target_names': ['srv-dev-01'],
            },
            format='json',
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn('error', response.data)

    def test_api_execution_invalid_token_returns_401(self):
        """
        Subtask 5.3: POST /executions with expired/invalid token → 401
        """
        response = self.client.post(
            '/api/v1/executions',
            {
                'action_id': self.action.id,
                'target_names': ['srv-dev-01'],
            },
            format='json',
            HTTP_AUTHORIZATION='Bearer invalid-token-12345',
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn('error', response.data)

    # =========================================================================
    # AC2: Refus explicite pour targets non autorisés ou payload invalide
    # =========================================================================

    def test_api_execution_forbidden_target_returns_403(self):
        """
        Subtask 5.4: POST /executions with unauthorized target → 403
        """
        token = self._get_valid_token()
        # No authorized targets for user
        allowed_targets = []

        with patch('executions.views.InventoryService') as MockInventoryService:
            MockInventoryService.return_value = self._mock_inventory_service(allowed_targets)

            response = self.client.post(
                '/api/v1/executions',
                {
                    'action_id': self.action.id,
                    'target_names': ['srv-unauthorized-01'],
                },
                format='json',
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )

        self.assertEqual(response.status_code, 403)
        self.assertIn('error', response.data)
        self.assertIn('FORBIDDEN', response.data['error']['code'])

    def test_api_execution_invalid_payload_returns_400(self):
        """
        Subtask 5.5: POST /executions with invalid payload → 400
        """
        token = self._get_valid_token()

        # Missing action_id
        response = self.client.post(
            '/api/v1/executions',
            {
                'target_names': ['srv-dev-01'],
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)

    def test_api_execution_action_not_found_returns_404(self):
        """
        Subtask 5.6: POST /executions with non-existent action_id → 404
        """
        token = self._get_valid_token()

        response = self.client.post(
            '/api/v1/executions',
            {
                'action_id': 999999,  # Non-existent action
                'target_names': ['srv-dev-01'],
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

        self.assertEqual(response.status_code, 404)
        self.assertIn('error', response.data)
        self.assertIn('ACTION_NOT_FOUND', response.data['error']['code'])

    def test_api_execution_missing_target_names_returns_400(self):
        """
        AC2: POST /executions without target_names for requires_target action → 400
        """
        token = self._get_valid_token()

        response = self.client.post(
            '/api/v1/executions',
            {
                'action_id': self.action.id,
                # Missing target_names
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)
        self.assertIn('target_names', response.data['error']['message'].lower())

    def test_api_execution_empty_target_names_returns_400(self):
        """
        AC2: POST /executions with empty target_names list → 400
        """
        token = self._get_valid_token()

        response = self.client.post(
            '/api/v1/executions',
            {
                'action_id': self.action.id,
                'target_names': [],
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.data)

    # =========================================================================
    # AC3: Visibilité portail des exécutions API
    # =========================================================================

    def test_api_execution_visible_in_portal_list(self):
        """
        Subtask 5.7: Execution created via API appears in GET /executions
        """
        token = self._get_valid_token()
        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]

        with patch('executions.views.InventoryService') as MockInventoryService:
            MockInventoryService.return_value = self._mock_inventory_service(allowed_targets)

            # Create execution via API
            create_response = self.client.post(
                '/api/v1/executions',
                {
                    'action_id': self.action.id,
                    'target_names': ['srv-dev-01'],
                },
                format='json',
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )

        self.assertEqual(create_response.status_code, 201)
        execution_id = create_response.data['data']['execution_id']

        # List executions
        list_response = self.client.get(
            '/api/v1/executions?scope=mine',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertIn('data', list_response.data)

        # Find the created execution in the list
        execution_ids = [e['id'] for e in list_response.data['data']]
        self.assertIn(execution_id, execution_ids)

    def test_api_execution_visible_in_portal_detail(self):
        """
        AC3: Execution created via API is accessible via GET /executions/{id}
        """
        token = self._get_valid_token()
        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]

        with patch('executions.views.InventoryService') as MockInventoryService:
            MockInventoryService.return_value = self._mock_inventory_service(allowed_targets)

            # Create execution via API
            create_response = self.client.post(
                '/api/v1/executions',
                {
                    'action_id': self.action.id,
                    'target_names': ['srv-dev-01'],
                },
                format='json',
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )

        self.assertEqual(create_response.status_code, 201)
        execution_id = create_response.data['data']['execution_id']

        # Get execution detail
        detail_response = self.client.get(
            f'/api/v1/executions/{execution_id}',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

        self.assertEqual(detail_response.status_code, 200)
        self.assertIn('data', detail_response.data)
        self.assertEqual(detail_response.data['data']['id'], execution_id)

    # =========================================================================
    # AC4: Traçabilité audit SOC1 pour exécutions API
    # =========================================================================

    def test_api_execution_audit_logged_with_source_api(self):
        """
        Subtask 5.8: Audit contains source=api, ip_address, correlation_id
        """
        token = self._get_valid_token()
        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]
        correlation_id = 'test-correlation-id-audit-001'

        with patch('executions.views.InventoryService') as MockInventoryService:
            MockInventoryService.return_value = self._mock_inventory_service(allowed_targets)

            response = self.client.post(
                '/api/v1/executions',
                {
                    'action_id': self.action.id,
                    'target_names': ['srv-dev-01'],
                },
                format='json',
                HTTP_AUTHORIZATION=f'Bearer {token}',
                HTTP_X_IDP_REQUEST_ID=correlation_id,
                REMOTE_ADDR='192.168.1.100',
            )

        self.assertEqual(response.status_code, 201)
        execution_id = response.data['data']['execution_id']

        # Find the audit log entry for this execution
        audit_entry = AuditLog.objects.filter(
            entity_type='execution',
            entity_id=execution_id,
            action_type='EXECUTION_SUBMITTED',
        ).first()

        self.assertIsNotNone(audit_entry)
        self.assertEqual(audit_entry.user_id, str(self.user.id))
        self.assertEqual(audit_entry.correlation_id, correlation_id)

        # Verify source and ip_address in details
        import json
        details = json.loads(audit_entry.details) if isinstance(audit_entry.details, str) else audit_entry.details
        self.assertEqual(details.get('source'), 'api')
        self.assertIn('ip_address', details)

    def test_api_execution_audit_includes_action_and_target_info(self):
        """
        AC4: Audit contains action_id, action_name, targets, environment
        """
        token = self._get_valid_token()
        allowed_targets = [
            {'name': 'srv-dev-01', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
            {'name': 'srv-dev-02', 'environment': 'dev', 'target_type': 'server', 'metadata': None},
        ]

        with patch('executions.views.InventoryService') as MockInventoryService:
            MockInventoryService.return_value = self._mock_inventory_service(allowed_targets)

            response = self.client.post(
                '/api/v1/executions',
                {
                    'action_id': self.action.id,
                    'target_names': ['srv-dev-01', 'srv-dev-02'],
                },
                format='json',
                HTTP_AUTHORIZATION=f'Bearer {token}',
            )

        self.assertEqual(response.status_code, 201)
        execution_id = response.data['data']['execution_id']

        # Find the audit log entry
        audit_entry = AuditLog.objects.filter(
            entity_type='execution',
            entity_id=execution_id,
            action_type='EXECUTION_SUBMITTED',
        ).first()

        self.assertIsNotNone(audit_entry)

        import json
        details = json.loads(audit_entry.details) if isinstance(audit_entry.details, str) else audit_entry.details
        self.assertEqual(details.get('action_id'), self.action.id)
        self.assertEqual(details.get('action_name'), self.action.name)
        self.assertEqual(details.get('environment'), 'dev')
        self.assertIn('targets', details)
        self.assertEqual(len(details['targets']), 2)


@pytest.mark.django_db
class APIExecutionNoTargetTests(TestCase):
    """
    Tests for actions that don't require targets (requires_target=False).
    """

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        self.user = User.objects.create(
            username='api_notarget_user',
            profile='DBA'
        )

        self.action = Action.objects.create(
            name='No Target Action',
            category='Monitoring',
            engine='Oracle',
            platform='AAP',
            status='published',
            requires_target=False
        )

    def _get_valid_token(self):
        """Generate a valid JWT token."""
        token_data = {
            'sub': str(self.user.id),
            'username': self.user.username,
            'profile': self.user.profile,
            'ad_groups': [self.user.profile],
        }
        return create_access_token(token_data)

    def test_api_execution_without_target_uses_environment(self):
        """
        Actions with requires_target=False can use environment directly.
        """
        token = self._get_valid_token()

        response = self.client.post(
            '/api/v1/executions',
            {
                'action_id': self.action.id,
                'environment': 'dev',
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

        self.assertEqual(response.status_code, 201)
        execution = Execution.objects.get(id=response.data['data']['execution_id'])
        self.assertEqual(execution.environment, 'dev')

    def test_api_execution_without_target_audit_source_api(self):
        """
        Audit for no-target action also includes source=api.
        """
        token = self._get_valid_token()

        response = self.client.post(
            '/api/v1/executions',
            {
                'action_id': self.action.id,
                'environment': 'dev',
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )

        self.assertEqual(response.status_code, 201)
        execution_id = response.data['data']['execution_id']

        audit_entry = AuditLog.objects.filter(
            entity_type='execution',
            entity_id=execution_id,
            action_type='EXECUTION_SUBMITTED',
        ).first()

        self.assertIsNotNone(audit_entry)
        import json
        details = json.loads(audit_entry.details) if isinstance(audit_entry.details, str) else audit_entry.details
        self.assertEqual(details.get('source'), 'api')
