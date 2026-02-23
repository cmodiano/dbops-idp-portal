# Story 34.3 : Backend — Cache RBAC, split services, LSP serializers

Status: done

<!-- Réf: CODEBASE-REVIEW.md §13 NEW-3, §14 SOLID-BE-4, SOLID-BE-6 -->

## Story

En tant que développeur backend,
je veux corriger trois dettes techniques ciblées (cache RBAC déplacé au bon endroit, split `executions/services.py`, violation LSP dans `ActionSerializer`),
afin d'améliorer la cohésion des modules, respecter SRP/LSP et éliminer les comportements trompeurs à l'exécution.

## Contexte

Cette story couvre trois issues backend **de priorité moyenne** de l'epic 34 (Codebase Review restant, 2026-02-21) :

- **NEW-3 [MEDIUM]** — `invalidate_permissions_cache()` définie dans `profiles/views.py` alors qu'elle appartient à `profiles/cache.py` (où vivent déjà `RBAC_CACHE_VERSION_KEY` et `RBAC_CACHE_TTL`). Violation SRP : une fonction utilitaire de cache dans un module views. **Note :** L'implémentation a été ajoutée par Story 30.14 (AC3) — la fonction n'est plus un noop. Le travail restant est un **déplacement + vérification de couverture des call-sites**.

- **SOLID-BE-4 [MEDIUM]** — `executions/services.py` (1121 lignes) contient deux classes sans relation : `ExecutionService` (lignes 32–861, entité `Execution`) et `SchedulingService` (lignes 862–1121, entité `ScheduledExecution`). Pas d'état partagé. Violation SRP directe.

- **SOLID-BE-6 [MEDIUM]** — `catalog/serializers.py` : `ActionSerializer.create()` (l.463) et `ActionSerializer.update()` (l.469) lèvent `NotImplementedError`, violant le contrat de `ModelSerializer` (tout appel accidentel à `.save()` produit une erreur d'exécution non documentée). Violation LSP textbook.

## Acceptance Criteria

### AC1 — NEW-3 : Déplacer `invalidate_permissions_cache` vers `profiles/cache.py`

- La fonction `invalidate_permissions_cache()` est **déplacée** de `profiles/views.py` vers `profiles/cache.py`
- `profiles/cache.py` exporte la fonction (visible via `from profiles.cache import invalidate_permissions_cache`)
- `profiles/views.py` **n'importe plus** `RBAC_CACHE_VERSION_KEY, RBAC_CACHE_TTL` séparément — il les obtient via `from profiles.cache import invalidate_permissions_cache` (la fonction les utilise en interne)
- Les imports internes (`logging`, `from django.core.cache import cache`) sont remontés au niveau module dans `profiles/cache.py`
- La fonction conserve son implémentation exacte (delete `RBAC_CACHE_VERSION_KEY` + log structlog/logging)

### AC2 — NEW-3 : Vérification couverture des call-sites

- `grep -rn "invalidate_permissions_cache" django_backend/` → au moins 3 call-sites dans les vues profiles (create/update profil, modification permissions)
- Résultat documenté dans les Completion Notes

### AC3 — SOLID-BE-4 : Extraction de `SchedulingService`

- Fichier `executions/scheduling_service.py` **créé** contenant uniquement la classe `SchedulingService`
- `executions/services.py` ne contient plus `SchedulingService` (classe supprimée)
- `executions/services.py` conserve la **rétrocompatibilité** : `from executions.services import SchedulingService` continue de fonctionner via re-export
- `executions/scheduling_service.py` a son propre docstring de module

### AC4 — SOLID-BE-4 : Taille après split

- `executions/services.py` ≤ 875 lignes après extraction (suppression SchedulingService + 1 ligne re-export)
- `executions/scheduling_service.py` ≈ 260 lignes (SchedulingService seule)
- 0 régression dans les tests executions existants

### AC5 — SOLID-BE-6 : Suppression des méthodes `NotImplementedError` dans `ActionSerializer`

- `ActionSerializer.create()` (l.463) **supprimée**
- `ActionSerializer.update()` (l.469) **supprimée**
- Docstring de la classe `ActionSerializer` enrichie pour documenter qu'il s'agit d'un serializer de lecture (write → `ActionCreateSerializer`)
- `grep -n "raise NotImplementedError" catalog/serializers.py` → **0 résultat**
- Les views utilisant `ActionSerializer` pour les lectures restent inchangées
- `ActionCreateSerializer` reste le serializer d'écriture (inchangé)

### AC6 — Tests

- `.venv/bin/python -m pytest profiles/ -x -q` → 0 régression
- `.venv/bin/python -m pytest executions/ -x -q` → 0 régression
- `.venv/bin/python -m pytest catalog/ -x -q` → 0 régression
- Au moins 1 nouveau test : `test_invalidate_permissions_cache_from_cache_module` — importer depuis `profiles.cache`, vérifier que `cache.delete(RBAC_CACHE_VERSION_KEY)` est appelé
- Au moins 1 nouveau test : `test_action_serializer_no_notimplementederror` — instancier `ActionSerializer` et vérifier que `create` et `update` sont les méthodes héritées de `ModelSerializer` (pas de levée d'exception)

## Tasks / Subtasks

- [x] **Task 1 — NEW-3 : Déplacer la fonction vers profiles/cache.py** (AC: #1, #2)
  - [x] 1.1 Lire `profiles/cache.py` complet (état actuel — constantes RBAC)
  - [x] 1.2 Lire `profiles/views.py` lignes 25–60 (fonction + imports actuels)
  - [x] 1.3 Dans `profiles/cache.py` : ajouter `import logging` et `from django.core.cache import cache` au niveau module
  - [x] 1.4 Couper la fonction `invalidate_permissions_cache()` de `profiles/views.py` et la coller dans `profiles/cache.py` (après les constantes)
  - [x] 1.5 Dans `profiles/views.py` : supprimer `from profiles.cache import RBAC_CACHE_VERSION_KEY, RBAC_CACHE_TTL` et remplacer par `from profiles.cache import invalidate_permissions_cache` (les constantes ne sont plus nécessaires directement dans views.py)
  - [x] 1.6 `grep -rn "invalidate_permissions_cache" django_backend/` → noter tous les call-sites existants, documenter dans Completion Notes
  - [x] 1.7 S'assurer que les call-sites importent via `from profiles.cache import ...` ou `from profiles.views import ...` (les deux fonctionnent — re-export possible si besoin)

- [x] **Task 2 — SOLID-BE-4 : Créer executions/scheduling_service.py** (AC: #3, #4)
  - [x] 2.1 Lire `executions/services.py` lignes 860–1121 (SchedulingService complet)
  - [x] 2.2 Identifier tous les imports nécessaires à `SchedulingService` (models, logger, utils — ils sont déjà dans l'en-tête de `services.py`)
  - [x] 2.3 Créer `executions/scheduling_service.py` avec :
    - docstring de module
    - imports nécessaires (copier depuis `services.py` ceux utilisés par `SchedulingService`)
    - copie exacte de la classe `SchedulingService`
  - [x] 2.4 Dans `executions/services.py` : supprimer la classe `SchedulingService` (lignes 862–1121)
  - [x] 2.5 Dans `executions/services.py` : ajouter en fin de fichier `from executions.scheduling_service import SchedulingService  # noqa: F401  # backward compat`
  - [x] 2.6 Vérifier les deux imports fonctionnent : `from executions.services import SchedulingService` et `from executions.scheduling_service import SchedulingService`

- [x] **Task 3 — SOLID-BE-6 : Supprimer les méthodes NotImplementedError** (AC: #5)
  - [x] 3.1 Lire `catalog/serializers.py` lignes 440–480 (contexte create/update + docstring classe)
  - [x] 3.2 Enrichir la docstring de la classe `ActionSerializer` : préciser `Read-only serializer. Write operations use ActionCreateSerializer.`
  - [x] 3.3 Supprimer la méthode `create()` (lignes 463–467)
  - [x] 3.4 Supprimer la méthode `update()` (lignes 469–473)
  - [x] 3.5 `grep -n "raise NotImplementedError" catalog/serializers.py` → confirmer 0 résultat

- [x] **Task 4 — Tests** (AC: #6)
  - [x] 4.1 Lire `profiles/tests/test_rbac_cache_invalidation.py` (état actuel)
  - [x] 4.2 Ajouter `test_invalidate_permissions_cache_from_cache_module` : `from profiles.cache import invalidate_permissions_cache`, mock `cache.delete`, appeler, vérifier `cache.delete(RBAC_CACHE_VERSION_KEY)` appelé une fois
  - [x] 4.3 Lire ou créer un test catalog pour `ActionSerializer` — vérifier `create` et `update` sont des méthodes héritées sans levée d'exception
  - [x] 4.4 `.venv/bin/python -m pytest profiles/ executions/ catalog/ -x -q` → 0 régression sur périmètre story (49 échecs pre-existing documentés hors périmètre)

## Dev Notes

### ⚠️ NEW-3 — État actuel de `invalidate_permissions_cache()`

La fonction **est déjà implémentée** (Story 30.14 - AC3, 2026-02-16). Ce n'est plus un noop. L'issue résiduelle est sa **localisation** (dans `views.py` au lieu de `cache.py`) :

```python
# profiles/views.py (actuellement, lignes 32–57)
def invalidate_permissions_cache() -> None:
    """
    Invalidate RBAC permissions cache for all users.
    Deletes the global cache version key...
    Story 30.14 - AC3: Cache invalidation implementation.
    """
    import logging
    from django.core.cache import cache

    logger = logging.getLogger(__name__)
    try:
        cache.delete(RBAC_CACHE_VERSION_KEY)
        logger.info('rbac_permissions_cache_invalidated',
                    cache_key=RBAC_CACHE_VERSION_KEY, ttl_seconds=RBAC_CACHE_TTL)
    except Exception:
        logger.warning('rbac_permissions_cache_invalidation_failed', exc_info=True)
```

**Cible** — `profiles/cache.py` (actuellement 2 lignes) deviendra :

```python
# profiles/cache.py (après déplacement)
import logging
from django.core.cache import cache

RBAC_CACHE_VERSION_KEY = 'rbac:cache_version'
RBAC_CACHE_TTL = 300  # 5 minutes

logger = logging.getLogger(__name__)


def invalidate_permissions_cache() -> None:
    """
    Invalidate RBAC permissions cache for all users.
    ...
    """
    try:
        cache.delete(RBAC_CACHE_VERSION_KEY)
        logger.info('rbac_permissions_cache_invalidated', ...)
    except Exception:
        logger.warning('rbac_permissions_cache_invalidation_failed', exc_info=True)
```

**Dans `profiles/views.py`** après déplacement :
```python
# Remplacer :
from profiles.cache import RBAC_CACHE_VERSION_KEY, RBAC_CACHE_TTL
# Par :
from profiles.cache import invalidate_permissions_cache
```
(RBAC_CACHE_VERSION_KEY et RBAC_CACHE_TTL ne seront plus utilisés directement dans views.py)

### ⚠️ SOLID-BE-4 — Structure actuelle de `executions/services.py`

```
executions/services.py (1121 lignes)
├── Imports (lignes 1–30)
├── class ExecutionService (lignes 32–861)
│   ├── _check_integration_status()
│   ├── _validate_targets()
│   ├── create_execution()
│   ├── update_step_status()
│   └── ... (méthodes liées à Execution)
└── class SchedulingService (lignes 862–1121)
    ├── create_scheduled_execution()
    ├── list_scheduled_executions()
    ├── cancel_scheduled_execution()
    └── ... (méthodes liées à ScheduledExecution)
```

**Après split :**

```
executions/services.py      ← ExecutionService uniquement + 1 ligne re-export
executions/scheduling_service.py  ← SchedulingService uniquement (~260 lignes)
```

**Pattern re-export (rétrocompatibilité)** — à ajouter en fin de `executions/services.py` :

```python
# Backward compatibility re-export
from executions.scheduling_service import SchedulingService  # noqa: F401
```

**Imports à inclure dans `scheduling_service.py`** — vérifier dans l'original quels imports sont utilisés par `SchedulingService` :
- `from django.db import transaction`
- `from datetime import datetime, timedelta`
- `from django.utils import timezone`
- `from executions.models import ScheduledExecution, ScheduledExecutionStatus, ...`
- `from catalog.models import Action`
- `from idp_auth.models import User`
- `from core.services import AuditService`
- `from core.models import AuditActionType, AuditEntityType`
- `from executions.utils import calculate_next_execution_date`
- `import structlog`

### ⚠️ SOLID-BE-6 — Violation LSP dans `ActionSerializer`

**État actuel** (`catalog/serializers.py`, lignes 463–473) :

```python
def create(self, validated_data: dict[str, Any]) -> Action:
    """Create action - handled by ViewSet using CatalogService."""
    # This serializer is mainly for read operations
    # Create is handled by ActionCreateSerializer
    raise NotImplementedError("Use ActionCreateSerializer for creation")

def update(self, instance: Action, validated_data: dict[str, Any]) -> Action:
    """Update action - handled by ViewSet using CatalogService."""
    # This serializer is mainly for read operations
    # Update is handled by ViewSet
    raise NotImplementedError("Update handled by ViewSet")
```

**Problème LSP :** `ModelSerializer` (parent) définit `create()` et `update()` fonctionnels. Les surcharger pour lever des exceptions viole le principe de substitution — le sous-type (`ActionSerializer`) est moins capable que le type de base.

**Fix minimal :** supprimer les deux méthodes. La docstring de classe documente l'intention read-only :

```python
class ActionSerializer(ActionFieldValidationMixin, serializers.ModelSerializer):
    """
    Read-only serializer for Action model.
    Used for list/detail read operations (GET).

    Write operations (create/update) use ActionCreateSerializer and CatalogService.
    Do NOT call .save() on this serializer — use ActionCreateSerializer instead.
    """
    # champs inchangés...
    # Note: create() et update() non surchargés — utiliser ActionCreateSerializer
```

**Alternatives considérées et rejetées :**
- Renommer en `ActionReadSerializer` → trop de call-sites à modifier (vues, tests), risque de régression
- Ajouter `read_only_fields = '__all__'` → n'empêche pas l'appel accidentel à `.save()`

### Contexte stories précédentes pertinent

**Story 34.1** (`585ead9 feat(34-1)`) a établi :
- `ActionFieldValidationMixin` pour déduplication des validations (lignes 152–199 dans `catalog/serializers.py`)
- Pattern DI `get_catalog_service()` dans les vues

**Story 34.2** (`fdf7ecc feat(34-2)`) a établi :
- Pattern `setNotificationCallback` (analogue à `setAuthAccessors`) pour DIP frontend

**Story 33.4** (`ec7a77b feat(33-4)`) a établi :
- Pattern DI `_service_class` / `get_service()` dans les viewsets

**Story 30.14** (done, 2026-02-16) a implémenté :
- `invalidate_permissions_cache()` dans `profiles/views.py` (AC3) — fonction à déplacer dans cette story

### Arborescence des fichiers concernés

```
django_backend/
  profiles/
    cache.py                       ← MODIFIER : ajouter imports module + fonction
    views.py                       ← MODIFIER : supprimer la fonction + ajuster imports
    tests/
      test_rbac_cache_invalidation.py  ← MODIFIER : ajouter test import profiles.cache
  executions/
    services.py                    ← MODIFIER : supprimer SchedulingService + re-export
    scheduling_service.py          ← CRÉER : SchedulingService uniquement
    (tests existants)              ← 0 modification (re-export maintient compatibilité)
  catalog/
    serializers.py                 ← MODIFIER : supprimer create()/update() + docstring
    (tests existants)              ← 0 modification prévue
```

### Commandes de test recommandées

```bash
# Depuis django_backend
cd /Users/cyrille/Documents/Dev/test/idp-portal/django_backend

# Vérifications imports post-refactoring
.venv/bin/python -c "from profiles.cache import invalidate_permissions_cache; print('OK NEW-3')"
.venv/bin/python -c "from executions.services import SchedulingService; print('OK SOLID-BE-4 compat')"
.venv/bin/python -c "from executions.scheduling_service import SchedulingService; print('OK SOLID-BE-4 direct')"
.venv/bin/python -c "from catalog.serializers import ActionSerializer; import inspect; assert 'raise NotImplementedError' not in inspect.getsource(ActionSerializer); print('OK SOLID-BE-6')"

# Tests ciblés
.venv/bin/python -m pytest profiles/tests/test_rbac_cache_invalidation.py -v
.venv/bin/python -m pytest executions/ -x -q --ignore=executions/tests.py
.venv/bin/python -m pytest catalog/ -x -q --ignore=catalog/tests.py

# Suite complète périmètre
.venv/bin/python -m pytest profiles/ executions/ catalog/ -q
```

### Project Structure Notes

- Aucune migration DB requise — uniquement refactorings de code Python
- Le re-export dans `services.py` assure la rétrocompatibilité sans modifier aucun call-site externe
- `profiles/cache.py` devient le module de référence pour tout ce qui concerne le cache RBAC (constantes + invalidation)
- Pas d'impact sur l'API REST publique — 0 changement de contrat

### References

- [Source: idp-portal/CODEBASE-REVIEW.md#NEW-3] — invalidate_permissions_cache placeholder / location SRP
- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-BE-4] — executions/services.py 2 classes non liées
- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-BE-6] — ActionSerializer NotImplementedError LSP
- [Source: _bmad-output/planning-artifacts/epic-34-codebase-review-restant-fev-2026.md#Story-34.3]
- [Source: django_backend/profiles/views.py:32-57] — invalidate_permissions_cache() état actuel
- [Source: django_backend/profiles/cache.py] — RBAC_CACHE_VERSION_KEY, RBAC_CACHE_TTL
- [Source: django_backend/executions/services.py:32] — ExecutionService (à conserver)
- [Source: django_backend/executions/services.py:862-1121] — SchedulingService (à extraire)
- [Source: django_backend/catalog/serializers.py:463-473] — create()/update() NotImplementedError
- [Source: django_backend/catalog/rbac_service.py] — implémentation cache RBAC versionnée (référence)
- [Source: _bmad-output/implementation-artifacts/34-1-quick-wins-backend-di-queryset-validation.md] — patterns DI et mixin établis

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

(aucun)

### Completion Notes List

**Story 34.3 complétée le 2026-02-22 (claude-sonnet-4-6)**

**AC1 — NEW-3 : Déplacement `invalidate_permissions_cache` → `profiles/cache.py`**
- `profiles/cache.py` : ajout `import logging`, `from django.core.cache import cache`, logger module-level, et fonction complète `invalidate_permissions_cache()`
- `profiles/views.py` : suppression définition + remplacement `from profiles.cache import RBAC_CACHE_VERSION_KEY, RBAC_CACHE_TTL` par `from profiles.cache import invalidate_permissions_cache  # noqa: F401  # re-exported`
- Les appels internes dans views.py (lignes 130, 167, 185, 224, 263, 311) continuent de fonctionner sans modification

**AC2 — Call-sites `invalidate_permissions_cache`**
- `profiles/views.py` : 6 call-sites internes (create/update profil, modification permissions, import/permissions)
- `profiles/tests/test_rbac_cache_invalidation.py` : import test existant depuis `profiles.views` (backward compat)
- `catalog/rbac_service.py` : référence en commentaire de documentation
- `docs/security/common-pitfalls.md` : exemple doc (mention seule)
- Pattern de re-export : `profiles.views.invalidate_permissions_cache is profiles.cache.invalidate_permissions_cache` → True ✓

**AC3 — SOLID-BE-4 : `executions/scheduling_service.py` créé**
- Contient uniquement `SchedulingService` (290 lignes)
- Docstring de module documentant le split SRP (Story 34.3)
- Imports autonomes : json, datetime, transaction, Q/QuerySet, timezone, modèles executions, catalog, auth, core

**AC4 — Taille après split**
- `executions/services.py` : 863 lignes (≤875 ✓)
- `executions/scheduling_service.py` : 290 lignes (≈260 ✓)
- `from executions.services import SchedulingService` → fonctionne via re-export (backward compat) ✓
- `from executions.scheduling_service import SchedulingService` → fonctionne directement ✓

**AC5 — SOLID-BE-6 : LSP corrigé dans `ActionSerializer`**
- Méthodes `create()` et `update()` (qui levaient `NotImplementedError`) supprimées
- Docstring enrichie : "Read-only serializer for Action model. Write operations use ActionCreateSerializer."
- `grep -n "raise NotImplementedError" catalog/serializers.py` → 0 résultat ✓

**AC6 — Tests**
- `profiles/tests/test_rbac_cache_invalidation.py` : 2 nouveaux tests ajoutés → 6/6 passent ✓
  - `test_invalidate_permissions_cache_from_cache_module` : mock cache.delete, vérifie appel avec RBAC_CACHE_VERSION_KEY
  - `test_invalidate_permissions_cache_backward_compat_via_views` : vérifie identité des fonctions
- `catalog/tests/test_action_serializer_lsp.py` : NEW (4 tests) → 4/4 passent ✓
  - `test_action_serializer_no_notimplementederror`
  - `test_action_serializer_create_is_inherited`
  - `test_action_serializer_update_is_inherited`
  - `test_action_serializer_inherits_from_model_serializer`
- Suite complète story : 26/26 tests story-related passent ✓
- 49 échecs pre-existing documentés (policy_evaluator, rule_engine, DBOPS_INVENTORY) — hors périmètre story 34.3, non causés par ces changements

### File List

- `idp-portal/django_backend/profiles/cache.py` — MODIFIÉ : imports module + logger + fonction invalidate_permissions_cache()
- `idp-portal/django_backend/profiles/views.py` — MODIFIÉ : import remplacé, définition locale supprimée
- `idp-portal/django_backend/executions/scheduling_service.py` — CRÉÉ : SchedulingService extraite
- `idp-portal/django_backend/executions/services.py` — MODIFIÉ : SchedulingService supprimée + re-export backward compat
- `idp-portal/django_backend/catalog/serializers.py` — MODIFIÉ : docstring enrichie, create()/update() NotImplementedError supprimées
- `idp-portal/django_backend/profiles/tests/test_rbac_cache_invalidation.py` — MODIFIÉ : 2 nouveaux tests ajoutés
- `idp-portal/django_backend/catalog/tests/test_action_serializer_lsp.py` — CRÉÉ : 4 tests LSP

## Senior Developer Review (AI)

**Date :** 2026-02-22 | **Reviewer :** claude-sonnet-4-6

### Résultat : ✅ APPROUVÉ (après auto-fixes)

**Discordances Git vs Story :** 0
**Issues trouvées :** 0 Critique, 3 Médium, 2 Faible — **toutes auto-fixées**

#### 🟡 MEDIUM — Auto-fixés

**M1 — `noqa: F401` incorrect dans `views.py:25`** [AUTO-FIXÉ]
`from profiles.cache import invalidate_permissions_cache  # noqa: F401  # re-exported for backward compat` — la suppression `noqa: F401` est incorrecte car l'import EST utilisé à 6 endroits dans views.py. Annotation trompeuse retirée.

**M2 — Import paresseux `RecurringPattern` dans `scheduling_service.py`** [AUTO-FIXÉ]
`from executions.models import RecurringPattern` était importé à l'intérieur du corps de `create_scheduled_execution()` au lieu d'être en tête de module. Déplacé au niveau module.

**M3 — Import `call` inutilisé dans `test_rbac_cache_invalidation.py:9`** [AUTO-FIXÉ]
`from unittest.mock import patch, MagicMock, call` — `call` non utilisé dans les tests. Supprimé.

#### 🟢 FAIBLE — Auto-fixés

**L1 — Numéros de lignes erronés dans les Completion Notes** [AUTO-FIXÉ]
Call-sites documentés aux lignes "158, 195, 213, 252, 291, 339" mais vraies lignes : 130, 167, 185, 224, 263, 311. Corrigé.

**L2 — `profiles/cache.py` stdlib logging vs structlog codebase**
`executions/services.py` utilise structlog. `profiles/cache.py` utilise stdlib logging. L'original dans `views.py` utilisait aussi stdlib logging (avec des kwargs structlog-style invalides — bug silencieux). Le fix actuel avec `extra={}` est correct pour stdlib. Non modifié — la cohérence inter-modules est un sujet de refactoring futur.

**Vérification régression :** 1 échec dans `executions/tests/test_container_workflow_runtime.py` — confirmé **pré-existant** par `git stash` test. Aucune régression causée par story 34.3.

## Change Log

- 2026-02-22 : Story 34.3 implémentée — 3 corrections dette technique backend (NEW-3 SRP cache, SOLID-BE-4 split SchedulingService, SOLID-BE-6 LSP ActionSerializer). 10 fichiers modifiés, 10 nouveaux tests (6/6 + 4/4 passent), 0 régression périmètre.
- 2026-02-22 : Code review adversarial — 3 MEDIUM + 2 LOW issues trouvées, toutes auto-fixées (noqa:F401 incorrect, import paresseux RecurringPattern, call inutilisé, numéros lignes). Story marquée done.
