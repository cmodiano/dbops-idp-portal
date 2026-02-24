# Story 37.4 : Paramètre d'action — inventory_value_column (backend)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que DBOPS configurant une action,
je veux pouvoir indiquer quelle colonne de l'entité inventaire (name, id, etc.) doit fournir la valeur du paramètre lorsque `source: inventory`,
afin d'utiliser la colonne métier adaptée (ex. id technique au lieu du nom) indépendamment des filtres (environment, server_names, engine_type).

## Acceptance Criteria

1. **Given** la validation du `parameters_schema` (catalog)
   **When** une propriété de paramètre a `source: 'inventory'` et optionnellement `inventory_value_column: <valeur>`
   **Then** si `inventory_value_column` est présent, il doit être une valeur autorisée pour l'`inventory_type` concerné
   **And** valeurs autorisées par type :
   - `servers` → `name`, `id`, `environment`, `engine_type`
   - `instances` → `name`, `id`, `server_ref`, `db_ref`
   - `databases` → `name`, `id`
   **And** si `inventory_value_column` est absent, le schéma reste valide (rétrocompatibilité)

2. **Given** `inventory_value_column` contient une valeur non autorisée pour l'entité
   **Then** la validation renvoie une erreur explicite :
   `"Parameter '<param_name>': inventory_value_column must be one of: name, id, ... for inventory_type <type>"`

3. **Given** sauvegarde / mise à jour d'une action avec un `parameters_schema` contenant `inventory_value_column` valide
   **Then** la valeur est persistée telle quelle dans PARAMETERS_SCHEMA (Oracle JSON)
   **And** les API GET action retournent le schéma inchangé (round-trip sans altération)

4. **Given** un `parameters_schema` existant sans `inventory_value_column`
   **Then** la validation passe sans erreur (zéro régression sur les actions existantes)

## Tasks / Subtasks

- [x] Task 1 : Ajouter le mapping `VALID_INVENTORY_VALUE_COLUMNS` dans `catalog/serializers.py` (AC: #1, #2)
  - [x] 1.1 Définir la constante `VALID_INVENTORY_VALUE_COLUMNS: dict[str, tuple[str, ...]]` après `VALID_INVENTORY_TYPES` :
    ```python
    VALID_INVENTORY_VALUE_COLUMNS: dict[str, tuple[str, ...]] = {
        'servers':   ('name', 'id', 'environment', 'engine_type'),
        'instances': ('name', 'id', 'server_ref', 'db_ref'),
        'databases': ('name', 'id'),
    }
    ```
  - [x] 1.2 Vérifier que les clés de `VALID_INVENTORY_VALUE_COLUMNS` couvrent exactement `VALID_INVENTORY_TYPES`

- [x] Task 2 : Étendre `validate_parameters_schema_inventory` pour valider `inventory_value_column` (AC: #1, #2, #4)
  - [x] 2.1 Dans la boucle `for param_name, prop in properties.items()`, après la validation de `inventory_type`, ajouter :
    ```python
    inventory_value_column = prop.get('inventory_value_column')
    if inventory_value_column is not None:
        allowed = VALID_INVENTORY_VALUE_COLUMNS.get(inventory_type, ())
        if inventory_value_column not in allowed:
            raise serializers.ValidationError(
                f"Parameter '{param_name}': inventory_value_column must be one of: "
                f"{', '.join(allowed)} for inventory_type '{inventory_type}'"
            )
    ```
  - [x] 2.2 S'assurer que la validation `inventory_value_column` arrive **après** la validation `inventory_type` (le type doit être valide avant de consulter le mapping des colonnes)
  - [x] 2.3 Vérifier que `inventory_value_column=None` ou absent laisse passer sans erreur (AC #4)

- [x] Task 3 : Mettre à jour l'export public dans `catalog/serializers.py` (AC: #1)
  - [x] 3.1 Vérifier que `VALID_INVENTORY_VALUE_COLUMNS` est exportable depuis `catalog.serializers` (pas de `__all__` restrictif)

- [x] Task 4 : Tests dans `catalog/tests/test_parameters_schema_validation.py` (AC: #1–#4)
  - [x] 4.1 `test_inventory_value_column_valid_name_passes` — `source=inventory, inventory_type=servers, inventory_value_column=name` → passe
  - [x] 4.2 `test_inventory_value_column_valid_id_passes` — `inventory_type=databases, inventory_value_column=id` → passe
  - [x] 4.3 `test_inventory_value_column_valid_server_ref_passes` — `inventory_type=instances, inventory_value_column=server_ref` → passe
  - [x] 4.4 `test_inventory_value_column_invalid_fails_with_message` — `inventory_type=servers, inventory_value_column=bad_col` → exception avec message explicite contenant le nom du param et "must be one of"
  - [x] 4.5 `test_inventory_value_column_wrong_type_fails` — `inventory_type=databases, inventory_value_column=engine_type` (non autorisé pour databases) → exception
  - [x] 4.6 `test_inventory_value_column_absent_passes` — schéma valide sans `inventory_value_column` (AC #4 — rétrocompatibilité)
  - [x] 4.7 `test_inventory_value_column_none_passes` — `inventory_value_column=None` explicite → passe (AC #4)
  - [x] 4.8 Parametrize `test_all_valid_columns_per_type` — pour chaque `(inventory_type, column)` de `VALID_INVENTORY_VALUE_COLUMNS` → passe
  - [x] 4.9 `test_inventory_value_column_persisted_in_schema` — vérifier que `validate_parameters_schema_inventory` retourne exactement le schéma passé (round-trip, AC #3)
  - [x] 4.10 Exécuter la suite complète : 33/33 tests PASSED

## Dev Notes

### Contexte et dépendances

Story 37.4 est **indépendante des stories 37.1–37.3** (toutes `done`) au niveau code. Les stories précédentes modifient le query executor et le frontend ; cette story ne touche que la **validation du catalog**.

- **37.1** (done) : dérivation environment via JOIN servers — aucun impact sur cette story
- **37.2** (done) : paramètre engine_type sur instances/databases — aucun impact
- **37.3** (done) : frontend passe engine_type — aucun impact
- **37.5** (prérequis de cette story) : le frontend édite et utilise `inventory_value_column` — attend que le backend valide et persiste correctement

### Architecture — Composants concernés

**Seul fichier backend à modifier :** `catalog/serializers.py`
**Seul fichier de test à modifier :** `catalog/tests/test_parameters_schema_validation.py`

**Pas de migration ni modification de modèle :** `parameters_schema` est un champ `OracleJSONField` (JSON flexible) — toute propriété supplémentaire dans le JSON est stockée telle quelle. La validation est purement applicative dans le serializer.

### Analyse du code existant

#### `catalog/serializers.py` — fonction cible

```python
# Ligne 30 — constante existante
VALID_INVENTORY_TYPES = ('servers', 'instances', 'databases')

# Lignes 79–110 — fonction à étendre
def validate_parameters_schema_inventory(value: Any) -> Any:
    """
    Story 23.5: Validate inventory_type in parameters_schema properties.
    ...
    """
    if not value or not isinstance(value, dict):
        return value

    properties = value.get('properties')
    if not properties or not isinstance(properties, dict):
        return value

    for param_name, prop in properties.items():
        if not isinstance(prop, dict):
            continue
        source = prop.get('source')
        if source != 'inventory':
            continue
        inventory_type = prop.get('inventory_type')
        if not inventory_type:
            raise serializers.ValidationError(
                f"Parameter '{param_name}': inventory_type is required when source is 'inventory'"
            )
        if inventory_type not in VALID_INVENTORY_TYPES:
            raise serializers.ValidationError(
                f"Parameter '{param_name}': inventory_type must be one of: "
                f"{', '.join(VALID_INVENTORY_TYPES)}"
            )
        # ← AJOUTER ICI la validation inventory_value_column (Task 2.1)

    return value
```

La fonction est appelée depuis deux endroits :
- `ActionAdminSerializer.validate_parameters_schema` (ligne ~308)
- Second serializer `validate_parameters_schema` (ligne ~529)

Les deux appellent simplement `validate_parameters_schema_inventory(value)` — aucune modification nécessaire à ces appels.

#### Colonnes autorisées — alignement avec `inventory/mapper.py`

Le mapper (Story 23.1) définit pour chaque entité les colonnes exposées via `build_select_clause` :

```python
# Exemple de config mapper (documentation dans mapper.py lignes 12–23)
{
    "servers":   {"columns": {"name": "HOSTNAME", "environment": "ENV", "engine_type": "ENGINE"}},
    "instances": {"columns": {"name": "INSTANCE_NAME", "environment": "ENV",
                              "server_ref": "SERVER_NAME", "db_ref": "DB_NAME"}},
    "databases": {"columns": {"name": "DB_NAME", "environment": "ENV"}},
}
```

De plus, chaque entité expose `id` via `id_column` (aliasé `AS id` dans SELECT).

**Mapping retenu pour Story 37.4 :**
- `servers` → `('name', 'id', 'environment', 'engine_type')` — colonnes standard + engine (pertinent comme valeur)
- `instances` → `('name', 'id', 'server_ref', 'db_ref')` — environment exclu (dérivé de servers depuis 37.1, pas de valeur métier pour "valeur du paramètre")
- `databases` → `('name', 'id')` — colonnes minimales suffisantes

> **Note :** La spec indique "au minimum name, id". Les colonnes supplémentaires sont choisies par utilité métier. Si l'équipe souhaite réduire au strict minimum, ne garder que `('name', 'id')` pour chaque type — la liste dans la constante `VALID_INVENTORY_VALUE_COLUMNS` fait autorité.

### Pattern de validation — implémentation complète

```python
# catalog/serializers.py — après la ligne 30

VALID_INVENTORY_VALUE_COLUMNS: dict[str, tuple[str, ...]] = {
    'servers':   ('name', 'id', 'environment', 'engine_type'),
    'instances': ('name', 'id', 'server_ref', 'db_ref'),
    'databases': ('name', 'id'),
}


def validate_parameters_schema_inventory(value: Any) -> Any:
    """
    Story 23.5 + 37.4: Validate inventory parameters in parameters_schema.

    If a parameter property has source='inventory':
    - inventory_type must be one of 'servers', 'instances', 'databases'.
    - inventory_value_column (optional) must be an allowed column for the inventory_type.
    """
    if not value or not isinstance(value, dict):
        return value

    properties = value.get('properties')
    if not properties or not isinstance(properties, dict):
        return value

    for param_name, prop in properties.items():
        if not isinstance(prop, dict):
            continue
        source = prop.get('source')
        if source != 'inventory':
            continue
        inventory_type = prop.get('inventory_type')
        if not inventory_type:
            raise serializers.ValidationError(
                f"Parameter '{param_name}': inventory_type is required when source is 'inventory'"
            )
        if inventory_type not in VALID_INVENTORY_TYPES:
            raise serializers.ValidationError(
                f"Parameter '{param_name}': inventory_type must be one of: "
                f"{', '.join(VALID_INVENTORY_TYPES)}"
            )
        # Story 37.4 — validate optional inventory_value_column
        inventory_value_column = prop.get('inventory_value_column')
        if inventory_value_column is not None:
            allowed = VALID_INVENTORY_VALUE_COLUMNS.get(inventory_type, ())
            if inventory_value_column not in allowed:
                raise serializers.ValidationError(
                    f"Parameter '{param_name}': inventory_value_column must be one of: "
                    f"{', '.join(allowed)} for inventory_type '{inventory_type}'"
                )

    return value
```

### Pattern de test — exemples clés

```python
# test_parameters_schema_validation.py — ajouts Story 37.4

from catalog.serializers import (
    validate_parameters_schema_inventory,
    VALID_INVENTORY_TYPES,
    VALID_INVENTORY_VALUE_COLUMNS,  # nouveau
)

class TestInventoryValueColumn:
    """Story 37.4: Tests for optional inventory_value_column property."""

    @pytest.mark.parametrize(
        "inventory_type,column",
        [
            (itype, col)
            for itype, cols in VALID_INVENTORY_VALUE_COLUMNS.items()
            for col in cols
        ]
    )
    def test_all_valid_columns_pass(self, inventory_type, column):
        schema = {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": inventory_type,
                    "inventory_value_column": column,
                }
            },
        }
        result = validate_parameters_schema_inventory(schema)
        assert result == schema

    def test_invalid_column_raises_explicit_error(self):
        schema = {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "servers",
                    "inventory_value_column": "bad_col",
                }
            },
        }
        with pytest.raises(serializers.ValidationError) as exc_info:
            validate_parameters_schema_inventory(schema)
        error = str(exc_info.value)
        assert "target" in error
        assert "must be one of" in error
        assert "servers" in error

    def test_column_wrong_type_raises(self):
        """engine_type is valid for servers but not for databases."""
        schema = {
            "type": "object",
            "properties": {
                "db": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "databases",
                    "inventory_value_column": "engine_type",
                }
            },
        }
        with pytest.raises(serializers.ValidationError):
            validate_parameters_schema_inventory(schema)

    def test_absent_inventory_value_column_passes(self):
        """Backward compatibility — existing schemas without inventory_value_column pass."""
        schema = {
            "type": "object",
            "properties": {
                "srv": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "servers",
                }
            },
        }
        result = validate_parameters_schema_inventory(schema)
        assert result == schema

    def test_none_inventory_value_column_passes(self):
        """Explicit None is treated as absent — passes."""
        schema = {
            "type": "object",
            "properties": {
                "srv": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "servers",
                    "inventory_value_column": None,
                }
            },
        }
        result = validate_parameters_schema_inventory(schema)
        assert result == schema

    def test_round_trip_preserves_schema(self):
        """validate_parameters_schema_inventory returns the schema unchanged (AC #3)."""
        schema = {
            "type": "object",
            "properties": {
                "instance": {
                    "type": "string",
                    "source": "inventory",
                    "inventory_type": "instances",
                    "inventory_value_column": "server_ref",
                }
            },
        }
        result = validate_parameters_schema_inventory(schema)
        assert result is schema  # même objet, pas de copie
```

### Lancer les tests

```bash
# Depuis idp-portal/django_backend/ :
.venv/bin/python -m pytest catalog/tests/test_parameters_schema_validation.py -v
```

**Attention — known issue :** ne pas utiliser `pytest catalog/tests/` sans `--ignore=catalog/tests.py` si un fichier `tests.py` conflictuel existe. Ici le chemin direct vers le fichier évite le problème.

### Project Structure Notes

**Fichiers à modifier :**
- `idp-portal/django_backend/catalog/serializers.py`
  - Ajouter constante `VALID_INVENTORY_VALUE_COLUMNS` après ligne 30
  - Étendre `validate_parameters_schema_inventory` avec bloc Story 37.4

**Fichiers de test à modifier :**
- `idp-portal/django_backend/catalog/tests/test_parameters_schema_validation.py`
  - Ajouter import `VALID_INVENTORY_VALUE_COLUMNS`
  - Ajouter classe `TestInventoryValueColumn` avec ~9 tests (tâches 4.1–4.9)

**Aucune modification requise :**
- `catalog/models.py` — `OracleJSONField` stocke JSON flexible, aucun changement de schéma
- `inventory/` — aucun impact sur query executor, views, serializers
- `catalog/views.py` — validation appelée via serializer, transparente

### Références

- `idp-portal/django_backend/catalog/serializers.py` lignes 30, 79–110 (`VALID_INVENTORY_TYPES`, `validate_parameters_schema_inventory`)
- `idp-portal/django_backend/catalog/tests/test_parameters_schema_validation.py` — tests existants Story 23.5
- `idp-portal/django_backend/inventory/mapper.py` lignes 3–50 — colonnes exposées par entité
- `_bmad-output/planning-artifacts/epic-37-inventaire-environnement-serveur-colonne-engine.md` — Story 37.4 AC complets
- `_bmad-output/planning-artifacts/spec-inventaire-environnement-serveur-colonne-engine.md` — Section 2

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

Aucun blocage. Implémentation directe selon les Dev Notes.

### Completion Notes List

- Ajout de `VALID_INVENTORY_VALUE_COLUMNS` (constante) dans `catalog/serializers.py` après `VALID_INVENTORY_TYPES` (ligne 31).
- Extension de `validate_parameters_schema_inventory` : bloc Story 37.4 ajouté après la validation `inventory_type`. La validation `inventory_value_column` est optionnelle (None/absent → passe), et l'erreur inclut le nom du paramètre, les valeurs autorisées et l'inventory_type.
- Pas de `__all__` restrictif dans `catalog/serializers.py` : `VALID_INVENTORY_VALUE_COLUMNS` est directement importable.
- 18 nouveaux tests ajoutés dans `TestInventoryValueColumn` (4.1–4.9, dont 10 cas paramétrés). 33/33 tests PASSED, 0 régression.
- Aucune migration, aucun changement de modèle requis (`parameters_schema` est un champ JSON flexible).

### File List

- `idp-portal/django_backend/catalog/serializers.py`
- `idp-portal/django_backend/catalog/tests/test_parameters_schema_validation.py`

## Senior Developer Review (AI)

**Date :** 2026-02-23 | **Reviewer :** Cyrille (AI) | **Résultat :** Approuvé avec corrections

### Constatations

**ACs :** Tous implémentés et vérifiés ✅
**Tests initiaux :** 33/33 PASSED ✅

**Problèmes corrigés automatiquement :**

| # | Sévérité | Fichier | Description | Statut |
|---|----------|---------|-------------|--------|
| M1 | MEDIUM | `test_parameters_schema_validation.py` | Ajout de `test_valid_inventory_value_columns_covers_all_inventory_types` — invariant qui garantit que `VALID_INVENTORY_VALUE_COLUMNS` couvre exactement `VALID_INVENTORY_TYPES`. Sans ce test, un désynchronisme produirait le message vide `"must be one of: "`. | Corrigé |
| M2 | MEDIUM | `test_parameters_schema_validation.py` | Ajout de `test_inventory_value_column_invalid_on_second_param_fails` — couverture multi-params : premier param valide + second param avec colonne invalide. | Corrigé |
| L1 | LOW | `catalog/serializers.py` | Docstring `ActionSerializer.validate_parameters_schema` mise à jour : `"Story 23.5"` → `"Story 23.5 + 37.4"`. | Corrigé |
| L2 | LOW | `test_parameters_schema_validation.py` | Test 4.4 renforcé : ajout `assert "inventory_value_column" in error` (AC2 spécifie ce terme dans le format du message). | Corrigé |
| L3 | LOW | `test_parameters_schema_validation.py` | Ajout de `test_inventory_value_column_empty_string_fails` — edge case `""` non None, symétrique à `test_inventory_type_empty_string_fails`. | Corrigé |

**Résultat après corrections :** 36/36 PASSED ✅ (3 nouveaux tests ajoutés)

## Change Log

- 2026-02-23 : Story 37.4 implémentée — ajout `VALID_INVENTORY_VALUE_COLUMNS` et validation `inventory_value_column` optionnelle dans `validate_parameters_schema_inventory` ; 18 nouveaux tests (33/33 pass).
- 2026-02-23 : Code review AI — 2 MEDIUM + 3 LOW corrigés (invariant test, multi-param test, docstring, assertion AC2, edge case empty string) ; 36/36 tests pass. Status → done.
