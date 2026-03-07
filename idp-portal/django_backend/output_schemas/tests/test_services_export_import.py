"""
Tests for output_schemas export/import service.
Story 63.1 - Infrastructure des Schémas d'Output (Backend).
"""

import pytest
import yaml

from output_schemas.models import OutputSchema, SchemaType
from output_schemas.services_export_import import (
    export_output_schemas_yaml,
    import_output_schemas_yaml,
)


def make_schema(name, schema_type=SchemaType.ACTION, target_name='flyway', **kwargs):
    defaults = {'schema_json': {'output_fields': [{'name': 'result', 'type': 'string'}]}}
    defaults.update(kwargs)
    return OutputSchema.objects.create(name=name, schema_type=schema_type, target_name=target_name, **defaults)


@pytest.mark.django_db
class TestExportOutputSchemasYaml:
    def test_export_empty(self):
        content = export_output_schemas_yaml()
        parsed = yaml.safe_load(content)
        assert parsed == {'items': []}

    def test_export_contains_schema(self):
        make_schema('export-test', target_name='flyway-migrate')
        content = export_output_schemas_yaml()
        parsed = yaml.safe_load(content)
        assert len(parsed['items']) == 1
        item = parsed['items'][0]
        assert item['metadata']['name'] == 'export-test'
        assert item['metadata']['schema_type'] == 'action'
        assert item['metadata']['target_name'] == 'flyway-migrate'
        assert item['apiVersion'] == 'idp/v1'
        assert item['kind'] == 'OutputSchema'

    def test_export_includes_operation(self):
        make_schema('sn-schema', schema_type=SchemaType.INTEGRATION,
                    target_name='servicenow', operation='create_change')
        content = export_output_schemas_yaml()
        parsed = yaml.safe_load(content)
        item = parsed['items'][0]
        assert item['metadata']['operation'] == 'create_change'

    def test_export_includes_inherits_from(self):
        parent = make_schema('parent-schema')
        make_schema('child-schema', target_name='child-action', inherits_from=parent)
        content = export_output_schemas_yaml()
        parsed = yaml.safe_load(content)
        items_by_name = {i['metadata']['name']: i for i in parsed['items']}
        assert items_by_name['child-schema']['spec']['inherits_from'] == 'parent-schema'
        assert items_by_name['parent-schema']['spec']['inherits_from'] is None

    def test_export_spec_includes_output_fields(self):
        make_schema('fields-schema', schema_json={
            'output_fields': [{'name': 'change_number', 'type': 'string'}]
        })
        content = export_output_schemas_yaml()
        parsed = yaml.safe_load(content)
        spec = parsed['items'][0]['spec']
        assert 'output_fields' in spec
        assert spec['output_fields'][0]['name'] == 'change_number'


@pytest.mark.django_db
class TestImportOutputSchemasYaml:
    VALID_YAML = """items:
  - apiVersion: idp/v1
    kind: OutputSchema
    metadata:
      name: imported-schema
      schema_type: action
      target_name: flyway-migrate
      operation: null
    spec:
      inherits_from: null
      output_fields:
        - name: result
          type: string
"""

    def test_import_creates_schema(self):
        stats = import_output_schemas_yaml(self.VALID_YAML, mode='additive')
        assert stats['created'] == 1
        assert stats['updated'] == 0
        assert OutputSchema.objects.filter(name='imported-schema').exists()

    def test_import_idempotent_unchanged(self):
        import_output_schemas_yaml(self.VALID_YAML, mode='additive')
        stats = import_output_schemas_yaml(self.VALID_YAML, mode='additive')
        assert stats['created'] == 0
        assert stats['unchanged'] == 1

    def test_import_updates_existing(self):
        make_schema('imported-schema', target_name='old-target',
                    schema_json={'output_fields': []})
        stats = import_output_schemas_yaml(self.VALID_YAML, mode='additive')
        assert stats['updated'] == 1
        schema = OutputSchema.objects.get(name='imported-schema')
        assert schema.target_name == 'flyway-migrate'

    def test_import_full_mode_deletes_absent(self):
        make_schema('to-be-deleted', target_name='old')
        stats = import_output_schemas_yaml(self.VALID_YAML, mode='full')
        assert stats['deleted'] == 1
        assert not OutputSchema.objects.filter(name='to-be-deleted').exists()

    def test_import_additive_does_not_delete(self):
        make_schema('keep-me', target_name='keep')
        stats = import_output_schemas_yaml(self.VALID_YAML, mode='additive')
        assert stats['deleted'] == 0
        assert OutputSchema.objects.filter(name='keep-me').exists()

    def test_import_rejects_invalid_output_field_type(self):
        """Import rejette les output_fields avec type invalide."""
        yaml_invalid = """items:
  - apiVersion: idp/v1
    kind: OutputSchema
    metadata:
      name: bad-type-schema
      schema_type: action
      target_name: foo
      operation: null
    spec:
      inherits_from: null
      output_fields:
        - name: logs
          type: tex
"""
        with pytest.raises(ValueError, match="invalide"):
            import_output_schemas_yaml(yaml_invalid, mode='additive')

    def test_import_empty_items(self):
        stats = import_output_schemas_yaml('items: []', mode='additive')
        assert stats['created'] == 0

    def test_import_invalid_yaml_raises(self):
        # Fix L2: invalid YAML must raise ValueError (so the view returns 400, not 500)
        with pytest.raises(ValueError, match="YAML invalide"):
            import_output_schemas_yaml(': invalid: yaml: {{{', mode='additive')

    def test_roundtrip(self):
        """Export → import should be idempotent."""
        make_schema('rt-schema', schema_type=SchemaType.INTEGRATION,
                    target_name='servicenow', operation='create_change',
                    schema_json={'output_fields': [{'name': 'sys_id', 'type': 'string'}]})
        exported = export_output_schemas_yaml()
        OutputSchema.objects.all().delete()
        stats = import_output_schemas_yaml(exported, mode='full')
        assert stats['created'] == 1
        schema = OutputSchema.objects.get(name='rt-schema')
        assert schema.schema_type == 'integration'
        assert schema.operation == 'create_change'
        assert schema.schema_json is not None

    def test_roundtrip_with_inheritance(self):
        """Export → import préserve inherits_from (parent chargé avant enfant)."""
        parent = make_schema(
            'rt-parent',
            schema_type=SchemaType.PLATFORM_CONVENTION,
            target_name='rt-parent',
            schema_json={'output_fields': [{'name': 'base_field', 'type': 'string'}]}
        )
        make_schema(
            'rt-child',
            schema_type=SchemaType.ACTION,
            target_name='rt-child-action',
            inherits_from=parent,
            schema_json={'output_fields': [{'name': 'extra_field', 'type': 'integer'}]}
        )
        exported = export_output_schemas_yaml()
        # Vérifier ordre : parent avant enfant dans le YAML (order_by('id'))
        parsed = yaml.safe_load(exported)
        names = [i['metadata']['name'] for i in parsed['items']]
        assert names.index('rt-parent') < names.index('rt-child')

        OutputSchema.objects.all().delete()
        stats = import_output_schemas_yaml(exported, mode='full')
        assert stats['created'] == 2

        child = OutputSchema.objects.get(name='rt-child')
        assert child.inherits_from is not None
        assert child.inherits_from.name == 'rt-parent'
