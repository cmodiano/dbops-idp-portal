"""
Story 25.5: Mutex inter-actions - Admin API tests.

Tests for:
- GET /admin/actions/{id}/mutex/ - List mutex rules
- POST /admin/actions/{id}/mutex/ - Create mutex rule
- DELETE /admin/actions/{id}/mutex/{rule_id}/ - Delete mutex rule
"""
import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from catalog.models import Action, ActionStatus, ActionMutex
from idp_auth.models import User


@pytest.mark.django_db
class TestStory255AdminMutexAPI(TestCase):
    """Task 4.3: Admin API CRUD tests for mutex rules."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username='admin_mutex_user', profile='DBOPS')
        self.client.force_authenticate(user=self.user)
        
        # Create test actions
        self.action_patching = Action.objects.create(
            name='Patching Oracle',
            category='Patching',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            requires_target=True,
        )
        
        self.action_backup = Action.objects.create(
            name='Backup Database',
            category='Administration',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            requires_target=True,
        )
        
        self.action_monitoring = Action.objects.create(
            name='Health Check',
            category='Monitoring',
            engine='Oracle',
            platform='AAP',
            status=ActionStatus.PUBLISHED,
            requires_target=True,
        )

    def test_list_mutex_rules_empty(self):
        """GET /admin/actions/{id}/mutex/ with no rules returns empty list."""
        response = self.client.get(f'/api/v1/admin/actions/{self.action_patching.id}/mutex/')
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.data)
        self.assertEqual(len(response.data['data']), 0)

    def test_create_mutex_rule_same_target(self):
        """POST /admin/actions/{id}/mutex/ with same_target=True creates rule."""
        payload = {
            'incompatible_with_id': self.action_backup.id,
            'same_target': True,
            'description': 'Patching et backup ne peuvent pas tourner sur la même base'
        }
        
        response = self.client.post(
            f'/api/v1/admin/actions/{self.action_patching.id}/mutex/',
            payload,
            format='json'
        )
        
        self.assertEqual(response.status_code, 201)
        self.assertIn('data', response.data)
        data = response.data['data']
        self.assertEqual(data['action_id'], self.action_patching.id)
        self.assertEqual(data['incompatible_with_id'], self.action_backup.id)
        self.assertTrue(data['same_target'])
        self.assertEqual(data['description'], payload['description'])
        
        # Verify DB
        self.assertEqual(ActionMutex.objects.count(), 2)  # 2 because symmetric rule created

    def test_create_mutex_rule_global(self):
        """POST /admin/actions/{id}/mutex/ with same_target=False creates global mutex."""
        payload = {
            'incompatible_with_id': self.action_monitoring.id,
            'same_target': False,
        }
        
        response = self.client.post(
            f'/api/v1/admin/actions/{self.action_patching.id}/mutex/',
            payload,
            format='json'
        )
        
        self.assertEqual(response.status_code, 201)
        data = response.data['data']
        self.assertFalse(data['same_target'])
        
        # Verify symmetric rule created
        symmetric = ActionMutex.objects.filter(
            action_id=self.action_monitoring.id,
            incompatible_with=self.action_patching
        ).first()
        self.assertIsNotNone(symmetric)

    def test_create_mutex_rule_self_reference_rejected(self):
        """POST /admin/actions/{id}/mutex/ with self-reference returns 400."""
        payload = {
            'incompatible_with_id': self.action_patching.id,
            'same_target': True,
        }
        
        response = self.client.post(
            f'/api/v1/admin/actions/{self.action_patching.id}/mutex/',
            payload,
            format='json'
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('incompatible_with_id', response.data['error']['details'])

    def test_create_mutex_rule_duplicate_rejected(self):
        """POST /admin/actions/{id}/mutex/ with duplicate rule returns 400."""
        # Create first rule
        ActionMutex.objects.create(
            action=self.action_patching,
            incompatible_with=self.action_backup,
            same_target=True,
        )
        
        # Attempt duplicate
        payload = {
            'incompatible_with_id': self.action_backup.id,
            'same_target': True,
        }
        
        response = self.client.post(
            f'/api/v1/admin/actions/{self.action_patching.id}/mutex/',
            payload,
            format='json'
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertIn('incompatible_with_id', response.data['error']['details'])

    def test_create_mutex_rule_disabled_action_rejected(self):
        """POST /admin/actions/{id}/mutex/ with disabled action returns 400."""
        from django.utils import timezone
        self.action_backup.status = ActionStatus.DISABLED
        self.action_backup.deleted_at = timezone.now()
        self.action_backup.deleted_by = self.user
        self.action_backup.deletion_reason = 'Test soft delete'
        self.action_backup.save()
        
        payload = {
            'incompatible_with_id': self.action_backup.id,
            'same_target': True,
        }
        
        response = self.client.post(
            f'/api/v1/admin/actions/{self.action_patching.id}/mutex/',
            payload,
            format='json'
        )
        
        self.assertEqual(response.status_code, 400)

    def test_create_mutex_rule_nonexistent_action_rejected(self):
        """POST /admin/actions/{id}/mutex/ with non-existent action returns 400."""
        payload = {
            'incompatible_with_id': 99999,
            'same_target': True,
        }
        
        response = self.client.post(
            f'/api/v1/admin/actions/{self.action_patching.id}/mutex/',
            payload,
            format='json'
        )
        
        self.assertEqual(response.status_code, 400)

    def test_list_mutex_rules_includes_both_directions(self):
        """GET /admin/actions/{id}/mutex/ returns rules where action is on either side."""
        # Create rule A→B
        ActionMutex.objects.create(
            action=self.action_patching,
            incompatible_with=self.action_backup,
            same_target=True,
        )
        
        # Create rule C→A
        ActionMutex.objects.create(
            action=self.action_monitoring,
            incompatible_with=self.action_patching,
            same_target=False,
        )
        
        response = self.client.get(f'/api/v1/admin/actions/{self.action_patching.id}/mutex/')
        
        self.assertEqual(response.status_code, 200)
        data = response.data['data']
        self.assertEqual(len(data), 2)
        
        # Verify both rules present
        action_ids = [r['action_id'] for r in data]
        self.assertIn(self.action_patching.id, action_ids)
        self.assertIn(self.action_monitoring.id, action_ids)

    def test_delete_mutex_rule_success(self):
        """DELETE /admin/actions/{id}/mutex/{rule_id}/ deletes rule and symmetric."""
        # Create rule A→B (with symmetric B→A)
        rule_ab = ActionMutex.objects.create(
            action=self.action_patching,
            incompatible_with=self.action_backup,
            same_target=True,
        )
        ActionMutex.objects.create(
            action=self.action_backup,
            incompatible_with=self.action_patching,
            same_target=True,
        )
        
        self.assertEqual(ActionMutex.objects.count(), 2)
        
        response = self.client.delete(
            f'/api/v1/admin/actions/{self.action_patching.id}/mutex/{rule_ab.id}/'
        )
        
        self.assertEqual(response.status_code, 204)
        
        # Verify both rules deleted
        self.assertEqual(ActionMutex.objects.count(), 0)

    def test_delete_mutex_rule_not_found(self):
        """DELETE /admin/actions/{id}/mutex/{rule_id}/ with wrong action returns 404."""
        rule = ActionMutex.objects.create(
            action=self.action_backup,
            incompatible_with=self.action_monitoring,
            same_target=True,
        )
        
        # Try to delete from wrong action
        response = self.client.delete(
            f'/api/v1/admin/actions/{self.action_patching.id}/mutex/{rule.id}/'
        )
        
        self.assertEqual(response.status_code, 404)
        self.assertEqual(ActionMutex.objects.count(), 1)  # Rule still exists

    def test_mutex_api_requires_authentication(self):
        """Mutex API endpoints require authentication."""
        self.client.force_authenticate(user=None)
        
        response = self.client.get(f'/api/v1/admin/actions/{self.action_patching.id}/mutex/')
        self.assertEqual(response.status_code, 401)
        
        response = self.client.post(f'/api/v1/admin/actions/{self.action_patching.id}/mutex/', {}, format='json')
        self.assertEqual(response.status_code, 401)
