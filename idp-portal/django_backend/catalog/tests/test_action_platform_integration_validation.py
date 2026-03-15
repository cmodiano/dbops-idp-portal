"""
Story 83-13: Tests pour la dérivation automatique de platform depuis integration.type.

Story 29.4 (legacy) : la validation platform ↔ integration.type était gérée côté serializer.
Story 83-13 : platform est désormais TOUJOURS dérivé automatiquement par le backend
depuis integration.type via platform_registry. Le champ platform n'est plus accepté dans
les payloads externes — il est toujours calculé.
"""
from __future__ import annotations

import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status as http_status

from catalog.serializers import ActionCreateSerializer
from integrations.models import IntegrationRole
from reference.models import RefEngine
from profiles.models import Profile
from tests.factories import (
    UserFactory,
    ActionFactory,
    IntegrationFactory,
    IntegrationTypeCatalogueFactory,
)


@pytest.mark.django_db
class TestActionPlatformAutoDerived(TestCase):
    """Tests Story 83-13 : platform dérivé automatiquement depuis integration.type."""

    def setUp(self):
        self.user = UserFactory(username='testuser', profile='DBA')

        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)

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
        IntegrationTypeCatalogueFactory(
            code='servicenow', name='ServiceNow', integration_role=IntegrationRole.SERVICE,
        )
        IntegrationTypeCatalogueFactory(
            code='vault', name='HashiCorp Vault', integration_role=IntegrationRole.SERVICE,
        )

        self.integration_aap = IntegrationFactory(type='aap', name='Test AAP')
        self.integration_github = IntegrationFactory(type='github_actions', name='Test GitHub')
        self.integration_azure = IntegrationFactory(type='azure_devops', name='Test Azure')
        self.integration_terraform = IntegrationFactory(type='terraform_cloud', name='Test Terraform Cloud')
        self.integration_tower = IntegrationFactory(type='tower', name='Test Tower')
        self.integration_servicenow = IntegrationFactory(type='servicenow', name='Test ServiceNow')
        self.integration_vault = IntegrationFactory(type='vault', name='Test Vault')

    # ===== AC2: platform dérivé depuis integration_id =====

    def test_platform_auto_derived_aap(self):
        """AC2: integration_id=aap → platform='AAP' dérivé automatiquement (workflow pour éviter action_config)."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Workflow',
            'item_type': 'workflow',
            'engine': 'Oracle',
            'integration_id': self.integration_aap.id,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['platform'], 'AAP')

    def test_platform_auto_derived_tower(self):
        """AC2: integration_id=tower → platform='Tower' dérivé automatiquement."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Tower',
            'item_type': 'workflow',
            'engine': 'Oracle',
            'integration_id': self.integration_tower.id,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['platform'], 'Tower')

    def test_platform_auto_derived_github_actions(self):
        """AC2: integration_id=github_actions → platform='GitHub Actions' dérivé."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test GitHub',
            'item_type': 'workflow',
            'engine': 'Oracle',
            'integration_id': self.integration_github.id,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['platform'], 'GitHub Actions')

    def test_platform_auto_derived_azure_devops(self):
        """AC2: integration_id=azure_devops → platform='Azure DevOps' dérivé."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Azure',
            'item_type': 'workflow',
            'engine': 'Oracle',
            'integration_id': self.integration_azure.id,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['platform'], 'Azure DevOps')

    def test_platform_auto_derived_terraform_cloud(self):
        """AC2: integration_id=terraform_cloud → platform='Terraform' dérivé."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Terraform',
            'item_type': 'workflow',
            'engine': 'Oracle',
            'integration_id': self.integration_terraform.id,
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['platform'], 'Terraform')

    def test_platform_empty_when_no_integration(self):
        """AC2/AC3: pas d'integration_id → platform='' (acceptable pour les workflows)."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Workflow No Intg',
            'item_type': 'workflow',
            'engine': 'Oracle',
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['platform'], '')

    def test_action_type_requires_integration_for_platform(self):
        """AC2: item_type='action' sans integration_id → platform=None → erreur 'platform is required'."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Action No Intg',
            'item_type': 'action',
            'engine': 'Oracle',
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)
        self.assertIn('platform is required', str(serializer.errors['non_field_errors']))

    def test_service_integration_gives_none_platform(self):
        """AC2: integration service (servicenow) → platform=None → erreur pour action type."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Action Service Intg',
            'item_type': 'action',
            'engine': 'Oracle',
            'integration_id': self.integration_servicenow.id,
        })
        self.assertFalse(serializer.is_valid())
        # Platform sera None (servicenow pas dans le registry), donc "platform is required"
        self.assertIn('non_field_errors', serializer.errors)

    def test_vault_integration_gives_none_platform(self):
        """AC2: integration vault (service) → platform=None → erreur pour action type."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Action Vault',
            'item_type': 'action',
            'engine': 'Oracle',
            'integration_id': self.integration_vault.id,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('non_field_errors', serializer.errors)

    def test_integration_not_found_rejected(self):
        """AC2: integration_id inexistant → 400 integration_id."""
        serializer = ActionCreateSerializer(data={
            'name': 'Test Action',
            'item_type': 'action',
            'engine': 'Oracle',
            'integration_id': 99999,
        })
        self.assertFalse(serializer.is_valid())
        self.assertIn('integration_id', serializer.errors)

    def test_platform_field_in_payload_ignored(self):
        """AC2: platform envoyé dans le payload est ignoré — la valeur dérivée prend la priorité.

        Envoie platform='AAP' mais integration est github_actions : le backend doit dériver
        'GitHub Actions' depuis integration.type, ignorant la valeur client.
        """
        serializer = ActionCreateSerializer(data={
            'name': 'Test Workflow',
            'item_type': 'workflow',
            'engine': 'Oracle',
            'integration_id': self.integration_github.id,
            'platform': 'AAP',  # valeur client erronée — doit être ignorée
        })
        self.assertTrue(serializer.is_valid(), serializer.errors)
        # platform dérivé depuis integration.type='github_actions', pas depuis le payload client
        self.assertEqual(serializer.validated_data['platform'], 'GitHub Actions')
        self.assertNotEqual(serializer.validated_data['platform'], 'AAP')

    # ===== AC3: Update — platform recalculé si integration_id change =====

    def test_patch_integration_id_change_recalculates_platform(self):
        """AC3: PATCH avec nouveau integration_id → platform recalculée."""
        serializer = ActionCreateSerializer(
            data={
                'name': 'Updated',
                'integration_id': self.integration_github.id,
            },
            partial=True,
            context={'is_update': True, 'instance': ActionFactory(
                platform='AAP',
                engine='Oracle',
                integration=self.integration_aap,
                created_by=self.user,
            )},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data['platform'], 'GitHub Actions')

    def test_patch_without_integration_id_keeps_derived_platform(self):
        """AC3: PATCH sans integration_id → platform dérivée de l'integration existante."""
        existing_action = ActionFactory(
            platform='AAP',
            engine='Oracle',
            integration=self.integration_aap,
            created_by=self.user,
        )
        serializer = ActionCreateSerializer(
            data={'name': 'Updated Name'},
            context={'is_update': True, 'instance': existing_action},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        # Platform dérivée de l'integration existante (aap → 'AAP')
        self.assertEqual(serializer.validated_data['platform'], 'AAP')


@pytest.mark.django_db
class TestActionPlatformIntegrationE2E(TestCase):
    """E2E tests Story 83-13: création/mise à jour d'action sans envoyer platform."""

    def setUp(self):
        Profile.objects.get_or_create(
            name='DBOPS',
            defaults={'ad_group': 'CN=DBOPS,OU=Groups,DC=example,DC=com', 'is_admin': 1, 'is_auditor': 0},
        )
        self.client = APIClient()
        self.dbops_user = UserFactory(username='dbops_user', profile='DBOPS')
        self.client.force_authenticate(user=self.dbops_user)

        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)

        IntegrationTypeCatalogueFactory(
            code='aap', name='AAP', integration_role=IntegrationRole.PLATFORM,
        )
        IntegrationTypeCatalogueFactory(
            code='github_actions', name='GitHub Actions', integration_role=IntegrationRole.PLATFORM,
        )
        IntegrationTypeCatalogueFactory(
            code='servicenow', name='ServiceNow', integration_role=IntegrationRole.SERVICE,
        )

        self.integration_aap = IntegrationFactory(type='aap', name='Test AAP')
        self.integration_github = IntegrationFactory(type='github_actions', name='Test GitHub')
        self.integration_servicenow = IntegrationFactory(type='servicenow', name='Test SN')

    def test_e2e_create_workflow_with_integration_no_platform(self):
        """AC2 E2E: créer un workflow avec integration_id sans platform → 201, platform dérivé."""
        response = self.client.post('/api/v1/admin/actions/', {
            'name': 'AAP Workflow No Platform',
            'engine': 'Oracle',
            'item_type': 'workflow',
            'integration_id': self.integration_aap.id,
            # platform absent — doit être dérivé par le backend
        }, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_e2e_create_action_with_github_integration(self):
        """AC2 E2E: créer une action avec integration github_actions → 201, platform dérivé."""
        response = self.client.post('/api/v1/admin/actions/', {
            'name': 'GitHub Action No Platform',
            'engine': 'Oracle',
            'item_type': 'action',
            'integration_id': self.integration_github.id,
            # platform absent — doit être dérivé comme 'GitHub Actions'
        }, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_e2e_create_workflow_service_integration_ok(self):
        """AC2 E2E: workflow avec service integration → 201 (workflows n'exigent pas de platform)."""
        response = self.client.post('/api/v1/admin/actions/', {
            'name': 'SN Workflow',
            'engine': 'Oracle',
            'item_type': 'workflow',
            'integration_id': self.integration_servicenow.id,
        }, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)

    def test_e2e_create_action_service_integration_rejected(self):
        """AC2 E2E: action avec service integration → 400 (platform=None, requis pour action)."""
        response = self.client.post('/api/v1/admin/actions/', {
            'name': 'Service Mismatch Action',
            'engine': 'Oracle',
            'item_type': 'action',
            'integration_id': self.integration_servicenow.id,
        }, format='json')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
