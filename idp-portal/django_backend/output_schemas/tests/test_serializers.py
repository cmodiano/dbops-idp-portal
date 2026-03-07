"""
Tests for output_schemas serializers.
Story 63.1 - Infrastructure des Schémas d'Output (Backend).
"""

import pytest
from output_schemas.models import OutputSchema, SchemaType
from output_schemas.serializers import OutputSchemaSerializer


@pytest.mark.django_db
class TestOutputSchemaSerializer:
    def _make_schema(self, **kwargs):
        defaults = {
            'name': 'test-schema',
            'schema_type': SchemaType.ACTION,
            'target_name': 'flyway-migrate',
            'schema_json': {'output_fields': [{'name': 'result', 'type': 'string'}]},
        }
        defaults.update(kwargs)
        return OutputSchema.objects.create(**defaults)

    def test_serializes_all_fields(self):
        schema = self._make_schema()
        s = OutputSchemaSerializer(schema)
        data = s.data
        assert data['name'] == 'test-schema'
        assert data['schema_type'] == 'action'
        assert data['target_name'] == 'flyway-migrate'
        assert data['operation'] is None
        assert data['inherits_from'] is None
        assert data['inherits_from_name'] is None
        assert 'id' in data
        assert 'created_at' in data
        assert 'updated_at' in data

    def test_serializes_inherits_from_name(self):
        parent = self._make_schema(name='parent', target_name='base')
        child = self._make_schema(name='child', target_name='derived', inherits_from=parent)
        s = OutputSchemaSerializer(child)
        assert s.data['inherits_from'] == parent.pk
        assert s.data['inherits_from_name'] == str(parent)

    def test_validate_schema_json_missing_output_fields(self):
        s = OutputSchemaSerializer(data={
            'name': 'bad',
            'schema_type': 'action',
            'target_name': 'foo',
            'schema_json': {'not_output_fields': []},
        })
        assert not s.is_valid()
        assert 'schema_json' in s.errors

    def test_validate_schema_json_not_dict(self):
        s = OutputSchemaSerializer(data={
            'name': 'bad2',
            'schema_type': 'action',
            'target_name': 'foo',
            'schema_json': [1, 2, 3],
        })
        assert not s.is_valid()
        assert 'schema_json' in s.errors

    def test_validate_schema_json_output_fields_not_list(self):
        s = OutputSchemaSerializer(data={
            'name': 'bad3',
            'schema_type': 'action',
            'target_name': 'foo',
            'schema_json': {'output_fields': 'not-a-list'},
        })
        assert not s.is_valid()
        assert 'schema_json' in s.errors

    def test_validate_schema_json_none_allowed(self):
        s = OutputSchemaSerializer(data={
            'name': 'null-json',
            'schema_type': 'action',
            'target_name': 'foo',
            'schema_json': None,
        })
        assert s.is_valid(), s.errors

    def test_validate_schema_json_valid(self):
        s = OutputSchemaSerializer(data={
            'name': 'valid-schema',
            'schema_type': 'integration',
            'target_name': 'servicenow',
            'operation': 'create_change',
            'schema_json': {'output_fields': [{'name': 'change_number', 'type': 'string'}]},
        })
        assert s.is_valid(), s.errors
