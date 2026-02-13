# OracleJSONField — Champs JSON pour Oracle CLOB

## Problème

Le modèle Action contenait ~75 lignes de code dupliqué pour la gestion JSON :
- 5 paires getter/setter (parameters_schema, impact_rules, execution_steps, change_type_config, remediation_rules)
- Chaque paire : 15 lignes (9 getter + 6 setter)
- Modifier la sérialisation JSON = toucher 10 méthodes

## Solution

`OracleJSONField` — champ Django custom qui centralise la sérialisation/désérialisation JSON pour Oracle CLOB.

**Fichier :** `core/fields.py`

## Architecture

```
OracleJSONField(models.TextField)
├── from_db_value()    → Désérialise JSON après SELECT (CLOB string → dict/list)
├── get_prep_value()   → Sérialise avant INSERT/UPDATE (dict/list → JSON string)
├── to_python()        → Validation pour forms/serializers
└── validator (opt.)   → Callable de validation custom
```

## Usage

```python
from core.fields import OracleJSONField

class MyModel(models.Model):
    json_data = OracleJSONField(null=True, blank=True, db_column='JSON_DATA')

# Accès transparent
obj.json_data = {"key": "value"}  # Auto-sérialisé vers JSON string
obj.save()
data = obj.json_data  # Auto-désérialisé vers dict
```

### Avec validation

```python
from django.core.exceptions import ValidationError
import jsonschema

def validate_json_schema(value):
    """Validate that value is a valid JSON Schema."""
    if not isinstance(value, dict):
        raise ValidationError("Must be a dict")
    if 'type' not in value:
        raise ValidationError("Must have 'type' field for JSON schema")
    # Optional: validate against JSON Schema meta-schema
    try:
        jsonschema.Draft7Validator.check_schema(value)
    except jsonschema.SchemaError as e:
        raise ValidationError(f"Invalid JSON schema: {e}")

def validate_impact_rules(value):
    """Validate impact_rules structure."""
    if not isinstance(value, list):
        raise ValidationError("impact_rules must be a list")
    for rule in value:
        if not isinstance(rule, dict) or 'impact_level' not in rule:
            raise ValidationError("Each rule must have 'impact_level'")

class MyModel(models.Model):
    schema = OracleJSONField(validator=validate_json_schema, null=True, blank=True)
    rules = OracleJSONField(validator=validate_impact_rules, null=True, blank=True)
```

**Note:** Validation actuelle dans Action model (Story 17.4) n'utilise PAS de validators. La validation peut être ajoutée plus tard si nécessaire.

## Migration depuis getter/setter

| Avant | Après |
|-------|-------|
| `action.get_parameters_schema()` | `action.parameters_schema` |
| `action.set_parameters_schema(value)` | `action.parameters_schema = value` |

### Checklist de migration

Lors de la migration d'un modèle vers OracleJSONField:

1. **Modèle:**
   - ✅ Remplacer `TextField` par `OracleJSONField`
   - ✅ Supprimer méthodes `get_field()` et `set_field()`
   - ✅ Importer `from core.fields import OracleJSONField`

2. **Services:**
   - ✅ Remplacer `obj.set_field(value)` par `obj.field = value`
   - ✅ Remplacer `obj.get_field()` par `obj.field`
   - ✅ Retirer imports `json` si plus nécessaires

3. **Serializers:**
   - ✅ Remplacer `SerializerMethodField()` par `JSONField()`
   - ✅ Supprimer méthodes `get_field(obj)` redondantes
   - ✅ Le champ est déjà désérialisé — pas besoin de `json.loads()`

4. **Tests:**
   - ✅ Remplacer mocks de getters/setters par accès direct
   - ✅ Vérifier que les fixtures utilisent des dicts, pas des strings JSON
   - ✅ Tester avec `None`, `{}`, `[]`, et JSON complexe

5. **Vues:**
   - ✅ Remplacer appels getters par accès direct
   - ✅ Le champ retourne déjà un dict — pas besoin de conversion

## Modèles utilisant OracleJSONField

- **Action** (catalog/models.py) : parameters_schema, impact_rules, execution_steps, change_type_config, remediation_rules
- Réutilisable pour d'autres modèles (Workflow, Integration, etc.)

## Gestion d'erreurs

- **Désérialisation** (from_db_value) : JSON invalide → `None` + warning loggé
- **Sérialisation** (get_prep_value) : Objet non-sérialisable → `ValidationError`
- **Validation** (to_python) : JSON invalide → `ValidationError`

## Story

Story 17.4 — Epic 17 (Réduction dette technique)
