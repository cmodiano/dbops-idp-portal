"""
Story 24.1: Tests for catalogue serializers.
"""

import json
import pytest

from integrations.serializers import (
    IntegrationTypeCatalogueSerializer,
    IntegrationActionSerializer,
    IntegrationTypeWithActionsSerializer,
)
from tests.factories import IntegrationTypeCatalogueFactory, IntegrationActionFactory


@pytest.mark.django_db
class TestIntegrationTypeCatalogueSerializer:
    """Tests for IntegrationTypeCatalogueSerializer."""

    def test_serialize_type(self):
        t = IntegrationTypeCatalogueFactory(code='aap', name='AAP', version='1.0')
        data = IntegrationTypeCatalogueSerializer(t).data
        assert data['code'] == 'aap'
        assert data['name'] == 'AAP'
        assert data['version'] == '1.0'
        assert data['is_active'] is True
        assert 'created_at' in data
        assert 'updated_at' in data

    def test_fields_present(self):
        t = IntegrationTypeCatalogueFactory()
        data = IntegrationTypeCatalogueSerializer(t).data
        expected = {'code', 'name', 'description', 'version', 'is_active', 'created_at', 'updated_at'}
        assert set(data.keys()) == expected


@pytest.mark.django_db
class TestIntegrationActionSerializer:
    """Tests for IntegrationActionSerializer."""

    def test_serialize_action(self):
        a = IntegrationActionFactory(action_code='start_job', action_label='Démarrer')
        data = IntegrationActionSerializer(a).data
        assert data['action_code'] == 'start_job'
        assert data['action_label'] == 'Démarrer'
        assert data['is_active'] is True
        assert isinstance(data['required_params'], dict)
        assert isinstance(data['optional_params'], dict)
        assert isinstance(data['response_format'], dict)

    def test_json_fields_deserialized(self):
        schema = {"type": "object", "properties": {"id": {"type": "integer"}}}
        a = IntegrationActionFactory(required_params=json.dumps(schema))
        data = IntegrationActionSerializer(a).data
        assert data['required_params'] == schema

    def test_empty_json_fields(self):
        a = IntegrationActionFactory(
            required_params='{}',
            optional_params='{}',
            response_format='{}',
        )
        data = IntegrationActionSerializer(a).data
        assert data['required_params'] == {}
        assert data['optional_params'] == {}
        assert data['response_format'] == {}

    def test_fields_present(self):
        a = IntegrationActionFactory()
        data = IntegrationActionSerializer(a).data
        expected = {
            'id', 'action_code', 'action_label', 'description',
            'required_params', 'optional_params', 'response_format',
            'is_active', 'created_at', 'updated_at',
        }
        assert set(data.keys()) == expected


@pytest.mark.django_db
class TestIntegrationTypeWithActionsSerializer:
    """Tests for IntegrationTypeWithActionsSerializer (nested)."""

    def test_nested_actions(self):
        t = IntegrationTypeCatalogueFactory(code='aap')
        IntegrationActionFactory(integration_type=t, action_code='start_job')
        IntegrationActionFactory(integration_type=t, action_code='cancel_job')
        data = IntegrationTypeWithActionsSerializer(t).data
        assert data['code'] == 'aap'
        assert len(data['actions']) == 2
        action_codes = [a['action_code'] for a in data['actions']]
        assert 'start_job' in action_codes
        assert 'cancel_job' in action_codes

    def test_empty_actions(self):
        t = IntegrationTypeCatalogueFactory(code='empty')
        data = IntegrationTypeWithActionsSerializer(t).data
        assert data['actions'] == []

    def test_nested_action_has_json_fields(self):
        t = IntegrationTypeCatalogueFactory(code='sn')
        schema = {"type": "object", "properties": {"x": {"type": "string"}}}
        IntegrationActionFactory(
            integration_type=t,
            action_code='create_change',
            required_params=json.dumps(schema),
        )
        data = IntegrationTypeWithActionsSerializer(t).data
        assert data['actions'][0]['required_params'] == schema

    def test_fields_include_actions(self):
        t = IntegrationTypeCatalogueFactory()
        data = IntegrationTypeWithActionsSerializer(t).data
        expected = {'code', 'name', 'description', 'version', 'is_active', 'created_at', 'updated_at', 'actions'}
        assert set(data.keys()) == expected
