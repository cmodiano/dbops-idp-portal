# Story 34.4 : Backend — RuntimeRegistry (launch_workflow), Webhooks DI

Status: done

<!-- Réf: CODEBASE-REVIEW.md SOLID-BE-7, SOLID-BE-9 -->

## Story

En tant que mainteneur,
je veux remplacer le switch sur `item_type` dans `launch_workflow()` par un registry de runtimes, et alimenter les webhooks via le DI au lieu d'un monkey-patch,
afin de respecter OCP/DIP et de rendre les tests plus fiables.

## Contexte

- **SOLID-BE-7** : `executions/services.py` (l.382-408) — `launch_workflow()` fait un `if action.item_type == "workflow": ... elif SIMULATE_EXECUTION_DEV: ...` avec import conditionnel de classes concrètes. Pour ajouter un nouveau type (ex. simulation), il faut modifier ce fichier. Violation OCP directe.
- **SOLID-BE-9** : `executions/views/github_webhooks.py:34` et `executions/views/terraform_webhooks.py:34` utilisent `_execution_service_factory = ExecutionService` au niveau module ; les tests font un monkey-patch. Fragile et pas thread-safe.

## Acceptance Criteria

1. **Given** on lance une exécution (action ou workflow)
   **When** le code détermine quel runtime utiliser
   **Then** un registry (`RuntimeRegistry`) dans `executions/runtime_registry.py` est utilisé : enregistrement `workflow` → `ContainerWorkflowRuntime`, `simulation` → `SimulationService` (si `SIMULATE_EXECUTION_DEV`), aucun `if/elif` sur `item_type` avec import conditionnel dans `launch_workflow()`.

2. **And** les webhooks (GitHub, Terraform) obtiennent le service d'exécution via `core.di.get_execution_service()` au lieu de la variable module-level `_execution_service_factory` ; les tests injectent un mock via `override_service('execution_service', ...)` + `reset_services()`.

3. **And** les tests existants (executions, webhooks) passent ; aucune régression sur le lancement workflow/action ou le traitement des webhooks.

## Tasks / Subtasks

- [x] Task 1 — RuntimeRegistry (SOLID-BE-7) (AC: #1)
  - [x] 1.1 Créer `executions/runtime_registry.py` — classe `RuntimeRegistry` avec `register(key, factory)`, `get(key)`, `list_keys()`. Modeler sur `services/registry.py` (Story 33.1) et `executions/interpreters/registry.py` (singleton thread-safe).
  - [x] 1.2 Enregistrer dans le module : `workflow` → `ContainerWorkflowRuntime`, `simulation` → `SimulationService` (conditionnel `SIMULATE_EXECUTION_DEV`). Le cas `action` standard n'a pas de runtime dédié (exécution directe via adapter) — documenter dans une note.
  - [x] 1.3 Dans `launch_workflow()` (`executions/services.py:382-408`) : remplacer le bloc `if/elif` par un lookup dans le registry. Fallback : si aucun runtime enregistré pour la clé → log warning + retour (comportement actuel implicite pour action standard).
  - [x] 1.4 Tests : vérifier que `launch_workflow()` avec `item_type='workflow'` appelle bien `ContainerWorkflowRuntime.run()` ; avec `item_type='simulation'` (si settings) appelle `SimulationService.create_simulated_steps()` ; avec une clé inconnue ne lève pas d'exception.

- [x] Task 2 — Webhooks DI (SOLID-BE-9) (AC: #2)
  - [x] 2.1 Dans `executions/views/github_webhooks.py` : supprimer `_execution_service_factory = ExecutionService` (ligne 34) et remplacer `svc = _execution_service_factory()` (ligne ~210) par `from core.di import get_execution_service` + `svc = get_execution_service()`.
  - [x] 2.2 Dans `executions/views/terraform_webhooks.py` : appliquer la même transformation (ligne 34 + ligne ~219).
  - [x] 2.3 Adapter les tests des webhooks (GitHub et Terraform) : remplacer le monkey-patch `m._execution_service_factory = ...` par `override_service('execution_service', lambda: mock)` + tearDown `reset_services()`.
  - [x] 2.4 Vérifier que les imports `from executions.services import ExecutionService` au niveau module (pour type hints éventuels) ne causent pas de circularités. Vérifié : `runtime_registry.py` utilise `TYPE_CHECKING` guard pour `Execution`, tous les imports de classes concrètes (`ContainerWorkflowRuntime`, `SimulationService`) sont dans des closures (lazy). Test de fumée : `.venv/bin/python -c "from executions.runtime_registry import runtime_registry; print(runtime_registry.list_keys())"` → `['workflow']` sans erreur.

- [x] Task 3 — Tests de régression (AC: #3)
  - [x] 3.1 `.venv/bin/python -m pytest executions/ -x -q --ignore=executions/tests.py` → 0 régression.
  - [x] 3.2 Au moins 3 nouveaux tests : `test_runtime_registry_workflow`, `test_runtime_registry_unknown_key`, `test_webhook_di_override_service`.

## Dev Notes

### ⚠️ SOLID-BE-7 — Code actuel `launch_workflow()` (executions/services.py:382-408)

```python
@staticmethod
def launch_workflow(execution: Execution, correlation_id: str | None = None) -> None:
    """
    Start the workflow runtime for an execution (Story 7.4 / 25.4).
    Used after creation (when not PENDING_APPROVAL) and after DBA approval.
    """
    from django.conf import settings
    action = execution.action
    if not action:
        return
    if action.item_type == "workflow":
        from executions.container_workflow_runtime import ContainerWorkflowRuntime
        ContainerWorkflowRuntime(execution).run()
        logger.info(
            "container_workflow_execution_launched",
            execution_id=execution.id,
            correlation_id=correlation_id,
        )
    elif getattr(settings, "SIMULATE_EXECUTION_DEV", False):
        from executions.simulation_service import SimulationService
        SimulationService.create_simulated_steps(execution)
        SimulationService.start_simulation(execution)
        logger.info(
            "execution_simulation_started",
            execution_id=execution.id,
            correlation_id=correlation_id,
        )
```

**Problème OCP :** ajout d'un nouveau type de runtime = modification directe de ce fichier + import conditionnel à l'intérieur de la méthode.

**Cible après registry :**

```python
@staticmethod
def launch_workflow(execution: Execution, correlation_id: str | None = None) -> None:
    """
    Start the workflow runtime for an execution.
    Runtime dispatch via RuntimeRegistry (Story 34.4 — SOLID-BE-7).
    """
    from executions.runtime_registry import runtime_registry  # noqa: PLC0415
    action = execution.action
    if not action:
        return
    runtime = runtime_registry.get(action.item_type)
    if runtime is None:
        logger.info(
            "no_runtime_registered_for_item_type",
            item_type=action.item_type,
            execution_id=execution.id,
        )
        return
    runtime(execution, correlation_id=correlation_id)
```

### ⚠️ SOLID-BE-7 — Pattern RuntimeRegistry à créer

Modeler sur les registries existants :

**`services/registry.py`** (Story 33.1) :
```python
class ServiceRegistry:
    def __init__(self) -> None:
        self._registry: dict[str, Callable[..., Any]] = {}

    def register(self, service_type: str, factory: Callable[..., Any]) -> None:
        self._registry[service_type] = factory

    def get(self, service_type: str, **kwargs: Any) -> Any:
        factory = self._registry.get(service_type)
        if factory is None:
            raise ValueError(f"Unknown service type: {service_type!r}")
        return factory(**kwargs)
```

**Adaptation pour `RuntimeRegistry`** — les runtimes reçoivent `execution` + `correlation_id` :

```python
# executions/runtime_registry.py
"""
RuntimeRegistry — dispatch de runtime d'exécution (Story 34.4, SOLID-BE-7).

Remplace le if/elif sur item_type dans launch_workflow().
OCP : enregistrer un nouveau runtime ne nécessite pas de modifier ExecutionService.
"""
from __future__ import annotations
from typing import Callable, TYPE_CHECKING
import structlog

if TYPE_CHECKING:
    from executions.models import Execution

logger = structlog.get_logger(__name__)


class RuntimeRegistry:
    """
    Registry de runtimes d'exécution.

    Associe item_type (str) à une factory callable(execution, correlation_id=None).
    Enregistrement via register(), dispatch via get() ou call().
    """

    def __init__(self) -> None:
        self._registry: dict[str, Callable] = {}

    def register(self, item_type: str, factory: Callable) -> None:
        """Enregistrer une factory pour item_type."""
        if item_type in self._registry:
            logger.warning("runtime_registry_overwrite", item_type=item_type)
        self._registry[item_type] = factory

    def unregister(self, item_type: str) -> None:
        """Retirer un runtime (utilitaire de test)."""
        self._registry.pop(item_type, None)

    def get(self, item_type: str) -> Callable | None:
        """Retourner la factory ou None si non enregistrée."""
        return self._registry.get(item_type)

    def list_keys(self) -> list[str]:
        return list(self._registry.keys())


runtime_registry = RuntimeRegistry()


def _register_defaults() -> None:
    """Enregistrer les runtimes par défaut au chargement du module."""
    from django.conf import settings  # noqa: PLC0415

    def _workflow_runtime(execution: Execution, correlation_id: str | None = None) -> None:
        from executions.container_workflow_runtime import ContainerWorkflowRuntime  # noqa: PLC0415
        ContainerWorkflowRuntime(execution).run()
        logger.info(
            "container_workflow_execution_launched",
            execution_id=execution.id,
            correlation_id=correlation_id,
        )

    runtime_registry.register("workflow", _workflow_runtime)

    if getattr(settings, "SIMULATE_EXECUTION_DEV", False):
        def _simulation_runtime(execution: Execution, correlation_id: str | None = None) -> None:
            from executions.simulation_service import SimulationService  # noqa: PLC0415
            SimulationService.create_simulated_steps(execution)
            SimulationService.start_simulation(execution)
            logger.info(
                "execution_simulation_started",
                execution_id=execution.id,
                correlation_id=correlation_id,
            )
        runtime_registry.register("simulation", _simulation_runtime)


_register_defaults()
```

> **Note action standard :** `item_type == "action"` n'a pas de runtime propre — `launch_workflow()` ne fait rien pour ce cas (l'adapter est appelé en amont). Le `get()` retourne `None`, et la fonction retourne silencieusement (comportement conservé).

### ⚠️ SOLID-BE-9 — Code actuel webhooks (même pattern dans les deux fichiers)

**`executions/views/github_webhooks.py:34`** :
```python
# Story 33.4 (DIP): module-level factory, overridable in tests via:
#   import executions.views.github_webhooks as m
#   m._execution_service_factory = lambda: MockExecutionService()
_execution_service_factory = ExecutionService
```

**Usage (ligne ~210) :**
```python
svc = _execution_service_factory()
svc.update_status(execution.id, idp_status, str(execution.user_id))
```

**`executions/views/terraform_webhooks.py:34`** : pattern identique, usage à la ligne ~219.

**Fix :**
```python
# Supprimer _execution_service_factory = ExecutionService
# Remplacer svc = _execution_service_factory() par :
from core.di import get_execution_service  # noqa: PLC0415 (import lazy in view)
svc = get_execution_service()
```

### ⚠️ SOLID-BE-9 — core/di.py (API existante à utiliser)

`core/di.py` expose déjà (104 lignes, Story 33.4) :

```python
def get_execution_service():
    """Return an ExecutionService instance (overridable in tests)."""
    factory = _service_registry.get('execution_service')
    if factory:
        return factory()
    from executions.services import ExecutionService  # noqa: PLC0415
    return ExecutionService()

def override_service(name: str, factory: Callable) -> None:
    """Register a custom factory for *name* (used in test setUp / fixture)."""
    _service_registry[name] = factory

def reset_services() -> None:
    """Clear all service overrides (call in test tearDown / fixture finalizer)."""
    _service_registry.clear()
```

**Les tests webhooks doivent migrer :**
```python
# Avant (monkey-patch fragile) :
import executions.views.github_webhooks as m
m._execution_service_factory = lambda: MockExecutionService()

# Après (DI propre) :
from core.di import override_service, reset_services
override_service('execution_service', lambda: MockExecutionService())
# ... test ...
reset_services()  # dans tearDown
```

### Contexte stories précédentes pertinent

**Story 33.1** (`ec7a77b feat(33-4)`) a établi :
- `ServiceRegistry` dans `services/registry.py` et `AdapterRegistry` dans `adapters/registry.py` — même pattern à réutiliser pour `RuntimeRegistry`

**Story 33.4** (`ec7a77b feat(33-4)`) a établi :
- Pattern DI `_service_class` / `get_service()` dans les viewsets
- `core/di.py` avec `override_service()` / `reset_services()` — la fondation est là, il faut juste l'utiliser dans les webhooks

**Story 34.3** (`07dd0e5 feat(34-3)`) a établi :
- `executions/scheduling_service.py` comme split de `executions/services.py` — `services.py` est maintenant ≤863 lignes
- Pattern d'import lazy `# noqa: PLC0415` pour éviter les imports circulaires

**Story 34.1** (`585ead9 feat(34-1)`) a établi :
- Pattern DI `get_catalog_service()` dans les vues — analogue à `get_execution_service()` dans les webhooks

**Story 34.2** (`fdf7ecc feat(34-2)`) a établi :
- Pattern `setNotificationCallback` (analogue DIP frontend) — référence pour DIP cohérent cross-stack

### Registries existants (référence pour cohérence)

| Registry | Fichier | Clés | Méthodes |
|----------|---------|------|---------|
| `ServiceRegistry` | `services/registry.py` | vault, splunk, servicenow, jira, notification | register, unregister, get, list_types |
| `AdapterRegistry` | `adapters/registry.py` | aap, tower, azure_devops, github_actions, terraform_cloud | register, unregister, get, list_types |
| `OutputInterpreterRegistry` | `executions/interpreters/registry.py` | step_types | get_instance (singleton), register, get |
| **`RuntimeRegistry`** | `executions/runtime_registry.py` ← **CRÉER** | workflow, simulation | register, unregister, get, list_keys |

### Arborescence des fichiers concernés

```
idp-portal/django_backend/
  executions/
    runtime_registry.py              ← CRÉER : RuntimeRegistry + defaults
    services.py                      ← MODIFIER : launch_workflow() lookup via registry
    views/
      github_webhooks.py             ← MODIFIER : ligne 34 (_exec_service_factory) + ~210 (svc =)
      terraform_webhooks.py          ← MODIFIER : ligne 34 (_exec_service_factory) + ~219 (svc =)
    tests/
      test_runtime_registry.py       ← CRÉER : 3+ tests
      test_github_webhooks.py        ← MODIFIER : monkey-patch → override_service
      test_terraform_webhooks.py     ← MODIFIER : monkey-patch → override_service
  core/
    di.py                            ← LIRE seulement (get_execution_service est déjà là)
```

### Project Structure Notes

- Aucune migration DB requise — refactorings de code Python uniquement
- Pas d'impact sur l'API REST publique — contrats inchangés
- `runtime_registry.py` suit le pattern `_register_defaults()` existant dans d'autres registries du projet
- L'import de `SIMULATE_EXECUTION_DEV` dans `_register_defaults()` est conditionnel au boot — compatible avec les tests qui ne définissent pas ce setting (il sera `False` par défaut)
- Les tests webhook doivent appeler `reset_services()` dans `tearDown` pour éviter les fuites d'état entre tests (déjà documenté dans `core/di.py`)

### Commandes de test recommandées

```bash
# Depuis django_backend
cd /Users/cyrille/Documents/Dev/test/idp-portal/django_backend

# Vérifications imports post-refactoring
.venv/bin/python -c "from executions.runtime_registry import runtime_registry; print('keys:', runtime_registry.list_keys())"
.venv/bin/python -c "from core.di import get_execution_service; svc = get_execution_service(); print('DI OK:', type(svc).__name__)"

# Tests ciblés
.venv/bin/python -m pytest executions/tests/test_runtime_registry.py -v
.venv/bin/python -m pytest executions/tests/test_github_webhooks.py -v
.venv/bin/python -m pytest executions/tests/test_terraform_webhooks.py -v

# Suite complète périmètre
.venv/bin/python -m pytest executions/ -x -q --ignore=executions/tests.py
```

### References

- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-BE-7] — launch_workflow() if/elif item_type OCP violation
- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-BE-9] — _execution_service_factory module-level monkey-patch
- [Source: django_backend/executions/services.py:382-408] — launch_workflow() code actuel
- [Source: django_backend/executions/views/github_webhooks.py:34] — _execution_service_factory (GitHub)
- [Source: django_backend/executions/views/terraform_webhooks.py:34] — _execution_service_factory (Terraform)
- [Source: django_backend/core/di.py] — get_execution_service(), override_service(), reset_services()
- [Source: django_backend/services/registry.py] — ServiceRegistry pattern (Story 33.1) — modèle pour RuntimeRegistry
- [Source: django_backend/adapters/registry.py] — AdapterRegistry pattern (Story 33.1) — modèle pour RuntimeRegistry
- [Source: django_backend/executions/interpreters/registry.py] — OutputInterpreterRegistry (singleton thread-safe) — référence
- [Source: _bmad-output/planning-artifacts/epic-34-codebase-review-restant-fev-2026.md#Story-34.4]
- [Source: _bmad-output/implementation-artifacts/34-3-backend-cache-rbac-split-services-lsp-serializers.md] — pattern import lazy noqa:PLC0415 établi

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

Aucun blocage. Confirmation que les 19 échecs restants dans `executions/` sont pré-existants (avant : 22 failed, 625 passed → après : 19 failed, 628 passed). Aucune régression.

### Completion Notes List

- **Task 1 (SOLID-BE-7)** : `executions/runtime_registry.py` créé — `RuntimeRegistry` avec `register/get/unregister/list_keys` + `_register_defaults()` qui enregistre `workflow` → `ContainerWorkflowRuntime` et `simulation` → `SimulationService` (conditionnel `SIMULATE_EXECUTION_DEV`). `launch_workflow()` dans `services.py` simplifié : dispatch via registry, retour silencieux si clé inconnue.
- **Task 2 (SOLID-BE-9)** : `github_webhooks.py` et `terraform_webhooks.py` — suppression de `_execution_service_factory = ExecutionService` (niveau module) et remplacement par import lazy `from core.di import get_execution_service`. Tests webhooks migrés vers `override_service` + `teardown_method` → `reset_services()`.
- **Task 3 (Régression)** : 11/11 `test_runtime_registry.py` pass ; 9/9 `test_github_webhooks.py` pass ; 20/20 `test_terraform_webhooks.py` pass ; suite globale 628 passed (vs 625 avant), 0 nouvelle régression.
- Nouveau fichier `test_github_webhooks.py` créé (inexistant auparavant) avec le test `test_webhook_di_override_service` (AC2).

### File List

- `idp-portal/django_backend/executions/runtime_registry.py` — CRÉÉ ; MODIFIÉ (code review : ajout `threading.Lock`)
- `idp-portal/django_backend/executions/services.py` — MODIFIÉ (launch_workflow) ; MODIFIÉ (code review : `logger.info` → `logger.debug`)
- `idp-portal/django_backend/executions/views/github_webhooks.py` — MODIFIÉ (DI get_execution_service)
- `idp-portal/django_backend/executions/views/terraform_webhooks.py` — MODIFIÉ (DI get_execution_service)
- `idp-portal/django_backend/executions/tests/test_runtime_registry.py` — CRÉÉ ; MODIFIÉ (code review : assertion test_overwrite_logs_warning, 2 nouveaux tests _register_defaults)
- `idp-portal/django_backend/executions/tests/test_github_webhooks.py` — CRÉÉ
- `idp-portal/django_backend/executions/tests/test_terraform_webhooks.py` — MODIFIÉ (override_service + teardown)

### Senior Developer Review (AI)

**Date :** 2026-02-22 | **Reviewer :** claude-sonnet-4-6

**Verdict :** ✅ APPROUVÉ après corrections automatiques

**Résumé :** Toutes les ACs sont implémentées. 5 problèmes trouvés et corrigés automatiquement.

| # | Sévérité | Fichier | Problème | Statut |
|---|----------|---------|----------|--------|
| M1 | MEDIUM | `tests/test_runtime_registry.py:52` | `test_overwrite_logs_warning` sans assertion réelle — test fantôme | ✅ Corrigé : `patch.object(logger, 'warning')` + `assert_called_once_with` |
| M2 | MEDIUM | `runtime_registry.py` | Pas de `threading.Lock` — divergence vs `OutputInterpreterRegistry` (modèle cité) | ✅ Corrigé : `self._lock = threading.Lock()` sur `register/unregister/list_keys` |
| L1 | LOW | `services.py:395` | `logger.info` pour type "action" (cas normal sans runtime) → bruit prod | ✅ Corrigé : `logger.debug` |
| L2 | LOW | `tests/test_runtime_registry.py` | Branche `SIMULATE_EXECUTION_DEV=True` dans `_register_defaults()` non testée | ✅ Corrigé : 2 nouveaux tests `test_register_defaults_*` |
| L3 | LOW | Story Task 2.4 | Marquée `[x]` sans trace vérifiable de la vérification imports circulaires | ✅ Corrigé : documentation ajoutée dans Task 2.4 |

**Tests après corrections :** 42/42 ✅ (vs 40/40 avant)
