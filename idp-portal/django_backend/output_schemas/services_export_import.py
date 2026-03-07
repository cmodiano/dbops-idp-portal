"""
Export/import IaC service for output schemas.
Story 63.1 - Infrastructure des Schémas d'Output (Backend).
"""

from typing import Any

import yaml
from output_schemas.models import OutputSchema

ENVELOPE_API_VERSION = 'idp/v1'
ENVELOPE_KIND = 'OutputSchema'


def export_output_schemas_yaml() -> str:
    """Export all OutputSchema as YAML envelope list."""
    schemas = OutputSchema.objects.select_related('inherits_from').order_by('id')
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


def _item_to_schema_data(item: dict) -> dict:
    """Convert a YAML envelope item to a dict for OutputSchema create/update."""
    metadata = item.get('metadata', {})
    spec = item.get('spec', {}) or {}

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

    return {
        'name': metadata.get('name', ''),
        'schema_type': metadata.get('schema_type', ''),
        'target_name': metadata.get('target_name', ''),
        'operation': metadata.get('operation') or None,
        'inherits_from': inherits_from,
        'schema_json': schema_json if schema_json else None,
    }


def import_output_schemas_yaml(content: str, mode: str = 'additive') -> dict:
    """
    Import OutputSchema from YAML envelope.

    Args:
        content: YAML string with envelope format
        mode: 'additive' (upsert only) or 'full' (delete absent schemas)

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

    stats: dict[str, Any] = {'created': 0, 'updated': 0, 'unchanged': 0, 'deleted': 0, 'mode': mode}
    seen_names = set()

    for item in items:
        data = _item_to_schema_data(item)
        name = data.pop('name')
        if not name:
            continue
        seen_names.add(name)

        try:
            schema = OutputSchema.objects.select_related('inherits_from').get(name=name)
            # Check if update needed
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

    # Invalider le cache du registry après tout import
    from output_schemas.registry import schema_registry  # noqa: PLC0415 — import tardif pour éviter les cycles
    schema_registry.invalidate()

    return stats
