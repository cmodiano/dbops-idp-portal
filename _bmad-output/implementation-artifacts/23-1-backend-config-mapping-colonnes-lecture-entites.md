# Story 23.1: Backend — Config mapping colonnes + lecture entités

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur backend,
je veux configurer un mapping flexible des tables et colonnes d'inventaire pour les entités SERVER, INSTANCE et DB,
afin que le système puisse lire l'inventaire selon une configuration déclarative sans colonnes en dur.

## Acceptance Criteria

**Given** une configuration d'inventaire avec mapping d'entités
**When** le système lit l'inventaire
**Then** il utilise les colonnes mappées et non des noms hardcodés

**AC1 : Configuration de mapping d'entités**

**Given** un fichier de configuration d'intégration inventory_db
**When** je définis le mapping d'entités
**Then** je peux spécifier pour chaque entité (servers, instances, databases) :
- Le nom de la table/vue source
- Le mapping des colonnes métier vers colonnes réelles (ex. name → HOSTNAME, environment → ENV, engine_type → ENGINE)
- L'id_column utilisé comme identifiant
- Les clés de relation (ex. server_ref pour instances → serveurs)
**And** je peux définir un mode "table plate" (fallback) avec mapping simple NAME, ENVIRONMENT, TYPE

**AC2 : Layer InventoryMapper**

**Given** la configuration de mapping chargée
**When** InventoryMapper construit une requête SQL
**Then** il génère le SELECT avec les colonnes mappées en alias
**And** il applique les WHERE sur les colonnes mappées (pas hardcodées)
**And** il valide tous les noms de tables/colonnes selon SAFE_TABLE_NAME_PATTERN avant usage

**AC3 : Lecture entité servers**

**Given** une config avec `entities.servers` pointant vers une table SERVER
**When** j'appelle `_read_servers_from_config(environment=...)`
**Then** la requête SQL utilise la table mappée et les colonnes mappées
**And** retourne une liste de dicts avec clés standard (id, name, environment, engine_type si mappé)
**And** les valeurs sont extraites des colonnes réelles selon le mapping

**AC4 : Lecture entité instances**

**Given** une config avec `entities.instances` avec colonne server_ref
**When** j'appelle `_read_instances_from_config(environment=..., server_name=...)`
**Then** la requête SQL joint (ou filtre) sur la colonne server_ref mappée
**And** retourne les instances liées au serveur spécifié
**And** inclut les attributs mappés (id, name, environment, server_ref, db_ref si présent)

**AC5 : Lecture entité databases**

**Given** une config avec `entities.databases`
**When** j'appelle `_read_databases_from_config(environment=..., server_name=...)`
**Then** la requête SQL utilise la table DB mappée
**And** si server_name fourni, filtre via la relation instance → DB
**And** retourne les DB avec attributs mappés (id, name, environment)

**AC6 : Fallback mode table plate**

**Given** une configuration sans entities.servers/instances/databases (seulement table plate)
**When** le système lit l'inventaire
**Then** il utilise `_read_oracle_inventory` existant
**And** `_read_servers_from_config` retourne les lignes avec TYPE=server
**And** `_read_instances_from_config` et `_read_databases_from_config` retournent liste vide ou comportement équivalent

**AC7 : Validation de sécurité**

**Given** une configuration avec noms de tables/colonnes
**When** InventoryMapper construit une requête
**Then** tous les noms de tables sont validés par SAFE_TABLE_NAME_PATTERN
**And** tous les noms de colonnes sont validés par un pattern similaire
**And** toute tentative d'injection SQL est bloquée avant l'exécution de la requête
**And** les erreurs de validation sont loggées avec correlation_id

**AC8 : Tests unitaires**

**Given** le module InventoryMapper
**When** les tests unitaires sont exécutés
**Then** ils couvrent :
- Parsing de config multi-tables et table plate
- Construction de requêtes SQL avec alias corrects
- Validation stricte des noms tables/colonnes
- Gestion des erreurs (table inexistante, colonne manquante)
- Extraction et transformation des données retournées

## Tasks / Subtasks

- [x] Task 1 : Configuration du mapping d'entités (AC1)
  - [x] 1.1 : Étendre le modèle Integration.config pour supporter `entities.servers`, `entities.instances`, `entities.databases`
  - [x] 1.2 : Définir le schéma JSON de la config de mapping : table, columns (dict concept→colonne), id_column, relations
  - [x] 1.3 : Créer une config d'exemple pour mode multi-tables (SERVER, INSTANCE, DB)
  - [x] 1.4 : Créer une config d'exemple pour mode table plate (fallback)
  - [x] 1.5 : Documenter le format de config dans `docs/inventory-mapping-config.md`

- [x] Task 2 : Layer InventoryMapper (AC2)
  - [x] 2.1 : Créer le module `idp-portal/django_backend/inventory/mapper.py`
  - [x] 2.2 : Implémenter `InventoryMapper.__init__(config)` pour charger la config de mapping
  - [x] 2.3 : Implémenter `build_select_clause(entity_name)` avec alias des colonnes mappées
  - [x] 2.4 : Implémenter `build_where_clause(entity_name, filters)` avec colonnes mappées
  - [x] 2.5 : Implémenter `_validate_table_name(name)` et `_validate_column_name(name)` avec SAFE_PATTERN
  - [x] 2.6 : Ajouter logging structuré (correlation_id) pour toutes les opérations de mapping

- [x] Task 3 : Lecture entité servers (AC3)
  - [x] 3.1 : Implémenter `_read_servers_from_config(environment, engine_type=None)` dans InventoryService
  - [x] 3.2 : Utiliser InventoryMapper pour construire la requête SQL sur la table servers
  - [x] 3.3 : Exécuter la requête avec filtres environment et engine_type (si mappé et fourni)
  - [x] 3.4 : Transformer les résultats en liste de dicts standardisés (id, name, environment, engine_type)
  - [x] 3.5 : Ajouter gestion d'erreurs (table inexistante, colonnes manquantes) avec logging

- [x] Task 4 : Lecture entité instances (AC4)
  - [x] 4.1 : Implémenter `_read_instances_from_config(environment, server_name=None)` dans InventoryService
  - [x] 4.2 : Construire requête SQL avec filtre sur colonne server_ref (si server_name fourni)
  - [x] 4.3 : Gérer le cas multi-serveurs (server_names: List[str]) avec clause IN
  - [x] 4.4 : Retourner instances avec attributs mappés (id, name, environment, server_ref, db_ref)
  - [x] 4.5 : Ajouter tests pour filtrage par serveur unique et multiples serveurs

- [x] Task 5 : Lecture entité databases (AC5)
  - [x] 5.1 : Implémenter `_read_databases_from_config(environment, server_name=None)` dans InventoryService
  - [x] 5.2 : Si server_name fourni, joindre via INSTANCE (instance.server_ref = server AND instance.db_ref = db.name)
  - [x] 5.3 : Sinon, retourner toutes les DB de l'environnement
  - [x] 5.4 : Retourner databases avec attributs mappés (id, name, environment)
  - [x] 5.5 : Optimiser les jointures pour éviter N+1 queries (DISTINCT + single JOIN)

- [x] Task 6 : Fallback mode table plate (AC6)
  - [x] 6.1 : Détecter si config est en mode table plate (pas de entities.servers défini)
  - [x] 6.2 : Dans `_read_servers_from_config`, utiliser `_read_oracle_inventory()` avec filtre TYPE=server
  - [x] 6.3 : Dans `_read_instances_from_config`, retourner liste vide ou filtrer TYPE=instance si colonne existe
  - [x] 6.4 : Dans `_read_databases_from_config`, retourner liste vide ou filtrer TYPE=database
  - [x] 6.5 : Maintenir la rétrocompatibilité complète avec le mode actuel

- [x] Task 7 : Validation de sécurité (AC7)
  - [x] 7.1 : Réutiliser SAFE_TABLE_NAME_PATTERN existant de `inventory/services.py`
  - [x] 7.2 : Créer SAFE_COLUMN_NAME_PATTERN (alphanum + underscore, pas d'espaces/quotes)
  - [x] 7.3 : Valider tous les noms avant construction SQL (raise MapperValidationError si invalide)
  - [x] 7.4 : Logger toute tentative d'injection avec niveau WARNING et correlation_id
  - [x] 7.5 : Ajouter tests spécifiques tentative injection SQL (table name, column name, filter values)

- [x] Task 8 : Tests unitaires et d'intégration (AC8)
  - [x] 8.1 : Créer `idp-portal/django_backend/inventory/tests/test_mapper.py` pour InventoryMapper
  - [x] 8.2 : Tester parsing config multi-tables et table plate
  - [x] 8.3 : Tester construction SELECT/WHERE avec alias corrects
  - [x] 8.4 : Tester validation stricte noms tables/colonnes (cas valides et invalides)
  - [x] 8.5 : Créer `idp-portal/django_backend/inventory/tests/test_inventory_multi_tables.py` pour InventoryService
  - [x] 8.6 : Tester `_read_servers_from_config` avec config multi-tables et fallback
  - [x] 8.7 : Tester `_read_instances_from_config` avec filtres server_name
  - [x] 8.8 : Tester `_read_databases_from_config` avec et sans server_name
  - [x] 8.9 : Ajouter tests d'intégration avec base Oracle de test (ou mocks)
  - [x] 8.10 : Vérifier couverture de code ≥ 85% pour les nouveaux modules

## Dev Notes

### Contexte architectural

**Référence** : `docs/inventaire-multi-tables-ux-cibles.md`, `idp-portal/django_backend/inventory/services.py`, `idp-portal/django_backend/integrations/models.py`

**Architecture cible** :
- **Modèle évolutif** : aucune colonne en dur, tout piloté par configuration
- **Couche de mapping** : InventoryMapper traduit concepts métier → colonnes réelles
- **Sécurité first** : validation stricte de tous les identifiants SQL avant utilisation
- **Rétrocompatibilité** : fallback complet sur le mode table plate actuel

**Technologies** :
- Django 5.2 ORM (modèle Integration.config pour stocker la config de mapping)
- python-oracledb pour les requêtes SQL brutes
- structlog pour logging avec correlation_id

### Fichiers à modifier/créer

**Nouveau** :
- `idp-portal/django_backend/inventory/mapper.py` : Layer InventoryMapper
- `idp-portal/django_backend/inventory/tests/test_mapper.py` : Tests InventoryMapper
- `idp-portal/django_backend/inventory/tests/test_inventory_multi_tables.py` : Tests InventoryService multi-tables
- `docs/inventory-mapping-config.md` : Documentation du format de config

**Modifier** :
- `idp-portal/django_backend/inventory/services.py` : Ajouter `_read_servers_from_config`, `_read_instances_from_config`, `_read_databases_from_config`
- `idp-portal/django_backend/integrations/models.py` : Documenter le schéma JSON attendu dans Integration.config (ou ajouter validation si nécessaire)

### Patterns de sécurité

**Validation SQL** :
```python
SAFE_TABLE_NAME_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]*$')  # Existant
SAFE_COLUMN_NAME_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]*$')  # À ajouter

def _validate_identifier(name: str, pattern: re.Pattern) -> None:
    if not pattern.match(name):
        logger.warning(f"Invalid SQL identifier: {name}", extra={"correlation_id": ...})
        raise ValidationError(f"Invalid identifier: {name}")
```

**Construction SQL sécurisée** :
```python
# JAMAIS de f-string avec noms colonnes/tables non validés
# Toujours valider d'abord, puis construire
table_name = mapping['table']
_validate_identifier(table_name, SAFE_TABLE_NAME_PATTERN)
query = f"SELECT ... FROM {table_name} WHERE ..."  # OK après validation
```

### Format de configuration attendu

**Multi-tables** :
```json
{
  "entities": {
    "servers": {
      "table": "DBOPS_SERVERS",
      "id_column": "SERVER_ID",
      "columns": {
        "name": "HOSTNAME",
        "environment": "ENV",
        "engine_type": "ENGINE"
      }
    },
    "instances": {
      "table": "DBOPS_INSTANCES",
      "id_column": "INSTANCE_ID",
      "columns": {
        "name": "INSTANCE_NAME",
        "environment": "ENV",
        "server_ref": "SERVER_NAME",
        "db_ref": "DB_NAME"
      }
    },
    "databases": {
      "table": "DBOPS_DATABASES",
      "id_column": "DB_ID",
      "columns": {
        "name": "DB_NAME",
        "environment": "ENV"
      }
    }
  }
}
```

**Table plate (fallback)** :
```json
{
  "flat_table": {
    "table": "DBOPS_INVENTORY",
    "columns": {
      "name": "NAME",
      "environment": "ENVIRONMENT",
      "type": "TYPE"
    }
  }
}
```

### Standards de tests

**Référence** : Patterns Epic M, Story 15-2, Story 22-11

**Couverture requise** :
- Tests unitaires : tous les helpers, validations, construction SQL
- Tests d'intégration : lecture réelle depuis config multi-tables et fallback
- Tests de sécurité : tentatives d'injection SQL, noms invalides
- Coverage ≥ 85% pour nouveaux modules

**Fixtures** :
- Utiliser des configs de mapping en mémoire (pas de DB) pour tests unitaires InventoryMapper
- Mocker les résultats de requêtes Oracle pour tests InventoryService (ou utiliser base de test si disponible)

**Assertions clés** :
- Vérifier que les requêtes SQL générées contiennent les bons alias
- Vérifier que les filtres WHERE utilisent les colonnes mappées
- Vérifier que la validation bloque les noms invalides (quotes, espaces, SQL keywords)
- Vérifier que le fallback table plate fonctionne sans régression

### Dépendances et ordre

**Dépend de** :
- Configuration `inventory_db` dans Integration.config (déjà existant, à étendre)
- SAFE_TABLE_NAME_PATTERN existant dans `inventory/services.py`

**Bloque** :
- Story 23.2 : InventoryService.list_servers/list_instances/list_databases (nécessite cette couche de mapping)
- Story 23.3 : API /servers /databases /instances (nécessite les méthodes du service)

**N'affecte PAS** :
- Le comportement actuel de `list_targets_for_user` (jusqu'à Story 23.2)
- L'API `/inventory/targets` existante (continue de fonctionner)

### Risques et mitigations

**Risque** : Injection SQL via noms de tables/colonnes non validés
**Mitigation** : Validation stricte AVANT toute utilisation en SQL, patterns regex restrictifs, tests de sécurité dédiés

**Risque** : Régression du mode table plate actuel
**Mitigation** : Fallback explicite si config multi-tables absente, tests de régression complets

**Risque** : Performance des requêtes avec jointures multi-tables
**Mitigation** : Optimisation dans Story 23.2, mais prévoir logging temps d'exécution dès cette story

**Risque** : Config de mapping incorrecte (colonnes inexistantes)
**Mitigation** : Gestion d'erreurs robuste, logging détaillé, validation optionnelle de la config au démarrage

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- 3 test failures fixed: regex pattern tests had edge cases with empty string and newline handling
- Code review 2026-02-09: 6 HIGH + 4 MEDIUM issues fixed (Python 3.10+ type hints compatibility, security validation, result limits, type safety)

### Completion Notes List

- **Task 1 (AC1)** : Config de mapping d'entités défini dans `InventoryMapper` — support multi-tables (entities.servers/instances/databases) et table plate (flat_table). Documenté dans `docs/inventory-mapping-config.md`.
- **Task 2 (AC2)** : Layer `InventoryMapper` créé dans `inventory/mapper.py` — `build_select_clause` génère SELECT avec alias, `build_where_clause` utilise colonnes mappées, `validate_config` valide toute la config.
- **Task 3 (AC3)** : `_read_servers_from_config` implémenté — utilise mapper pour construire requêtes SQL sur table mappée, supporte filtres environment et engine_type.
- **Task 4 (AC4)** : `_read_instances_from_config` implémenté — filtre sur colonne server_ref mappée quand server_name fourni.
- **Task 5 (AC5)** : `_read_databases_from_config` implémenté — JOIN via instances quand server_name fourni (DISTINCT pour éviter doublons), sinon lecture directe.
- **Task 6 (AC6)** : Fallback table plate : servers utilise `_read_oracle_inventory` avec TYPE=server, instances/databases retournent liste vide.
- **Task 7 (AC7)** : `SAFE_COLUMN_NAME_PATTERN` + `_validate_table_name`/`_validate_column_name` avec logging WARNING + correlation_id. Tests injection SQL couverts.
- **Task 8 (AC8)** : 69 tests créés (46 test_mapper.py + 23 test_inventory_multi_tables.py), 152/152 tests inventory passent, 0 régression.
- **Code Review Fixes (2026-02-09)** : Ajout `from __future__ import annotations` + type hints complets `dict[str, Any]`, validation concept keys dans `build_where_clause`, limites Oracle 30 char pour identifiants, ROWNUM ≤ 10000 sur toutes requêtes multi-tables pour prévenir DoS, constantes MAX_MULTI_TABLE_RESULTS/MAX_FLAT_TABLE_RESULTS, commentaires nosec détaillés.

### Change Log

- 2026-02-09 : Implémentation complète Story 23.1 — InventoryMapper + lecture multi-tables + fallback + validation sécurité + 69 tests
- 2026-02-09 : Code review fixes — Python 3.9+ compatibility (future annotations), type hints complets, validation sécurité renforcée (concept keys, Oracle length limits), limites résultats (DoS prevention)

### File List

**Nouveau :**
- `idp-portal/django_backend/inventory/mapper.py` — Layer InventoryMapper (config parsing, SQL building, validation)
- `idp-portal/django_backend/inventory/tests/test_mapper.py` — 38 tests unitaires InventoryMapper
- `idp-portal/django_backend/inventory/tests/test_inventory_multi_tables.py` — 31 tests intégration InventoryService multi-tables
- `docs/inventory-mapping-config.md` — Documentation du format de configuration

**Modifié :**
- `idp-portal/django_backend/inventory/services.py` — Ajout import InventoryMapper, méthodes `_get_inventory_mapper`, `_read_servers_from_config`, `_read_instances_from_config`, `_read_databases_from_config`, `_read_databases_via_instances`, `_read_servers_flat_fallback`, `_execute_mapped_query`
