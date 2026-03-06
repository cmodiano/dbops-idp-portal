"""
Tests for RefEngine admin API (Story 31.3).
AC5: Persistance icon_url, exposition API, endpoint admin PATCH.
AC6: PATCH /api/v1/admin/engines/{pk}/ — DBOPS only.
"""

from rest_framework.test import APITestCase
from rest_framework import status

from reference.models import RefEngine
from idp_auth.models import User
from profiles.models import Profile


class RefEngineAdminPatchTests(APITestCase):
    """Tests for PATCH /api/v1/admin/engines/{pk}/ (AC6)."""

    def setUp(self):
        Profile.objects.get_or_create(
            name='DBOPS',
            defaults={'ad_group': 'CN=DBOPS,OU=Groups,DC=example,DC=com', 'is_admin': 1, 'is_auditor': 0},
        )
        Profile.objects.get_or_create(
            name='DBA',
            defaults={'ad_group': 'CN=DBA,OU=Groups,DC=example,DC=com', 'is_admin': 0, 'is_auditor': 0},
        )
        self.dbops_user = User.objects.create(username='dbops', profile='DBOPS')
        self.regular_user = User.objects.create(username='regular', profile='DBA')
        self.engine = RefEngine.objects.create(
            code='TEST_ENGINE', label='Test Engine', display_order=99, is_active=1
        )

    def test_patch_icon_url_success(self):
        """DBOPS peut mettre à jour icon_url (AC1, AC6)."""
        self.client.force_authenticate(self.dbops_user)
        response = self.client.patch(
            f'/api/v1/admin/engines/{self.engine.pk}/',
            {'icon_url': 'https://example.com/icon.svg'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.engine.refresh_from_db()
        self.assertEqual(self.engine.icon_url, 'https://example.com/icon.svg')

    def test_patch_icon_url_returned_in_response(self):
        """La réponse PATCH contient icon_url mis à jour."""
        self.client.force_authenticate(self.dbops_user)
        response = self.client.patch(
            f'/api/v1/admin/engines/{self.engine.pk}/',
            {'icon_url': '/icons/engines/test.svg'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['icon_url'], '/icons/engines/test.svg')

    def test_patch_label_and_display_order(self):
        """DBOPS peut mettre à jour label et display_order."""
        self.client.force_authenticate(self.dbops_user)
        response = self.client.patch(
            f'/api/v1/admin/engines/{self.engine.pk}/',
            {'label': 'New Label', 'display_order': 42},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.engine.refresh_from_db()
        self.assertEqual(self.engine.label, 'New Label')
        self.assertEqual(self.engine.display_order, 42)

    def test_patch_forbidden_for_non_dbops(self):
        """Non-DBOPS → 403 (AC6)."""
        self.client.force_authenticate(self.regular_user)
        response = self.client.patch(
            f'/api/v1/admin/engines/{self.engine.pk}/',
            {'icon_url': 'https://example.com/icon.svg'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_patch_unauthenticated(self):
        """Utilisateur non authentifié → 401."""
        response = self.client.patch(
            f'/api/v1/admin/engines/{self.engine.pk}/',
            {'icon_url': 'https://example.com/icon.svg'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_patch_engine_not_found(self):
        """Moteur inexistant → 404."""
        self.client.force_authenticate(self.dbops_user)
        response = self.client.patch(
            '/api/v1/admin/engines/99999/',
            {'icon_url': 'https://example.com/icon.svg'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_icon_url_too_long(self):
        """icon_url > 500 chars → 400 (AC5 — validation)."""
        self.client.force_authenticate(self.dbops_user)
        long_url = 'https://example.com/' + 'a' * 500
        response = self.client.patch(
            f'/api/v1/admin/engines/{self.engine.pk}/',
            {'icon_url': long_url},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_icon_url_clear_to_empty(self):
        """Envoyer icon_url vide → chaîne vide en BD."""
        self.engine.icon_url = 'https://example.com/old.svg'
        self.engine.save()
        self.client.force_authenticate(self.dbops_user)
        response = self.client.patch(
            f'/api/v1/admin/engines/{self.engine.pk}/',
            {'icon_url': ''},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.engine.refresh_from_db()
        self.assertEqual(self.engine.icon_url, '')

    def test_patch_icon_url_clear_to_null(self):
        """Envoyer icon_url null → null en BD (model null=True)."""
        self.engine.icon_url = 'https://example.com/old.svg'
        self.engine.save()
        self.client.force_authenticate(self.dbops_user)
        response = self.client.patch(
            f'/api/v1/admin/engines/{self.engine.pk}/',
            {'icon_url': None},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.engine.refresh_from_db()
        self.assertIsNone(self.engine.icon_url)


class RefEngineListAPIIconUrlTests(APITestCase):
    """Tests for icon_url exposure in GET /api/v1/reference/engines/ (AC2, AC4)."""

    def setUp(self):
        Profile.objects.get_or_create(
            name='DBOPS',
            defaults={'ad_group': 'CN=DBOPS,OU=Groups,DC=example,DC=com', 'is_admin': 1, 'is_auditor': 0},
        )
        Profile.objects.get_or_create(
            name='DBA',
            defaults={'ad_group': 'CN=DBA,OU=Groups,DC=example,DC=com', 'is_admin': 0, 'is_auditor': 0},
        )
        self.user = User.objects.create(username='testuser', profile='DBA')
        self.client.force_authenticate(self.user)

    def test_icon_url_null_by_default(self):
        """Moteur créé sans icon_url → null dans la réponse API (AC4)."""
        RefEngine.objects.create(code='ORACLE', label='Oracle', display_order=1, is_active=1)
        response = self.client.get('/api/v1/reference/engines/?active_only=false')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = {e['code']: e for e in response.data['data']}
        self.assertIn('ORACLE', data)
        self.assertIsNone(data['ORACLE']['icon_url'])

    def test_icon_url_exposed_when_set(self):
        """Moteur avec icon_url → valeur retournée dans l'API (AC2)."""
        RefEngine.objects.create(
            code='ORACLE', label='Oracle', display_order=1, is_active=1,
            icon_url='https://example.com/oracle.svg',
        )
        response = self.client.get('/api/v1/reference/engines/?active_only=false')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = {e['code']: e for e in response.data['data']}
        self.assertEqual(data['ORACLE']['icon_url'], 'https://example.com/oracle.svg')

    def test_icon_url_persists_after_patch(self):
        """icon_url mis à jour via PATCH est retourné par GET (AC5)."""
        engine = RefEngine.objects.create(
            code='SQLSERVER', label='SQL Server', display_order=2, is_active=1,
        )
        dbops = User.objects.create(username='dbops', profile='DBOPS')
        self.client.force_authenticate(dbops)
        patch_response = self.client.patch(
            f'/api/v1/admin/engines/{engine.pk}/',
            {'icon_url': '/icons/engines/sqlserver.svg'},
            format='json',
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        # Re-authenticate as regular user to test GET
        self.client.force_authenticate(self.user)
        response = self.client.get('/api/v1/reference/engines/?active_only=false')
        data = {e['code']: e for e in response.data['data']}
        self.assertEqual(data['SQLSERVER']['icon_url'], '/icons/engines/sqlserver.svg')
