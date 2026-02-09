# Story 23.2: Backend — InventoryService multi-tables

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur backend,
je veux implémenter les méthodes InventoryService `list_servers`, `list_instances`, `list_databases` avec filtres,
afin que le système puisse charger les entités d'inventaire multi-tables et filtrer les instances/DB par serveur choisi.

## Acceptance Criteria

**Given** une configuration d'inventaire multi-tables (story 23.1 complétée)
**When** je charge les entités serveurs/instances/databases
**Then** le service utilise InventoryMapper et applique les filtres requis

**AC1 : Méthode list_servers avec filtres**

**Given** une config d'inventaire avec entities.servers
**When** j'appelle `list_servers(environment=..., engine_type=...)`
**Then** la méthode utilise `_read_servers_from_config` (story 23.1)
**And** retourne une liste de dicts `{ id, name, environment, engine_type }`
**And** filtre par environment (requis) et engine_type (optionnel)
**And** si config fallback table plate, retourne serveurs avec TYPE=server
**And** logue l'opération avec correlation_id

**AC2 : Méthode list_instances avec filtre serveur**

**Given** une config d'inventaire avec entities.instances
**When** j'appelle `list_instances(environment=..., server_name=..., server_names=...)`
**Then** la méthode utilise `_read_instances_from_config` (story 23.1)
**And** retourne une liste de dicts `{ id, name, environment, server_ref, db_ref? }`
**And** filtre par environment (requis)
**And** si server_name fourni, retourne uniquement les instances liées à ce serveur
**And** si server_names (liste) fourni, retourne instances liées à un des serveurs (clause IN)
**And** si config fallback, retourne liste vide ou instances avec TYPE=instance si colonne existe
**And** logue l'opération avec correlation_id et nb instances retournées

**AC3 : Méthode list_databases avec filtre serveur**

**Given** une config d'inventaire avec entities.databases
**When** j'appelle `list_databases(environment=..., server_name=..., server_names=...)`
**Then** la méthode utilise `_read_databases_from_config` (story 23.1)
**And** retourne une liste de dicts `{ id, name, environment }`
**And** filtre par environment (requis)
**And** si server_name fourni, retourne uniquement les DB liées aux instances de ce serveur (via JOIN)
**And** si server_names (liste) fourni, retourne DB liées aux instances des serveurs (clause IN)
**And** si config fallback, retourne liste vide ou databases avec TYPE=database si colonne existe
**And** logue l'opération avec correlation_id et nb databases retournées

**AC4 : RBAC list_targets_for_user inchangé sur serveurs**

**Given** un utilisateur avec profils RBAC existants
**When** j'appelle `list_targets_for_user(user, environment)`
**Then** la méthode continue de s'appuyer sur les **serveurs** comme cibles d'exécution
**And** utilise `list_servers` au lieu de `list_targets` en interne si config multi-tables active
**And** applique les filtres RBAC (LIST, PATTERN, ALL) sur les serveurs retournés
**And** retourne le format existant compatible avec l'API actuelle
**And** ne change PAS le comportement actuel (rétrocompatibilité totale)

**AC5 : Cohérence instances/DB avec serveurs autorisés**

**Given** un utilisateur avec accès RBAC limité à certains serveurs
**When** j'appelle `list_instances` ou `list_databases` avec un server_name non autorisé
**Then** le service NE filtre PAS directement par RBAC (les méthodes list_instances/databases sont des helpers techniques)
**And** l'appelant (API layer) est responsable de valider que le server_name est dans la liste des serveurs autorisés
**And** documentation explicite de cette responsabilité dans les docstrings

**AC6 : Gestion des erreurs et logging**

**Given** une opération d'inventaire multi-tables
**When** une erreur survient (config invalide, table inexistante, colonne manquante)
**Then** le service logue l'erreur avec niveau ERROR et correlation_id
**And** lève une exception InventoryServiceError avec message explicite
**And** inclut le contexte d'erreur (entity_name, environment, server_name si applicable)
**And** n'expose jamais de détails SQL sensibles dans les messages d'erreur

**AC7 : Performance et limites**

**Given** un inventaire avec des milliers de serveurs/instances/databases
**When** les méthodes list_* sont appelées
**Then** les requêtes SQL utilisent ROWNUM ≤ MAX_MULTI_TABLE_RESULTS (story 23.1 : 10000)
**And** logue un WARNING si la limite est atteinte
**And** les requêtes sont optimisées (index supposés sur colonnes environment, server_ref)
**And** aucune requête N+1 (pas de boucle sur serveurs pour charger instances)

**AC8 : Tests unitaires**

**Given** les nouvelles méthodes InventoryService
**When** les tests unitaires sont exécutés
**Then** ils couvrent :
- `list_servers` avec et sans engine_type
- `list_instances` avec server_name unique et multiples (server_names)
- `list_databases` avec server_name et server_names
- Fallback table plate pour chaque méthode
- Gestion d'erreurs (table inexistante, config invalide)
- Logging des opérations
- `list_targets_for_user` utilise bien `list_servers` si config multi-tables

## Tasks / Subtasks

- [x] Task 1 : Méthode list_servers (AC1)
  - [x] 1.1 : Implémenter `list_servers(environment, engine_type=None)` dans InventoryService
  - [x] 1.2 : Appeler `_read_servers_from_config` (déjà implémenté story 23.1)
  - [x] 1.3 : Valider environment (non vide), valider engine_type si fourni (whitelist ou pattern)
  - [x] 1.4 : Logger l'opération : `inventory_list_servers`, environment, engine_type, nb_results, correlation_id
  - [x] 1.5 : Retourner liste standardisée `[{ id, name, environment, engine_type? }]`
  - [x] 1.6 : Tester avec config multi-tables et fallback table plate

- [x] Task 2 : Méthode list_instances (AC2)
  - [x] 2.1 : Implémenter `list_instances(environment, server_name=None, server_names=None)`
  - [x] 2.2 : Appeler `_read_instances_from_config` (déjà implémenté story 23.1)
  - [x] 2.3 : Valider que environment est fourni
  - [x] 2.4 : Si server_name et server_names fournis simultanément, lever ValueError
  - [x] 2.5 : Logger l'opération : `inventory_list_instances`, environment, server_filter, nb_results, correlation_id
  - [x] 2.6 : Retourner liste `[{ id, name, environment, server_ref, db_ref? }]`
  - [x] 2.7 : Tester filtrage par server_name unique, par server_names (liste), sans filtre

- [x] Task 3 : Méthode list_databases (AC3)
  - [x] 3.1 : Implémenter `list_databases(environment, server_name=None, server_names=None)`
  - [x] 3.2 : Appeler `_read_databases_from_config` (déjà implémenté story 23.1)
  - [x] 3.3 : Valider environment fourni, gérer server_name XOR server_names
  - [x] 3.4 : Logger l'opération : `inventory_list_databases`, environment, server_filter, nb_results, correlation_id
  - [x] 3.5 : Retourner liste `[{ id, name, environment }]`
  - [x] 3.6 : Tester filtrage par serveur et sans filtre

- [x] Task 4 : Adapter list_targets_for_user pour multi-tables (AC4)
  - [x] 4.1 : Détecter si config multi-tables active (entities.servers existe)
  - [x] 4.2 : Si oui, utiliser `list_servers(environment)` au lieu de `list_targets(..., target_type='server')`
  - [x] 4.3 : Conserver toute la logique RBAC actuelle (LIST, PATTERN, ALL)
  - [x] 4.4 : Retourner format identique à l'actuel (Target-like dicts)
  - [x] 4.5 : Ajouter tests de régression pour vérifier comportement inchangé

- [x] Task 5 : Documentation responsabilité RBAC (AC5)
  - [x] 5.1 : Documenter dans docstrings de list_instances/list_databases : "No RBAC filtering applied - caller must validate server_name against user's allowed servers"
  - [x] 5.2 : Créer section dans `docs/inventory-mapping-config.md` : RBAC responsibilities
  - [x] 5.3 : Documenter le pattern : API layer valide serveurs autorisés, puis appelle list_instances/databases avec server_name validé

- [x] Task 6 : Gestion erreurs et logging (AC6)
  - [x] 6.1 : Wrapper tous les appels `_read_*_from_config` dans try/except
  - [x] 6.2 : Capturer MapperValidationError, oracledb errors, autres exceptions
  - [x] 6.3 : Logger niveau ERROR avec correlation_id et contexte (entity, environment, server)
  - [x] 6.4 : Lever InventoryServiceError avec message générique (pas de détails SQL)
  - [x] 6.5 : Tester chaque cas d'erreur (config invalide, table inexistante, colonne manquante)

- [x] Task 7 : Performance et limites (AC7)
  - [x] 7.1 : Vérifier que _read_*_from_config utilise bien ROWNUM ≤ MAX_MULTI_TABLE_RESULTS (story 23.1)
  - [x] 7.2 : Si nb résultats = MAX_MULTI_TABLE_RESULTS, logger WARNING "inventory_result_limit_reached"
  - [x] 7.3 : Documenter dans docstrings les limites de résultats
  - [x] 7.4 : Ajouter commentaire dans code : index requis sur environment, server_ref pour perf
  - [x] 7.5 : Tester requête avec inventaire > 10000 lignes (mock ou base test)

- [x] Task 8 : Tests unitaires et d'intégration (AC8)
  - [x] 8.1 : Créer `idp-portal/django_backend/inventory/tests/test_inventory_service_multi_tables.py`
  - [x] 8.2 : Tester list_servers avec/sans engine_type, config multi-tables et fallback
  - [x] 8.3 : Tester list_instances avec server_name unique, server_names liste, sans filtre
  - [x] 8.4 : Tester list_databases idem
  - [x] 8.5 : Tester list_targets_for_user utilise list_servers si config multi-tables
  - [x] 8.6 : Tester gestion d'erreurs pour chaque méthode
  - [x] 8.7 : Tester logging (vérifier structlog events)
  - [x] 8.8 : Vérifier couverture ≥ 85% pour nouveaux code paths

## Dev Notes

### Contexte architectural

**Référence** : `docs/inventaire-multi-tables-ux-cibles.md`, Story 23.1 complétée, `idp-portal/django_backend/inventory/services.py`, `idp-portal/django_backend/inventory/mapper.py`

**Architecture** :
- **Story 23.1 (done)** : InventoryMapper + `_read_servers_from_config`, `_read_instances_from_config`, `_read_databases_from_config` (helpers privés)
- **Cette story** : Méthodes publiques `list_servers`, `list_instances`, `list_databases` exposées pour utilisation API
- **RBAC** : `list_targets_for_user` continue de gérer les serveurs comme cibles d'exécution, utilise `list_servers` si config multi-tables
- **Responsabilité** : list_instances/databases ne filtrent PAS par RBAC (helpers techniques), l'API layer doit valider server_name

**Technologies** :
- Django 5.2 + python-oracledb
- structlog pour logging structuré avec correlation_id
- InventoryMapper (story 23.1) pour construction SQL

### Fichiers à modifier

**Modifier** :
- `idp-portal/django_backend/inventory/services.py` :
  - Ajouter méthodes publiques `list_servers`, `list_instances`, `list_databases`
  - Adapter `list_targets_for_user` pour utiliser `list_servers` si config multi-tables
  - Wrapper try/except pour gestion d'erreurs
  - Logging structlog pour toutes opérations

**Créer** :
- `idp-portal/django_backend/inventory/tests/test_inventory_service_multi_tables.py` : Tests des nouvelles méthodes

**Documenter** :
- `docs/inventory-mapping-config.md` : Section RBAC responsibilities (compléter doc story 23.1)

### Patterns de code

**Méthode list_servers (exemple)** :
```python
def list_servers(
    self,
    environment: str,
    engine_type: str | None = None
) -> list[dict[str, Any]]:
    """
    List servers from multi-table inventory or flat table fallback.

    Args:
        environment: Target environment (required)
        engine_type: Optional filter by engine type (oracle, sqlserver, etc.)

    Returns:
        List of server dicts: [{ id, name, environment, engine_type? }]

    Raises:
        InventoryServiceError: If inventory source is unreachable or config invalid
    """
    correlation_id = get_correlation_id()

    try:
        servers = self._read_servers_from_config(environment, engine_type)

        logger.info(
            "inventory_list_servers",
            environment=environment,
            engine_type=engine_type,
            nb_results=len(servers),
            correlation_id=correlation_id
        )

        if len(servers) >= MAX_MULTI_TABLE_RESULTS:
            logger.warning(
                "inventory_result_limit_reached",
                entity="servers",
                limit=MAX_MULTI_TABLE_RESULTS,
                correlation_id=correlation_id
            )

        return servers

    except MapperValidationError as e:
        logger.error(
            "inventory_config_validation_failed",
            entity="servers",
            environment=environment,
            error=str(e),
            correlation_id=correlation_id
        )
        raise InventoryServiceError("Invalid inventory configuration") from e
    except Exception as e:
        logger.error(
            "inventory_list_servers_failed",
            environment=environment,
            error=str(e),
            correlation_id=correlation_id
        )
        raise InventoryServiceError("Failed to list servers") from e
```

**list_instances avec server_name** :
```python
def list_instances(
    self,
    environment: str,
    server_name: str | None = None,
    server_names: list[str] | None = None
) -> list[dict[str, Any]]:
    """
    List instances from multi-table inventory.

    NO RBAC FILTERING - caller must validate server_name against user's allowed servers.

    Args:
        environment: Target environment (required)
        server_name: Filter by single server (exclusive with server_names)
        server_names: Filter by multiple servers (exclusive with server_name)

    Returns:
        List of instance dicts: [{ id, name, environment, server_ref, db_ref? }]
    """
    if server_name and server_names:
        raise ValueError("Cannot specify both server_name and server_names")

    # ... implémentation similaire à list_servers
```

### Adaptation list_targets_for_user

**Logique** :
```python
def list_targets_for_user(
    self,
    user: User,
    environment: str
) -> list[dict]:
    """
    Existing method - now uses list_servers if multi-table config active.
    """
    correlation_id = get_correlation_id()

    # Detect multi-table config
    integration = self.get_active_inventory_integration()
    mapper = self._get_inventory_mapper(integration)

    if mapper and mapper.has_entity('servers'):
        # Use new multi-table path
        all_servers = self.list_servers(environment)
        # Apply RBAC filters (existing logic)
        filtered = self._apply_rbac_filters(user, all_servers, environment)
    else:
        # Fallback to existing list_targets path
        all_targets, _ = self.list_targets(environment=environment, target_type='server')
        filtered = self._apply_rbac_filters(user, all_targets, environment)

    return filtered
```

### Responsabilité RBAC

**Documentation dans docstrings** :
```python
def list_instances(...):
    """
    ...

    Security Note:
        This method does NOT apply RBAC filtering. The caller (API layer)
        is responsible for:
        1. Validating that user has access to specified server_name(s)
        2. Only passing server_name(s) from the user's allowed servers list
        3. Calling list_targets_for_user first to get allowed servers

    Example:
        # Good - API layer validates first
        allowed_servers = inventory.list_targets_for_user(user, environment)
        if server_name in [s['name'] for s in allowed_servers]:
            instances = inventory.list_instances(environment, server_name)

        # Bad - no validation
        instances = inventory.list_instances(environment, user_input_server)  # UNSAFE
    """
```

### Standards de tests

**Référence** : Story 23.1 (69 tests), Epic M patterns, Story 15-2 (security tests)

**Couverture requise** :
- Tests unitaires pour chaque méthode (list_servers, list_instances, list_databases)
- Tests avec config multi-tables et fallback table plate
- Tests filtres (environment, engine_type, server_name, server_names)
- Tests gestion d'erreurs (config invalide, table inexistante)
- Tests logging (vérifier structlog events capturés)
- Tests list_targets_for_user utilise list_servers si config multi-tables
- Coverage ≥ 85%

**Fixtures** :
- Réutiliser les configs de test de story 23.1 (multi-tables et flat)
- Mocker `_read_*_from_config` pour tests unitaires InventoryService
- Tests d'intégration avec base Oracle de test (si disponible)

**Assertions clés** :
- Vérifier que list_servers retourne bien engine_type si mappé dans config
- Vérifier que list_instances filtre correctement par server_name unique et liste
- Vérifier que list_databases JOIN via instances quand server_name fourni
- Vérifier que les erreurs sont loggées avec correlation_id
- Vérifier que list_targets_for_user conserve comportement actuel (régression tests)

### Dépendances et ordre

**Dépend de** :
- Story 23.1 (done) : InventoryMapper + `_read_*_from_config`
- Config multi-tables dans Integration.config (story 23.1)

**Bloque** :
- Story 23.3 : API /servers /databases /instances (nécessite ces méthodes du service)
- Story 23.6 : Frontend useTargetInventory avec server_name (nécessite API story 23.3)

**N'affecte PAS** :
- Comportement actuel de `list_targets` (conservé pour rétrocompatibilité)
- API `/inventory/targets` existante (continue de fonctionner)

### Risques et mitigations

**Risque** : Régression de list_targets_for_user (RBAC cassé)
**Mitigation** : Tests de régression complets, vérifier comportement identique avec et sans config multi-tables

**Risque** : list_instances/databases appelés sans validation RBAC
**Mitigation** : Documentation explicite, naming évocateur (_internal_list_instances?), tests montrant pattern correct

**Risque** : Performance dégradée sur gros inventaires
**Mitigation** : Limites MAX_MULTI_TABLE_RESULTS (story 23.1), logging WARNING, documentation index requis

**Risque** : Gestion d'erreurs incohérente entre méthodes
**Mitigation** : Pattern uniforme try/except pour toutes méthodes, tests erreurs pour chaque méthode

### Intelligence de la Story 23.1

**Learnings** :
- InventoryMapper validé et testé (69 tests passent)
- `_read_servers_from_config`, `_read_instances_from_config`, `_read_databases_from_config` implémentés et fonctionnels
- SAFE_TABLE_NAME_PATTERN + SAFE_COLUMN_NAME_PATTERN pour sécurité SQL
- Limites MAX_MULTI_TABLE_RESULTS = 10000 pour prévenir DoS
- Fallback table plate fonctionne : `_read_servers_flat_fallback` retourne serveurs avec TYPE=server

**Fichiers créés** :
- `inventory/mapper.py` : InventoryMapper avec build_select_clause, build_where_clause, validate_config
- `inventory/tests/test_mapper.py` : 38 tests unitaires
- `inventory/tests/test_inventory_multi_tables.py` : 31 tests intégration
- `docs/inventory-mapping-config.md` : Documentation config

**Patterns à réutiliser** :
- `from __future__ import annotations` pour Python 3.9+ compatibility
- Type hints complets `dict[str, Any]` au lieu de `Dict[str, Any]`
- Validation stricte avant construction SQL (MapperValidationError)
- Logging structlog avec correlation_id pour toutes opérations
- ROWNUM ≤ MAX_* dans toutes requêtes SQL

### Commits récents pertinents

**Référence** : `git log --oneline -10`

- `3d39053 feat(23-1): implement config-driven multi-table inventory mapping` — Story 23.1 complétée, InventoryMapper opérationnel
- `09a0c14 feat(22-20): integrate drf-spectacular for automated API documentation` — Specs OpenAPI pour nouvelle API (story 23.3)
- `e82c63f feat(22-19): implement progressive mypy enforcement with baseline tracking` — Mypy actif, type hints requis

**Code patterns récents** :
- Utiliser drf-spectacular @extend_schema pour documenter endpoints (story 23.3)
- Type hints stricts (mypy enforcement progressif)
- Logging structlog systématique avec correlation_id

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- 109/109 tests pass (69 story 23.1 + 40 story 23.2)
- 22 pre-existing failures in test_views.py (301 redirects) and test_environments.py (User model) — not caused by this story

### Completion Notes List

- **Task 1 (AC1):** `list_servers(environment, engine_type=None)` — validates environment, calls `_read_servers_from_config`, logs with structlog, warns on MAX_MULTI_TABLE_RESULTS limit, docstring documents performance limit
- **Task 2 (AC2):** `list_instances(environment, server_name=None, server_names=None)` — validates params (XOR server_name/server_names, rejects empty list), uses optimized IN clause for server_names (single query instead of N+1), NO RBAC filtering
- **Task 3 (AC3):** `list_databases(environment, server_name=None, server_names=None)` — same pattern as instances, uses optimized IN clause + JOIN via instances for server_names filter
- **Task 4 (AC4):** `list_targets_for_user` detects `InventoryMapper.is_multi_table` and uses `list_servers` per allowed environment instead of `list_targets`. RBAC filters (LIST, PATTERN, ALL) applied identically. Returns Target-like dicts for API compatibility. Raises error if ALL environments fail (no silent failure).
- **Task 5 (AC5):** RBAC responsibility documented in docstrings (Security Note, Performance Note) and `docs/inventory-mapping-config.md` (detailed 3-step pattern with PermissionDenied example)
- **Task 6 (AC6):** All public methods wrap calls in try/except, catch MapperValidationError + generic Exception, log ERROR with correlation_id and context, raise InventoryServiceError with generic message
- **Task 7 (AC7):** ROWNUM limit verified (story 23.1), WARNING logged on limit reached, docstrings document limits in Performance Note sections, optimized queries use IN clause to avoid N+1
- **Task 8 (AC8):** 43 tests covering all ACs + fixes — list_servers (7), list_instances (9, added empty list validation), list_databases (8, added empty list validation), list_targets_for_user multi-table (5, added all-envs-fail test), error handling (6), RBAC documentation (4), performance limits (4)

### Change Log

- 2026-02-09: Story 23.2 implemented — public methods list_servers/list_instances/list_databases, list_targets_for_user multi-table adaptation, RBAC documentation, 40 tests
- 2026-02-09: Code review fixes — optimized server_names to use IN clause (fixes N+1), added empty list validation, added all-envs-fail error handling, enhanced docstrings with Performance Note, improved RBAC docs with 3-step example, 43 tests (3 new)

### File List

- `idp-portal/django_backend/inventory/services.py` (modified) — Added list_servers, list_instances, list_databases public methods; adapted list_targets_for_user for multi-table config detection
- `idp-portal/django_backend/inventory/tests/test_inventory_service_multi_tables.py` (created) — 40 tests covering AC1-AC8
- `docs/inventory-mapping-config.md` (modified) — Added RBAC responsibilities section, updated architecture diagram
