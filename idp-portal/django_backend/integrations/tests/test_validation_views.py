"""
Story 24.3: Tests for validate and validate-all API endpoints.
Story 30.6: Updated to verify {"data": ...} response format (APIFMT-1/APIFMT-2 fix).
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from idp_auth.models import User
from integrations.models import Integration, IntegrationStatus, IntegrationTypeCatalogue
from core.models import AuditLog, AuditActionType
from profiles.models import Profile


@pytest.mark.django_db
class TestValidateEndpoint(TestCase):
    """Tests for GET /admin/integrations/{id}/validate."""

    def setUp(self):
        Profile.objects.get_or_create(
            name='DBOPS',
            defaults={'ad_group': 'CN=DBOPS,OU=Groups,DC=example,DC=com', 'is_admin': 1, 'is_auditor': 0},
        )
        self.client = APIClient()
        self.user = User.objects.create(username='dbops_user', profile='dbops')
        self.client.force_authenticate(user=self.user)

        IntegrationTypeCatalogue.objects.create(
            code='aap', name='AAP', version='1.0', is_active=True
        )
        IntegrationTypeCatalogue.objects.create(
            code='old_type', name='Old', version='1.0', is_active=False
        )

        self.integration = Integration.objects.create(
            type='aap', name='AAP Dev', base_url='https://aap.example.com'
        )

    def test_validate_valid_integration(self):
        response = self.client.get(f'/api/v1/admin/integrations/{self.integration.id}/validate/')
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert data['current_status'] == 'valid'
        assert data['validation_details']['type_exists'] is True
        assert data['validation_details']['type_is_active'] is True

    def test_validate_deprecated_integration(self):
        integration = Integration.objects.create(
            type='old_type', name='Old Integration', base_url='https://old.example.com'
        )
        response = self.client.get(f'/api/v1/admin/integrations/{integration.id}/validate/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['current_status'] == 'deprecated'

    def test_validate_invalid_integration(self):
        integration = Integration.objects.create(
            type='nonexistent', name='Unknown', base_url='https://unknown.example.com'
        )
        response = self.client.get(f'/api/v1/admin/integrations/{integration.id}/validate/')
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert data['current_status'] == 'invalid'
        assert data['validation_details']['type_exists'] is False

    def test_validate_updates_status_and_creates_audit(self):
        integration = Integration.objects.create(
            type='old_type', name='Was Valid', base_url='https://dep.example.com',
            status=IntegrationStatus.VALID,
        )
        response = self.client.get(f'/api/v1/admin/integrations/{integration.id}/validate/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['current_status'] == 'deprecated'

        # DB updated
        integration.refresh_from_db()
        assert integration.status == IntegrationStatus.DEPRECATED

        # Audit entry created
        audit = AuditLog.objects.filter(
            action_type=AuditActionType.INTEGRATION_STATUS_UPDATED,
            entity_id=integration.id,
        )
        assert audit.count() == 1

    def test_validate_not_found(self):
        response = self.client.get('/api/v1/admin/integrations/99999/validate/')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_validate_response_structure(self):
        """Story 30.6 APIFMT-1: Verify response is wrapped in {"data": {...}}."""
        response = self.client.get(f'/api/v1/admin/integrations/{self.integration.id}/validate/')
        assert 'data' in response.data
        data = response.data['data']
        assert 'integration_id' in data
        assert 'integration_name' in data
        assert 'integration_type' in data
        assert 'current_status' in data
        assert 'validation_details' in data
        details = data['validation_details']
        assert 'status' in details
        assert 'type_exists' in details
        assert 'type_is_active' in details
        assert 'catalogue_version' in details
        assert 'validation_message' in details


@pytest.mark.django_db
class TestValidateAllEndpoint(TestCase):
    """Tests for POST /admin/integrations/validate-all."""

    def setUp(self):
        Profile.objects.get_or_create(
            name='DBOPS',
            defaults={'ad_group': 'CN=DBOPS,OU=Groups,DC=example,DC=com', 'is_admin': 1, 'is_auditor': 0},
        )
        self.client = APIClient()
        self.user = User.objects.create(username='dbops_user', profile='dbops')
        self.client.force_authenticate(user=self.user)

        IntegrationTypeCatalogue.objects.create(
            code='aap', name='AAP', version='1.0', is_active=True
        )

    def test_validate_all_returns_stats(self):
        Integration.objects.create(
            type='aap', name='Valid', base_url='https://aap.example.com'
        )
        Integration.objects.create(
            type='nonexistent', name='Invalid', base_url='https://inv.example.com'
        )

        response = self.client.post('/api/v1/admin/integrations/validate-all/')
        assert response.status_code == status.HTTP_200_OK
        data = response.data['data']
        assert data['valid'] == 1
        assert data['invalid'] == 1
        assert data['updated'] == 1

    def test_validate_all_empty_returns_zeros(self):
        response = self.client.post('/api/v1/admin/integrations/validate-all/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data'] == {'valid': 0, 'invalid': 0, 'deprecated': 0, 'updated': 0}

    def test_validate_all_response_has_data_wrapper(self):
        """Story 30.6 APIFMT-2: Verify response is wrapped in {"data": {...}}."""
        response = self.client.post('/api/v1/admin/integrations/validate-all/')
        assert response.status_code == status.HTTP_200_OK
        assert 'data' in response.data
        assert isinstance(response.data['data'], dict)
