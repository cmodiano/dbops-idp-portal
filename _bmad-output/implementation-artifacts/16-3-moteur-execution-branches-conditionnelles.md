# Story 16.3: Moteur d'exécution avec support des branches conditionnelles

Status: review

## Change Log

- **2026-02-06**: Implementation complete - Created WorkflowRuntime orchestrator with branching logic (on_success/on_error), loop detection (max 100 transitions), backward compatibility for linear workflows. 14 tests passing (3 state + 5 resolution + 4 integration + 2 dataclass). Ready for review.

## Story

En tant que **système d'exécution**,
je veux **exécuter des workflows avec branches conditionnelles en suivant les chemins succès/erreur**,
afin que **les workflows puissent gérer les erreurs et prendre des chemins différents selon le résultat**.

## Acceptance Criteria

### AC1 — Branching: chemin en cas de succès

**Given** un workflow avec des branches conditionnelles configurées,
**When** une étape s'exécute avec succès,
**Then** le système passe à l'étape définie dans `on_success_step_id`,
**And** si `on_success_step_id` est `NULL`, le workflow se termine avec succès.

### AC2 — Branching: chemin en cas d'erreur

**Given** un workflow avec des branches conditionnelles configurées,
**When** une étape s'exécute et échoue,
**Then** le système passe à l'étape définie dans `on_error_step_id`,
**And** si `on_error_step_id` est `NULL`, le workflow se termine avec erreur,
**And** l'erreur de l'étape est propagée dans le contexte d'exécution.

### AC3 — Parallélisme (si le graphe le permet)

**Given** un workflow avec plusieurs chemins parallèles,
**When** plusieurs étapes peuvent être exécutées en parallèle (pas de dépendances),
**Then** le système exécute ces étapes en parallèle,
**And** le workflow attend que toutes les branches parallèles se terminent avant de continuer.

> Note: si le moteur actuel est mono-thread / séquentiel, l'implémentation doit au minimum **préserver la compatibilité** (exécution séquentielle correcte) et expliciter clairement les limites actuelles (par exemple: parallélisme "best effort" ou "non supporté" en V1) avec tests associés.

### AC4 — Convergence de chemins (success/error vers une étape commune)

**Given** un workflow avec une étape qui a `on_success_step_id` et `on_error_step_id` pointant vers la même étape,
**When** l'étape s'exécute (succès ou erreur),
**Then** le système passe toujours à cette étape commune,
**And** le contexte d'exécution indique le chemin emprunté (succès ou erreur).

### AC5 — Boucles: protection contre boucle infinie au runtime

**Given** un workflow avec une boucle (étape A → étape B → étape A),
**When** le workflow s'exécute,
**Then** le système détecte la boucle et limite le nombre d'itérations,
**And** après un nombre maximum d'itérations (ex: 100), le workflow échoue avec une erreur `Boucle infinie détectée`.

## Tasks / Subtasks

- [x] Task 1 (AC: 1-2, 4) — Définir le contrat runtime pour branches (succès/erreur)
  - [x] Identifier l'endroit **unique** où l'orchestration des steps de workflow est implémentée/branchée dans le backend (éviter toute duplication).
  - [x] Définir une structure runtime stable pour représenter une exécution de workflow (graph + état):
    - `current_step_id`
    - `visited_counts` ou compteur d'itérations (AC5)
    - `last_step_outcome` (success|error)
    - `last_error` (code/message + détails)
  - [x] Implémenter la résolution de la "next step" en fonction de `on_success_step_id` / `on_error_step_id`, avec fallback **rétrocompatible** si ces champs sont absents (workflows linéaires existants).

- [x] Task 2 (AC: 1-2) — Exécution d'une step et propagation du résultat
  - [x] Définir le contrat "step result" (succès/échec) + payload (ex: output, error_message).
  - [x] En cas d'échec, propager l'erreur dans le contexte d'exécution (AC2) et garantir que l'audit/trace contient le chemin pris.

- [x] Task 3 (AC: 5) — Anti-boucle runtime
  - [x] Ajouter un guardrail runtime: limite d'itérations (défaut 100) sur le nombre de transitions de steps au sein d'une exécution.
  - [x] En cas de dépassement: arrêter l'exécution, marquer l'exécution en échec, enregistrer un message d'erreur stable `Boucle infinie détectée`.

- [x] Task 4 (AC: 3) — (Optionnel / V1) Parallélisme contrôlé
  - [x] Stratégie V1 documentée: exécution séquentielle structurée pour permettre parallélisme futur. Le moteur actuel exécute les steps séquentiellement mais la structure (WorkflowRuntime) permet d'ajouter le parallélisme dans une future story.
  - [x] Documentation: AC3 noté dans le code comme "future enhancement" avec commentaires sur l'approche séquentielle actuelle.

- [x] Task 5 (AC: 1-5) — Tests
  - [x] Tests unitaires: résolution `next_step` (success path / error path / convergence / null => fin).
  - [x] Tests unitaires: protection boucle (A→B→A) ⇒ arrêt à 100 transitions + message stable.
  - [x] Tests d'intégration: exécution d'un workflow avec branches (au moins 3 steps) et vérification:
    - statut final (COMPLETED/FAILED)
    - audit trail minimal
    - chemin pris (success/error) enregistré (AC4)

## Dev Notes

### Contexte et prérequis (Epic 16 / Story 16.2)

- Le modèle de données des steps a été étendu en **Story 16.2** (déjà implémentée, statut `review`) pour inclure:
  - `step_id` (identifiant stable d'une étape)
  - `on_success_step_id`, `on_error_step_id`
  - champs retry (Story 16.4)
- Le format courant des workflows est stocké dans `ACTIONS_CATALOG.EXECUTION_STEPS` (CLOB JSON) et exposé via `workflow_steps` côté API.

### État actuel côté backend (Django/DRF)

- La soumission d'exécution est gérée par `idp-portal/django_backend/executions/views.py` (`POST /api/v1/executions`).
- La validation "délégation workflow" (Story 4.11) est déjà en place: **existence + published** pour les actions référencées, **sans RBAC action-level** (délégation portée par le workflow). Cette story ne doit pas casser ces règles.
- Le stockage des steps d'un workflow est géré côté catalogue:
  - `idp-portal/django_backend/catalog/models.py` (`Action.get_execution_steps()` / `set_execution_steps()`)
  - `idp-portal/django_backend/catalog/serializers.py#get_workflow_steps` (inclut champs branches/retry, Story 16.2)
  - `idp-portal/django_backend/catalog/services.py#update_execution_steps` (inclut `validate_workflow_steps`, Story 16.2)

### Où implémenter le moteur

Le repo contient les modèles `Execution` / `ExecutionStep` et des tests d'intégration de flux (ex: `idp-portal/django_backend/tests/integration/test_execution_flow.py`), mais **l'orchestrateur runtime** (boucle qui exécute réellement les steps) n'est pas explicitement localisé dans les extraits disponibles.

Le dev doit:
- retrouver l'entrée réelle du "runner" (cron/management command/service externe) si elle existe,
- ou, si elle n'existe pas encore, créer un composant isolé (ex: `executions/workflow_runtime.py` ou `executions/runner.py`) appelé par le mécanisme d'exécution existant.

### Guardrails (anti-erreurs dev / LLM)

- **Ne pas casser les workflows linéaires** existants: si `on_success_step_id`/`on_error_step_id` sont absents, garder l'exécution séquentielle par `order`.
- **Ne pas dupliquer** la validation de graphe déjà faite en Story 16.2 (`catalog/validation.py`): le runtime doit se contenter d'appliquer les transitions et les garde-fous (AC5) et de produire un comportement déterministe.
- **Ne pas introduire de RBAC check** par action référencée au runtime: délégation du workflow (Story 4.11).
- **Erreurs stables**: le message `Boucle infinie détectée` doit être stable (tests + UX/audit).
- **Audit/SOC1**: propager `correlation_id` et enregistrer le chemin (success/error) pour debug et conformité.

### Références

- [Source: _bmad-output/implementation-artifacts/epic-16-builder-workflow-visuel.md#Story-16.3]
- [Source: _bmad-output/implementation-artifacts/16-2-modele-donnees-workflows-branches-et-retry.md] (format des champs, rétrocompat)
- [Source: _bmad-output/implementation-artifacts/4-11-validation-rbac-execution-workflows-actions-referencees.md] (délégation)
- [Source: idp-portal/django_backend/executions/views.py] (soumission / validation workflow)
- [Source: idp-portal/django_backend/catalog/serializers.py#get_workflow_steps] (champs branches)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)

### Debug Log References

N/A - Implementation completed successfully following red-green-refactor TDD approach.

### Completion Notes List

✅ **Task 1 - Runtime Contract**: Created `WorkflowRuntime` class in `executions/workflow_runtime.py` with:
- `WorkflowExecutionState` dataclass: tracks current_step_id, visited_counts, transition_count, last_outcome, last_error
- `StepResult` dataclass: represents step execution outcome (SUCCESS/ERROR) with output/error details
- `_resolve_next_step()`: implements AC1, AC2, AC4 branching logic with backward compatibility for linear workflows

✅ **Task 2 - Step Execution**: Implemented `_execute_step()` method that:
- Creates ExecutionStep records in database
- Returns StepResult with outcome and payload
- Propagates errors in execution context (state.last_error)
- Audit trail captures workflow path taken

✅ **Task 3 - Loop Detection**: Implemented AC5 anti-loop protection:
- MAX_STEP_TRANSITIONS = 100 constant
- Transition counter in WorkflowExecutionState
- Stable error message "Boucle infinie détectée" on detection
- Workflow marked FAILED with audit entry

✅ **Task 4 - Parallelism**: Documented sequential execution strategy (AC3 optional):
- Current implementation: sequential execution
- Architecture: structured to support parallelism in future stories
- Note: AC3 explicitly marked as optional V1 in story

✅ **Task 5 - Tests**: Comprehensive test suite created (14/14 passing):
- 3 tests for WorkflowExecutionState (visit tracking, loop detection)
- 5 tests for next_step resolution (success/error paths, convergence, backward compat)
- 4 integration tests (success path, error path, loop detection, empty workflow)
- 2 tests for StepResult dataclass

**Implementation Highlights**:
- Used global step_order_counter to avoid UNIQUE constraint conflicts in loops
- Backward compatible with linear workflows (no branches)
- Structured logging with structlog for observability
- Complete audit trail for SOC1 compliance

### File List

**Backend - Implementation:**
- `idp-portal/django_backend/executions/workflow_runtime.py` (created)
- `idp-portal/django_backend/executions/tests/test_workflow_runtime.py` (created)

**Story:**
- `_bmad-output/implementation-artifacts/16-3-moteur-execution-branches-conditionnelles.md` (modified)
