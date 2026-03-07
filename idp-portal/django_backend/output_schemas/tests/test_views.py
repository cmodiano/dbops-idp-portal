"""
Tests for output_schemas views.
Story 63.1 - Infrastructure des Schémas d'Output (Backend).
"""

import pytest
import yaml
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from output_schemas.models import OutputSchema, SchemaType


def make_schema(name, schema_type=SchemaType.ACTION, target_name='flyway-migrate', **kwargs):
    defaults = {'schema_json': {'output_fields': []}}
    defaults.update(kwargs)
    return OutputSchema.objects.create(name=name, schema_type=schema_type, target_name=target_name, **defaults)


@pytest.mark.django_db
class TestOutputSchemaViewSetPublic:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='testuser', password='pass')
        self.client.force_authenticate(user=self.user)

    def test_list_returns_200(self):
        make_schema('schema-a')
        make_schema('schema-b', schema_type=SchemaType.INTEGRATION, target_name='servicenow', operation='create_change')
        response = self.client.get('/api/v1/output-schemas/')
        assert response.status_code == 200

    def test_list_contains_schemas(self):
        make_schema('schema-c')
        response = self.client.get('/api/v1/output-schemas/')
        # CustomPageNumberPagination uses 'data' key
        names = [r['name'] for r in response.data['data']]
        assert 'schema-c' in names

    def test_list_pagination_keys(self):
        response = self.client.get('/api/v1/output-schemas/')
        assert response.status_code == 200
        assert 'data' in response.data
        assert 'pagination' in response.data

    def test_detail_returns_200(self):
        schema = make_schema('schema-d')
        response = self.client.get(f'/api/v1/output-schemas/{schema.pk}/')
        assert response.status_code == 200
        assert response.data['name'] == 'schema-d'

    def test_detail_404_not_found(self):
        response = self.client.get('/api/v1/output-schemas/99999/')
        assert response.status_code == 404

    def test_filter_by_schema_type(self):
        make_schema('action-schema', schema_type=SchemaType.ACTION, target_name='aap-run')
        make_schema('integ-schema', schema_type=SchemaType.INTEGRATION, target_name='servicenow', operation='op')
        response = self.client.get('/api/v1/output-schemas/?schema_type=action')
        results = response.data['data']
        assert all(r['schema_type'] == 'action' for r in results)

    def test_filter_by_target_name(self):
        make_schema('schema-aap', schema_type=SchemaType.ACTION, target_name='aap')
        make_schema('schema-flyway', schema_type=SchemaType.ACTION, target_name='flyway')
        response = self.client.get('/api/v1/output-schemas/?target_name=aap')
        results = response.data['data']
        assert all(r['target_name'] == 'aap' for r in results)

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        response = client.get('/api/v1/output-schemas/')
        assert response.status_code == 401

    def test_write_not_allowed(self):
        response = self.client.post('/api/v1/output-schemas/', data={}, format='json')
        assert response.status_code == 405

    def test_put_not_allowed(self):
        schema = make_schema('schema-put')
        response = self.client.put(f'/api/v1/output-schemas/{schema.pk}/', data={}, format='json')
        assert response.status_code == 405

    def test_delete_not_allowed(self):
        schema = make_schema('schema-del')
        response = self.client.delete(f'/api/v1/output-schemas/{schema.pk}/')
        assert response.status_code == 405


@pytest.mark.django_db
class TestAdminExportView:
    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(username='admin', password='pass', email='a@b.com')
        self.non_admin = User.objects.create_user(username='nonstaff', password='pass')

    def test_export_requires_admin(self):
        self.client.force_authenticate(user=self.non_admin)
        response = self.client.get('/api/v1/admin/output-schemas/export/yaml/')
        assert response.status_code == 403

    def test_export_returns_yaml(self):
        make_schema('export-schema')
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/output-schemas/export/yaml/')
        assert response.status_code == 200
        parsed = yaml.safe_load(response.content)
        assert 'items' in parsed

    def test_export_empty_returns_empty_items(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get('/api/v1/admin/output-schemas/export/yaml/')
        assert response.status_code == 200
        parsed = yaml.safe_load(response.content)
        assert parsed['items'] == []


@pytest.mark.django_db
class TestAdminSyncView:
    VALID_YAML = """items:
  - apiVersion: idp/v1
    kind: OutputSchema
    metadata:
      name: sync-schema-1
      schema_type: action
      target_name: flyway-migrate
      operation: null
    spec:
      inherits_from: null
      output_fields:
        - name: result
          type: string
"""

    def setup_method(self):
        self.client = APIClient()
        self.admin = User.objects.create_superuser(username='admin2', password='pass', email='c@d.com')
        self.non_admin = User.objects.create_user(username='nonstaff2', password='pass')

    def test_sync_requires_admin(self):
        self.client.force_authenticate(user=self.non_admin)
        response = self.client.post(
            '/api/v1/admin/output-schemas/sync/',
            data=self.VALID_YAML,
            content_type='application/x-yaml'
        )
        assert response.status_code == 403

    def test_sync_additive_creates_schemas(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/output-schemas/sync/',
            data=self.VALID_YAML,
            content_type='application/x-yaml'
        )
        assert response.status_code == 200
        data = response.data['data']
        assert data['created'] == 1
        assert OutputSchema.objects.filter(name='sync-schema-1').exists()

    def test_sync_invalid_mode_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/output-schemas/sync/?mode=invalid',
            data=self.VALID_YAML,
            content_type='application/x-yaml'
        )
        assert response.status_code == 400

    def test_sync_no_body_returns_400(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/output-schemas/sync/',
            data={},
            format='multipart'
        )
        assert response.status_code == 400

    def test_sync_full_mode_removes_absent(self):
        make_schema('will-be-deleted', target_name='old')
        self.client.force_authenticate(user=self.admin)
        response = self.client.post(
            '/api/v1/admin/output-schemas/sync/?mode=full',
            data=self.VALID_YAML,
            content_type='application/x-yaml'
        )
        assert response.status_code == 200
        data = response.data['data']
        assert data['deleted'] == 1
        assert not OutputSchema.objects.filter(name='will-be-deleted').exists()
