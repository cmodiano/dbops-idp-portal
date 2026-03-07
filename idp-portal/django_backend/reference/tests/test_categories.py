"""
Tests for RefCategory model and API views.
Story 2.30 - Categories: define on action and manage admin.
"""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from reference.models import RefCategory
from idp_auth.models import User
from profiles.models import Profile


class RefCategoryModelTests(TestCase):
    """Tests for RefCategory model (Task 14.1)."""

    def test_create_category(self):
        cat = RefCategory.objects.create(
            code='patching', label='Correctifs', display_order=20, is_active=1
        )
        self.assertEqual(cat.code, 'patching')
        self.assertEqual(cat.label, 'Correctifs')
        self.assertEqual(cat.display_order, 20)
        self.assertEqual(cat.is_active, 1)

    def test_category_unique_code(self):
        RefCategory.objects.create(code='patching', label='Correctifs', display_order=20, is_active=1)
        with self.assertRaises(Exception):
            RefCategory.objects.create(code='patching', label='Patches', display_order=21, is_active=1)

    def test_active_queryset(self):
        RefCategory.objects.create(code='patching', label='Correctifs', display_order=20, is_active=1)
        RefCategory.objects.create(code='deprecated', label='Obsolète', display_order=99, is_active=0)
        active = RefCategory.objects.active()
        self.assertEqual(active.count(), 1)
        self.assertEqual(active.first().code, 'patching')

    def test_ordered_queryset(self):
        RefCategory.objects.create(code='monitoring', label='Surveillance', display_order=40, is_active=1)
        RefCategory.objects.create(code='patching', label='Correctifs', display_order=20, is_active=1)
        RefCategory.objects.create(code='provisioning', label='Approvisionnement', display_order=10, is_active=1)
        ordered = RefCategory.objects.ordered()
        codes = [c.code for c in ordered]
        self.assertEqual(codes, ['provisioning', 'patching', 'monitoring'])

    def test_str_representation(self):
        cat = RefCategory.objects.create(code='backup', label='Sauvegarde', display_order=50, is_active=1)
        self.assertEqual(str(cat), "backup (active)")
        cat.is_active = 0
        cat.save()
        self.assertEqual(str(cat), "backup (inactive)")


class RefCategoriesListAPITests(TestCase):
    """Tests for GET /api/v1/reference/categories (Task 14.2)."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create(username='testuser', profile='DBA')
        self.client.force_authenticate(user=self.user)
        RefCategory.objects.create(code='patching', label='Correctifs', display_order=20, is_active=1)
        RefCategory.objects.create(code='provisioning', label='Approvisionnement', display_order=10, is_active=1)
        RefCategory.objects.create(code='deprecated', label='Obsolète', display_order=99, is_active=0)

    def test_list_active_only_default(self):
        response = self.client.get('/api/v1/reference/categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)
        data = response.data['data']
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)
        codes = [c['code'] for c in data]
        self.assertNotIn('deprecated', codes)

    def test_list_all_including_inactive(self):
        response = self.client.get('/api/v1/reference/categories/?active_only=false')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 3)

    def test_list_ordered_by_display_order(self):
        response = self.client.get('/api/v1/reference/categories/')
        codes = [c['code'] for c in response.data['data']]
        self.assertEqual(codes, ['provisioning', 'patching'])

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/v1/reference/categories/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_serializer_fields(self):
        response = self.client.get('/api/v1/reference/categories/')
        cat = response.data['data'][0]
        for field in ['id', 'code', 'label', 'display_order', 'is_active']:
            self.assertIn(field, cat)


class RefCategoriesCRUDAPITests(TestCase):
    """Tests for POST/PATCH/DELETE /api/v1/admin/categories (Task 14.3, 14.4)."""

    def setUp(self):
        Profile.objects.get_or_create(
            name='DBOPS',
            defaults={'ad_group': 'CN=DBOPS,OU=Groups,DC=example,DC=com', 'is_admin': 1, 'is_auditor': 0},
        )
        Profile.objects.get_or_create(
            name='DBA',
            defaults={'ad_group': 'CN=DBA,OU=Groups,DC=example,DC=com', 'is_admin': 0, 'is_auditor': 0},
        )
        self.client = APIClient()
        self.dbops_user = User.objects.create(username='dbops', profile='DBOPS')
        self.regular_user = User.objects.create(username='regular', profile='DBA')
        self.client.force_authenticate(user=self.dbops_user)

    def test_create_category(self):
        response = self.client.post('/api/v1/admin/categories/', {
            'code': 'backup',
            'label': 'Sauvegarde',
            'display_order': 50,
            'is_active': 1,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['data']['code'], 'backup')
        self.assertEqual(response.data['data']['label'], 'Sauvegarde')
        self.assertTrue(RefCategory.objects.filter(code='backup').exists())

    def test_create_requires_dbops(self):
        """DBA (is_admin=0) gets 403 on admin endpoints."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post('/api/v1/admin/categories/', {
            'code': 'test', 'label': 'Test', 'display_order': 0, 'is_active': 1,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_invalid_code_uppercase(self):
        response = self.client.post('/api/v1/admin/categories/', {
            'code': 'Backup', 'label': 'Sauvegarde', 'display_order': 50, 'is_active': 1,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_invalid_code_spaces(self):
        response = self.client.post('/api/v1/admin/categories/', {
            'code': 'back up', 'label': 'Sauvegarde', 'display_order': 50, 'is_active': 1,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_duplicate_code(self):
        RefCategory.objects.create(code='backup', label='Sauvegarde', display_order=50, is_active=1)
        response = self.client.post('/api/v1/admin/categories/', {
            'code': 'backup', 'label': 'Autre', 'display_order': 51, 'is_active': 1,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_category(self):
        cat = RefCategory.objects.create(code='backup', label='Sauvegarde', display_order=50, is_active=1)
        response = self.client.patch(f'/api/v1/admin/categories/{cat.id}/', {
            'label': 'Sauvegarde & Restauration',
            'display_order': 55,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['label'], 'Sauvegarde & Restauration')
        self.assertEqual(response.data['data']['display_order'], 55)

    def test_update_requires_dbops(self):
        """DBA gets 403 on admin endpoints."""
        cat = RefCategory.objects.create(code='backup', label='Sauvegarde', display_order=50, is_active=1)
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.patch(f'/api/v1/admin/categories/{cat.id}/', {
            'label': 'Hack',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_not_found(self):
        response = self.client.patch('/api/v1/admin/categories/99999/', {
            'label': 'Nope',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_soft_deletes(self):
        cat = RefCategory.objects.create(code='backup', label='Sauvegarde', display_order=50, is_active=1)
        response = self.client.delete(f'/api/v1/admin/categories/{cat.id}/delete/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        cat.refresh_from_db()
        self.assertEqual(cat.is_active, 0)  # Soft deleted, not removed

    def test_delete_requires_dbops(self):
        cat = RefCategory.objects.create(code='backup', label='Sauvegarde', display_order=50, is_active=1)
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.delete(f'/api/v1/admin/categories/{cat.id}/delete/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_not_found(self):
        response = self.client.delete('/api/v1/admin/categories/99999/delete/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_negative_display_order_rejected(self):
        response = self.client.post('/api/v1/admin/categories/', {
            'code': 'test', 'label': 'Test', 'display_order': -1, 'is_active': 1,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ActionSerializerCategoryValidationTests(TestCase):
    """Tests for ActionSerializer.validate_category (Task 14.5)."""

    def setUp(self):
        Profile.objects.get_or_create(
            name='DBOPS',
            defaults={'ad_group': 'CN=DBOPS,OU=Groups,DC=example,DC=com', 'is_admin': 1, 'is_auditor': 0},
        )
        Profile.objects.get_or_create(
            name='DBA',
            defaults={'ad_group': 'CN=DBA,OU=Groups,DC=example,DC=com', 'is_admin': 0, 'is_auditor': 0},
        )
        self.client = APIClient()
        self.user = User.objects.create(username='dbops', profile='DBOPS')
        self.client.force_authenticate(user=self.user)
        RefCategory.objects.create(code='patching', label='Correctifs', display_order=20, is_active=1)
        RefCategory.objects.create(code='deprecated', label='Obsolète', display_order=99, is_active=0)

    def test_create_action_with_valid_category(self):
        """Creating an action with a valid active category code should succeed."""
        from reference.models import RefEngine
        from integrations.models import IntegrationTypeCatalogue, IntegrationRole
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)
        IntegrationTypeCatalogue.objects.get_or_create(code='aap', defaults={'name': 'AAP', 'integration_role': IntegrationRole.PLATFORM, 'is_active': True})

        response = self.client.post('/api/v1/admin/actions/', {
            'name': 'Test Action Category',
            'description': 'Test',
            'item_type': 'action',
            'category': 'patching',
            'engine': 'Oracle',
            'platform': 'AAP',
        }, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

    def test_create_action_with_invalid_category(self):
        """Creating an action with a non-existent category should fail."""
        from reference.models import RefEngine
        from integrations.models import IntegrationTypeCatalogue, IntegrationRole
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)
        IntegrationTypeCatalogue.objects.get_or_create(code='aap', defaults={'name': 'AAP', 'integration_role': IntegrationRole.PLATFORM, 'is_active': True})

        response = self.client.post('/api/v1/admin/actions/', {
            'name': 'Test Action Bad Category',
            'description': 'Test',
            'item_type': 'action',
            'category': 'nonexistent',
            'engine': 'Oracle',
            'platform': 'AAP',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_action_with_inactive_category(self):
        """Creating an action with an inactive category should fail."""
        from reference.models import RefEngine
        from integrations.models import IntegrationTypeCatalogue, IntegrationRole
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)
        IntegrationTypeCatalogue.objects.get_or_create(code='aap', defaults={'name': 'AAP', 'integration_role': IntegrationRole.PLATFORM, 'is_active': True})

        response = self.client.post('/api/v1/admin/actions/', {
            'name': 'Test Action Inactive Category',
            'description': 'Test',
            'item_type': 'action',
            'category': 'deprecated',
            'engine': 'Oracle',
            'platform': 'AAP',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_action_with_null_category(self):
        """Creating an action with null category should succeed (optional)."""
        from reference.models import RefEngine
        from integrations.models import IntegrationTypeCatalogue, IntegrationRole
        RefEngine.objects.create(code='Oracle', label='Oracle', display_order=1, is_active=1)
        IntegrationTypeCatalogue.objects.get_or_create(code='aap', defaults={'name': 'AAP', 'integration_role': IntegrationRole.PLATFORM, 'is_active': True})

        response = self.client.post('/api/v1/admin/actions/', {
            'name': 'Test Action No Category',
            'description': 'Test',
            'item_type': 'action',
            'engine': 'Oracle',
            'platform': 'AAP',
        }, format='json')
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
