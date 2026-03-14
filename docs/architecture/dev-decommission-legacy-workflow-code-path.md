# Decommission de l'ancien code path workflow (dev-only)

Date: 2026-03-13  
Statut: Plan d'execution (DEV uniquement)  
Audience: Backend, QA, DevOps

---

## 1) Objectif

Completer le reset des donnees par la suppression effective de l'ancien code path workflow:

- retirer les chemins "legacy runtime + retry legacy"
- conserver un seul chemin d'orchestration
- simplifier le code, la config Celery et les tests

Contexte: environnement dev-only, sans contrainte de conservation historique.

---

## 2) Scope legacy a decommissionner

Contexte: plateforme non utilisee, dev uniquement — rien a conserver. Suppression totale du legacy.

## 2.1 Modules legacy cibles (supprimer)

- `executions/workflow_runtime.py`
- `executions/workflow_step_executor.py`
- `executions/workflow_retry.py`
- `executions/tasks/retry.py`
- `executions/workflow_types.py` (StepOutcome, StepResult, WorkflowExecutionState — utilises uniquement par le legacy)

## 2.2 Points d'entree / references a nettoyer

- `executions/tasks/__init__.py` — retirer re-export `retry_workflow_step`
- `executions/tasks/gates.py` — supprimer branche `old_style_step_def` et tout appel a `retry_workflow_step`
- `executions/container_workflow_runtime.py` — supprimer le bloc legacy fallback (thread-based, `WORKFLOW_LEGACY_RUNTIME_ENABLED`)
- `idp_backend/settings.py`:
  - `CELERY_TASK_ROUTES['executions.tasks.retry_workflow_step']`
  - `CELERY_TASK_TIME_LIMITS['retry_workflow_step']`
  - `WORKFLOW_LEGACY_RUNTIME_ENABLED` (plus de fallback)
- `executions/exceptions.py` — supprimer `WorkflowLegacyDisabledError` si plus reference
- `idp_backend/test_settings.py` — retirer `WORKFLOW_LEGACY_RUNTIME_ENABLED`

## 2.3 Surface de tests legacy (supprimer ou migrer)

Tests a supprimer (centres sur legacy):

- `executions/tests/test_workflow_runtime.py`
- `executions/tests/test_workflow_runtime_retry.py`
- `executions/tests/test_workflow_runtime_retry_integration.py`
- `executions/tests/test_workflow_runtime_retry_slow.py`
- `executions/tests/test_workflow_step_executor.py`
- `executions/tests/test_workflow_retry.py`
- `executions/tests/test_celery_retry_tasks.py`
- `executions/tests/test_schedule_step_executor.py` (StepExecutor legacy)
- `executions/tests/test_condition_gates.py` (WorkflowRuntime)
- `executions/tests/test_condition_gates_integration.py` (WorkflowRuntime)
- `executions/tests/test_execution_integration_validation.py` (WorkflowRuntime)
- `executions/tests/test_execution_step_audit_context.py` (WorkflowRuntime, StepExecutor)
- `executions/tests/test_exception_handling.py` (WorkflowRuntime)
- `executions/tests/test_websocket_broadcast.py` (StepExecutor — migrer vers chemin cible)
- `executions/tests/test_story_78_8_desactivation_legacy.py` (adapter ou supprimer — plus de fallback a desactiver)

## 2.4 Autres references a nettoyer

- `executions/cancellation_cache.py` — GARDER (utilise par container_workflow_runtime, gates, workflow_commands)
- `tests/KNOWN_ISSUES.md` — retirer mentions workflow_runtime, workflow_step_executor
- `docs/backend/decisions/adr-007-*.md` — mettre a jour references obsoletes

---

## 3) Preconditions de decommission

1. Reset dev valide via seed (`--reset`) et verifications QA de base OK.
2. Aucun workflow/action legacy a conserver.
3. Equipe alignee sur "pas de rollback data old-path".
4. Pipeline CI verte sur le chemin d'orchestration cible.

---

## 4) Plan de decommission (PR par PR)

## PR1 - Freeze legacy et preparation

Objectif: empecher toute nouvelle dependance au legacy.

Actions:

1. Marquer les modules legacy comme "decommission ciblee" dans les docstrings.
2. Ajouter une note explicite dans la doc architecture:
   - aucun nouveau test ne doit importer `workflow_runtime`/`workflow_step_executor`.
3. Ajouter un check de recherche dans CI (simple guard):
   - echec si nouvel import legacy apparait hors fichiers explicitement whitelistes.

Sortie attendue: dette legacy stabilisee (pas d'extension de surface).

## PR2 - Cutover fonctionnel (suppression des appels legacy)

Objectif: aucun flux runtime ne doit appeler `retry_workflow_step` / `WorkflowRuntime`.

Actions minimales:

1. `executions/tasks/gates.py`
   - supprimer la branche `old_style_step_def` dans `_resume_workflow_after_gate()`
   - garder uniquement le chemin orchestration cible
2. `executions/container_workflow_runtime.py`
   - supprimer le bloc legacy fallback (garde `WORKFLOW_LEGACY_RUNTIME_ENABLED`, thread `_run_workflow_loop`)
   - si `initial_wave is None` → marquer FAILED directement (pas de fallback thread)
3. verifier les appels runtime depuis:
   - `executions/views/execution_views.py`
   - `executions/tasks/scheduled.py`
   - `executions/runtime_registry.py`
   (doivent pointer uniquement vers le runtime cible)
4. supprimer les references fonctionnelles restantes au retry legacy.

Sortie attendue: plus aucun chemin de prod/dev standard ne depend de `tasks/retry.py` ni du fallback thread.

## PR3 - Suppression des fichiers legacy et cleanup config

Objectif: enlever le code mort.

Actions:

1. Supprimer les fichiers:
   - `executions/workflow_runtime.py`
   - `executions/workflow_step_executor.py`
   - `executions/workflow_retry.py`
   - `executions/tasks/retry.py`
   - `executions/workflow_types.py`
2. Supprimer le bloc legacy fallback dans `executions/container_workflow_runtime.py`:
   - garde `WORKFLOW_LEGACY_RUNTIME_ENABLED`, thread `_run_workflow_loop` — supprimer entierement
   - si `initial_wave is None` → FAILED direct (pas de fallback)
3. Mettre a jour `executions/tasks/__init__.py`: retirer import/re-export `retry_workflow_step`
4. Mettre a jour `idp_backend/settings.py`:
   - retirer route Celery `executions.tasks.retry_workflow_step`
   - retirer time limit `retry_workflow_step`
   - retirer `WORKFLOW_LEGACY_RUNTIME_ENABLED`
5. Supprimer `WorkflowLegacyDisabledError` de `executions/exceptions.py` si plus reference
6. Verifier qu'aucun import legacy ne subsiste (workflow_runtime, workflow_step_executor, workflow_retry, retry_workflow_step, workflow_types).

Sortie attendue: codebase sans modules runtime legacy.

## PR4 - Cleanup tests + docs + observabilite

Objectif: finir la contraction.

Actions:

1. Supprimer ou migrer les tests legacy (14+ fichiers):
   - test_workflow_runtime.py, test_workflow_runtime_retry*.py, test_workflow_retry.py
   - test_workflow_step_executor.py, test_celery_retry_tasks.py, test_schedule_step_executor.py
   - test_condition_gates.py, test_condition_gates_integration.py
   - test_execution_integration_validation.py, test_execution_step_audit_context.py
   - test_exception_handling.py, test_websocket_broadcast.py (StepExecutor)
   - test_story_78_8_desactivation_legacy.py
2. Migrer les assertions utiles vers tests du chemin cible (gate handler, gates, container runtime).
3. Conserver et renforcer les tests du chemin cible: orchestration end-to-end, gates/approvals, reconcile/recovery.
4. Nettoyer docs/commentaires: KNOWN_ISSUES.md, ADR-007, CODEBASE-REVIEW.md.
5. Ajuster dashboards/alertes (si metriques legacy encore referencees).

Sortie attendue: test suite coherente avec l'architecture cible uniquement.

---

## 5) Strategie de verification

Apres chaque PR:

1. `pytest` scope executions (puis full suite en CI)
2. scenario manuel minimal:
   - creation execution workflow
   - step gate (attente puis reprise)
   - echec step + comportement recovery
3. verification absence imports legacy:
   - recherche `workflow_runtime`, `workflow_step_executor`, `workflow_retry`, `retry_workflow_step`, `workflow_types`

---

## 6) Risques et mitigations

1. **Risque**: suppression trop rapide de tests utiles  
   **Mitigation**: migrer d'abord les assertions importantes vers tests du chemin cible.

2. **Risque**: reference legacy oubliee (import indirect)  
   **Mitigation**: garde CI + recherche systematique avant merge.

3. **Risque**: regression sur reprise apres gate/reconcile  
   **Mitigation**: scenarios de non-regression dedies dans PR2 et PR4.

---

## 7) Definition of done

- aucun fichier runtime/retry/workflow_types legacy present dans `executions/`
- aucune route/time-limit Celery pour `retry_workflow_step`
- aucun fallback legacy dans `container_workflow_runtime.py`
- `WORKFLOW_LEGACY_RUNTIME_ENABLED` et `WorkflowLegacyDisabledError` supprimes
- aucun import legacy restant dans le backend
- tests aligns sur le runtime cible uniquement
- reset + seed dev toujours fonctionnels

---

## 8) Lien avec le document reset

Ce document complete:

- `docs/architecture/dev-reset-workflows-actions-via-seed.md`

Le reset de donnees simplifie la migration, mais ne remplace pas la suppression du code legacy.
