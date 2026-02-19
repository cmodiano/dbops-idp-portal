"""
Story 28.4: Tests for BusinessRulePolicy CRUD API (AC#4, AC#9).
"""
import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from tests.factories import UserFactory
from catalog.models import BusinessRulePolicy, Action
from core.models import AuditLog, AuditActionType


VALID_POLICY_JSON = {
    "on_step_output": [
        {
            "when": {"step_type": "terraform_cloud"},
            "policy": {
                "type": "review_if_modified",
                "require_review_if_modified": [
                    {"resource_type": "azurerm_mssql_database", "attribute_paths": ["sku_name"]}
                ],
                "auto_approve_if_none_match": True,
            },
        }
    ]
}

INVALID_POLICY_JSON = {
    "on_step_output": "not_a_list"  # Must be a list
}

AAP_POLICY_JSON = {
    "on_step_output": [
        {
            "when": {"step_type": "aap"},
            "policy": {
                "type": "review_if_modified",
                "require_review_if_modified": [
                    {"resource_type": "host", "attribute_paths": ["status"]}
                ],
                "auto_approve_if_none_match": False,
            },
        }
    ]
}


@pytest.mark.django_db
class TestBusinessRulePolicyAPI(TestCase):
    """Tests for CRUD operations on BusinessRulePolicy (AC#4, AC#9)."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = UserFactory(username='admin_brp', profile='DBOPS')
        self.regular_user = UserFactory(username='regular_brp', profile='readonly')
        self.url = '/api/v1/admin/business-rule-policies/'
        self.client.force_authenticate(user=self.admin_user)

    def _create_policy(self, name='Test Terraform Policy', policy_json=None, is_active=True):
        """Helper to create a BusinessRulePolicy."""
        return BusinessRulePolicy.objects.create(
            name=name,
            description='Test policy description',
            policy_json=policy_json or VALID_POLICY_JSON,
            is_active=is_active,
            created_by=self.admin_user,
        )

    def test_create_business_rule_policy(self):
        """POST /api/v1/admin/business-rule-policies/ → 201 + audit trail."""
        response = self.client.post(self.url, {
            'name': 'Revue Terraform SQL sku_name',
            'description': 'Revue si plan Terraform modifie sku_name',
            'policy_json': VALID_POLICY_JSON,
            'is_active': True,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.data['data']
        self.assertEqual(data['name'], 'Revue Terraform SQL sku_name')
        self.assertEqual(data['step_type'], 'terraform_cloud')
        self.assertTrue(data['is_active'])

        # Verify audit trail
        audit = AuditLog.objects.filter(
            action_type=AuditActionType.POLICY_CREATED
        ).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.entity_id, data['id'])

    def test_create_invalid_policy_json(self):
        """POST with invalid JSON → 400 with validation errors."""
        response = self.client.post(self.url, {
            'name': 'Invalid Policy',
            'policy_json': INVALID_POLICY_JSON,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_business_rule_policies(self):
        """GET → 200 with paginated list."""
        self._create_policy(name='Policy 1')
        self._create_policy(name='Policy 2', policy_json=AAP_POLICY_JSON)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Paginated response (CustomPageNumberPagination)
        self.assertIn('data', response.data)
        self.assertEqual(len(response.data['data']), 2)

    def test_filter_by_step_type(self):
        """GET ?step_type=terraform_cloud → filtered."""
        self._create_policy(name='Terraform Policy')
        self._create_policy(name='AAP Policy', policy_json=AAP_POLICY_JSON)

        response = self.client.get(f'{self.url}?step_type=terraform_cloud')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['data']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['step_type'], 'terraform_cloud')

    def test_filter_by_platform(self):
        """GET ?platform=AAP → maps to step_type=aap and returns matching policies."""
        self._create_policy(name='Terraform Policy')
        self._create_policy(name='AAP Policy', policy_json=AAP_POLICY_JSON)

        response = self.client.get(f'{self.url}?platform=AAP')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['data']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['step_type'], 'aap')
        self.assertEqual(results[0]['name'], 'AAP Policy')

    def test_filter_by_is_active(self):
        """GET ?is_active=true → active only."""
        self._create_policy(name='Active Policy', is_active=True)
        self._create_policy(name='Inactive Policy', is_active=False)

        response = self.client.get(f'{self.url}?is_active=true')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data['data']
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]['is_active'])

    def test_update_business_rule_policy(self):
        """PATCH → 200 + audit trail."""
        policy = self._create_policy()

        response = self.client.patch(
            f'{self.url}{policy.id}/',
            {'name': 'Updated Policy Name', 'is_active': False},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data['data']
        self.assertEqual(data['name'], 'Updated Policy Name')
        self.assertFalse(data['is_active'])

        # Verify audit trail
        audit = AuditLog.objects.filter(
            action_type=AuditActionType.POLICY_UPDATED
        ).first()
        self.assertIsNotNone(audit)

    def test_delete_business_rule_policy(self):
        """DELETE → 204 + audit trail."""
        policy = self._create_policy()

        response = self.client.delete(f'{self.url}{policy.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(BusinessRulePolicy.objects.filter(id=policy.id).exists())

        # Verify audit trail
        audit = AuditLog.objects.filter(
            action_type=AuditActionType.POLICY_DELETED
        ).first()
        self.assertIsNotNone(audit)

    def test_permissions_dbops_only(self):
        """Non-DBOPS → 403 Forbidden."""
        self.client.force_authenticate(user=self.regular_user)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_business_rule_policy(self):
        """GET /api/v1/admin/business-rule-policies/{id}/ → 200."""
        policy = self._create_policy()

        response = self.client.get(f'{self.url}{policy.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data['data']
        self.assertEqual(data['name'], policy.name)
        self.assertEqual(data['policy_json'], VALID_POLICY_JSON)
        self.assertIn('actions_count', data)

    def test_unique_name_constraint(self):
        """POST with duplicate name → 400."""
        self._create_policy(name='Unique Policy')

        response = self.client.post(self.url, {
            'name': 'Unique Policy',
            'policy_json': VALID_POLICY_JSON,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@pytest.mark.django_db
class TestActionWithBusinessRulePolicy(TestCase):
    """Tests for Action model with FK business_rule_policy_id (AC#5, AC#9)."""

    def setUp(self):
        self.client = APIClient()
        self.user = UserFactory(username='action_brp_user', profile='DBOPS')
        self.client.force_authenticate(user=self.user)

    def _create_policy(self, name='Test Policy', is_active=True):
        return BusinessRulePolicy.objects.create(
            name=name,
            policy_json=VALID_POLICY_JSON,
            is_active=is_active,
            created_by=self.user,
        )

    def test_action_with_predefined_policy(self):
        """Action with FK → effective_business_rule_policies returns policy_json."""
        policy = self._create_policy()
        action = Action.objects.create(
            name='Action with FK policy',
            engine='oracle',
            platform='AAP',
            business_rule_policy=policy,
            created_by=self.user,
        )
        self.assertEqual(action.effective_business_rule_policies, VALID_POLICY_JSON)

    def test_action_with_inline_policy(self):
        """Action with inline → effective_business_rule_policies returns inline JSON."""
        action = Action.objects.create(
            name='Action with inline policy',
            engine='oracle',
            platform='AAP',
            business_rule_policies=VALID_POLICY_JSON,
            created_by=self.user,
        )
        self.assertEqual(action.effective_business_rule_policies, VALID_POLICY_JSON)

    def test_action_with_no_policy(self):
        """Action without rule → effective_business_rule_policies returns None."""
        action = Action.objects.create(
            name='Action without policy',
            engine='oracle',
            platform='AAP',
            created_by=self.user,
        )
        self.assertIsNone(action.effective_business_rule_policies)

    def test_action_with_inactive_policy(self):
        """Action with FK to inactive policy → effective_business_rule_policies returns None."""
        policy = self._create_policy(is_active=False)
        action = Action.objects.create(
            name='Action with inactive FK',
            engine='oracle',
            platform='AAP',
            business_rule_policy=policy,
            created_by=self.user,
        )
        self.assertIsNone(action.effective_business_rule_policies)

    def test_action_with_both_policies_fails_validation(self):
        """Action with both FK and inline → ValidationError."""
        policy = self._create_policy()
        action = Action(
            name='Action with both',
            engine='oracle',
            platform='AAP',
            business_rule_policy=policy,
            business_rule_policies=VALID_POLICY_JSON,
            created_by=self.user,
        )
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            action.clean()

    def test_patch_action_with_predefined_policy(self):
        """PATCH /api/v1/admin/actions/{id}/ with business_rule_policy_id."""
        policy = self._create_policy()
        action = Action.objects.create(
            name='Action to patch FK',
            engine='oracle',
            platform='AAP',
            created_by=self.user,
        )

        response = self.client.patch(
            f'/api/v1/admin/actions/{action.id}/',
            {'business_rule_policy_id': policy.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        action.refresh_from_db()
        self.assertEqual(action.business_rule_policy_id, policy.id)
        self.assertIsNone(action.business_rule_policies)

    def test_patch_action_clears_fk_when_inline_set(self):
        """PATCH with business_rule_policies clears business_rule_policy_id."""
        policy = self._create_policy()
        action = Action.objects.create(
            name='Action to switch to inline',
            engine='oracle',
            platform='AAP',
            business_rule_policy=policy,
            created_by=self.user,
        )

        response = self.client.patch(
            f'/api/v1/admin/actions/{action.id}/',
            {'business_rule_policies': AAP_POLICY_JSON},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        action.refresh_from_db()
        self.assertIsNone(action.business_rule_policy_id)
        self.assertEqual(action.business_rule_policies, AAP_POLICY_JSON)
