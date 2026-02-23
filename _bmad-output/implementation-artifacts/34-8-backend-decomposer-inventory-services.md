# Story 34.8 : Backend — Décomposer inventory/services.py (InventoryService)

Status: done

<!-- Réf: CODEBASE-REVIEW.md SOLID-BE-5 -->

## Story

En tant que mainteneur,
je veux extraire les responsabilités restantes de `InventoryService` (933 lignes, méthodes `_aggregate_profile_permissions` et `_load_targets`) en classes dédiées et injectables,
afin de rendre chaque composant testable indépendamment et de réduire le fichier d'orchestration (SRP).

## Acceptance Criteria

1. **Given** le fichier `inventory/services.py` actuel (933 lignes)
   **Then** la logique d'agrégation des permissions RBAC est extraite dans `inventory/permission_aggregator.py` — classe `RBACPermissionAggregator` (méthodes `aggregate`, `get_allowed_environments`), normalisation d'environment en méthode privée.

2. **And** la logique de chargement des targets est extraite dans `inventory/target_loader.py` — classe `TargetLoader` (méthode `load`) recevant `query_executor`, `list_targets_fn`, `list_servers_fn` par injection de dépendances.

3. **And** `InventoryService` dans `services.py` devient un orchestrateur pur :
   - `__init__` instancie les collaborateurs : `RBACPermissionAggregator` et `TargetLoader` via DI.
   - `list_targets_for_user` délègue à `self.permission_aggregator.aggregate(...)` et `self.target_loader.load(...)`.
   - `get_allowed_environments_for_user` délègue à `self.permission_aggregator.get_allowed_environments(...)`.

4. **And** aucun changement de comportement fonctionnel : tous les tests existants (`test_services.py`, `test_inventory_service_multi_tables.py`, `test_rbac_exclusion.py`, `test_rbac_filter_by_attribute.py`, `test_environments.py`, `test_views.py`, `test_views_multi_tables.py`, `test_integration_multi_tables.py`) passent **sans modification**.

5. **And** les backward-compat exports restent accessibles depuis `inventory.services` :
   - `InventoryService`, `InventoryServiceError`, `connection`, `MapperValidationError`
   - `MAX_MULTI_TABLE_RESULTS`, `MAX_FLAT_TABLE_RESULTS`, `SAFE_TABLE_NAME_PATTERN`
   - `_environments_cache` (importé par `test_services.py:446`)

6. **And** les nouveaux composants (`RBACPermissionAggregator`, `TargetLoader`) sont injectables (DI via constructeur) et testables unitairement en isolation.

## Tasks / Subtasks

- [x] Task 1 — Analyser les dépendances et cartographier les extractions
  - [x] 1.1 Confirmer les dépendances de `_aggregate_profile_permissions` (lignes 541–661) :
    - `EnvironmentHelper.normalize()`, `.is_in()`, `.matches()` → imports directs dans le nouveau fichier
    - `self.list_environments()` → à passer comme callable `list_environments_fn`
    - `self.get_default_environments()` → à passer comme callable `get_default_environments_fn`
    - `self._normalize_environment()` → déplacer comme méthode privée `_normalize_environment` dans `RBACPermissionAggregator`
  - [x] 1.2 Confirmer les dépendances de `_load_targets` (lignes 663–755) :
    - `self._get_inventory_mapper()` → appeler `self.query_executor._get_inventory_mapper()` directement dans `TargetLoader`
    - `self.list_servers(environment=env)` → à passer comme callable `list_servers_fn`
    - `self.list_targets(...)` → à passer comme callable `list_targets_fn`
    - `MAX_TARGETS_FOR_RBAC_FILTER` → import depuis `inventory.rbac_filter`
    - `MAX_MULTI_TABLE_RESULTS` → import depuis `inventory.query_executor`
  - [x] 1.3 Confirmer que `get_allowed_environments_for_user` (lignes 833–861) migre vers `RBACPermissionAggregator.get_allowed_environments()`
  - [x] 1.4 Confirmer que `_normalize_environment` (lignes 810–831) migre vers `RBACPermissionAggregator` (privée — seule utilisée dans contexte RBAC)

- [x] Task 2 — Créer `inventory/permission_aggregator.py` (RBACPermissionAggregator)
  - [x] 2.1 Créer la classe `RBACPermissionAggregator` avec :
    - Constructeur : `RBACPermissionAggregator(list_environments_fn, get_default_environments_fn)` — callables injectés.
    - Méthode principale : `aggregate(profiles, environment, correlation_id) -> dict[str, Any] | None` (extrait de `_aggregate_profile_permissions`)
    - Méthode publique : `get_allowed_environments(ad_groups: list[str]) -> set[str]` (extrait de `get_allowed_environments_for_user`) — requête profiles en interne
    - Méthode privée : `_normalize_environment(raw_env: str) -> str` (extrait de `_normalize_environment`)
  - [x] 2.2 Docstring de module SRP : `"""Agrégation des permissions RBAC multi-profils pour l'inventaire — InventoryService."""`
  - [x] 2.3 Imports top-level : `from profiles.models import Profile`, `from core.environment import EnvironmentHelper`, `from inventory.query_executor import InventoryServiceError`

- [x] Task 3 — Créer `inventory/target_loader.py` (TargetLoader)
  - [x] 3.1 Créer la classe `TargetLoader` avec :
    - Constructeur : `TargetLoader(query_executor, list_targets_fn, list_servers_fn)`
    - Méthode principale : `load(permissions, allowed_environments, search, target_type, user_id, correlation_id) -> tuple[list[dict], bool]` (extrait de `_load_targets`)
  - [x] 3.2 Docstring de module SRP : `"""Chargement des targets depuis l'inventaire (multi-table ou flat-table) — InventoryService."""`
  - [x] 3.3 Imports : `from inventory.query_executor import InventoryQueryExecutor, InventoryServiceError, MAX_MULTI_TABLE_RESULTS` et `from inventory.rbac_filter import MAX_TARGETS_FOR_RBAC_FILTER`

- [x] Task 4 — Refactoriser `InventoryService` pour déléguer
  - [x] 4.1 Ajouter imports en haut de `services.py` :
    ```python
    from inventory.permission_aggregator import RBACPermissionAggregator
    from inventory.target_loader import TargetLoader
    ```
  - [x] 4.2 Modifier `InventoryService.__init__` — instancier après les composants de base (ordre critique) :
    ```python
    self.source_resolver = InventorySourceResolver()
    self.query_executor = InventoryQueryExecutor()
    self.rbac_filter = InventoryRBACFilter()
    self.permission_aggregator = RBACPermissionAggregator(
        list_environments_fn=self.list_environments,
        get_default_environments_fn=self.get_default_environments,
    )
    self.target_loader = TargetLoader(
        query_executor=self.query_executor,
        list_targets_fn=self.list_targets,
        list_servers_fn=self.list_servers,
    )
    ```
  - [x] 4.3 Dans `list_targets_for_user` : remplacer `self._aggregate_profile_permissions(...)` par `self.permission_aggregator.aggregate(...)` ; remplacer `self._load_targets(...)` par `self.target_loader.load(...)`
  - [x] 4.4 Remplacer le corps de `get_allowed_environments_for_user` par délégation à `self.permission_aggregator.get_allowed_environments(ad_groups)` (backward-compat maintenu)
  - [x] 4.5 `_aggregate_profile_permissions` et `_load_targets` conservés comme stubs backward-compat sur `InventoryService` (délèguent aux nouveaux composants)
  - [x] 4.6 Vérifier que `_environments_cache`, `logger`, et `connection` restent **dans `services.py`** (patchés par les tests)

- [x] Task 5 — Tests et validation de régression
  - [x] 5.1 Vérifier backward-compat imports : tous les imports OK (confirmé)
  - [x] 5.2 Exécuter la suite tests inventory complète : 30 échecs identiques à la baseline pré-existante — zéro régression
  - [x] 5.3 Tests unitaires `RBACPermissionAggregator` créés dans `inventory/tests/test_permission_aggregator.py` : 23 tests, 100% pass
  - [x] 5.4 Tests unitaires `TargetLoader` créés dans `inventory/tests/test_target_loader.py` : 12 tests, 100% pass

## Dev Notes

### Contexte : état de services.py AVANT cette story

`inventory/services.py` a déjà subi un refactoring en Story 26.1 qui a extrait :

| Module | Fichier | Lignes | Responsabilité |
|--------|---------|--------|----------------|
| `InventorySourceResolver` | `source_resolver.py` | 67 | WHERE (quelle source) |
| `InventoryQueryExecutor` | `query_executor.py` | 667 | HOW (requêtes Oracle) |
| `InventoryRBACFilter` | `rbac_filter.py` | 364 | WHAT (filtres RBAC) |

Malgré cette extraction, `services.py` reste à **933 lignes** car il contient encore la logique d'agrégation RBAC et de chargement. C'est le périmètre exact de SOLID-BE-5.

### Cartographie des méthodes à extraire vs garder

**→ Extraire vers `permission_aggregator.py` :**

| Méthode actuelle | Lignes | Destination |
|------------------|--------|-------------|
| `_aggregate_profile_permissions` | 541–661 (~120 l.) | `RBACPermissionAggregator.aggregate()` |
| `get_allowed_environments_for_user` | 833–861 (~28 l.) | `RBACPermissionAggregator.get_allowed_environments()` |
| `_normalize_environment` | 810–831 (~21 l.) | `RBACPermissionAggregator._normalize_environment()` |

**→ Extraire vers `target_loader.py` :**

| Méthode actuelle | Lignes | Destination |
|------------------|--------|-------------|
| `_load_targets` | 663–755 (~92 l.) | `TargetLoader.load()` |

**→ Garder dans `services.py` (orchestrateur) :**

| Élément | Raison |
|---------|--------|
| `list_targets` + `_list_targets_from_*` | Dispatch source inventaire |
| `list_servers`, `list_instances`, `list_databases` | Délégation + logs + error handling |
| `list_targets_for_user` | Orchestration pipeline (allégée) |
| `_apply_rbac_chain_for_user` | Thin delegation rbac_filter (~10 l.) |
| `_paginate` | Simple utilitaire (~10 l.) |
| `list_environments`, `get_default_environments` | Cache + fallback ; injectés dans aggregator |
| `get_next_maintenance_window` | Stub futur |
| `_environments_cache`, `logger`, `connection` | **Rester ici** — patchés par tests |
| Backward compat stubs + `__all__` | Imports externes |

**Taille estimée après extraction :** ~650–680 lignes (vs 933 → réduction ~28%)

### Pattern DI pour `RBACPermissionAggregator`

```python
# inventory/permission_aggregator.py
from __future__ import annotations
from typing import Any, Callable
from django.db.models import QuerySet
import structlog
from core.environment import EnvironmentHelper
from inventory.query_executor import InventoryServiceError
from profiles.models import Profile

logger = structlog.get_logger(__name__)

class RBACPermissionAggregator:
    """Agrégation des permissions RBAC multi-profils pour l'inventaire."""

    def __init__(
        self,
        list_environments_fn: Callable[[], list[str]],
        get_default_environments_fn: Callable[[], list[str]],
    ) -> None:
        self._list_environments = list_environments_fn
        self._get_default_environments = get_default_environments_fn

    def aggregate(
        self,
        profiles: QuerySet,
        environment: str | None,
        correlation_id: str,
    ) -> dict[str, Any] | None:
        """Extrait de _aggregate_profile_permissions (lignes 541-661 de services.py)."""
        # Corps identique — remplacer self.list_environments() par self._list_environments()
        # et self.get_default_environments() par self._get_default_environments()
        # et self._normalize_environment(e) par self._normalize_environment(e)
        ...

    def get_allowed_environments(self, ad_groups: list[str]) -> set[str]:
        """Extrait de get_allowed_environments_for_user (lignes 833-861 de services.py)."""
        profiles = Profile.objects.find_by_ad_groups(ad_groups).prefetch_related(
            'profileactionpermission'
        )
        allowed_environments: set[str] = set()
        for profile in profiles:
            action_perm = getattr(profile, 'profileactionpermission', None)
            if action_perm:
                envs = action_perm.get_environments()
                if envs:
                    for e in envs:
                        if isinstance(e, str):
                            raw_env = EnvironmentHelper.normalize(e)
                            normalized_env = self._normalize_environment(e)
                            allowed_environments.add(normalized_env)
                            if raw_env and raw_env != normalized_env:
                                allowed_environments.add(raw_env)
        return allowed_environments

    def _normalize_environment(self, raw_env: str) -> str:
        """Extrait de _normalize_environment (lignes 810-831 de services.py)."""
        env_aliases = {
            'certif': 'staging',
            'certification': 'staging',
            'stg': 'staging',
            'development': 'dev',
            'production': 'prod',
        }
        normalized = EnvironmentHelper.normalize(raw_env)
        return env_aliases.get(normalized, normalized)
```

### Pattern DI pour `TargetLoader`

```python
# inventory/target_loader.py
from __future__ import annotations
from typing import Any, Callable
import structlog
from inventory.query_executor import (
    InventoryQueryExecutor, InventoryServiceError, MAX_MULTI_TABLE_RESULTS
)
from inventory.rbac_filter import MAX_TARGETS_FOR_RBAC_FILTER

logger = structlog.get_logger(__name__)

class TargetLoader:
    """Chargement des targets depuis l'inventaire (multi-table ou flat-table)."""

    def __init__(
        self,
        query_executor: InventoryQueryExecutor,
        list_targets_fn: Callable,   # InventoryService.list_targets bound method
        list_servers_fn: Callable,   # InventoryService.list_servers bound method
    ) -> None:
        self.query_executor = query_executor
        self._list_targets = list_targets_fn
        self._list_servers = list_servers_fn

    def load(
        self,
        permissions: dict,
        allowed_environments: set[str],
        search: str | None,
        target_type: str | None,
        user_id: int,
        correlation_id: str,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Extrait de _load_targets (lignes 663-755 de services.py)."""
        mapper = self.query_executor._get_inventory_mapper()
        use_multi_table = mapper is not None and mapper.is_multi_table
        # Corps identique — remplacer self._get_inventory_mapper() par
        # self.query_executor._get_inventory_mapper(), self.list_servers() par
        # self._list_servers(), self.list_targets() par self._list_targets()
        ...
```

### Instanciation dans `InventoryService.__init__`

**Ordre critique** : les bound methods (`self.list_targets`, etc.) doivent référencer des méthodes qui existent sur `self`. En Python, la bound method est résolue au moment de l'appel, pas au moment de la capture — cela fonctionne.

```python
def __init__(self) -> None:
    self.source_resolver = InventorySourceResolver()
    self.query_executor = InventoryQueryExecutor()
    self.rbac_filter = InventoryRBACFilter()
    # Instanciation APRÈS les composants de base
    self.permission_aggregator = RBACPermissionAggregator(
        list_environments_fn=self.list_environments,
        get_default_environments_fn=self.get_default_environments,
    )
    self.target_loader = TargetLoader(
        query_executor=self.query_executor,
        list_targets_fn=self.list_targets,
        list_servers_fn=self.list_servers,
    )
```

### Contraintes backward-compat critiques — NE PAS CASSER

```python
# test_services.py:9 — import direct
from inventory.services import InventoryService, InventoryServiceError

# test_services.py:72,92,109,136,196,206... — patch du module services
@patch('inventory.services.connection')
# ↑ connection (django.db) doit rester dans services.py

# test_services.py:401 — patch du logger services
@patch('inventory.services.logger')
# ↑ logger = structlog.get_logger(__name__) doit rester dans services.py

# test_services.py:446 — import interne
from inventory.services import _environments_cache
# ↑ _environments_cache = TTLCache(...) doit rester dans services.py

# test_services.py:331
from inventory.services import SAFE_TABLE_NAME_PATTERN
# ↑ déjà re-exporté via __all__ — maintenir

# test_views_multi_tables.py:13, test_integration_multi_tables.py:13
from inventory.services import InventoryServiceError
# ↑ déjà re-exporté depuis query_executor — maintenir dans __all__
```

### Consommateurs directs de `inventory/services.py`

| Fichier | Symboles importés |
|---------|------------------|
| `core/di.py:74` | `InventoryService` (lazy) |
| `core/tests/test_di.py:54` | `InventoryService` |
| `catalog/rbac_service.py:135` | `InventoryService` (lazy) |
| `catalog/tests/test_rbac_service.py:82,106` | `InventoryService` (mock patch) |
| `inventory/mapper.py:284` | `InventoryService` (lazy) |
| `inventory/tests/test_services.py` | multiples symboles (voir ci-dessus) |
| `inventory/tests/test_rbac_exclusion.py:8` | `InventoryService` |
| `inventory/tests/test_views_multi_tables.py:13` | `InventoryServiceError` |
| `inventory/tests/test_integration_multi_tables.py:13` | `InventoryServiceError` |

**Aucun de ces fichiers ne doit être modifié.** Le refactoring est purement structurel.

### Tests existants — périmètre couvert

| Fichier test | Lignes | Ce qu'il couvre |
|-------------|--------|----------------|
| `test_services.py` | 1761 | `InventoryService` complet + patching `connection`, `logger`, `_environments_cache` |
| `test_inventory_service_multi_tables.py` | 838 | `list_servers`, `list_instances`, `list_databases`, `list_targets_for_user` |
| `test_rbac_exclusion.py` | 286 | Pipeline RBAC via `list_targets_for_user` — exclusion patterns |
| `test_rbac_filter_by_attribute.py` | 352 | `_aggregate_profile_permissions` → via `list_targets_for_user` |
| `test_environments.py` | 122 | `list_environments`, `get_default_environments` |
| `test_views.py` | 430 | Views Django (via `InventoryService` mocké) |
| `test_views_multi_tables.py` | 644 | Multi-table views |
| `test_integration_multi_tables.py` | 213 | Intégration multi-tables |
| `test_inventory_multi_tables.py` | 500 | Multi-table unitaires |

**Tous doivent passer sans modification.** Si des tests patchent `InventoryService._aggregate_profile_permissions` ou `InventoryService._load_targets`, ils continueront de fonctionner si les méthodes sont retirées de la classe (patches sur méthodes inexistantes échouent silencieusement avec `patch.object` mais lèvent `AttributeError` avec `patch`). Vérifier dans `test_services.py` si ces méthodes privées sont patchées directement.

### Imports circulaires — à éviter absolument

- `permission_aggregator.py` : **PAS** d'import depuis `inventory.services` (circular)
- `target_loader.py` : **PAS** d'import depuis `inventory.services` (circular)
- Les deux fichiers peuvent importer depuis `inventory.query_executor`, `inventory.rbac_filter`, `profiles`, `core`

### Précédents établis

**Story 34.7** (WorkflowRuntime → RetryHandler + StepExecutor) : pattern identique — bound methods passées comme callables, backward compat, tests inchangés. **Reproduire exactement ce pattern.**

**Story 26.1** : premier split de `inventory/services.py` — `InventorySourceResolver`, `InventoryQueryExecutor`, `InventoryRBACFilter` créés. Les docstrings existantes dans `services.py` documentent ce découpage (`Story 26.1 - AC2`, `AC4`). Maintenir ce style.

**Story 34.5** : `GenericPoller(execution, correlation_id)` — même DI via constructeur.

### Commandes de test recommandées

```bash
cd /Users/cyrille/Documents/Dev/test/idp-portal/django_backend

# 1. Vérification imports backward compat
.venv/bin/python -c "
from inventory.services import (
    InventoryService, InventoryServiceError, connection,
    MapperValidationError, MAX_MULTI_TABLE_RESULTS,
    MAX_FLAT_TABLE_RESULTS, SAFE_TABLE_NAME_PATTERN, _environments_cache
)
from inventory.permission_aggregator import RBACPermissionAggregator
from inventory.target_loader import TargetLoader
print('Tous les imports OK')
"

# 2. Tests régression inventory complet
.venv/bin/python -m pytest inventory/tests/ -x -q --ignore=inventory/tests.py 2>&1 | tail -20

# 3. Tests nouveaux composants uniquement
.venv/bin/python -m pytest inventory/tests/test_permission_aggregator.py inventory/tests/test_target_loader.py -v 2>&1 | tail -30

# 4. Vérification mypy (bloquant depuis Story 26.16)
.venv/bin/python -m mypy inventory/permission_aggregator.py inventory/target_loader.py inventory/services.py --ignore-missing-imports 2>&1 | tail -10
```

### Effort et risques

**Effort :** Moyen — 2-3h de refactoring soigneux (moins complexe que Story 34.7 : pas de types partagés entre modules).

**Risque 1 (mypy)** : Les callables `Callable[..., ...]` peuvent nécessiter des annotations précises. Utiliser `Callable[..., tuple[list[dict], int]]` pour `list_targets_fn` et `Callable[[str], list[dict]]` pour `list_servers_fn`. Vérifier avec mypy avant commit.

**Risque 2 (logger patch)** : `@patch('inventory.services.logger')` dans `test_services.py:401` patche le logger module-level de `services.py`. Ce logger doit rester dans `services.py`. Les nouveaux fichiers auront leurs propres loggers (pas patchés par les tests existants).

**Risque 3 (méthodes privées patchées)** : Vérifier si `test_services.py` patche `_aggregate_profile_permissions` ou `_load_targets` directement (`grep -n "_aggregate_profile_permissions\|_load_targets" inventory/tests/test_services.py`). Si oui, prévoir des méthodes de délégation backward-compat sur `InventoryService` (comme fait pour `_call_platform_adapter` en Story 34.7).

### Fichiers à créer / modifier

```
idp-portal/django_backend/inventory/
  permission_aggregator.py        ← CRÉER (~180 lignes, RBACPermissionAggregator)
  target_loader.py                ← CRÉER (~120 lignes, TargetLoader)
  services.py                     ← MODIFIER (~650 lignes, orchestrateur pur)
  tests/
    test_permission_aggregator.py ← CRÉER (~150 lignes, tests RBACPermissionAggregator)
    test_target_loader.py         ← CRÉER (~100 lignes, tests TargetLoader)
```

**Aucune migration DB. Aucun impact API REST. Aucune modification frontend.**

### Project Structure Notes

- Cohérence avec `source_resolver.py`, `query_executor.py`, `rbac_filter.py` (même convention de nommage domaine-orienté)
- `services.py` reste le seul point d'entrée connu des consommateurs
- Ne pas créer de package `inventory/services/` — impact d'import trop large pour un bénéfice faible

### References

- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-BE-5] — `inventory/services.py` 933 lignes, 4-5 responsabilités, fix recommandé
- [Source: django_backend/inventory/services.py:541-661] — `_aggregate_profile_permissions` à extraire
- [Source: django_backend/inventory/services.py:663-755] — `_load_targets` à extraire
- [Source: django_backend/inventory/services.py:810-861] — `_normalize_environment`, `get_allowed_environments_for_user` à migrer
- [Source: django_backend/inventory/tests/test_services.py:401,446] — `logger` et `_environments_cache` backward compat critiques
- [Source: _bmad-output/planning-artifacts/epic-34-codebase-review-restant-fev-2026.md#Story-34.8] — priorité backlog structurel
- [Source: _bmad-output/implementation-artifacts/34-7-backend-decomposer-workflow-runtime.md] — pattern DI callables — reproduire exactement
- [Source: _bmad-output/implementation-artifacts/34-5-backend-poller-generique-unifie.md] — pattern DI constructeur
- [Source: django_backend/inventory/query_executor.py] — `InventoryQueryExecutor`, `MAX_MULTI_TABLE_RESULTS`, `MAX_FLAT_TABLE_RESULTS`, `SAFE_TABLE_NAME_PATTERN`
- [Source: django_backend/inventory/rbac_filter.py] — `InventoryRBACFilter`, `MAX_TARGETS_FOR_RBAC_FILTER`

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

_Aucun blocage — implémentation conforme au plan._

### Completion Notes List

- **AC1 ✅** : `RBACPermissionAggregator` créé dans `inventory/permission_aggregator.py` (~213 lignes) avec `aggregate()`, `get_allowed_environments()`, `_normalize_environment()`.
- **AC2 ✅** : `TargetLoader` créé dans `inventory/target_loader.py` (~136 lignes) avec `load()` (multi-table et flat-table).
- **AC3 ✅** : `InventoryService.__init__` instancie les deux collaborateurs via DI (lambdas pour respecter les patches test). `list_targets_for_user` délègue. Stubs backward-compat `_aggregate_profile_permissions`, `_load_targets`, `_normalize_environment`, `get_allowed_environments_for_user` conservés sur `InventoryService`.
- **AC4 ✅** : 30 échecs de tests — exactement identiques à la baseline pré-existante (zéro régression). `_environments_cache`, `logger`, `connection` restent dans `services.py`.
- **AC5 ✅** : Exports backward-compat dans `__all__` inchangés.
- **AC6 ✅** : 35 tests unitaires créés (23 pour `RBACPermissionAggregator`, 12 pour `TargetLoader`) — 100% pass. +2 tests revue (admin mixte) → 37 total.
- **Note pattern** : lambdas utilisées dans `__init__` au lieu de bound methods directes (`lambda: self.list_environments()`) pour permettre le monkey-patching dans les tests (Python résout `self.list_x` via `__dict__` au moment de l'appel).

### Senior Developer Review (AI)

**Date :** 2026-02-22 | **Revue :** adversariale — 6 problèmes identifiés et corrigés.

**Findings (tous corrigés) :**
- **[HIGH]** Import mort `MAX_MULTI_TABLE_RESULTS` dans `target_loader.py` → supprimé
- **[HIGH]** Violation DRY — logique de normalisation d'env dupliquée entre `aggregate()` et `get_allowed_environments()` → extraite en `_add_normalized_environments()` avec renommage `raw_env` → `basic_env`
- **[MEDIUM]** Violation type annotation : `_normalize_environment(raw_env: str)` appelé avec `None` dans le test → signature mise à jour `str | None`, garde `if not raw_env: return ''` ajoutée
- **[MEDIUM]** Couverture test manquante : aucun test profil mixte admin + non-admin → 2 tests ajoutés (`TestRBACPermissionAggregatorAggregateMixedAdminNonAdmin`)
- **[MEDIUM]** Variable `raw_env` trompeuse (valeur déjà normalisée par EnvironmentHelper) → renommée `basic_env` via extraction helper
- **[LOW]** `TargetLoader.query_executor` public incohérent avec `_list_targets`, `_list_servers`, `_get_mapper` → renommé `_query_executor`

**Outcome :** Approved — toutes ACs validées, 0 régression, 6/6 issues fixées.

### File List

- `idp-portal/django_backend/inventory/permission_aggregator.py` (CRÉÉ)
- `idp-portal/django_backend/inventory/target_loader.py` (CRÉÉ)
- `idp-portal/django_backend/inventory/services.py` (MODIFIÉ — DI collaborateurs + backward-compat stubs)
- `idp-portal/django_backend/inventory/tests/test_permission_aggregator.py` (CRÉÉ)
- `idp-portal/django_backend/inventory/tests/test_target_loader.py` (CRÉÉ)
- `_bmad-output/implementation-artifacts/34-8-backend-decomposer-inventory-services.md` (MODIFIÉ — story)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (MODIFIÉ — statut review)

## Change Log

| Date | Change |
|------|--------|
| 2026-02-23 | Story 34.8 — Décomposition `InventoryService` (SOLID-BE-5) : création `RBACPermissionAggregator` + `TargetLoader` via DI, backward-compat stubs, 35 tests unitaires nouveaux (100% pass), zéro régression. |
| 2026-02-22 | Code review adversariale — 6 issues corrigées (import mort, DRY, type annotation, coverage test, naming, encapsulation). Status → done. |
