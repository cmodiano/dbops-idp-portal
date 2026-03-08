"""
Tests for catalog CaC views (actions, policies, tags export/sync).
Story 64.8 — API endpoints for CaC sync (export GET + sync POST).
"""

import pytest
from rest_framework.test import APIClient

from idp_auth.models import User
from catalog.models import Action, Tag


@pytest.mark.django_db
class TestActionExportView:
    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create(username='admin_ae', profile='DBOPS')
        self.non_admin = User.objects.create(username='user_ae', profile='dba')

    def test_export_requires_admin(self):
        self.client.force_authenticate(user=self.non_admin)
        response = self.client.get('/api/v1/admin/actions/export/yaml/')
        assert response.status_code == 403

    def test_export_returns_yaml_content_type(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/actions/export/yaml/')
        assert response.status_code == 200
        assert 'application/x-yaml' in response['Content-Type']

    def test_export_has_content_disposition(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/actions/export/yaml/')
        assert 'Content-Disposition' in response
        assert 'actions.yaml' in response['Content-Disposition']

    def test_export_empty_db_returns_empty_bytes(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/actions/export/yaml/')
        assert response.status_code == 200
        assert response.content == b''

    def test_unauthenticated_returns_401(self):
        response = self.client.get('/api/v1/admin/actions/export/yaml/')
        assert response.status_code == 401


@pytest.mark.django_db
class TestActionSyncView:
    VALID_YAML = """\
apiVersion: idp/v1
kind: Action
metadata:
  name: test-action-sync
spec:
  engine: shell
  platform: linux
  status: published
  item_type: action
  requires_target: false
  description: test description
"""

    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create(username='admin_as', profile='DBOPS')
        self.non_admin = User.objects.create(username='user_as', profile='dba')

    def test_sync_requires_admin(self):
        self.client.force_authenticate(user=self.non_admin)
        response = self.client.post(
            '/api/v1/admin/actions/sync/',
            data=self.VALID_YAML,
            content_type='application/x-yaml',
        )
        assert response.status_code == 403

    def test_sync_empty_body_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/actions/sync/',
            data={},
            format='multipart',
        )
        assert response.status_code == 400
        assert response.data['error']['code'] == 'EMPTY_BODY'

    def test_sync_invalid_mode_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/actions/sync/?mode=wrong',
            data=self.VALID_YAML,
            content_type='application/x-yaml',
        )
        assert response.status_code == 400

    def test_sync_creates_action_returns_201(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/actions/sync/',
            data=self.VALID_YAML,
            content_type='application/x-yaml',
        )
        assert response.status_code == 201
        data = response.data['data']
        assert data['created'] == 1
        assert data['updated'] == 0
        assert data['mode'] == 'additive'
        assert Action.objects.filter(name='test-action-sync').exists()

    def test_sync_updates_existing_returns_200(self):
        Action.objects.create(name='test-action-sync')
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/actions/sync/',
            data=self.VALID_YAML,
            content_type='application/x-yaml',
        )
        assert response.status_code == 200
        data = response.data['data']
        assert data['updated'] == 1

    def test_sync_mode_transmitted_in_response(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/actions/sync/?mode=full',
            data=self.VALID_YAML,
            content_type='application/x-yaml',
        )
        assert response.status_code in (200, 201)
        assert response.data['data']['mode'] == 'full'

    def test_sync_via_multipart_file_upload(self):
        from io import BytesIO
        self.client.force_authenticate(user=self.admin)
        yaml_file = BytesIO(self.VALID_YAML.encode('utf-8'))
        yaml_file.name = 'actions.yaml'
        response = self.client.post(
            '/api/v1/admin/actions/sync/',
            {'file': yaml_file},
            format='multipart',
        )
        assert response.status_code == 201
        assert response.data['data']['created'] == 1

    def test_unauthenticated_returns_401(self):
        response = self.client.post('/api/v1/admin/actions/sync/', data={})
        assert response.status_code == 401


@pytest.mark.django_db
class TestPolicySyncView:
    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create(username='admin_ps', profile='DBOPS')

    def test_policy_export_returns_200(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/policies/export/yaml/')
        assert response.status_code == 200
        assert 'application/x-yaml' in response['Content-Type']
        assert 'policies.yaml' in response['Content-Disposition']

    def test_policy_sync_empty_body_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/policies/sync/',
            data={},
            format='multipart',
        )
        assert response.status_code == 400
        assert response.data['error']['code'] == 'EMPTY_BODY'


@pytest.mark.django_db
class TestTagSyncView:
    VALID_YAML = """\
apiVersion: idp/v1
kind: Tags
metadata: {}
spec:
  - oracle
  - mysql
"""

    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create(username='admin_ts', profile='DBOPS')

    def test_tag_export_returns_yaml(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/tags/export/yaml/')
        assert response.status_code == 200
        assert 'application/x-yaml' in response['Content-Type']
        assert 'tags.yaml' in response['Content-Disposition']

    def test_tag_sync_creates_tags(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/tags/sync/',
            data=self.VALID_YAML,
            content_type='application/x-yaml',
        )
        assert response.status_code == 201
        data = response.data['data']
        assert data['created'] == 2
        assert Tag.objects.filter(name='oracle').exists()
        assert Tag.objects.filter(name='mysql').exists()

    def test_tag_sync_empty_body_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/tags/sync/',
            data={},
            format='multipart',
        )
        assert response.status_code == 400
        assert response.data['error']['code'] == 'EMPTY_BODY'

    def test_tag_sync_mode_in_response(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/tags/sync/?mode=full',
            data=self.VALID_YAML,
            content_type='application/x-yaml',
        )
        assert response.status_code in (200, 201)
        assert response.data['data']['mode'] == 'full'


@pytest.mark.django_db
class TestActionExportByIdView:
    """Story 64.13 — Single-entity export endpoint for actions."""

    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create(username='admin_aeid', profile='DBOPS')
        self.non_admin = User.objects.create(username='user_aeid', profile='dba')
        self.action = Action.objects.create(name='test-action-by-id', engine='shell', platform='linux')

    def test_export_by_id_returns_yaml(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f'/api/v1/admin/actions/{self.action.pk}/export/yaml/')
        assert response.status_code == 200
        assert 'application/x-yaml' in response['Content-Type']

    def test_export_by_id_has_content_disposition(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(f'/api/v1/admin/actions/{self.action.pk}/export/yaml/')
        assert 'Content-Disposition' in response
        assert self.action.name in response['Content-Disposition']

    def test_export_by_id_returns_404_on_missing_pk(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/actions/99999/export/yaml/')
        assert response.status_code == 404

    def test_export_by_id_requires_admin(self):
        self.client.force_authenticate(user=self.non_admin)
        response = self.client.get(f'/api/v1/admin/actions/{self.action.pk}/export/yaml/')
        assert response.status_code == 403
