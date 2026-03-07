"""
Serializers for output_schemas app.
Story 63.1 - Infrastructure des Schémas d'Output (Backend).
"""

from rest_framework import serializers
from output_schemas.models import OutputSchema

# Types autorisés pour output_fields (évite typos et valeurs arbitraires)
ALLOWED_OUTPUT_FIELD_TYPES = frozenset({'string', 'integer', 'boolean', 'text', 'array', 'object'})


class OutputSchemaSerializer(serializers.ModelSerializer):
    inherits_from_name = serializers.SerializerMethodField()
    schema_json = serializers.JSONField(allow_null=True, required=False)

    class Meta:
        model = OutputSchema
        fields = [
            'id',
            'name',
            'schema_type',
            'target_name',
            'operation',
            'inherits_from',
            'inherits_from_name',
            'schema_json',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_inherits_from_name(self, obj):
        if obj.inherits_from_id:
            return str(obj.inherits_from)
        return None

    def validate_schema_json(self, value):
        if value is None:
            return value
        if not isinstance(value, dict):
            raise serializers.ValidationError(
                "schema_json doit être un objet JSON."
            )
        if 'output_fields' not in value:
            raise serializers.ValidationError(
                "schema_json doit contenir une clé 'output_fields'."
            )
        if not isinstance(value['output_fields'], list):
            raise serializers.ValidationError(
                "schema_json.output_fields doit être une liste."
            )
        for i, field in enumerate(value['output_fields']):
            if isinstance(field, dict) and 'type' in field:
                ft = field.get('type')
                if ft is not None and str(ft) not in ALLOWED_OUTPUT_FIELD_TYPES:
                    raise serializers.ValidationError(
                        f"output_fields[{i}].type '{ft}' invalide. "
                        f"Types autorisés : {sorted(ALLOWED_OUTPUT_FIELD_TYPES)}."
                    )
        return value
