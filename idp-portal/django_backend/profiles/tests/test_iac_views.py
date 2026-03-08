"""
Tests for profile IaC alias endpoints and extended response format.
Story 64.8 — AC#7: ProfileImportView returns unchanged + mode; aliases /export/yaml/ and /sync/.
"""

import pytest
import yaml
from io import BytesIO
from rest_framework.test import APIClient
from rest_framework import status

from idp_auth.models import User
from profiles.models import Profile


def _make_yaml_file(data: dict) -> BytesIO:
    """Helper: create a YAML file from dict."""
    content = yaml.dump(data).encode('utf-8')
    file = BytesIO(content)
    file.name = 'profiles.yaml'
    return file


@pytest.mark.django_db
class TestProfileImportExtendedResponse:
    """AC#7: ProfileImportView returns unchanged + mode in response."""

    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create(username='admin_pie', profile='DBOPS')

    def test_import_response_includes_unchanged_and_mode(self):
        """New response format includes unchanged and mode keys."""
        data = {
            'profiles': [{
                'name': 'test-profile-ext',
                'ad_group': 'GRP-EXT',
                'actions': {'type': 'all'},
                'targets': {'type': 'all'},
            }]
        }
        file = _make_yaml_file(data)
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/profiles/import/',
            {'file': file},
            format='multipart',
        )
        assert response.status_code == status.HTTP_201_CREATED
        payload = response.data['data']
        assert 'created' in payload
        assert 'updated' in payload
        assert 'unchanged' in payload
        assert 'mode' in payload
        assert payload['mode'] == 'additive'
        assert payload['unchanged'] == 0

    def test_import_mode_param_forwarded(self):
        """mode query param forwarded to response."""
        data = {
            'profiles': [{
                'name': 'test-mode-profile',
                'ad_group': 'GRP-MODE',
                'actions': {'type': 'all'},
                'targets': {'type': 'all'},
            }]
        }
        file = _make_yaml_file(data)
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/profiles/import/?mode=full',
            {'file': file},
            format='multipart',
        )
        assert response.status_code in (200, 201)
        assert response.data['data']['mode'] == 'full'

    def test_import_invalid_mode_returns_400(self):
        """Invalid mode returns 400 INVALID_IMPORT_MODE."""
        data = {'profiles': []}
        file = _make_yaml_file(data)
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/profiles/import/?mode=bad',
            {'file': file},
            format='multipart',
        )
        assert response.status_code == 400
        assert response.data['error']['code'] == 'INVALID_IMPORT_MODE'


@pytest.mark.django_db
class TestProfileAliasEndpoints:
    """AC#7: /profiles/export/yaml/ and /profiles/sync/ aliases work correctly."""

    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create(username='admin_pa', profile='DBOPS')

    def test_export_yaml_alias_returns_200(self):
        """GET /api/v1/admin/profiles/export/yaml/ returns YAML."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/profiles/export/yaml/')
        assert response.status_code == 200
        assert 'application/x-yaml' in response['Content-Type']

    def test_sync_alias_accepts_file(self):
        """POST /api/v1/admin/profiles/sync/ works as alias for import."""
        data = {
            'profiles': [{
                'name': 'alias-sync-profile',
                'ad_group': 'GRP-ALIAS',
                'actions': {'type': 'all'},
                'targets': {'type': 'all'},
            }]
        }
        file = _make_yaml_file(data)
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/profiles/sync/',
            {'file': file},
            format='multipart',
        )
        assert response.status_code in (200, 201)
        assert 'data' in response.data
        assert Profile.objects.filter(name='alias-sync-profile').exists()

    def test_sync_alias_returns_extended_format(self):
        """Sync alias response includes unchanged and mode."""
        data = {
            'profiles': [{
                'name': 'alias-ext-profile',
                'ad_group': 'GRP-ALIAS-EXT',
                'actions': {'type': 'all'},
                'targets': {'type': 'all'},
            }]
        }
        file = _make_yaml_file(data)
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/profiles/sync/',
            {'file': file},
            format='multipart',
        )
        assert response.status_code in (200, 201)
        payload = response.data['data']
        assert 'unchanged' in payload
        assert 'mode' in payload


@pytest.mark.django_db
class TestProfileExportByIdView:
    """Story 64.13 — Single-entity export endpoint for profiles."""

    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create(username='admin_peid', profile='DBOPS')
        self.non_admin = User.objects.create(username='user_peid', profile='dba')
        self.profile = Profile.objects.create(name='test-profile-by-id', ad_group='GRP-TEST')

    def test_export_by_id_returns_yaml(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f'/api/v1/admin/profiles/{self.profile.pk}/export/yaml/')
        assert response.status_code == 200
        assert 'application/x-yaml' in response['Content-Type']

    def test_export_by_id_has_content_disposition(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f'/api/v1/admin/profiles/{self.profile.pk}/export/yaml/')
        assert 'Content-Disposition' in response
        assert self.profile.name in response['Content-Disposition']

    def test_export_by_id_returns_404_on_missing_pk(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/profiles/99999/export/yaml/')
        assert response.status_code == 404

    def test_export_by_id_requires_admin(self):
        self.client.force_authenticate(user=self.non_admin)
        response = self.client.get(f'/api/v1/admin/profiles/{self.profile.pk}/export/yaml/')
        assert response.status_code == 403
