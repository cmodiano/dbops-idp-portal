"""
Export/import CaC service for output schemas.
Story 63.1 - Infrastructure des Schémas d'Output (Backend).
"""

from typing import Any

import yaml
from django.db import transaction
from output_schemas.models import OutputSchema
from output_schemas.serializers import ALLOWED_OUTPUT_FIELD_TYPES

ENVELOPE_API_VERSION = 'idp/v1'
ENVELOPE_KIND = 'OutputSchema'


def _topological_sort_schemas(schemas: list) -> list:
    """Order schemas so parents precede children (inherits_from dependency order).

    OS-LOW-02: Complexité O(n²) acceptable à l'échelle actuelle (dizaines de schémas).
    Optimisation appliquée : result_names est un set incrémental, évitant la reconstruction
    à chaque itération (was: {x.name for x in result} recréé à chaque tour de boucle).
    """
    by_name = {s.name: s for s in schemas}
    result: list[OutputSchema] = []
    result_names: set[str] = set()  # OS-LOW-02: set incrémental, O(1) lookup au lieu de O(n) rebuild
    remaining = list(schemas)
    while remaining:
        added = [
            s for s in remaining
            if s.inherits_from_id is None
            or s.inherits_from is None
            or s.inherits_from.name not in by_name
            or s.inherits_from.name in result_names
        ]
        if not added:
            raise ValueError("Circular inheritance or missing parent in schemas")
        for s in added:
            remaining.remove(s)
            result.append(s)
            result_names.add(s.name)
    return result


def export_output_schemas_yaml() -> str:
    """Export all OutputSchema as YAML envelope list (parents before children)."""
    all_schemas = list(
        OutputSchema.objects.select_related('inherits_from').order_by('id')
    )
    schemas = _topological_sort_schemas(all_schemas)
    items = []
    for schema in schemas:
        spec = {}
        spec['inherits_from'] = schema.inherits_from.name if schema.inherits_from else None
        if schema.schema_json:
            spec.update(schema.schema_json)
        items.append({
            'apiVersion': ENVELOPE_API_VERSION,
            'kind': ENVELOPE_KIND,
            'metadata': {
                'name': schema.name,
                'schema_type': schema.schema_type,
                'target_name': schema.target_name,
                'operation': schema.operation,
            },
            'spec': spec,
        })
    return yaml.dump({'items': items}, allow_unicode=True, sort_keys=False)


def _item_to_schema_data(item: Any) -> dict:
    """Convert a YAML envelope item to a dict for OutputSchema create/update."""
    if not isinstance(item, dict):
        raise ValueError("Chaque item doit être un objet (metadata, spec).")
    metadata = item.get('metadata')
    spec = item.get('spec')
    if not isinstance(metadata, dict):
        raise ValueError("L'item doit contenir 'metadata' (objet).")
    if not isinstance(spec, dict):
        raise ValueError("L'item doit contenir 'spec' (objet).")

    # Use get() instead of pop() to avoid mutating the parsed YAML dict (fix M3)
    inherits_from_name = spec.get('inherits_from', None)
    inherits_from = None
    if inherits_from_name:
        try:
            inherits_from = OutputSchema.objects.get(name=inherits_from_name)
        except OutputSchema.DoesNotExist:
            # Fix H3: raise instead of silently setting inherits_from=None
            raise ValueError(
                f"Schema parent introuvable : '{inherits_from_name}'. "
                "Importez d'abord les schémas parents."
            )

    schema_json = {k: v for k, v in spec.items() if k != 'inherits_from'} if spec else None

    # Valider les types des output_fields (aligné avec OutputSchemaSerializer)
    if schema_json and isinstance(schema_json.get('output_fields'), list):
        for i, field in enumerate(schema_json['output_fields']):
            if isinstance(field, dict) and 'type' in field:
                ft = field.get('type')
                if ft is not None and str(ft) not in ALLOWED_OUTPUT_FIELD_TYPES:
                    raise ValueError(
                        f"output_fields[{i}].type '{ft}' invalide. "
                        f"Types autorisés : {sorted(ALLOWED_OUTPUT_FIELD_TYPES)}."
                    )

    return {
        'name': metadata.get('name', ''),
        'schema_type': metadata.get('schema_type', ''),
        'target_name': metadata.get('target_name', ''),
        'operation': metadata.get('operation') or None,
        'inherits_from': inherits_from,
        'schema_json': schema_json if schema_json else None,
    }


def import_output_schemas_yaml(
    content: str,
    mode: str = 'additive',
    create_only: bool = False,
) -> dict:
    """
    Import OutputSchema from YAML envelope.

    Args:
        content: YAML string with envelope format
        mode: 'additive' (upsert only) or 'full' (delete absent schemas)
        create_only: if True, only create missing schemas; never update existing

    Returns:
        dict with keys: created, updated, unchanged, deleted, mode

    Note:
        Items must be ordered so parents precede children. A child schema
        references its parent via spec.inherits_from (name). If a child
        appears before its parent in the YAML, a ValueError is raised.
        The export uses order_by('id') to ensure correct ordering.
    """
    # Fix H1: catch yaml.YAMLError and re-raise as ValueError so the view returns 400
    try:
        parsed = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ValueError(f"YAML invalide : {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Le contenu YAML doit être un objet.")

    items = parsed.get('items', [])
    if not isinstance(items, list):
        raise ValueError("La clé 'items' doit être une liste.")

    # Structure validation before transaction (no DB writes)
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"L'item {i} doit être un objet (metadata, spec).")
        if not isinstance(item.get('metadata'), dict):
            raise ValueError(f"L'item {i} doit contenir 'metadata' (objet).")
        if not isinstance(item.get('spec'), dict):
            raise ValueError(f"L'item {i} doit contenir 'spec' (objet).")

    stats: dict[str, Any] = {'created': 0, 'updated': 0, 'unchanged': 0, 'deleted': 0, 'mode': mode}
    seen_names: set[str] = set()

    from output_schemas.registry import schema_registry  # noqa: PLC0415

    with transaction.atomic():
        for item in items:
            data = _item_to_schema_data(item)
            name = data.pop('name')
            if not name:
                continue
            seen_names.add(name)

            try:
                schema = OutputSchema.objects.select_related('inherits_from').get(name=name)
                if create_only:
                    stats['unchanged'] += 1
                    continue
                changed = any(getattr(schema, k) != v for k, v in data.items())
                if changed:
                    for k, v in data.items():
                        setattr(schema, k, v)
                    schema.save()
                    stats['updated'] += 1
                else:
                    stats['unchanged'] += 1
            except OutputSchema.DoesNotExist:
                OutputSchema.objects.create(name=name, **data)
                stats['created'] += 1

        if mode == 'full':
            deleted_qs = OutputSchema.objects.exclude(name__in=seen_names)
            stats['deleted'] = deleted_qs.count()
            deleted_qs.delete()

        transaction.on_commit(schema_registry.invalidate)

    return stats
