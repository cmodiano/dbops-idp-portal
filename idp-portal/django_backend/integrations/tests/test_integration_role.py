"""
Story 29.1: Tests for integration_role field on IntegrationTypeCatalogue.
Covers model, serializer, API filtering, and fixtures.
"""

import pytest
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework import status

from integrations.models import IntegrationTypeCatalogue, IntegrationRole
from integrations.serializers import IntegrationTypeWithActionsSerializer
from integrations.catalogue_service import IntegrationCatalogueService
from tests.factories import (
    UserFactory,
    IntegrationTypeCatalogueFactory,
    IntegrationActionFactory,
)


# ============================================================================
# Model Tests
# ============================================================================


@pytest.mark.django_db
class TestIntegrationRoleModel:
    """Tests for IntegrationTypeCatalogue.integration_role field."""

    def test_create_with_role_platform(self):
        t = IntegrationTypeCatalogueFactory(code='aap', integration_role='platform')
        assert t.integration_role == 'platform'

    def test_create_with_role_service(self):
        t = IntegrationTypeCatalogueFactory(code='vault', integration_role='service')
        assert t.integration_role == 'service'

    def test_default_role_is_platform(self):
        t = IntegrationTypeCatalogueFactory(code='test_default')
        assert t.integration_role == 'platform'

    def test_integration_role_enum_values(self):
        assert IntegrationRole.PLATFORM == 'platform'
        assert IntegrationRole.SERVICE == 'service'
        assert len(IntegrationRole.choices) == 2

    def test_integration_role_choices_labels(self):
        labels = dict(IntegrationRole.choices)
        assert labels['platform'] == "Plateforme d'exécution"
        assert labels['service'] == 'Service consommé'

    def test_invalid_role_fails_validation(self):
        t = IntegrationTypeCatalogueFactory.build(
            code='bad_role', integration_role='invalid'
        )
        with pytest.raises(ValidationError):
            t.full_clean()

    def test_str_representation_unchanged(self):
        t = IntegrationTypeCatalogueFactory(code='aap', name='AAP', integration_role='platform')
        assert str(t) == 'aap (AAP)'


# ============================================================================
# Serializer Tests
# ============================================================================


@pytest.mark.django_db
class TestIntegrationRoleSerializer:
    """Tests for integration_role in IntegrationTypeWithActionsSerializer."""

    def test_serializer_includes_integration_role(self):
        t = IntegrationTypeCatalogueFactory(code='aap', integration_role='platform')
        serializer = IntegrationTypeWithActionsSerializer(t)
        assert 'integration_role' in serializer.data
        assert serializer.data['integration_role'] == 'platform'

    def test_serializer_role_service(self):
        t = IntegrationTypeCatalogueFactory(code='vault', integration_role='service')
        serializer = IntegrationTypeWithActionsSerializer(t)
        assert serializer.data['integration_role'] == 'service'


# ============================================================================
# Service Tests
# ============================================================================


@pytest.mark.django_db
class TestIntegrationRoleService:
    """Tests for IntegrationCatalogueService.list_all_types with role filter."""

    def test_list_all_types_no_filter(self):
        IntegrationTypeCatalogueFactory(code='aap', integration_role='platform')
        IntegrationTypeCatalogueFactory(code='vault', integration_role='service')
        result = IntegrationCatalogueService.list_all_types()
        assert result.count() == 2

    def test_list_all_types_filter_platform(self):
        IntegrationTypeCatalogueFactory(code='aap', integration_role='platform')
        IntegrationTypeCatalogueFactory(code='vault', integration_role='service')
        result = IntegrationCatalogueService.list_all_types(role='platform')
        assert result.count() == 1
        assert result[0].code == 'aap'

    def test_list_all_types_filter_service(self):
        IntegrationTypeCatalogueFactory(code='aap', integration_role='platform')
        IntegrationTypeCatalogueFactory(code='vault', integration_role='service')
        result = IntegrationCatalogueService.list_all_types(role='service')
        assert result.count() == 1
        assert result[0].code == 'vault'

    def test_list_all_types_invalid_role_returns_all(self):
        IntegrationTypeCatalogueFactory(code='aap', integration_role='platform')
        IntegrationTypeCatalogueFactory(code='vault', integration_role='service')
        result = IntegrationCatalogueService.list_all_types(role='invalid')
        assert result.count() == 2


# ============================================================================
# API Endpoint Tests
# ============================================================================


@pytest.mark.django_db
class TestIntegrationRoleAPI:
    """Tests for GET /api/v1/integrations/types/ with ?role= filter."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory()
        self.client.force_authenticate(user=self.user)
        self.url = '/api/v1/integrations/types/'

    def test_list_returns_integration_role_field(self):
        IntegrationTypeCatalogueFactory(code='aap', integration_role='platform')
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data['data'][0]['integration_role'] == 'platform'

    def test_filter_role_platform(self):
        IntegrationTypeCatalogueFactory(code='aap', integration_role='platform')
        IntegrationTypeCatalogueFactory(code='tower', integration_role='platform')
        IntegrationTypeCatalogueFactory(code='vault', integration_role='service')
        IntegrationTypeCatalogueFactory(code='jira', integration_role='service')
        response = self.client.get(self.url, {'role': 'platform'})
        assert response.status_code == status.HTTP_200_OK
        codes = [t['code'] for t in response.data['data']]
        assert 'aap' in codes
        assert 'tower' in codes
        assert 'vault' not in codes
        assert 'jira' not in codes

    def test_filter_role_service(self):
        IntegrationTypeCatalogueFactory(code='aap', integration_role='platform')
        IntegrationTypeCatalogueFactory(code='vault', integration_role='service')
        IntegrationTypeCatalogueFactory(code='jira', integration_role='service')
        response = self.client.get(self.url, {'role': 'service'})
        assert response.status_code == status.HTTP_200_OK
        codes = [t['code'] for t in response.data['data']]
        assert 'vault' in codes
        assert 'jira' in codes
        assert 'aap' not in codes

    def test_no_filter_returns_all(self):
        IntegrationTypeCatalogueFactory(code='aap', integration_role='platform')
        IntegrationTypeCatalogueFactory(code='vault', integration_role='service')
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data']) == 2

    def test_filter_invalid_role_returns_400(self):
        response = self.client.get(self.url, {'role': 'invalid'})
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'error' in response.data

    def test_filter_empty_role_returns_400(self):
        """Fix LOW-2: Renamed from test_filter_empty_role_returns_all to match actual behavior."""
        IntegrationTypeCatalogueFactory(code='aap', integration_role='platform')
        IntegrationTypeCatalogueFactory(code='vault', integration_role='service')
        response = self.client.get(self.url, {'role': ''})
        # Empty string is technically invalid
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_filter_with_actions_included(self):
        t = IntegrationTypeCatalogueFactory(code='aap', integration_role='platform')
        IntegrationActionFactory(integration_type=t, action_code='start_job')
        response = self.client.get(self.url, {'role': 'platform'})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['data'][0]['actions']) == 1

    def test_unauthenticated_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.get(self.url, {'role': 'platform'})
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
