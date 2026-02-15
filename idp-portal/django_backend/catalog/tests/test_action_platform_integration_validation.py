"""
Story 29.4: Tests for platform ↔ integration.type consistency validation.

Tests ActionSerializer and ActionCreateSerializer validate() methods
to ensure platform and integration.type coherence when both are provided.
Includes E2E API tests for action creation/update with validation.
"""
from __future__ import annotations

import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status as http_status

from catalog.serializers import ActionSerializer, ActionCreateSerializer
from catalog.services import CatalogService
from integrations.models import Integration, IntegrationTypeCatalogue, IntegrationRole
from reference.models import RefPlatform, RefEngine
from tests.factories import (
    UserFactory,
    ActionFactory,
    IntegrationFactory,
    IntegrationTypeCatalogueFactory,
)


@pytest.mark.django_db
class TestActionPlatformIntegrationValidation(TestCase):
    """Tests for Story 29.4: platform ↔ integration.type consistency validation."""

    def setUp(self):
        """Set up reference data for validation tests."""
        self.user = UserFactory(username='testuser', profile='DBA')

        # Create REF_PLATFORMS entries
        RefPlatform.objects.create(code='AAP', label='AAP', display_order=1, is_active=1)
        RefPlatform.objects.create(code='GitHub Actions', label='GitHub Actions', display_order=2, is_active=1)
        RefPlatform.objects.create(code='Azure DevOps', label='Azure DevOps', display_order=3, is_active=1)
        RefPlatform.objects.create(code='Terraform', label='Terraform', display_order=4, is_active=1)
        RefPlatform.objects.create(code='Tower', label='Ansible Tower', display_order=5, is_active=1)
        RefPlatform.objects.create(code='Terraform Cloud', label='Terraform Cloud', display_order=6, is_active=1)

        # Create REF_ENGINES (needed for action creation)
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)

        # Create IntegrationTypeCatalogue entries — platforms
        IntegrationTypeCatalogueFactory(
            code='aap', name='AAP', integration_role=IntegrationRole.PLATFORM,
        )
        IntegrationTypeCatalogueFactory(
            code='tower', name='Ansible Tower', integration_role=IntegrationRole.PLATFORM,
        )
        IntegrationTypeCatalogueFactory(
            code='github_actions', name='GitHub Actions', integration_role=IntegrationRole.PLATFORM,
        )
        IntegrationTypeCatalogueFactory(
            code='azure_devops', name='Azure DevOps', integration_role=IntegrationRole.PLATFORM,
        )
        IntegrationTypeCatalogueFactory(
            code='terraform_cloud', name='Terraform Cloud', integration_role=IntegrationRole.PLATFORM,
        )

        # Create IntegrationTypeCatalogue entries — services
        IntegrationTypeCatalogueFactory(
            code='servicenow', name='ServiceNow', integration_role=IntegrationRole.SERVICE,
        )
        IntegrationTypeCatalogueFactory(
            code='vault', name='HashiCorp Vault', integration_role=IntegrationRole.SERVICE,
        )

        # Create Integration instances
        self.integration_aap = IntegrationFactory(type='aap', name='Test AAP')
        self.integration_github = IntegrationFactory(type='github_actions', name='Test GitHub')
        self.integration_azure = IntegrationFactory(type='azure_devops', name='Test Azure')
        self.integration_terraform = IntegrationFactory(type='terraform_cloud', name='Test Terraform Cloud')
        self.integration_tower = IntegrationFactory(type='tower', name='Test Tower')
        self.integration_servicenow = IntegrationFactory(type='servicenow', name='Test ServiceNow')
        self.integration_vault = IntegrationFactory(type='vault', name='Test Vault')

    # ===== AC1: Coherent platform ↔ integration.type (ActionCreateSerializer) =====

    def test_platform_aap_integration_aap_ok(self):
        """AC3/4.1: platform='AAP' + integration type='aap' → OK."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Action',
            'item_type': 'action',
            'engine': 'Oracle',
            'platform': 'AAP',
            'integration_id': self.integration_aap.id,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_platform_github_actions_integration_github_actions_ok(self):
        """AC3/4.2: platform='GitHub Actions' + integration type='github_actions' → OK."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Action',
            'item_type': 'action',
            'engine': 'Oracle',
            'platform': 'GitHub Actions',
            'integration_id': self.integration_github.id,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_platform_terraform_cloud_integration_terraform_cloud_ok(self):
        """Terraform Cloud + terraform_cloud → OK."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Action',
            'item_type': 'action',
            'engine': 'Oracle',
            'platform': 'Terraform Cloud',
            'integration_id': self.integration_terraform.id,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_platform_tower_integration_tower_ok(self):
        """Tower + tower → OK."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Action',
            'item_type': 'action',
            'engine': 'Oracle',
            'platform': 'Tower',
            'integration_id': self.integration_tower.id,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_platform_azure_devops_integration_azure_devops_ok(self):
        """Azure DevOps + azure_devops → OK."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Action',
            'item_type': 'action',
            'engine': 'Oracle',
            'platform': 'Azure DevOps',
            'integration_id': self.integration_azure.id,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    # ===== AC2: Incoherent combinations → 400 =====

    def test_platform_aap_integration_servicenow_rejected(self):
        """AC3/4.3: platform='AAP' + integration type='servicenow' → 400 (service, not platform)."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Action',
            'item_type': 'action',
            'engine': 'Oracle',
            'platform': 'AAP',
            'integration_id': self.integration_servicenow.id,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('integration_id', serializer.errors)
        self.assertIn('service', str(serializer.errors['integration_id']))

    def test_platform_aap_integration_vault_rejected(self):
        """platform='AAP' + integration type='vault' → 400 (service)."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Action',
            'item_type': 'action',
            'engine': 'Oracle',
            'platform': 'AAP',
            'integration_id': self.integration_vault.id,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('integration_id', serializer.errors)

    def test_platform_aap_integration_github_actions_rejected(self):
        """platform='AAP' + integration type='github_actions' → 400 (inconsistent)."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Action',
            'item_type': 'action',
            'engine': 'Oracle',
            'platform': 'AAP',
            'integration_id': self.integration_github.id,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('platform', serializer.errors)
        self.assertIn('inconsistent', str(serializer.errors['platform']))

    def test_platform_terraform_integration_aap_rejected(self):
        """AC3/4.4: platform='Terraform' + integration type='aap' → 400 (inconsistent)."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Action',
            'item_type': 'action',
            'engine': 'Oracle',
            'platform': 'Terraform',
            'integration_id': self.integration_aap.id,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('platform', serializer.errors)

    # ===== AC2: Skip validation when only one field provided =====

    def test_platform_only_no_integration_ok(self):
        """AC3/4.5: platform seul (pas d'integration_id) → OK (skip validation)."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Action',
            'item_type': 'action',
            'engine': 'Oracle',
            'platform': 'AAP',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_integration_only_no_platform_ok(self):
        """AC3/4.6: integration_id seul (pas de platform) → OK (skip validation)."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Action',
            'item_type': 'workflow',  # workflows don't require platform
            'engine': 'Oracle',
            'integration_id': self.integration_aap.id,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_integration_not_found_rejected(self):
        """integration_id not found → 400."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Action',
            'item_type': 'action',
            'engine': 'Oracle',
            'platform': 'AAP',
            'integration_id': 99999,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('integration_id', serializer.errors)

    # ===== ActionSerializer (update) validation =====

    def test_action_serializer_update_platform_coherent(self):
        """ActionSerializer.validate() on existing action with coherent platform."""
        action = ActionFactory(
            platform='AAP',
            engine='Oracle',
            integration=self.integration_aap,
            created_by=self.user,
        )
        serializer = ActionSerializer(
            instance=action,
            data={'platform': 'AAP'},
            partial=True,
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_action_serializer_update_platform_incoherent(self):
        """ActionSerializer.validate() on existing action with incoherent platform update."""
        action = ActionFactory(
            platform='AAP',
            engine='Oracle',
            integration=self.integration_github,
            created_by=self.user,
        )
        serializer = ActionSerializer(
            instance=action,
            data={'platform': 'AAP'},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('platform', serializer.errors)

    def test_action_serializer_update_platform_service_integration(self):
        """ActionSerializer.validate() rejects platform update when integration is a service."""
        action = ActionFactory(
            platform='AAP',
            engine='Oracle',
            integration=self.integration_servicenow,
            created_by=self.user,
        )
        serializer = ActionSerializer(
            instance=action,
            data={'platform': 'AAP'},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn('integration_id', serializer.errors)

    # ===== Mapping coverage =====

    def test_mapping_covers_all_platform_types(self):
        """AC3/4.7: All platform types in IntegrationTypeCatalogue have mapping."""
        platform_types = IntegrationTypeCatalogue.objects.filter(
            integration_role=IntegrationRole.PLATFORM
        ).values_list('code', flat=True)

        platform_codes = set(RefPlatform.objects.active().values_list('code', flat=True))

        # Normalize platform codes for matching
        normalized_codes = {code.lower().replace(' ', '_') for code in platform_codes}

        for integration_type_code in platform_types:
            self.assertIn(
                integration_type_code,
                normalized_codes,
                f"IntegrationTypeCatalogue platform '{integration_type_code}' "
                f"has no matching REF_PLATFORMS entry (normalized codes: {normalized_codes})"
            )


@pytest.mark.django_db
class TestActionPlatformIntegrationE2E(TestCase):
    """E2E tests for Story 29.4: API-level validation of platform ↔ integration.type."""

    def setUp(self):
        """Set up reference data and API client."""
        self.client = APIClient()
        self.dbops_user = UserFactory(username='dbops_user', profile='DBOPS')
        self.client.force_authenticate(user=self.dbops_user)

        # Reference data
        RefPlatform.objects.create(code='AAP', label='AAP', display_order=1, is_active=1)
        RefPlatform.objects.create(code='GitHub Actions', label='GitHub Actions', display_order=2, is_active=1)
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)

        # IntegrationTypeCatalogue
        IntegrationTypeCatalogueFactory(
            code='aap', name='AAP', integration_role=IntegrationRole.PLATFORM,
        )
        IntegrationTypeCatalogueFactory(
            code='github_actions', name='GitHub Actions', integration_role=IntegrationRole.PLATFORM,
        )
        IntegrationTypeCatalogueFactory(
            code='servicenow', name='ServiceNow', integration_role=IntegrationRole.SERVICE,
        )

        # Integrations
        self.integration_aap = IntegrationFactory(type='aap', name='Test AAP')
        self.integration_github = IntegrationFactory(type='github_actions', name='Test GitHub')
        self.integration_servicenow = IntegrationFactory(type='servicenow', name='Test SN')

    def test_e2e_create_action_coherent_platform_integration(self):
        """AC3/6.1: E2E create action with coherent platform + integration → 201."""
        response = self.client.post('/api/v1/admin/actions/', {
            'name': 'AAP Coherent Action',
            'engine': 'Oracle',
            'platform': 'AAP',
            'item_type': 'action',
            'integration_id': self.integration_aap.id,
        }, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_e2e_create_action_incoherent_platform_rejected(self):
        """AC3/6.2: E2E create action with incoherent platform + integration → 400."""
        response = self.client.post('/api/v1/admin/actions/', {
            'name': 'Incoherent Action',
            'engine': 'Oracle',
            'platform': 'AAP',
            'item_type': 'action',
            'integration_id': self.integration_github.id,
        }, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_e2e_create_action_service_integration_rejected(self):
        """E2E: create action with platform + service integration → 400."""
        response = self.client.post('/api/v1/admin/actions/', {
            'name': 'Service Mismatch Action',
            'engine': 'Oracle',
            'platform': 'AAP',
            'item_type': 'action',
            'integration_id': self.integration_servicenow.id,
        }, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
