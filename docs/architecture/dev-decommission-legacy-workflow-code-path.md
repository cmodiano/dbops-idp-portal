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

## 2.1 Modules legacy cibles

- `idp-portal/django_backend/executions/workflow_runtime.py`
- `idp-portal/django_backend/executions/workflow_step_executor.py`
- `idp-portal/django_backend/executions/workflow_retry.py`
- `idp-portal/django_backend/executions/tasks/retry.py`

## 2.2 Points d'entree / references a nettoyer

- `idp-portal/django_backend/executions/tasks/__init__.py` (`retry_workflow_step` re-export)
- `idp-portal/django_backend/executions/tasks/gates.py` (fallback old-style vers `retry_workflow_step`)
- `idp-portal/django_backend/idp_backend/settings.py`
  - `CELERY_TASK_ROUTES['executions.tasks.retry_workflow_step']`
  - `CELERY_TASK_TIME_LIMITS['retry_workflow_step']`

## 2.3 Surface de tests legacy

Tests explicitement centres sur legacy runtime/retry:

- `executions/tests/test_workflow_runtime.py`
- `executions/tests/test_workflow_runtime_retry.py`
- `executions/tests/test_workflow_runtime_retry_integration.py`
- `executions/tests/test_workflow_runtime_retry_slow.py`
- `executions/tests/test_workflow_step_executor.py`
- `executions/tests/test_workflow_retry.py`
- `executions/tests/test_celery_retry_tasks.py`
- `executions/tests/test_schedule_step_executor.py` (partiel)

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
2. verifier les appels runtime depuis:
   - `executions/views/execution_views.py`
   - `executions/tasks/scheduled.py`
   - `executions/runtime_registry.py`
   (doivent pointer uniquement vers le runtime cible)
3. supprimer les references fonctionnelles restantes au retry legacy.

Sortie attendue: plus aucun chemin de prod/dev standard ne depend de `tasks/retry.py`.

## PR3 - Suppression des fichiers legacy et cleanup config

Objectif: enlever le code mort.

Actions:

1. Supprimer les fichiers:
   - `executions/workflow_runtime.py`
   - `executions/workflow_step_executor.py`
   - `executions/workflow_retry.py`
   - `executions/tasks/retry.py`
2. Mettre a jour `executions/tasks/__init__.py`:
   - retirer import/re-export de `retry_workflow_step`
3. Mettre a jour `idp_backend/settings.py`:
   - retirer route Celery `executions.tasks.retry_workflow_step`
   - retirer time limit `retry_workflow_step`
4. Verifier qu'aucun import legacy ne subsiste.

Sortie attendue: codebase sans modules runtime legacy.

## PR4 - Cleanup tests + docs + observabilite

Objectif: finir la contraction.

Actions:

1. Supprimer/reecrire les tests legacy.
2. Conserver et renforcer les tests du chemin cible:
   - orchestration end-to-end
   - gates/approvals
   - reconcile/recovery
3. Nettoyer docs/commentaires mentionnant le retry legacy.
4. Ajuster dashboards/alertes (si metriques legacy encore referencees).

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
   - recherche `workflow_runtime`, `workflow_step_executor`, `retry_workflow_step`

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

- aucun fichier runtime/retry legacy present dans `executions/`
- aucune route/time-limit Celery pour `retry_workflow_step`
- aucun import legacy restant dans le backend
- tests aligns sur le runtime cible uniquement
- reset + seed dev toujours fonctionnels

---

## 8) Lien avec le document reset

Ce document complete:

- `docs/architecture/dev-reset-workflows-actions-via-seed.md`

Le reset de donnees simplifie la migration, mais ne remplace pas la suppression du code legacy.
