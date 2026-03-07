"""
Tests for output_schemas models.
Story 63.1 - Infrastructure des Schémas d'Output (Backend).
"""

import pytest
from django.db import IntegrityError

from output_schemas.models import OutputSchema, SchemaType


@pytest.mark.django_db
class TestOutputSchemaStr:
    def test_str_without_operation(self):
        schema = OutputSchema(
            name='test', schema_type='action', target_name='flyway-migrate', operation=None
        )
        assert str(schema) == 'action:flyway-migrate'

    def test_str_with_operation(self):
        schema = OutputSchema(
            name='test', schema_type='integration', target_name='servicenow', operation='create_change'
        )
        assert str(schema) == 'integration:servicenow:create_change'

    def test_str_platform_convention(self):
        schema = OutputSchema(
            name='test', schema_type='platform_convention', target_name='aap', operation=None
        )
        assert str(schema) == 'platform_convention:aap'


@pytest.mark.django_db
class TestOutputSchemaCreate:
    def test_create_action_schema(self):
        schema = OutputSchema.objects.create(
            name='flyway-migrate-schema',
            schema_type=SchemaType.ACTION,
            target_name='flyway-migrate',
            schema_json={'output_fields': [{'name': 'result', 'type': 'string'}]},
        )
        assert schema.pk is not None
        assert schema.schema_type == 'action'
        assert schema.operation is None
        assert schema.inherits_from is None

    def test_create_integration_schema_with_operation(self):
        schema = OutputSchema.objects.create(
            name='sn-create-change-schema',
            schema_type=SchemaType.INTEGRATION,
            target_name='servicenow',
            operation='create_change',
            schema_json={'output_fields': [{'name': 'change_number', 'type': 'string'}]},
        )
        assert schema.operation == 'create_change'

    def test_create_with_inherits_from(self):
        parent = OutputSchema.objects.create(
            name='base-schema',
            schema_type=SchemaType.PLATFORM_CONVENTION,
            target_name='aap',
            schema_json={'output_fields': []},
        )
        child = OutputSchema.objects.create(
            name='child-schema',
            schema_type=SchemaType.ACTION,
            target_name='aap-run',
            inherits_from=parent,
            schema_json={'output_fields': []},
        )
        assert child.inherits_from == parent
        assert parent.children.count() == 1

    def test_name_unique_constraint(self):
        OutputSchema.objects.create(
            name='unique-name',
            schema_type=SchemaType.ACTION,
            target_name='action-a',
            schema_json={'output_fields': []},
        )
        with pytest.raises(IntegrityError):
            OutputSchema.objects.create(
                name='unique-name',
                schema_type=SchemaType.ACTION,
                target_name='action-b',
                schema_json={'output_fields': []},
            )

    def test_schema_type_choices(self):
        assert SchemaType.ACTION == 'action'
        assert SchemaType.INTEGRATION == 'integration'
        assert SchemaType.PLATFORM_CONVENTION == 'platform_convention'

    def test_unique_constraint_schema_type_target_name_operation(self):
        """Fix H2: test uq_output_schema_type_target_op (condition: operation IS NOT NULL)."""
        OutputSchema.objects.create(
            name='integ-sn-create-1',
            schema_type=SchemaType.INTEGRATION,
            target_name='servicenow',
            operation='create_change',
            schema_json={'output_fields': []},
        )
        with pytest.raises(IntegrityError):
            OutputSchema.objects.create(
                name='integ-sn-create-2',
                schema_type=SchemaType.INTEGRATION,
                target_name='servicenow',
                operation='create_change',
                schema_json={'output_fields': []},
            )

    def test_schema_json_null_allowed(self):
        schema = OutputSchema.objects.create(
            name='no-json',
            schema_type=SchemaType.ACTION,
            target_name='some-action',
            schema_json=None,
        )
        assert schema.schema_json is None

    def test_auto_timestamps(self):
        schema = OutputSchema.objects.create(
            name='ts-schema',
            schema_type=SchemaType.ACTION,
            target_name='ts-action',
            schema_json={'output_fields': []},
        )
        assert schema.created_at is not None
        assert schema.updated_at is not None
