"""
Story 28.1: business_rule_policies API tests (AC3, AC7).

Tests for PATCH /admin/actions/{id}/ with business_rule_policies field:
- Valid business_rule_policies → 200 + persisted
- Invalid schema → 400 + validation errors
- Null → 200 (optional field)
- GET /admin/actions/{id}/ returns business_rule_policies
"""
import pytest
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from catalog.models import ActionStatus, ActionItemType, ActionEngine, ActionPlatform
from catalog.services import CatalogService
from reference.models import RefEngine
from integrations.models import IntegrationTypeCatalogue, IntegrationRole
from tests.factories import UserFactory


VALID_TERRAFORM_POLICY = {
    "on_step_output": [
        {
            "when": {
                "step_type": "terraform_cloud",
                "output_key": "plan_output"
            },
            "policy": {
                "type": "review_if_modified",
                "require_review_if_modified": [
                    {
                        "resource_type": "azurerm_sql_database",
                        "attribute_paths": ["sku_name", "max_size_gb"]
                    },
                    {
                        "resource_type": "azurerm_sql_server"
                    },
                    {
                        "attribute_paths": ["backup_retention_days"]
                    }
                ],
                "auto_approve_if_none_match": True
            }
        }
    ]
}


@pytest.mark.django_db
class TestBusinessRulePoliciesAPI(TestCase):
    """Tests for PATCH /admin/actions/{id}/ endpoint with business_rule_policies (Story 28.1 AC3)."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create reference data
        RefEngine.objects.get_or_create(code='Oracle', defaults={'label': 'Oracle', 'display_order': 1})
        IntegrationTypeCatalogue.objects.get_or_create(code='aap', defaults={'name': 'AAP', 'integration_role': IntegrationRole.PLATFORM, 'is_active': True})

        # Create DBOPS user
        self.dbops_user = UserFactory(username='dbops_brp', profile='dbops')

        # Create test action
        service = CatalogService()
        action_data = {
            'name': 'BRP Test Action',
            'description': 'Test for business rule policies',
            'engine': ActionEngine.ORACLE,
            'platform': ActionPlatform.AAP,
            'status': ActionStatus.DRAFT,
            'item_type': ActionItemType.ACTION,
        }
        self.action = service.create_action(action_data, self.dbops_user)
        self.url = f'/api/v1/admin/actions/{self.action.id}/'

        self.client.force_authenticate(user=self.dbops_user)

    def test_patch_business_rule_policies_valid(self):
        """PATCH with valid business_rule_policies → 200 + persisted (Story 28.1 AC3)."""
        response = self.client.patch(
            self.url,
            {'business_rule_policies': VALID_TERRAFORM_POLICY},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify persisted
        self.action.refresh_from_db()
        self.assertIsNotNone(self.action.business_rule_policies)
        self.assertEqual(
            self.action.business_rule_policies['on_step_output'][0]['when']['step_type'],
            'terraform_cloud'
        )

    def test_patch_business_rule_policies_invalid_schema(self):
        """PATCH with invalid schema → 400 + validation error details."""
        invalid_policy = {
            "on_step_output": [
                {
                    # Missing 'when' key
                    "policy": {
                        "type": "review_if_modified",
                        "require_review_if_modified": []
                    }
                }
            ]
        }
        response = self.client.patch(
            self.url,
            {'business_rule_policies': invalid_policy},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_business_rule_policies_null(self):
        """PATCH with null → 200 (optional field)."""
        # First set a value
        self.action.business_rule_policies = VALID_TERRAFORM_POLICY
        self.action.save()

        # Then set to null
        response = self.client.patch(
            self.url,
            {'business_rule_policies': None},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify cleared
        self.action.refresh_from_db()
        self.assertIsNone(self.action.business_rule_policies)

    def test_put_business_rule_policies_endpoint(self):
        """PUT /admin/actions/{id}/business-rule-policies/ → 200 + persisted (Story 28.1)."""
        put_url = f'/api/v1/admin/actions/{self.action.id}/business-rule-policies/'
        response = self.client.put(
            put_url,
            {'business_rule_policies': VALID_TERRAFORM_POLICY},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.action.refresh_from_db()
        self.assertIsNone(self.action.business_rule_policy_id)
        self.assertIsNotNone(self.action.business_rule_policies)
        self.assertEqual(
            self.action.business_rule_policies['on_step_output'][0]['when']['step_type'],
            'terraform_cloud'
        )

    def test_put_business_rule_policies_endpoint_clear(self):
        """PUT /admin/actions/{id}/business-rule-policies/ with null → 200 + cleared."""
        self.action.business_rule_policies = VALID_TERRAFORM_POLICY
        self.action.save()

        put_url = f'/api/v1/admin/actions/{self.action.id}/business-rule-policies/'
        response = self.client.put(
            put_url,
            {'business_rule_policies': None},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.action.refresh_from_db()
        self.assertIsNone(self.action.business_rule_policies)

    def test_get_action_includes_business_rule_policies(self):
        """GET /admin/actions/{id}/ returns business_rule_policies in response."""
        # Set business_rule_policies
        self.action.business_rule_policies = VALID_TERRAFORM_POLICY
        self.action.save()

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        action_data = response.data.get('data', response.data)
        self.assertIn('business_rule_policies', action_data)
        self.assertEqual(
            action_data['business_rule_policies']['on_step_output'][0]['when']['step_type'],
            'terraform_cloud'
        )

    def test_get_action_business_rule_policies_null(self):
        """GET /admin/actions/{id}/ returns null when business_rule_policies not set."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        action_data = response.data.get('data', response.data)
        self.assertIn('business_rule_policies', action_data)
        self.assertIsNone(action_data['business_rule_policies'])

    def test_patch_requires_authentication(self):
        """PATCH without auth → 401."""
        self.client.logout()
        response = self.client.patch(
            self.url,
            {'business_rule_policies': VALID_TERRAFORM_POLICY},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_requires_dbops_profile(self):
        """PATCH with non-DBOPS user → 403."""
        regular_user = UserFactory(username='regular_brp', profile='dba')
        self.client.force_authenticate(user=regular_user)
        response = self.client.patch(
            self.url,
            {'business_rule_policies': VALID_TERRAFORM_POLICY},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patch_invalid_missing_policy_type(self):
        """PATCH with missing policy.type → 400."""
        invalid_policy = {
            "on_step_output": [
                {
                    "when": {"step_type": "terraform_cloud"},
                    "policy": {
                        "require_review_if_modified": [
                            {"resource_type": "azurerm_sql_database"}
                        ]
                    }
                }
            ]
        }
        response = self.client.patch(
            self.url,
            {'business_rule_policies': invalid_policy},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_empty_dict_clears_policies(self):
        """PATCH with {} → 200 (empty dict treated as no policies)."""
        self.action.business_rule_policies = VALID_TERRAFORM_POLICY
        self.action.save()

        response = self.client.patch(
            self.url,
            {'business_rule_policies': {}},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_patch_empty_on_step_output(self):
        """PATCH with empty on_step_output array → 200."""
        response = self.client.patch(
            self.url,
            {'business_rule_policies': {"on_step_output": []}},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
