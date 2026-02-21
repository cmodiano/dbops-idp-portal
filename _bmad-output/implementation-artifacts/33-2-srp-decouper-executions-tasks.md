# Story 33.2 : SRP — Découper executions/tasks.py

Status: done

## Story

En tant que mainteneur,
je veux que `executions/tasks.py` soit découpé en modules cohérents,
afin de réduire la taille du fichier et isoler les responsabilités (retry, polling par plateforme, gate evaluation).

## Acceptance Criteria

1. **Given** le fichier `executions/tasks.py` actuel (~1 580 LOC)
   **Then** il est converti en package `executions/tasks/` avec au moins 3 modules distincts :
   - `executions/tasks/retry.py` — tâche de retry workflow
   - `executions/tasks/gates.py` — évaluation périodique des gates WAITING
   - `executions/tasks/polling.py` — toutes les tâches de polling plateforme

2. **And** les tâches Celery restent importables depuis `executions.tasks` via `__init__.py` ré-exportant toutes les tâches publiques (rétrocompatibilité totale)

3. **And** chaque module a un docstring de module décrivant sa responsabilité unique

4. **And** les tests existants passent SANS modification des imports (les tests importent depuis `executions.tasks.*` ou `executions.tasks`)

5. **And** `executions/workflow_runtime.py` (seul consommateur externe connu) continue de fonctionner sans modification ou avec une mise à jour minimale des imports

## Tasks / Subtasks

- [x] Task 1 — Créer le package `executions/tasks/` (AC: 1)
  - [x] 1.1 — Créer le répertoire `executions/tasks/`
  - [x] 1.2 — Créer `executions/tasks/retry.py` : déplacer `retry_workflow_step()` et ses imports directs (docstring de module requis)
  - [x] 1.3 — Créer `executions/tasks/gates.py` : déplacer `evaluate_waiting_gates()`, `_transition_step_to_running()`, `_update_waiting_context()`, `_handle_gate_timeout()` (docstring de module requis) — `_mark_execution_polling_exhausted` placé dans polling.py (dépendance `MAX_POLLING_RETRIES`)
  - [x] 1.4 — Créer `executions/tasks/polling.py` : déplacer les 5 tâches `poll_*` + `_broadcast_execution_update()` + `_update_execution_from_poll()` + `_mark_execution_polling_exhausted()` + constante `MAX_POLLING_RETRIES` (docstring de module requis)

- [x] Task 2 — Créer `executions/tasks/__init__.py` avec ré-exports (AC: 2)
  - [x] 2.1 — Importer et ré-exporter : `retry_workflow_step`, `evaluate_waiting_gates`, `poll_aap_job_status`, `poll_tower_job_status`, `poll_azure_devops_run_status`, `poll_github_actions_run_status`, `poll_terraform_cloud_run_status`
  - [x] 2.2 — Ré-exporter `MAX_POLLING_RETRIES` (utilisé dans les tests `test_polling_max_retries.py`)
  - [x] 2.3 — Définir `__all__` avec toutes les exportations publiques (+ helpers internes pour patchabilité des tests)

- [x] Task 3 — Supprimer l'ancien `executions/tasks.py` (AC: 1)
  - [x] 3.1 — Vérifier qu'aucune référence directe à `executions/tasks.py` en tant que fichier n'est présente dans la config Celery ou `INSTALLED_APPS`
  - [x] 3.2 — Supprimer `executions/tasks.py`

- [x] Task 4 — Mettre à jour `executions/workflow_runtime.py` si nécessaire (AC: 5)
  - [x] 4.1 — Vérifier l'import actuel : `from executions.tasks import retry_workflow_step`
  - [x] 4.2 — L'import via `executions.tasks` continue de fonctionner via `__init__.py` (aucune modification nécessaire)

- [x] Task 5 — Valider (AC: 4)
  - [x] 5.1 — Lancer la suite complète des tests : 104 tests passent + 1 skippé (intégration Celery broker)
  - [x] 5.2 — Vérifier spécifiquement : `test_celery_retry_tasks.py`, `test_evaluate_waiting_gates.py`, `test_polling_max_retries.py` — tous PASS
  - [x] 5.3 — Vérifier que l'import `from executions.tasks import retry_workflow_step` fonctionne toujours ✓

## Dev Notes

### Structure actuelle à migrer

**Fichier** : `idp-portal/django_backend/executions/tasks.py` — **1 580 LOC**

#### Inventaire complet des fonctions (avec numéros de ligne)

| Fonction | Lignes | Type | Module cible |
|----------|--------|------|--------------|
| `retry_workflow_step` | 30–222 | `@shared_task` | `tasks/retry.py` |
| `evaluate_waiting_gates` | 225–338 | `@shared_task` | `tasks/gates.py` |
| `_transition_step_to_running` | 341–428 | helper | `tasks/gates.py` |
| `_update_waiting_context` | 431–460 | helper | `tasks/gates.py` |
| `_handle_gate_timeout` | 463–572 | helper | `tasks/gates.py` |
| `_mark_execution_polling_exhausted` | 575–643 | helper | `tasks/polling.py` |
| `poll_aap_job_status` | 650–821 | `@shared_task` | `tasks/polling.py` |
| `poll_tower_job_status` | 828–967 | `@shared_task` | `tasks/polling.py` |
| `poll_azure_devops_run_status` | 974–1127 | `@shared_task` | `tasks/polling.py` |
| `_broadcast_execution_update` | 1130–1199 | helper | `tasks/polling.py` |
| `_update_execution_from_poll` | 1202–1258 | helper | `tasks/polling.py` |
| `poll_github_actions_run_status` | 1266–1423 | `@shared_task` | `tasks/polling.py` |
| `poll_terraform_cloud_run_status` | 1431–1580 | `@shared_task` | `tasks/polling.py` |

**Constante** : `MAX_POLLING_RETRIES = 20` (ligne 27) → `tasks/polling.py`

#### Imports top-level actuels (à répartir dans chaque module)

```python
from typing import Any
import structlog
from celery import shared_task
from django.utils import timezone
from executions.models import (Execution, ExecutionStatus, ExecutionStep, ExecutionStepStatus)
from executions.workflow_runtime import StepOutcome
from core.services import AuditService
from core.middleware import get_correlation_id
from core.models import AuditActionType, AuditEntityType
```

### Structure cible

```
executions/tasks/
├── __init__.py          # Ré-exports rétrocompatibles
├── retry.py             # retry_workflow_step
├── gates.py             # evaluate_waiting_gates + 4 helpers
└── polling.py           # 5 poll_* + 2 helpers + MAX_POLLING_RETRIES
```

### Contenu `__init__.py` (rétrocompatibilité)

```python
"""
Package executions/tasks — Celery tasks for workflow execution.

Ce package regroupe les tâches Celery par responsabilité :
- retry    : retry asynchrone des étapes de workflow
- gates    : évaluation périodique des conditions WAITING
- polling  : surveillance des jobs sur les plateformes externes
"""
from executions.tasks.retry import retry_workflow_step
from executions.tasks.gates import evaluate_waiting_gates
from executions.tasks.polling import (
    poll_aap_job_status,
    poll_tower_job_status,
    poll_azure_devops_run_status,
    poll_github_actions_run_status,
    poll_terraform_cloud_run_status,
    MAX_POLLING_RETRIES,
)

__all__ = [
    "retry_workflow_step",
    "evaluate_waiting_gates",
    "poll_aap_job_status",
    "poll_tower_job_status",
    "poll_azure_devops_run_status",
    "poll_github_actions_run_status",
    "poll_terraform_cloud_run_status",
    "MAX_POLLING_RETRIES",
]
```

### Responsabilités claires par module

**`tasks/retry.py`** — Responsabilité unique : exécuter un step de workflow en mode async retry avec backoff exponentiel.
- Imports spécifiques : `StepOutcome`, `WorkflowRuntime` (lazy), `cancellation_cache`, `AuditService`, `AuditActionType.EXECUTION_STEP_RETRY_*`

**`tasks/gates.py`** — Responsabilité unique : évaluation périodique des conditions WAITING et transition vers RUNNING.
- 5 fonctions : `evaluate_waiting_gates` (Celery Beat) + 4 helpers orchestrant la transition atomique et les timeouts
- Doit importer `retry_workflow_step` depuis `executions.tasks.retry` (PAS depuis `executions.tasks` pour éviter un import circulaire)

**`tasks/polling.py`** — Responsabilité unique : surveillance asynchrone des jobs sur 5 plateformes externes.
- Pattern commun : `asyncio.run()` pour appels adapters async
- Helpers partagés : `_broadcast_execution_update()` (WebSocket), `_update_execution_from_poll()` (DB)
- Adapters importés en lazy dans chaque tâche (pattern existant à conserver)

### PIÈGE CRITIQUE — Noms des tâches Celery

Après conversion en package, le nom Celery d'une tâche change :
- **Avant** : `"executions.tasks.retry_workflow_step"` (chemin `executions/tasks.py`)
- **Après** : `"executions.tasks.retry.retry_workflow_step"` (chemin `executions/tasks/retry.py`)

Si des tâches Celery sont en cours d'exécution ou schedulées avec l'ancien nom lors du déploiement, elles échoueront.

**Solution recommandée** — ajouter le paramètre `name=` explicite sur chaque `@shared_task` :

```python
# tasks/retry.py
@shared_task(bind=True, max_retries=0, name="executions.tasks.retry_workflow_step")
def retry_workflow_step(self: Any, ...) -> dict:
    ...

# tasks/gates.py
@shared_task(name="executions.tasks.evaluate_waiting_gates")
def evaluate_waiting_gates() -> dict:
    ...

# tasks/polling.py
@shared_task(bind=True, name="executions.tasks.poll_aap_job_status")
def poll_aap_job_status(self: Any, ...) -> None:
    ...
# (idem pour les 4 autres poll_*)
```

Cela garantit que les noms Celery restent identiques avant et après le refactoring.

### Dépendances entre sous-modules (ordre d'import)

```
tasks/retry.py        ← pas de dépendance entre sous-modules
tasks/gates.py        ← from executions.tasks.retry import retry_workflow_step
tasks/polling.py      ← autonome (5 tâches indépendantes)
tasks/__init__.py     ← from executions.tasks.{retry,gates,polling} import ...
```

### Découverte Celery

Vérifier `idp_backend/celery.py` — s'il utilise `autodiscover_tasks(['executions'])`, Celery trouvera automatiquement le package `executions/tasks/` via `__init__.py`. Aucun changement nécessaire.

### Commandes de test

```bash
# Depuis idp-portal/django_backend/
.venv/bin/python -m pytest executions/tests/test_celery_retry_tasks.py -v
.venv/bin/python -m pytest executions/tests/test_evaluate_waiting_gates.py -v
.venv/bin/python -m pytest executions/tests/test_polling_max_retries.py -v
.venv/bin/python -m pytest executions/tests/ -v --tb=short  # suite complète
```

### Apprentissages de la Story 33.1 (OCP Registry)

- **Ré-exports via `__init__.py`** — même pattern que `adapters/__init__.py` et `services/__init__.py` : importer les symboles publics et définir `__all__`.
- **Lazy imports** — conserver les imports dans les fonctions (pattern existant dans tasks.py) pour éviter les circulaires.
- **50/50 tests ont passé sans modification** en 33.1 grâce aux ré-exports corrects. Même approche ici.
- **Warning log sur écrasement** (B1 du code review 33.1) — non applicable ici, mais penser aux docstrings clairs sur chaque module.

### Project Structure Notes

**Fichiers à créer :**
```
idp-portal/django_backend/executions/tasks/__init__.py
idp-portal/django_backend/executions/tasks/retry.py
idp-portal/django_backend/executions/tasks/gates.py
idp-portal/django_backend/executions/tasks/polling.py
```

**Fichier à supprimer :**
```
idp-portal/django_backend/executions/tasks.py
```

**Fichiers potentiellement à mettre à jour :**
```
idp-portal/django_backend/executions/workflow_runtime.py  (import optionnel — fonctionne déjà via __init__)
idp-portal/django_backend/idp_backend/celery.py           (vérifier config Celery Beat)
```

**Fichiers de tests à NE PAS modifier (validés via ré-exports) :**
```
executions/tests/test_celery_retry_tasks.py
executions/tests/test_evaluate_waiting_gates.py
executions/tests/test_polling_max_retries.py
executions/tests/test_aap_monitoring.py
executions/tests/test_tower_monitoring.py
executions/tests/test_azure_devops_monitoring.py
executions/tests/test_workflow_runtime_retry*.py
```

### References

- [Source: _bmad-output/planning-artifacts/epic-33-conformite-solid.md#Story 33.2]
- [Source: idp-portal/django_backend/executions/tasks.py] — implémentation actuelle 1580 LOC
- [Source: idp-portal/django_backend/executions/workflow_runtime.py] — seul consommateur externe (`from executions.tasks import retry_workflow_step`)
- [Source: _bmad-output/implementation-artifacts/33-1-ocp-registry-pattern-adapters-services.md] — pattern ré-exports `__init__.py`, lazy imports, `__all__`
- [Source: idp-portal/django_backend/executions/tests/test_celery_retry_tasks.py] — tests retry à ne pas casser
- [Source: idp-portal/django_backend/executions/tests/test_evaluate_waiting_gates.py] — tests gates à ne pas casser

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- **Découpage réalisé** : `executions/tasks.py` (1 580 LOC) → package `executions/tasks/` avec 3 modules + `__init__.py`
- **Noms Celery préservés** : paramètre `name="executions.tasks.X"` explicite sur tous les `@shared_task`
- **Patchabilité des tests** : pattern `import executions.tasks as _tasks` appliqué de façon lazy dans chaque fonction (corps de fonction, jamais en import module-level) pour que `@patch("executions.tasks.X")` intercepte correctement les appels
- **`_mark_execution_polling_exhausted`** : placé dans `polling.py` (et non `gates.py` comme indiqué dans la table de l'inventaire) car il utilise `MAX_POLLING_RETRIES` (défini dans polling.py) et n'est appelé que par les polling tasks
- **`logger` et `get_correlation_id`** : ré-exportés depuis `__init__.py` pour les patches `@patch("executions.tasks.logger")` et `@patch("executions.tasks.get_correlation_id")`
- **Résultat tests** : 104 tests passent + 1 skippé (intégration Celery broker) sans modification des fichiers de tests
- **Code review 2026-02-21** : 4 MEDIUM + 2 LOW issues → 3 MEDIUM + 2 LOW auto-fixés : noms log génériques dans `_broadcast_execution_update`, paramètre `correlation_id` ajouté à `_broadcast_execution_update`, table Dev Notes corrigée (`_mark_execution_polling_exhausted` → `polling.py`), `_transition_step_to_running` + `_update_waiting_context` ajoutés aux re-exports `__init__.py`. MEDIUM non-fixé (carry-over) : clé `"aap_logs"` pour toutes les plateformes dans `_update_execution_from_poll` — nécessite coordination frontend, documenté pour story dédiée.

### File List

**Créés :**
- `idp-portal/django_backend/executions/tasks/__init__.py`
- `idp-portal/django_backend/executions/tasks/retry.py`
- `idp-portal/django_backend/executions/tasks/gates.py`
- `idp-portal/django_backend/executions/tasks/polling.py`

**Supprimé :**
- `idp-portal/django_backend/executions/tasks.py`
