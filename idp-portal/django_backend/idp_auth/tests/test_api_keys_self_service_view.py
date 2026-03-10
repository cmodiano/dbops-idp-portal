"""
Tests for self-service API keys endpoints (Story 44.7).
"""

import pytest
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from core.models import AuditLog, AuditActionType
from idp_auth.models import APIKey, APIKeyScope, User


@pytest.mark.django_db
class TestAPIKeysSelfServiceView(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(
            username='self.service.user',
            display_name='Self Service User',
            profile='dbops',
        )
        self.other_user = User.objects.create(
            username='other.user',
            display_name='Other User',
            profile='dba_applicatif',
        )

    def test_post_create_api_key_success_returns_raw_key_once(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            '/api/v1/auth/api-keys/',
            {'name': 'CI Pipeline', 'scope': APIKeyScope.EXECUTIONS},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()['data']
        self.assertIn('id', data)
        self.assertEqual(data['name'], 'CI Pipeline')
        self.assertEqual(data['scope'], APIKeyScope.EXECUTIONS)
        self.assertIn('created_at', data)
        self.assertIn('raw_key', data)
        self.assertTrue(data['raw_key'])

        instance = APIKey.objects.get(id=data['id'])
        self.assertEqual(instance.user_id, self.user.id)
        self.assertNotEqual(instance.key_hash, data['raw_key'])

    def test_post_create_api_key_invalid_scope_returns_400(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            '/api/v1/auth/api-keys/',
            {'name': 'Invalid scope key', 'scope': 'bad-scope'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['error']['code'], 'VALIDATION_ERROR')

    def test_post_create_api_key_empty_name_returns_400(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            '/api/v1/auth/api-keys/',
            {'name': '', 'scope': APIKeyScope.CATALOG},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()['error']['code'], 'VALIDATION_ERROR')

    def test_post_create_api_key_requires_authentication(self):
        response = self.client.post(
            '/api/v1/auth/api-keys/',
            {'name': 'No auth key', 'scope': APIKeyScope.FULL},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_post_create_api_key_enforces_max_5_active_keys(self):
        self.client.force_authenticate(user=self.user)

        for i in range(5):
            APIKey.objects.create_key(self.user, name=f'Key {i + 1}', scope=APIKeyScope.EXECUTIONS)

        response = self.client.post(
            '/api/v1/auth/api-keys/',
            {'name': 'Too many', 'scope': APIKeyScope.CATALOG},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.json()['error']['code'], 'API_KEY_LIMIT_REACHED')

    def test_get_list_api_keys_filters_by_user_and_hides_secret_fields(self):
        self.client.force_authenticate(user=self.user)

        own_active, _ = APIKey.objects.create_key(
            self.user,
            name='Own Active',
            scope=APIKeyScope.EXECUTIONS,
        )
        own_expired, _ = APIKey.objects.create_key(
            self.user,
            name='Own Expired',
            scope=APIKeyScope.CATALOG,
        )
        own_expired.expires_at = timezone.now() - timedelta(days=1)
        own_expired.save(update_fields=['expires_at'])

        other_user_key, _ = APIKey.objects.create_key(
            self.other_user,
            name='Other User Key',
            scope=APIKeyScope.FULL,
        )
        other_user_key.is_active = False
        other_user_key.save(update_fields=['is_active'])

        response = self.client.get('/api/v1/auth/api-keys/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        self.assertEqual(len(data), 2)
        names = {item['name'] for item in data}
        self.assertIn('Own Active', names)
        self.assertIn('Own Expired', names)
        self.assertNotIn('Other User Key', names)
        for item in data:
            self.assertNotIn('raw_key', item)
            self.assertNotIn('key_hash', item)
            self.assertIn(item['status'], {'active', 'expired'})

    def test_delete_api_key_success_soft_deletes(self):
        self.client.force_authenticate(user=self.user)
        api_key, _ = APIKey.objects.create_key(
            self.user,
            name='To revoke',
            scope=APIKeyScope.EXECUTIONS,
        )

        response = self.client.delete(f'/api/v1/auth/api-keys/{api_key.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        api_key.refresh_from_db()
        self.assertFalse(api_key.is_active)

    def test_delete_api_key_of_other_user_returns_403(self):
        self.client.force_authenticate(user=self.user)
        other_key, _ = APIKey.objects.create_key(
            self.other_user,
            name='Other secret key',
            scope=APIKeyScope.EXECUTIONS,
        )

        response = self.client.delete(f'/api/v1/auth/api-keys/{other_key.id}/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.json()['error']['code'], 'FORBIDDEN')

    def test_delete_api_key_not_found_returns_404(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.delete('/api/v1/auth/api-keys/999999/')

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # AUTH-HIGH-01: audit trail for API key creation (SOC1 compliance)
    def test_post_create_api_key_creates_audit_log_entry(self):
        """API key creation must produce an API_KEY_CREATED audit entry (SOC1).
        NEW-FIND-02: entity_id=user.id (entity_type=USER implies entity_id is the user).
        api_key_id is stored in details for traceability.
        """
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            '/api/v1/auth/api-keys/',
            {'name': 'Audit Trail Key', 'scope': APIKeyScope.EXECUTIONS},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        key_id = response.json()['data']['id']

        audit_entry = AuditLog.objects.filter(
            action_type=AuditActionType.API_KEY_CREATED,
            entity_id=self.user.id,
        ).first()
        self.assertIsNotNone(audit_entry, "API_KEY_CREATED audit entry must exist")
        self.assertEqual(audit_entry.user_id, str(self.user.id))
        details = audit_entry.get_details()
        self.assertEqual(details.get('key_name'), 'Audit Trail Key')
        self.assertEqual(details.get('scope'), APIKeyScope.EXECUTIONS)
        self.assertEqual(details.get('api_key_id'), key_id)

    # AUTH-HIGH-02: audit trail for API key revocation (SOC1 compliance)
    def test_delete_api_key_creates_audit_log_entry(self):
        """API key revocation must produce an API_KEY_REVOKED audit entry (SOC1).
        NEW-FIND-02: entity_id=user.id (entity_type=USER implies entity_id is the user).
        NEW-FIND-05: scope must be present in audit details.
        api_key_id is stored in details for traceability.
        """
        self.client.force_authenticate(user=self.user)
        api_key, _ = APIKey.objects.create_key(
            self.user,
            name='Key To Audit',
            scope=APIKeyScope.FULL,
        )

        response = self.client.delete(f'/api/v1/auth/api-keys/{api_key.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        audit_entry = AuditLog.objects.filter(
            action_type=AuditActionType.API_KEY_REVOKED,
            entity_id=self.user.id,
        ).first()
        self.assertIsNotNone(audit_entry, "API_KEY_REVOKED audit entry must exist")
        self.assertEqual(audit_entry.user_id, str(self.user.id))
        details = audit_entry.get_details()
        self.assertEqual(details.get('key_name'), 'Key To Audit')
        self.assertEqual(details.get('scope'), APIKeyScope.FULL)
        self.assertEqual(details.get('api_key_id'), api_key.id)

    # NEW-FIND-06: cas idempotent — révocation d'une clé déjà inactive
    def test_delete_already_inactive_api_key_creates_audit_log_entry(self):
        """Revoking an already-inactive key must still produce an API_KEY_REVOKED audit entry.
        Idempotent revoke is documented behavior — ensure audit trace exists.
        """
        self.client.force_authenticate(user=self.user)
        api_key, _ = APIKey.objects.create_key(
            self.user,
            name='Already Inactive Key',
            scope=APIKeyScope.EXECUTIONS,
        )
        api_key.is_active = False
        api_key.save(update_fields=['is_active', 'updated_at'])

        response = self.client.delete(f'/api/v1/auth/api-keys/{api_key.id}/')

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        audit_entry = AuditLog.objects.filter(
            action_type=AuditActionType.API_KEY_REVOKED,
            entity_id=self.user.id,
        ).first()
        self.assertIsNotNone(audit_entry, "API_KEY_REVOKED audit entry must exist even for idempotent revoke")
        details = audit_entry.get_details()
        self.assertEqual(details.get('key_name'), 'Already Inactive Key')
