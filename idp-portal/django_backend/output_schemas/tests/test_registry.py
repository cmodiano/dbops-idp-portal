"""
Tests for OutputSchemaRegistry.
Story 63.2 - Registre des Schémas & Résolution.

Couvre AC1 et AC6:
- Résolution simple (sans héritage)
- Résolution avec héritage 1 niveau
- Résolution avec héritage chaîné 2 niveaux
- Héritage introuvable (parent supprimé)
- Cache et invalidation
"""

import pytest
from output_schemas.models import OutputSchema, SchemaType
from output_schemas.registry import OutputSchemaRegistry


# ---------------------------------------------------------------------------
# Tests de résolution simple (sans héritage)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_action_schema_simple():
    """AC1: Résolution simple d'un schéma action sans héritage."""
    OutputSchema.objects.create(
        name='flyway-migrate',
        schema_type=SchemaType.ACTION,
        target_name='flyway-migrate',
        schema_json={'output_fields': [{'name': 'migrations_applied', 'type': 'integer'}]},
    )
    registry = OutputSchemaRegistry()
    result = registry.get_action_schema('flyway-migrate')
    assert result is not None
    assert result['output_fields'][0]['name'] == 'migrations_applied'


@pytest.mark.django_db
def test_get_action_schema_returns_none_when_not_found():
    """AC1: Retourne None si aucun schéma trouvé."""
    registry = OutputSchemaRegistry()
    result = registry.get_action_schema('inexistant-action')
    assert result is None


@pytest.mark.django_db
def test_get_integration_schema_simple():
    """AC1: Résolution simple d'un schéma intégration."""
    OutputSchema.objects.create(
        name='servicenow-create_change',
        schema_type=SchemaType.INTEGRATION,
        target_name='servicenow',
        operation='create_change',
        schema_json={'output_fields': [{'name': 'change_number', 'type': 'string'}]},
    )
    registry = OutputSchemaRegistry()
    result = registry.get_integration_schema('servicenow', 'create_change')
    assert result is not None
    assert result['output_fields'][0]['name'] == 'change_number'


@pytest.mark.django_db
def test_get_integration_schema_returns_none_when_not_found():
    """AC1: Retourne None si schéma intégration inexistant."""
    registry = OutputSchemaRegistry()
    result = registry.get_integration_schema('inexistant', 'op')
    assert result is None


@pytest.mark.django_db
def test_get_platform_convention_simple():
    """AC1: Résolution simple d'une convention plateforme."""
    OutputSchema.objects.create(
        name='aap-standard',
        schema_type=SchemaType.PLATFORM_CONVENTION,
        target_name='aap-standard',
        schema_json={'output_fields': [
            {'name': 'platform_job_id', 'type': 'string'},
            {'name': 'job_status', 'type': 'string'},
        ]},
    )
    registry = OutputSchemaRegistry()
    result = registry.get_platform_convention('aap-standard')
    assert result is not None
    field_names = [f['name'] for f in result['output_fields']]
    assert 'platform_job_id' in field_names
    assert 'job_status' in field_names


# ---------------------------------------------------------------------------
# Tests d'héritage 1 niveau
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_get_action_schema_with_inheritance():
    """AC1: Résolution avec héritage 1 niveau — les champs propres overrident."""
    parent = OutputSchema.objects.create(
        name='aap-standard',
        schema_type=SchemaType.PLATFORM_CONVENTION,
        target_name='aap-standard',
        schema_json={'output_fields': [
            {'name': 'platform_job_id', 'type': 'string'},
            {'name': 'job_status', 'type': 'string'},
        ]},
    )
    OutputSchema.objects.create(
        name='flyway-migrate-action',
        schema_type=SchemaType.ACTION,
        target_name='flyway-migrate',
        inherits_from=parent,
        schema_json={'output_fields': [
            {'name': 'migrations_applied', 'type': 'integer'},
        ]},
    )
    registry = OutputSchemaRegistry()
    result = registry.get_action_schema('flyway-migrate')
    assert result is not None
    field_names = [f['name'] for f in result['output_fields']]
    assert 'platform_job_id' in field_names   # hérité
    assert 'job_status' in field_names         # hérité
    assert 'migrations_applied' in field_names  # propre
    assert result['inherits_from'] == 'aap-standard'


@pytest.mark.django_db
def test_inheritance_own_fields_override_parent():
    """AC1: Les champs propres avec le même nom overrident ceux du parent."""
    parent = OutputSchema.objects.create(
        name='base-schema',
        schema_type=SchemaType.PLATFORM_CONVENTION,
        target_name='base-schema',
        schema_json={'output_fields': [
            {'name': 'shared_field', 'type': 'string', 'description': 'from parent'},
        ]},
    )
    OutputSchema.objects.create(
        name='child-action',
        schema_type=SchemaType.ACTION,
        target_name='child-action',
        inherits_from=parent,
        schema_json={'output_fields': [
            {'name': 'shared_field', 'type': 'integer', 'description': 'from child'},
        ]},
    )
    registry = OutputSchemaRegistry()
    result = registry.get_action_schema('child-action')
    assert result is not None
    # shared_field doit avoir la valeur du child (override)
    shared = next(f for f in result['output_fields'] if f['name'] == 'shared_field')
    assert shared['type'] == 'integer'
    assert shared['description'] == 'from child'


# ---------------------------------------------------------------------------
# Tests d'héritage chaîné 2 niveaux
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_inheritance_chained_two_levels():
    """AC1: Héritage chaîné 2 niveaux — grand-parent → parent → enfant."""
    grandparent = OutputSchema.objects.create(
        name='grandparent-convention',
        schema_type=SchemaType.PLATFORM_CONVENTION,
        target_name='grandparent-convention',
        schema_json={'output_fields': [
            {'name': 'base_field', 'type': 'string'},
        ]},
    )
    parent = OutputSchema.objects.create(
        name='parent-convention',
        schema_type=SchemaType.PLATFORM_CONVENTION,
        target_name='parent-convention',
        inherits_from=grandparent,
        schema_json={'output_fields': [
            {'name': 'parent_field', 'type': 'string'},
        ]},
    )
    # L'enfant hérite du parent (qui lui-même hérite du grand-parent)
    # La résolution ne traite que 1 niveau, donc seuls les champs du parent direct sont hérités
    OutputSchema.objects.create(
        name='child-action-deep',
        schema_type=SchemaType.ACTION,
        target_name='child-action-deep',
        inherits_from=parent,
        schema_json={'output_fields': [
            {'name': 'child_field', 'type': 'string'},
        ]},
    )
    registry = OutputSchemaRegistry()
    result = registry.get_action_schema('child-action-deep')
    assert result is not None
    field_names = [f['name'] for f in result['output_fields']]
    # Champs propres du parent direct inclus
    assert 'parent_field' in field_names
    # Champs propres de l'enfant inclus
    assert 'child_field' in field_names
    # Note : la résolution à 1 niveau ne remonte pas au grand-parent
    # (comportement documenté dans la story)


@pytest.mark.django_db
def test_inheritance_parent_deleted_graceful():
    """AC1: Si inherits_from est SET NULL (parent supprimé), retourne uniquement les champs propres."""
    parent = OutputSchema.objects.create(
        name='parent-to-delete',
        schema_type=SchemaType.PLATFORM_CONVENTION,
        target_name='parent-to-delete',
        schema_json={'output_fields': [{'name': 'parent_field', 'type': 'string'}]},
    )
    child = OutputSchema.objects.create(
        name='child-orphan',
        schema_type=SchemaType.ACTION,
        target_name='child-orphan',
        inherits_from=parent,
        schema_json={'output_fields': [{'name': 'child_field', 'type': 'string'}]},
    )
    # Supprimer le parent — inherits_from_id devient NULL (SET_NULL)
    parent.delete()
    child.refresh_from_db()
    assert child.inherits_from_id is None

    registry = OutputSchemaRegistry()
    result = registry.get_action_schema('child-orphan')
    assert result is not None
    field_names = [f['name'] for f in result['output_fields']]
    assert 'child_field' in field_names
    assert 'parent_field' not in field_names


# ---------------------------------------------------------------------------
# Tests de cache et invalidation
# ---------------------------------------------------------------------------


def test_invalidate_clears_cache():
    """AC1: invalidate() vide complètement le cache."""
    registry = OutputSchemaRegistry()
    registry._cache['action:test'] = {'output_fields': []}
    registry._cache['integration:sn:create'] = {'output_fields': []}
    registry.invalidate()
    assert registry._cache == {}


@pytest.mark.django_db
def test_cache_populated_after_first_call():
    """AC1: Le cache est populé après le premier appel réussi."""
    OutputSchema.objects.create(
        name='cache-populate-action',
        schema_type=SchemaType.ACTION,
        target_name='cache-populate-action',
        schema_json={'output_fields': [{'name': 'field1', 'type': 'string'}]},
    )
    registry = OutputSchemaRegistry()
    assert 'action:cache-populate-action' not in registry._cache
    registry.get_action_schema('cache-populate-action')
    assert 'action:cache-populate-action' in registry._cache


@pytest.mark.django_db
def test_cache_returns_same_result_on_second_call():
    """AC1: Le second appel retourne le même résultat depuis le cache."""
    OutputSchema.objects.create(
        name='cached-action',
        schema_type=SchemaType.ACTION,
        target_name='cached-action',
        schema_json={'output_fields': [{'name': 'field1', 'type': 'string'}]},
    )
    registry = OutputSchemaRegistry()
    result1 = registry.get_action_schema('cached-action')
    result2 = registry.get_action_schema('cached-action')
    assert result1 == result2
    # Vérifier que le cache contient la clé
    assert 'action:cached-action' in registry._cache


@pytest.mark.django_db
def test_invalidate_forces_fresh_db_read():
    """AC1: Après invalidation, le registry relit la DB."""
    schema = OutputSchema.objects.create(
        name='mutable-action',
        schema_type=SchemaType.ACTION,
        target_name='mutable-action',
        schema_json={'output_fields': [{'name': 'original_field', 'type': 'string'}]},
    )
    registry = OutputSchemaRegistry()
    result1 = registry.get_action_schema('mutable-action')
    assert result1['output_fields'][0]['name'] == 'original_field'

    # Modifier le schéma en DB
    schema.schema_json = {'output_fields': [{'name': 'updated_field', 'type': 'string'}]}
    schema.save()

    # Sans invalidation, le cache retourne l'ancienne valeur
    result_cached = registry.get_action_schema('mutable-action')
    assert result_cached['output_fields'][0]['name'] == 'original_field'

    # Après invalidation, la nouvelle valeur est retournée
    registry.invalidate()
    result2 = registry.get_action_schema('mutable-action')
    assert result2['output_fields'][0]['name'] == 'updated_field'
