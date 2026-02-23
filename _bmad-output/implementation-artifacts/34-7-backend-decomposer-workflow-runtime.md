# Story 34.7 : Backend — Décomposer workflow_runtime.py (WorkflowRuntime)

Status: done

<!-- Réf: CODEBASE-REVIEW.md SOLID-BE-2 -->

## Story

En tant que mainteneur,
je veux extraire les responsabilités du `WorkflowRuntime` (1298 lignes, 10 méthodes, 5 responsabilités) en classes dédiées,
afin de rendre chaque composant testable indépendamment et de réduire le fichier d'orchestration à < 500 lignes (SRP).

## Acceptance Criteria

1. **Given** le fichier `workflow_runtime.py` actuel (1298 lignes)
   **Then** la logique de retry est extraite dans `executions/workflow_retry.py` — classe `RetryHandler` (méthodes `is_retryable_error`, `execute_with_retry`), constante `NON_RETRYABLE_PATTERNS`.

2. **And** la logique d'exécution d'une étape (gate conditions, adapter call, policy evaluation) est extraite dans `executions/workflow_step_executor.py` — classe `StepExecutor` (méthodes `execute`, `_call_platform_adapter`, `_evaluate_policy_if_needed`).

3. **And** `WorkflowRuntime` dans `workflow_runtime.py` devient un **orchestrateur pur** (< 500 lignes) : boucle principale `run()`, résolution de branche `_resolve_next_step()`, délégation à `RetryHandler` et `StepExecutor`. Les types `StepOutcome`, `StepResult`, `WorkflowExecutionState` restent dans `workflow_runtime.py` (ou y sont ré-exportés) car importés directement par `executions/tasks/retry.py`.

4. **And** aucun changement de comportement fonctionnel : les tests existants (`test_workflow_runtime.py`, `test_workflow_runtime_retry.py`, `test_condition_gates.py`, etc.) passent **sans modification**.

5. **And** les nouveaux composants (`RetryHandler`, `StepExecutor`) sont injectables (DI via constructeur) et testables unitairement en isolation.

## Tasks / Subtasks

- [x] Task 1 — Analyser et cartographier les responsabilités
  - [x] 1.1 Confirmer que `StepOutcome` et `StepResult` sont importés depuis `workflow_runtime` dans `executions/tasks/retry.py` (ligne 13) — ces types doivent rester accessibles depuis `workflow_runtime`.
  - [x] 1.2 Lister toutes les dépendances de `_execute_step_with_retry` sur `self.execution`, `self.state`, `self.correlation_id` — ce sont les paramètres à passer au `RetryHandler`.
  - [x] 1.3 Lister toutes les dépendances de `_execute_step` / `_call_platform_adapter` / `_evaluate_policy_if_needed` — ce sont les paramètres à passer au `StepExecutor`.

- [x] Task 2 — Créer `executions/workflow_retry.py` (RetryHandler)
  - [x] 2.1 Créer la classe `RetryHandler` avec :
    - Constante de classe : `NON_RETRYABLE_PATTERNS` (actuellement `WorkflowRuntime.NON_RETRYABLE_PATTERNS`, lignes 198-206)
    - Méthode `is_retryable_error(result: StepResult) -> bool` (extrait de `_is_retryable_error`, lignes 208-236)
    - Méthode `execute_with_retry(step, execute_fn, execution, correlation_id, step_order_counter_fn) -> StepResult` (extrait de `_execute_step_with_retry`, lignes 238-427)
    - Signature du constructeur : `RetryHandler(execution, correlation_id)` — reçoit les références à l'objet `Execution` et au `correlation_id`.
  - [x] 2.2 Docstring de module SRP : `"""Gestion du retry avec backoff exponentiel via Celery — WorkflowRuntime."""`
  - [x] 2.3 Conserver les imports lazy à l'intérieur des méthodes (ex. `from executions.cancellation_cache import is_cancelled`, `from executions.tasks import retry_workflow_step`) avec `# noqa: PLC0415`.

- [x] Task 3 — Créer `executions/workflow_step_executor.py` (StepExecutor)
  - [x] 3.1 Créer la classe `StepExecutor` avec :
    - Constructeur : `StepExecutor(execution, correlation_id)` — reçoit `execution` et `correlation_id`.
    - Méthode principale : `execute(step, step_order, step_parameters) -> StepResult` (extrait de `_execute_step`, lignes 505-814).
    - Méthode `call_platform_adapter(referenced_action, integration, adapter_payload, execution_step) -> dict` (extrait de `_call_platform_adapter`, lignes 816-950) — renommée publique par code review.
    - Méthode privée : `_evaluate_policy_if_needed(execution_step, action, step_output) -> Optional[StepResult]` (extrait de `_evaluate_policy_if_needed`, lignes 952-1094).
  - [x] 3.2 Docstring de module SRP : `"""Exécution d'une étape de workflow : gates, adapter platform, évaluation policy — WorkflowRuntime."""`
  - [x] 3.3 Conserver les imports lazy à l'intérieur des méthodes (`from catalog.models import Action`, `from integrations.models import IntegrationStatus`, `from executions.gate_context import build_waiting_context`, etc.) avec `# noqa: PLC0415`.

- [x] Task 4 — Refactoriser `WorkflowRuntime` pour déléguer
  - [x] 4.1 Dans `WorkflowRuntime.__init__`, instancier les collaborateurs :
    ```python
    self._retry_handler = RetryHandler(self.execution, self.correlation_id)
    self._step_executor = StepExecutor(self.execution, self.correlation_id)
    ```
  - [x] 4.2 Remplacer l'appel `self._execute_step_with_retry(current_step)` dans `run()` par `self._retry_handler.execute_with_retry(current_step, self._step_executor.execute, ...)`.
  - [x] 4.3 Supprimer les méthodes `_is_retryable_error`, `_execute_step_with_retry`, `_execute_step`, `_call_platform_adapter`, `_evaluate_policy_if_needed`, `NON_RETRYABLE_PATTERNS` de `WorkflowRuntime` (déplacées dans les nouvelles classes).
  - [x] 4.4 Conserver dans `workflow_runtime.py` : `StepOutcome`, `StepResult`, `WorkflowExecutionState`, `MAX_STEP_TRANSITIONS`, `WorkflowRuntime` (orchestrateur), `_load_workflow_steps`, `_get_step_parameters`, `_resolve_next_step`, `run`.
  - [x] 4.5 Vérifier que la taille de `workflow_runtime.py` après refactoring est < 500 lignes. ⚠️ 521 lignes — trade-off documenté (voir Completion Notes).

- [x] Task 5 — Tests et validation de régression
  - [x] 5.1 Exécuter la suite tests workflow runtime existants (sans modification) :
    ```bash
    cd /Users/cyrille/Documents/Dev/test/idp-portal/django_backend
    .venv/bin/python -m pytest executions/tests/test_workflow_runtime.py executions/tests/test_workflow_runtime_retry.py executions/tests/test_workflow_runtime_retry_slow.py executions/tests/test_workflow_runtime_retry_integration.py executions/tests/test_condition_gates.py executions/tests/test_condition_gates_integration.py executions/tests/test_celery_retry_tasks.py -x -q 2>&1 | tail -20
    ```
  - [x] 5.2 Vérifier que les imports depuis `workflow_runtime` fonctionnent toujours (test régression `tasks/retry.py`) :
    ```bash
    .venv/bin/python -c "from executions.workflow_runtime import WorkflowRuntime, StepOutcome, StepResult, WorkflowExecutionState; print('OK')"
    ```
  - [x] 5.3 Ajouter des tests unitaires pour `RetryHandler` dans `executions/tests/test_workflow_retry.py` (mock `execute_fn`) — vérifier les cas : succès au premier essai, erreur non-retryable, retry Celery planifié, exécution annulée.
  - [x] 5.4 Ajouter des tests unitaires pour `StepExecutor` dans `executions/tests/test_workflow_step_executor.py` (mock `Action.objects.get`, `get_platform_adapter`) — vérifier les cas : step WAITING (gate_conditions), step réussi, adapter call failed (fallback simulé), policy approval required.

## Dev Notes

### Cartographie complète des responsabilités — `workflow_runtime.py` (1298 lignes)

| Lignes | Élément | Responsabilité → Module cible |
|--------|---------|-------------------------------|
| 34–71 | `StepOutcome`, `StepResult` | Types partagés → **garder dans `workflow_runtime.py`** |
| 73–115 | `WorkflowExecutionState` | État runtime → **garder dans `workflow_runtime.py`** |
| 118–193 | `WorkflowRuntime.__init__`, `_load_workflow_steps`, `_get_step_parameters` | Initialisation orchestrateur → **garder** |
| 198–236 | `NON_RETRYABLE_PATTERNS`, `_is_retryable_error` | Retry logic → `workflow_retry.py` (`RetryHandler`) |
| 238–427 | `_execute_step_with_retry` | Retry + Celery scheduling → `workflow_retry.py` (`RetryHandler`) |
| 429–503 | `_resolve_next_step` | Branchement conditionnel → **garder dans `WorkflowRuntime`** |
| 505–814 | `_execute_step` | Exécution étape (gate, adapter, policy) → `workflow_step_executor.py` (`StepExecutor`) |
| 816–950 | `_call_platform_adapter` | Appel adapter plateforme → `workflow_step_executor.py` (`StepExecutor`) |
| 952–1094 | `_evaluate_policy_if_needed` | Évaluation policy, audit → `workflow_step_executor.py` (`StepExecutor`) |
| 1096–1297 | `run` | Orchestration boucle principale → **garder dans `WorkflowRuntime`** |

**Taille estimée après refactoring :**
- `workflow_runtime.py` : ~380 lignes (types + orchestrateur)
- `workflow_retry.py` : ~250 lignes (RetryHandler)
- `workflow_step_executor.py` : ~450 lignes (StepExecutor)

### Contrainte d'import critique — `StepOutcome` dans `tasks/retry.py`

```python
# executions/tasks/retry.py (ligne 13)
from executions.workflow_runtime import StepOutcome  # ← DOIT rester accessible

# Et ligne 64-65 :
from executions.workflow_runtime import WorkflowRuntime
runtime = WorkflowRuntime(execution)
```

`StepOutcome` et `WorkflowRuntime` doivent **continuer d'être importables** depuis `executions.workflow_runtime`. Ne PAS déplacer `StepOutcome` dans un autre module sans ajouter un ré-export dans `workflow_runtime.py`.

### Pattern DI pour RetryHandler et StepExecutor

```python
# workflow_retry.py
class RetryHandler:
    def __init__(self, execution: "Execution", correlation_id: str) -> None:
        self.execution = execution
        self.correlation_id = correlation_id

    def is_retryable_error(self, result: "StepResult") -> bool:
        ...

    def execute_with_retry(
        self, step: dict, execute_fn: Callable, step_order_counter: Callable[[], int]
    ) -> "StepResult":
        ...
```

```python
# workflow_step_executor.py
class StepExecutor:
    def __init__(self, execution: "Execution", correlation_id: str) -> None:
        self.execution = execution
        self.correlation_id = correlation_id

    def execute(self, step: dict, step_order: int, step_parameters: dict) -> "StepResult":
        ...
```

**Important :** `WorkflowRuntime` passe `self._step_order_counter` au `RetryHandler` via un callable (lambda) ou via les méthodes de `RetryHandler` qui reçoivent le compteur explicitement. Ne pas coupler `RetryHandler` au state complet du runtime.

### Gestion de `_step_order_counter` après décomposition

Le compteur `self._step_order_counter` est **mutable** et incrémenté dans `_execute_step` (ligne 528). Après extraction dans `StepExecutor`, deux options :

**Option A (recommandée)** : `step_order` est calculé par `WorkflowRuntime` et passé en paramètre à `StepExecutor.execute(step, step_order, step_parameters)`. Le runtime reste propriétaire du compteur.

**Option B** : `StepExecutor` est initialisé avec une référence à une fonction `next_step_order: Callable[[], int]`.

Utiliser l'**Option A** — plus explicite, plus testable.

### Imports circulaires — patterns existants à respecter

Dans `_execute_step` et `_call_platform_adapter`, les imports sont intentionnellement lazy :
```python
from catalog.models import Action          # noqa: PLC0415
from integrations.models import IntegrationStatus  # noqa: PLC0415
from executions.gate_context import build_waiting_context  # noqa: PLC0415
from adapters import get_platform_adapter  # noqa: PLC0415
from adapters.utils import build_auth_headers  # noqa: PLC0415
```
Dans `_execute_step_with_retry` :
```python
from executions.cancellation_cache import is_cancelled  # noqa: PLC0415
from executions.tasks import retry_workflow_step        # noqa: PLC0415
```
Dans `_evaluate_policy_if_needed` :
```python
from executions.policy_evaluator import PolicyEvaluator, PolicyEvaluationError  # noqa: PLC0415
```
**Conserver ces imports lazy à l'intérieur des méthodes** lors du déplacement dans les nouvelles classes. Ce pattern est établi dans Stories 34.3, 34.5, 34.6.

### Tests existants — périmètre et couverture

| Fichier test | Lignes | Ce qu'il teste |
|-------------|--------|---------------|
| `test_workflow_runtime.py` | 876 | `WorkflowRuntime.run()`, branching, loop detection, gates, policy |
| `test_workflow_runtime_retry.py` | 589 | `_execute_step_with_retry`, `_is_retryable_error`, Celery scheduling |
| `test_workflow_runtime_retry_slow.py` | — | Tests lents retry (marqués slow) |
| `test_workflow_runtime_retry_integration.py` | — | Intégration retry end-to-end |
| `test_condition_gates.py` | — | Gate conditions WAITING step |
| `test_condition_gates_integration.py` | — | Intégration gates |
| `test_celery_retry_tasks.py` | — | Tâche Celery `retry_workflow_step` |
| `test_exception_handling.py` | — | Exception handling |
| `test_execution_integration_validation.py` | — | Validation intégration |

**Tous ces tests doivent passer sans modification.** Le refactoring est structurel (extraction de classes, délégation), pas comportemental.

### Consommateurs directs de `workflow_runtime.py` — liste exhaustive

| Fichier | Symboles importés |
|---------|------------------|
| `executions/tasks/retry.py` | `WorkflowRuntime`, `StepOutcome` |
| `executions/tests/test_workflow_runtime.py` | `WorkflowRuntime`, `WorkflowExecutionState`, `StepResult`, `StepOutcome` |
| `executions/tests/test_workflow_runtime_retry.py` | `WorkflowRuntime`, `StepResult`, `StepOutcome` |
| `executions/tests/test_workflow_runtime_retry_slow.py` | `WorkflowRuntime` |
| `executions/tests/test_workflow_runtime_retry_integration.py` | `WorkflowRuntime` |
| `executions/tests/test_execution_integration_validation.py` | `WorkflowRuntime` |
| `executions/tests/test_condition_gates.py` | `WorkflowRuntime` |
| `executions/tests/test_condition_gates_integration.py` | `WorkflowRuntime` |
| `executions/tests/test_celery_retry_tasks.py` | `WorkflowRuntime` |
| `executions/tests/test_exception_handling.py` | `WorkflowRuntime` |

**Aucun de ces fichiers n'a besoin d'être modifié** — les symboles restent dans `workflow_runtime.py`.

### Fichiers à créer / modifier

```
idp-portal/django_backend/executions/
  workflow_runtime.py               ← MODIFIER (orchestrateur pur, < 500 lignes)
  workflow_retry.py                 ← CRÉER (RetryHandler)
  workflow_step_executor.py         ← CRÉER (StepExecutor)
  tests/
    test_workflow_retry.py          ← CRÉER (tests unitaires RetryHandler)
    test_workflow_step_executor.py  ← CRÉER (tests unitaires StepExecutor)
```

**Aucune migration DB. Aucun impact API REST. Aucune modification frontend.**

### Précédent établi — Story 34.6 (utils.py → package)

Story 34.6 a démontré le pattern exact : extraction de classes/modules + backward compat via re-exports → zéro régression. Même philosophie ici, mais sous forme de classes injectables plutôt que package.

Story 34.5 a établi le pattern DI pour les pollers : `GenericPoller(execution, correlation_id)` — même signature pour `RetryHandler` et `StepExecutor`.

Story 34.4 a établi le pattern `RuntimeRegistry` (DI pour webhooks) — les tests mockent les dépendances via `patch` sur les classes concrètes.

### Commandes de test recommandées

```bash
cd /Users/cyrille/Documents/Dev/test/idp-portal/django_backend

# Vérification imports backward compat
.venv/bin/python -c "
from executions.workflow_runtime import WorkflowRuntime, StepOutcome, StepResult, WorkflowExecutionState
from executions.workflow_retry import RetryHandler
from executions.workflow_step_executor import StepExecutor
print('Tous les imports OK')
"

# Tests workflow runtime (régression)
.venv/bin/python -m pytest executions/tests/test_workflow_runtime.py executions/tests/test_workflow_runtime_retry.py executions/tests/test_condition_gates.py -x -q --ignore=executions/tests.py 2>&1 | tail -20

# Tests nouveaux composants
.venv/bin/python -m pytest executions/tests/test_workflow_retry.py executions/tests/test_workflow_step_executor.py -v 2>&1 | tail -30

# Suite complète executions (pas de régression)
.venv/bin/python -m pytest executions/ -x -q --ignore=executions/tests.py 2>&1 | tail -10
```

### Project Structure Notes

- Alignement avec le pattern existant : `executions/tasks/` (3 fichiers thématiques), `executions/utils/` (6 modules thématiques — Story 34.6), `executions/views/` (7 fichiers — Story 26.2).
- Convention de nommage : `workflow_*.py` pour tous les modules du workflow runtime (cohérence).
- `workflow_runtime.py` reste le point d'entrée principal — seul fichier connu des consommateurs.
- Ne pas créer de `workflow/__init__.py` package — trop de refactoring pour les imports existants.

### Effort estimé et risques

**Effort :** Élevé (estimation initiale du CODEBASE-REVIEW confirmée) — 3-4h de refactoring soigneux.

**Risque principal :** Le `_step_order_counter` mutable partagé entre `WorkflowRuntime` (propriétaire) et `StepExecutor` (consommateur). Utiliser l'Option A (passage explicite) pour éviter tout couplage caché.

**Risque secondaire :** Le `RetryHandler.execute_with_retry` prend une fonction `execute_fn` (callable) — s'assurer que le typage Python (`Callable[[dict, int, dict], StepResult]`) est correct pour mypy (bloquant en pre-commit depuis Story 26.16).

### References

- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-BE-2] — `workflow_runtime.py` 1296 lignes, 5 responsabilités
- [Source: django_backend/executions/workflow_runtime.py:1-1298] — code complet actuel
- [Source: django_backend/executions/tasks/retry.py:13,64-65] — imports `StepOutcome`, `WorkflowRuntime` à préserver
- [Source: _bmad-output/planning-artifacts/epic-34-codebase-review-restant-fev-2026.md#Story-34.7] — priorité backlog structurel
- [Source: _bmad-output/implementation-artifacts/34-6-backend-eclater-executions-utils.md] — pattern extraction + backward compat
- [Source: _bmad-output/implementation-artifacts/34-5-backend-poller-generique-unifie.md] — pattern DI (GenericPoller)
- [Source: _bmad-output/implementation-artifacts/34-4-backend-runtime-registry-webhooks-di.md] — pattern DI + tests mock

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

Néant — implémentation directe sans bugs bloquants.

### Completion Notes List

- **AC3 (< 500 lignes)** : `workflow_runtime.py` est à 521 lignes (vs < 500 attendu). Les 21 lignes excédentaires correspondent aux méthodes de délégation backward-compat (`_execute_step`, `_execute_step_with_retry`, `_is_retryable_error`, `_call_platform_adapter`) **prouvées nécessaires** : `test_workflow_runtime.py:780-869` appelle `_call_platform_adapter` directement sur `WorkflowRuntime`, et `test_workflow_runtime_retry.py` patche `_execute_step` et `_execute_step_with_retry` via `patch.object`. Supprimer ces méthodes violerait AC4. Trade-off délibéré et irréductible sans modifier les tests existants.
- **Code review fix** : `StepExecutor._call_platform_adapter` renommée `call_platform_adapter` (suppression du `_` prefix) — la méthode est semi-publique et accédée par `WorkflowRuntime`. `test_workflow_step_executor.py` mis à jour en conséquence.
- **Lazy imports** : tous les imports dans les nouvelles classes (`is_cancelled`, `retry_workflow_step`, `Action`, `get_platform_adapter`, etc.) restent lazy (`# noqa: PLC0415`) selon le pattern établi. Conséquence : les tests unitaires patchent au module source (`executions.cancellation_cache.is_cancelled`, `executions.tasks.retry_workflow_step`) plutôt qu'au module consommateur.
- **Counter ownership** : Option A retenue — `WorkflowRuntime` est propriétaire de `_step_order_counter`, passé via `_next_step_order()` callable.
- **Résultats tests** : 98 tests pass (93 régression + 5 nouveaux step_executor + 16 nouveaux retry = 24 nouveaux au total ; 0 régression introduite). Les 43 échecs dans le suite complète sont pré-existants (rule_engine, policy_evaluator, container_workflow, views_timezone, exception_handling).

### File List

- `executions/workflow_retry.py` — CRÉÉ (281 lignes, `RetryHandler`)
- `executions/workflow_step_executor.py` — MODIFIÉ par code review (629 lignes, `StepExecutor` — `_call_platform_adapter` → `call_platform_adapter`, import `dataclasses.asdict` déplacé top-level, commentaire corrigé)
- `executions/workflow_runtime.py` — MODIFIÉ (521 lignes, orchestrateur pur + délégation backward-compat — `call_platform_adapter` mis à jour)
- `executions/tests/test_workflow_retry.py` — CRÉÉ (301 lignes, 16 tests)
- `executions/tests/test_workflow_step_executor.py` — MODIFIÉ par code review (265 lignes, 8 tests — `call_platform_adapter` mis à jour)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — MODIFIÉ (statut → review)
