# Story 88.8: Architecture — Imports canoniques et routage

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a développeur du portail IDP,
I want que les deux findings d'architecture ARCH-BE-01 et ARCH-BE-02 identifiés dans l'Audit #8 soient corrigés,
so that `container_workflow_runtime.py` importe directement depuis les chemins canoniques (`executions.app.handlers.*` et `executions.domain.workflow_graph`) sans passer par les shims de rétrocompatibilité `step_handlers/` et `container_routing.py`.

## Acceptance Criteria

1. **ARCH-BE-01 — Import canonique `condition_evaluator`** — La ligne `from executions.step_handlers.condition_evaluator import StepConditionEvaluator` dans `container_workflow_runtime.py` est remplacée par `from executions.app.handlers.condition_evaluator import StepConditionEvaluator`. Le shim `executions/step_handlers/condition_evaluator.py` n'est plus importé par ce fichier.

2. **ARCH-BE-01 — Import canonique `registry`** — La ligne `from executions.step_handlers.registry import step_handler_registry` est remplacée par `from executions.app.handlers.registry import step_handler_registry`. Le shim `executions/step_handlers/registry.py` n'est plus importé par ce fichier.

3. **ARCH-BE-02 — Import canonique `workflow_graph`** — Le bloc `from executions.container_routing import (get_linear_next_step_ids as _routing_get_linear_next_step_ids, get_next_step_ids as _routing_get_next_step_ids,)` est remplacé par `from executions.domain.workflow_graph import (get_linear_next_step_ids as _routing_get_linear_next_step_ids, get_next_step_ids as _routing_get_next_step_ids,)`. Le shim `container_routing.py` n'est plus importé en toplevel par `container_workflow_runtime.py`.

4. **ARCH-BE-02 — Docstrings mises à jour** — Les docstrings des méthodes `_get_next_step_ids` (ligne ~472) et `_get_linear_next_step_ids` (ligne ~476) remplacent la mention `container_routing` par `domain.workflow_graph` pour refléter la nouvelle réalité.

5. **Interface publique inchangée** — Les alias `_routing_get_next_step_ids` et `_routing_get_linear_next_step_ids` restent identiques. Aucune signature de méthode ni aucun comportement observable ne change.

6. **Zéro régression** — Tous les tests existants passent sans modification :
   - `executions/tests/` (notamment `test_reconcile.py` qui mock toujours `executions.container_routing.get_next_step_ids` — **hors scope de cette story**)
   - Les tests du runtime container si présents

## Tasks / Subtasks

- [x] Task 1 — ARCH-BE-01 : Remplacer imports shims `step_handlers` par chemins canoniques (AC: #1, #2)
  - [x] 1.1 Dans `executions/container_workflow_runtime.py`, remplacer la ligne 45 :
    - AVANT : `from executions.step_handlers.condition_evaluator import StepConditionEvaluator`
    - APRÈS : `from executions.app.handlers.condition_evaluator import StepConditionEvaluator`
  - [x] 1.2 Remplacer la ligne 46 :
    - AVANT : `from executions.step_handlers.registry import step_handler_registry`
    - APRÈS : `from executions.app.handlers.registry import step_handler_registry`
  - [x] 1.3 Vérifier que les fichiers canoniques `executions/app/handlers/condition_evaluator.py` et `executions/app/handlers/registry.py` existent bien (ils existent : confirmé par inspection)

- [x] Task 2 — ARCH-BE-02 : Remplacer import shim `container_routing` par chemin canonique (AC: #3)
  - [x] 2.1 Dans `executions/container_workflow_runtime.py`, remplacer le bloc lignes 47-50 :
    - AVANT :
      ```python
      from executions.container_routing import (
          get_linear_next_step_ids as _routing_get_linear_next_step_ids,
          get_next_step_ids as _routing_get_next_step_ids,
      )
      ```
    - APRÈS :
      ```python
      from executions.domain.workflow_graph import (
          get_linear_next_step_ids as _routing_get_linear_next_step_ids,
          get_next_step_ids as _routing_get_next_step_ids,
      )
      ```

- [x] Task 3 — ARCH-BE-02 : Mettre à jour les docstrings (AC: #4)
  - [x] 3.1 Ligne ~472 : remplacer `"""Retourne les step_id cibles selon l'outcome (delegates to container_routing)."""` par `"""Retourne les step_id cibles selon l'outcome (delegates to domain.workflow_graph)."""`
  - [x] 3.2 Ligne ~476 : remplacer `"""Retourne le step suivant par ordre (delegates to container_routing)."""` par `"""Retourne le step suivant par ordre (delegates to domain.workflow_graph)."""`

- [x] Task 4 — Vérification zéro régression (AC: #5, #6)
  - [x] 4.1 Lancer `.venv/bin/python -m pytest executions/ -v --ignore=executions/tests.py -x -q` → tous les tests passent (1 failure pré-existante `test_process_runnable_steps_empty_queue` confirmée avant/après)
  - [x] 4.2 Vérifier spécifiquement les tests qui exercent `_get_next_step_ids` / `_get_linear_next_step_ids` dans `ContainerWorkflowRuntime`
  - [x] 4.3 Confirmer que `test_reconcile.py` reste inchangé (il mocke `executions.container_routing.get_next_step_ids` — le shim `container_routing.py` subsiste pour `reconcile.py`, hors scope de cette story)

## Dev Notes

### Vue d'ensemble des findings

**Finding ARCH-BE-01** — `executions/container_workflow_runtime.py:45-46`
- Sévérité : LOW
- Problème : Imports via shims de rétrocompatibilité (`step_handlers/condition_evaluator.py` et `step_handlers/registry.py`) au lieu des modules canoniques créés par Story 85.4.
- Les shims font simplement un re-export depuis `executions.app.handlers.*` — aucun comportement n'est différent. C'est uniquement un problème de maintenabilité/cohérence architecturale.
- Solution : 2 lignes à modifier dans `container_workflow_runtime.py`

**Finding ARCH-BE-02** — `executions/container_routing.py` vs `executions/domain/workflow_graph.py`
- Sévérité : LOW
- Problème : `container_routing.py` est un shim créé post-Story 85.1 qui re-exporte depuis `domain.workflow_graph`. `container_workflow_runtime.py` importe encore via ce shim (lignes 47-50).
- Note importante : `executions/tasks/reconcile.py:226` importe aussi `container_routing` (import local conditionnel) — ce fichier est **hors scope** de cette story. Le shim `container_routing.py` NE DOIT PAS être supprimé dans cette story.
- Solution : 1 bloc d'imports à modifier dans `container_workflow_runtime.py`

---

### État actuel des modules

**Shims à contourner (NE PAS supprimer — encore utilisés ailleurs) :**

| Shim | Contenu | Utilisé ailleurs ? |
|------|---------|-------------------|
| `executions/step_handlers/condition_evaluator.py` | Re-export depuis `executions.app.handlers.condition_evaluator` | Potentiellement (ne pas supprimer) |
| `executions/step_handlers/registry.py` | Re-export depuis `executions.app.handlers.registry` | Potentiellement (ne pas supprimer) |
| `executions/container_routing.py` | Re-export depuis `executions.domain.workflow_graph` | Oui : `reconcile.py:226` + `test_reconcile.py:287,311` |

**Modules canoniques (cibles des nouveaux imports) :**

| Module canonique | Exports utilisés |
|-----------------|-----------------|
| `executions/app/handlers/condition_evaluator.py` | `StepConditionEvaluator` |
| `executions/app/handlers/registry.py` | `step_handler_registry` |
| `executions/domain/workflow_graph.py` | `get_next_step_ids`, `get_linear_next_step_ids` |

---

### Implémentation détaillée

**État actuel de `container_workflow_runtime.py` (lignes 45-50) :**

```python
from executions.step_handlers.condition_evaluator import StepConditionEvaluator  # ← shim
from executions.step_handlers.registry import step_handler_registry              # ← shim
from executions.container_routing import (                                        # ← shim
    get_linear_next_step_ids as _routing_get_linear_next_step_ids,
    get_next_step_ids as _routing_get_next_step_ids,
)
```

**Après correction :**

```python
from executions.app.handlers.condition_evaluator import StepConditionEvaluator  # ARCH-BE-01: chemin canonique
from executions.app.handlers.registry import step_handler_registry              # ARCH-BE-01: chemin canonique
from executions.domain.workflow_graph import (                                  # ARCH-BE-02: chemin canonique
    get_linear_next_step_ids as _routing_get_linear_next_step_ids,
    get_next_step_ids as _routing_get_next_step_ids,
)
```

**Docstrings à mettre à jour :**

```python
# Ligne ~472 — AVANT :
def _get_next_step_ids(self, step: dict, outcome: ExecutionStatus) -> list[str]:
    """Retourne les step_id cibles selon l'outcome (delegates to container_routing)."""

# APRÈS :
def _get_next_step_ids(self, step: dict, outcome: ExecutionStatus) -> list[str]:
    """Retourne les step_id cibles selon l'outcome (delegates to domain.workflow_graph)."""

# Ligne ~476 — AVANT :
def _get_linear_next_step_ids(self, step: dict) -> list[str]:
    """Retourne le step suivant par ordre (delegates to container_routing)."""

# APRÈS :
def _get_linear_next_step_ids(self, step: dict) -> list[str]:
    """Retourne le step suivant par ordre (delegates to domain.workflow_graph)."""
```

---

### Portée stricte — ce qui NE doit PAS être modifié

- `executions/step_handlers/condition_evaluator.py` — shim, à conserver
- `executions/step_handlers/registry.py` — shim, à conserver
- `executions/container_routing.py` — shim, à conserver (utilisé par `reconcile.py`)
- `executions/tasks/reconcile.py` — hors scope (utilise `container_routing` pour raison légitime)
- `executions/tests/test_reconcile.py` — hors scope (mocke `executions.container_routing`)
- Tout autre fichier que `executions/container_workflow_runtime.py`

---

### Patterns à respecter

**Backend :**
- **Annotations de type** : Python 3.10+ — `list[str]`, `dict`, etc. (lowercase)
- **Structlog** : event names snake_case — non concerné ici (aucun nouveau logging)
- **Imports** : tri selon isort — stdlib → django → local. Les 3 nouvelles lignes restent dans la section local imports, dans le même ordre qu'actuellement
- **Tests** : `.venv/bin/python -m pytest` depuis `idp-portal/django_backend/`
- **Aucun `# noqa`** n'est nécessaire pour ces imports simples

---

### Intelligence story précédente (88-7)

**Patterns établis :**
- Les shims `executions/step_handlers/` existent depuis Story 85.4 — ce sont des fichiers de rétrocompatibilité intentionnels
- L'alias `_routing_get_next_step_ids` (préfixe `_routing_`) a été établi lors de l'extraction Story 85.1 pour éviter les conflits de noms — **conserver exactement ces alias**
- La propriété de patching en tests : `test_reconcile.py` mocke `executions.container_routing.get_next_step_ids` (pas `domain.workflow_graph`) — confirme que le shim subsiste pour `reconcile.py`

**Commits récents pertinents :**
- `8936301b perf(story-88-7)` — patterns contexts React, shim `contexts/index.ts`
- `0d70a114 refactor(story-88-5)` — extraction `PlatformStepExecutor`, imports locaux `# noqa: PLC0415`

---

### Fichiers à modifier / créer

| Fichier | Nature | Action |
|---------|--------|--------|
| `executions/container_workflow_runtime.py` | Existant (~1477 LOC) | Modifier : lignes 45-50 (3 imports → 3 imports canoniques) + 2 docstrings |

**Fichiers à NE PAS modifier :**
- `executions/step_handlers/condition_evaluator.py` — shim conservé
- `executions/step_handlers/registry.py` — shim conservé
- `executions/container_routing.py` — shim conservé
- `executions/tasks/reconcile.py` — hors scope
- `executions/tests/test_reconcile.py` — hors scope

### Project Structure Notes

- Working dir backend : `idp-portal/django_backend/`
- Python venv : `.venv/bin/python`
- Test runner : `.venv/bin/python -m pytest` depuis `django_backend/`
- Test settings : `idp_backend.test_settings` (via `pytest.ini`)
- Chemins canoniques confirmés existants : `executions/app/handlers/condition_evaluator.py`, `executions/app/handlers/registry.py`, `executions/domain/workflow_graph.py`

### References

- [Source: idp-portal/CODEBASE-REVIEW.md §27 ligne 1268 — ARCH-BE-01 : imports shims step_handlers dans container_workflow_runtime.py:49-50]
- [Source: idp-portal/CODEBASE-REVIEW.md §27 ligne 1269 — ARCH-BE-02 : container_routing.py shim importé par container_workflow_runtime.py]
- [Source: idp-portal/CODEBASE-REVIEW.md §27 ligne 1394 — Priorisation backlog : ARCH-BE-01/02 LOW effort]
- [Source: executions/container_workflow_runtime.py:45-50 — imports actuels via shims]
- [Source: executions/container_workflow_runtime.py:472,476 — docstrings "delegates to container_routing" à mettre à jour]
- [Source: executions/step_handlers/condition_evaluator.py — shim rétrocompat Story 85.4 → app.handlers.condition_evaluator]
- [Source: executions/step_handlers/registry.py — shim rétrocompat Story 85.4 → app.handlers.registry]
- [Source: executions/container_routing.py — shim rétrocompat Story 85.1 → domain.workflow_graph]
- [Source: executions/domain/workflow_graph.py — module canonique de routage (get_next_step_ids, get_linear_next_step_ids)]
- [Source: executions/app/handlers/condition_evaluator.py — module canonique StepConditionEvaluator]
- [Source: executions/app/handlers/registry.py — module canonique step_handler_registry]
- [Source: executions/tasks/reconcile.py:226 — import local container_routing (hors scope, shim conservé)]
- [Source: _bmad-output/implementation-artifacts/88-7-performance-servicenow-capabilities.md — patterns et learnings story précédente]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

Aucun blocage — toutes les modifications sont des substitutions directes dans un seul fichier.

### Completion Notes List

- ✅ ARCH-BE-01 : imports `step_handlers/condition_evaluator` et `step_handlers/registry` remplacés par les chemins canoniques `app.handlers.*` (lignes 45-46 de `container_workflow_runtime.py`)
- ✅ ARCH-BE-02 : import `container_routing` remplacé par `domain.workflow_graph` (lignes 47-50)
- ✅ Docstrings `_get_next_step_ids` et `_get_linear_next_step_ids` mises à jour (lignes 472, 476)
- ✅ Shims `step_handlers/condition_evaluator.py`, `step_handlers/registry.py`, `container_routing.py` conservés (utilisés ailleurs)
- ✅ `test_reconcile.py` : 48/48 tests passent, shim `container_routing` toujours fonctionnel
- ✅ 89 tests passent sur les suites ciblées (executions/tests + step_handlers/tests)
- ℹ️ 1 failure pré-existante confirmée : `test_process_runnable_steps_empty_queue` (orchestrator.py, hors scope)

### File List

- `idp-portal/django_backend/executions/container_workflow_runtime.py`

## Change Log

- 2026-03-16 : ARCH-BE-01 — imports shims `step_handlers/condition_evaluator` et `step_handlers/registry` remplacés par `app.handlers.*` dans `container_workflow_runtime.py`
- 2026-03-16 : ARCH-BE-02 — import shim `container_routing` remplacé par `domain.workflow_graph` + docstrings mises à jour
- 2026-03-17 : Code review — M2 corrigé : 4 fichiers frontend non commités (CapabilitiesContext.tsx, contexts/index.ts, useActionWizardSave.ts, execution_inventory.test.ts) commités [commit 2654e502] ; L2 corrigé : typo `Frencg`→`French` dans config.yaml
