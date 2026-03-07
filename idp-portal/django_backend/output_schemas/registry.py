"""
Registre central des OutputSchema avec résolution d'héritage et cache mémoire.
Story 63.2 - Registre des Schémas & Résolution.
"""

import threading

from output_schemas.models import OutputSchema, SchemaType


class OutputSchemaRegistry:
    """
    Registre central des OutputSchema avec résolution d'héritage et cache mémoire.
    Thread-safe via threading.Lock.
    """

    def __init__(self) -> None:
        self._cache: dict[str, dict] = {}
        self._lock = threading.Lock()

    def invalidate(self) -> None:
        """Vide le cache. Appeler après import_output_schemas_yaml()."""
        with self._lock:
            self._cache.clear()

    def _resolve(self, schema: OutputSchema) -> dict:
        """
        Résout le schéma en fusionnant les champs hérités.
        Les champs propres du schéma overrident ceux du parent.
        Support de l'héritage à 1 niveau (le parent ne re-résout pas récursivement
        pour éviter les cycles, mais la FK est une référence directe).
        """
        own_fields = (schema.schema_json or {}).get('output_fields', [])
        own_template_vars = (schema.schema_json or {}).get('template_variables', [])

        if schema.inherits_from_id:
            # select_related('inherits_from') doit avoir été utilisé à l'appel
            parent = schema.inherits_from
            if parent:
                parent_fields = (parent.schema_json or {}).get('output_fields', [])
                parent_template_vars = (parent.schema_json or {}).get('template_variables', [])
                # Merge : parent fields first, then own fields override by name
                merged_by_name = {f['name']: f for f in parent_fields}
                for f in own_fields:
                    merged_by_name[f['name']] = f
                merged_fields = list(merged_by_name.values())
                # Template variables: own override parent by name
                tv_by_name = {v['name']: v for v in parent_template_vars}
                for v in own_template_vars:
                    tv_by_name[v['name']] = v
                return {
                    'output_fields': merged_fields,
                    'template_variables': list(tv_by_name.values()),
                    'inherits_from': parent.name,
                }

        return {
            'output_fields': own_fields,
            'template_variables': own_template_vars,
        }

    def get_action_schema(self, action_name: str) -> dict | None:
        """Résout le schéma pour un step plateforme (action_name = nom de l'action catalogue)."""
        cache_key = f"action:{action_name}"
        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        try:
            schema = OutputSchema.objects.select_related('inherits_from').get(
                schema_type=SchemaType.ACTION,
                target_name=action_name,
                operation__isnull=True,
            )
        except (OutputSchema.DoesNotExist, OutputSchema.MultipleObjectsReturned):
            return None

        resolved = self._resolve(schema)
        with self._lock:
            self._cache[cache_key] = resolved
        return resolved

    def get_integration_schema(self, integration_type: str, operation: str) -> dict | None:
        """Résout le schéma pour un step service_call (integration_type + operation)."""
        cache_key = f"integration:{integration_type}:{operation}"
        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        try:
            schema = OutputSchema.objects.select_related('inherits_from').get(
                schema_type=SchemaType.INTEGRATION,
                target_name=integration_type,
                operation=operation,
            )
        except (OutputSchema.DoesNotExist, OutputSchema.MultipleObjectsReturned):
            return None

        resolved = self._resolve(schema)
        with self._lock:
            self._cache[cache_key] = resolved
        return resolved

    def get_platform_convention(self, convention_name: str) -> dict | None:
        """Résout une convention plateforme (ex: 'aap-standard')."""
        cache_key = f"platform_convention:{convention_name}"
        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]

        try:
            schema = OutputSchema.objects.select_related('inherits_from').get(
                schema_type=SchemaType.PLATFORM_CONVENTION,
                target_name=convention_name,
                operation__isnull=True,
            )
        except (OutputSchema.DoesNotExist, OutputSchema.MultipleObjectsReturned):
            return None

        resolved = self._resolve(schema)
        with self._lock:
            self._cache[cache_key] = resolved
        return resolved


# Instance globale — importée par les vues et services
schema_registry = OutputSchemaRegistry()
