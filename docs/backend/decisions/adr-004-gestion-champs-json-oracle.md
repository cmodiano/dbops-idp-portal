# ADR-004 : Gestion des Champs JSON avec Oracle Database

**Date :** 2026-02-08
**Statut :** Accepté
**Décideurs :** Équipe IDP — Migration Epic M

## Contexte

La base de données Oracle du projet IDP stocke plusieurs colonnes en format JSON dans des colonnes CLOB :
- `parameters_schema` (Action) — schéma JSON des paramètres d'exécution
- `impact_rules` (Action) — règles d'impact par environnement
- `execution_steps` (Action) — étapes d'exécution ordonnées
- `config` (Integration) — configuration de la plateforme externe
- `remediation_rules` (Action) — règles de remédiation automatique

Le backend FastAPI gérait ces champs manuellement avec `json.loads()` / `json.dumps()`. La migration vers Django nécessitait de choisir une approche standardisée.

## Décision

**Utiliser `OracleJSONField` (champ custom Django) pour les nouveaux champs JSON et les champs migrés.** Ce champ :
1. Stocke les données en CLOB Oracle
2. Sérialise/désérialise automatiquement Python dict ↔ JSON string
3. Valide le format JSON à la sauvegarde
4. Permet les queries JSON natives Oracle (via `JSON_VALUE` en raw SQL si nécessaire)

**Pour les champs legacy :** `TextField` + `json.loads()` pour les colonnes existantes non encore migrées, avec validation applicative dans le serializer.

**Pattern :**
```python
# core/fields.py
class OracleJSONField(models.TextField):
    """Champ JSON stocké en CLOB Oracle avec sérialisation automatique."""

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return json.loads(value) if isinstance(value, str) else value

    def get_prep_value(self, value):
        if value is None:
            return value
        return json.dumps(value)
```

## Conséquences

### Positives
- Sérialisation automatique — plus de `json.loads()` / `json.dumps()` manuels dans les vues
- Validation JSON à la sauvegarde — détection précoce des données corrompues
- Compatibilité Oracle CLOB — pas besoin de colonne JSON native (Oracle 21c+)
- Serializers DRF simplifié — le champ retourne directement un dict Python

### Négatives
- Pas de queries JSON natives Django (pas de `__jsonpath` lookup) — nécessite SQL brut pour filtrer dans le JSON
- Validation de schéma JSON à implémenter côté application (pas de contrainte BD)
- Performance : désérialisation à chaque lecture, même si le JSON n'est pas utilisé (atténué par `defer()`)

### Neutres
- Compatible avec Oracle 12c+ (CLOB) — pas besoin d'Oracle 21c (JSON natif)
- Migration progressive possible : les champs legacy peuvent être migrés un par un

## Alternatives Considérées

### Alternative 1 : Normaliser les colonnes JSON en tables relationnelles
- **Description :** Remplacer `parameters_schema` JSON par des tables `action_parameters` avec colonnes dédiées
- **Raison du rejet :** Refonte de base trop lourde pour le MVP — les schémas JSON sont dynamiques et variables par action

### Alternative 2 : Type JSON natif Oracle 21c
- **Description :** Utiliser le type `JSON` natif d'Oracle (disponible depuis 21c)
- **Raison du rejet :** Stack Oracle imposée est 19c — pas de type JSON natif disponible

### Alternative 3 : JSONField Django standard
- **Description :** Utiliser `django.db.models.JSONField` (supporté nativement depuis Django 3.1)
- **Raison du rejet :** `JSONField` Django utilise `JSON_TYPE` Oracle qui n'est pas disponible sur Oracle 19c en CLOB. Le champ custom `OracleJSONField` gère correctement le stockage CLOB.

## Références

- OracleJSONField implementation — `idp-portal/django_backend/core/fields.py` (dépôt)
- Story 17-4 — Refactoring OracleJSONField
- [Django JSONField documentation](https://docs.djangoproject.com/en/stable/ref/models/fields/#jsonfield)
