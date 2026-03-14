# Epic 81 : Decommission de l'ancien code path workflow (dev-only)

**Date :** 2026-03-14  
**Statut :** Draft  
**Réf :** docs/architecture/dev-decommission-legacy-workflow-code-path.md  
**Périmètre :** `executions/`, `idp_backend/settings.py`, CI

---

## 1. Objectif

Suppression totale du legacy — plateforme non utilisée, rien à conserver.

- retirer les chemins "legacy runtime + retry legacy"
- conserver un seul chemin d'orchestration (ContainerWorkflowRuntime + queue)
- supprimer workflow_types, fallback thread-based, feature flags legacy
- simplifier le code, la config Celery et les tests

**Préconditions :** Epic 80 (reset) terminé ; pipeline CI verte sur le chemin cible.

---

## 2. Scope legacy à décommissionner (exhaustif)

**Modules à supprimer :** `workflow_runtime.py`, `workflow_step_executor.py`, `workflow_retry.py`, `tasks/retry.py`, `workflow_types.py`

**Code à retirer :** bloc legacy fallback dans `container_workflow_runtime.py` (thread `_run_workflow_loop`, garde `WORKFLOW_LEGACY_RUNTIME_ENABLED`)

**Config à retirer :** `WORKFLOW_LEGACY_RUNTIME_ENABLED`, route/time-limit Celery `retry_workflow_step`, `WorkflowLegacyDisabledError`

**Tests à supprimer ou migrer :** test_workflow_runtime*, test_workflow_retry*, test_celery_retry_tasks, test_schedule_step_executor, test_condition_gates*, test_execution_integration_validation, test_execution_step_audit_context, test_exception_handling, test_websocket_broadcast (StepExecutor), test_story_78_8_desactivation_legacy

---

## 3. Stories (alignées PR1–PR4)

### Story 81.1 — Freeze legacy et préparation (PR1)

**Priorité :** Haute  
**Effort estimé :** M

**Description :**  
Empêcher toute nouvelle dépendance au legacy.

**Acceptance criteria :**
- AC1 : Modules legacy marqués "decommission ciblee" dans les docstrings.
- AC2 : Note explicite dans la doc architecture : aucun nouveau test ne doit importer `workflow_runtime`/`workflow_step_executor`.
- AC3 : Check CI : échec si nouvel import legacy hors fichiers whitelistés.
- AC4 : Dette legacy stabilisée (pas d'extension de surface).

---

### Story 81.2 — Cutover fonctionnel — suppression des appels legacy (PR2)

**Priorité :** Haute  
**Effort estimé :** L

**Description :**  
Aucun flux runtime ne doit appeler `retry_workflow_step` / `WorkflowRuntime`. Supprimer le fallback legacy dans container_workflow_runtime.

**Acceptance criteria :**
- AC1 : `executions/tasks/gates.py` : branche `old_style_step_def` supprimée dans `_resume_workflow_after_gate()`.
- AC2 : `executions/container_workflow_runtime.py` : bloc legacy fallback supprimé (garde `WORKFLOW_LEGACY_RUNTIME_ENABLED`, thread `_run_workflow_loop`). Si `initial_wave is None` → FAILED direct.
- AC3 : Appels runtime depuis `execution_views.py`, `scheduled.py`, `runtime_registry.py` pointent uniquement vers le runtime cible.
- AC4 : Plus aucune référence fonctionnelle au retry legacy.
- AC5 : `pytest` scope executions + scénario manuel (workflow, gate, recovery) OK.

---

### Story 81.3 — Suppression des fichiers legacy et cleanup config (PR3)

**Priorité :** Haute  
**Effort estimé :** M

**Description :**  
Supprimer le code mort et les configs associées.

**Acceptance criteria :**
- AC1 : Fichiers supprimés : `workflow_runtime.py`, `workflow_step_executor.py`, `workflow_retry.py`, `tasks/retry.py`, `workflow_types.py`.
- AC2 : `executions/tasks/__init__.py` : retrait import/re-export `retry_workflow_step`.
- AC3 : `idp_backend/settings.py` : retrait route Celery + time limit `retry_workflow_step` + `WORKFLOW_LEGACY_RUNTIME_ENABLED`.
- AC4 : `executions/exceptions.py` : retrait `WorkflowLegacyDisabledError` si plus référencé.
- AC5 : `idp_backend/test_settings.py` : retrait `WORKFLOW_LEGACY_RUNTIME_ENABLED`.
- AC6 : Aucun import legacy restant (workflow_runtime, workflow_step_executor, workflow_retry, retry_workflow_step, workflow_types).

---

### Story 81.4 — Cleanup tests, docs et observabilité (PR4)

**Priorité :** Haute  
**Effort estimé :** L

**Description :**  
Finir la contraction de la surface legacy.

**Acceptance criteria :**
- AC1 : Tests legacy supprimés ou migrés : test_workflow_runtime*, test_workflow_retry*, test_celery_retry_tasks, test_schedule_step_executor, test_condition_gates*, test_execution_integration_validation, test_execution_step_audit_context, test_exception_handling, test_websocket_broadcast (StepExecutor), test_story_78_8_desactivation_legacy
- AC2 : Assertions importantes migrées vers tests du chemin cible (gate handler, gates, container runtime).
- AC3 : Tests du chemin cible renforcés : orchestration end-to-end, gates/approvals, reconcile/recovery.
- AC4 : Docs/commentaires mentionnant le retry legacy nettoyés (KNOWN_ISSUES.md, ADR-007, etc.).
- AC5 : Dashboards/alertes ajustés si métriques legacy encore référencées.
- AC6 : Reset + seed dev toujours fonctionnels.

---

## 4. Definition of done (Epic)

- aucun fichier runtime/retry/workflow_types legacy présent dans `executions/`
- aucune route/time-limit Celery pour `retry_workflow_step`
- aucun fallback legacy dans `container_workflow_runtime.py`
- `WORKFLOW_LEGACY_RUNTIME_ENABLED` et `WorkflowLegacyDisabledError` supprimés
- aucun import legacy restant dans le backend (workflow_runtime, workflow_step_executor, workflow_retry, retry_workflow_step, workflow_types)
- tests alignés sur le runtime cible uniquement
- reset + seed dev toujours fonctionnels
