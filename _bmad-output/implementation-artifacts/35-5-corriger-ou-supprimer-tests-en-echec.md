# Story 35.5 : Corriger ou supprimer les tests en échec

Status: done
<!-- Code review 2026-02-23: 1 HIGH + 2 MEDIUM + 2 LOW issues auto-corrigés (File List factories.py, KNOWN_ISSUES.md 3e skip, catégorisation views/__init__.py, Completion Notes) -->

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur,
je veux que tous les tests (backend + frontend) soient au vert en CI,
afin d'assurer la qualité du code et détecter les régressions dès le commit.

## Acceptance Criteria

1. Tous les tests backend (pytest) exécutés en CI sont verts — zéro échec non justifié.
2. Tous les tests frontend (Vitest) exécutés en CI sont verts — zéro échec non justifié.
3. Pour chaque test modifié : raison explicite (fix suite refactoring Epic 33/34/35 ou setup incorrect).
4. Pour chaque test supprimé : raison explicite dans le commit (redondant, détail d'implémentation obsolète, ou cas métier disparu).
5. Aucune régression fonctionnelle introduite — les tests corrigés couvrent le comportement d'origine.
6. `KNOWN_ISSUES.md` mis à jour pour refléter l'état final (0 échec, skipped justifiés).

## État initial — Diagnostic (23 février 2026)

### Backend : 93 tests en échec (3395 passed, 4 skipped)

| Fichier | Échecs | Cause probable |
|---------|--------|----------------|
| `executions/tests/test_container_workflow_runtime.py` | 21 | Refactoring 34.7 — décomposition `container_workflow_runtime.py` ; imports ou chemins cassés |
| `inventory/tests/test_views_multi_tables.py` | 20 | Refactoring 34.8 — décomposition `inventory/services.py` ; service classes renommées ou déplacées |
| `integrations/tests/test_new_adapter_types_fixtures.py` | 8 | Refactoring 34.5 / 33.1 — registry adapters + BaseAdapter ISP split (34.15) |
| `executions/tests/test_rule_engine.py` | 8 | Refactoring 33.x / 34.x — décomposition exécutions |
| `executions/tests/test_policy_evaluator.py` | 7 | Idem test_rule_engine — imports cassés post-refactoring |
| `inventory/tests/test_integration_multi_tables.py` | 5 | Refactoring 34.8 — services multi-tables |
| `catalog/tests/test_bug_be5_pagination_integration.py` | 5 | Refactoring 34.3 — cache RBAC split services |
| `inventory/tests/test_views.py` | 3 | Refactoring 34.8 ou 26.1 |
| `integrations/tests/test_integration_views.py` | 3 | Refactoring 27.x / 33.1 registry |
| `executions/tests/test_exception_handling.py` | 3 | Refactoring 35.2 — gestion exceptions |
| `inventory/tests/test_environments.py` | 2 | Refactoring 26.7 / 34.8 EnvironmentHelper |
| `executions/tests/test_policy_evaluator_clob.py` | 2 | Idem test_policy_evaluator |
| `core/tests/test_bug_be3_integration_logs.py` | 2 | Refactoring middleware logging (m-8 / 34.x) |
| `tests/security/test_soc1_compliance.py` | 1 | Possiblement secret ou settings modifié |
| `executions/tests/test_views_timezone.py` | 1 | Import `ensure_utc_isoformat` déplacé post-refactoring |
| `catalog/tests/test_rbac_service_di.py` | 1 | Refactoring 26.3 — `CatalogRBACService` DI |
| `catalog/tests/test_action_platform_integration_validation.py` | 1 | Refactoring 31.x — Tower platform type |

### Frontend : état inconnu (lancer `pnpm test --run` pour mesurer)

Le fichier de résultats Vitest `node_modules/.vite/vitest/.../results.json` est supprimé (git status `D`). Lancer une mesure de base avant de commencer.

## Tasks / Subtasks

### Phase 0 — Mesure de base

- [x] **T0.1** — Lancer `pytest --tb=short -q 2>&1 | tee /tmp/test-failures-baseline.txt` et noter le nombre exact d'échecs
- [x] **T0.2** — Lancer `pnpm test --run 2>&1 | tail -30` depuis `idp-portal/frontend/` et noter les échecs frontend
- [x] **T0.3** — Documenter le baseline (fichiers, comptes) avant toute modification

### Phase 1 — Corrections backend (lot par module)

- [x] **T1.1 — `executions/tests/test_container_workflow_runtime.py`** (21 échecs) (AC: 1, 3, 4)
  - [x] Lire les erreurs complètes (`--tb=short`)
  - [x] Identifier si les classes/modules importés ont changé de chemin (refactoring 34.7)
  - [x] Corriger les imports vers les nouveaux modules (ex. `WorkflowRuntimeOrchestrator`, `WorkflowStepExecutor`, etc.)
  - [x] Si un test vérifie un détail d'implémentation interne devenu obsolète : supprimer avec commentaire de commit

- [x] **T1.2 — `inventory/tests/test_views_multi_tables.py`** (20 échecs) (AC: 1, 3, 4)
  - [x] Lire les erreurs — vérifier si `InventoryService` a été découpé en sous-classes (refactoring 34.8)
  - [x] Corriger les patches de mock (`@patch('inventory.services.InventoryService...')`) vers les nouveaux chemins
  - [x] Corriger les imports de fixtures si le service DI a changé

- [x] **T1.3 — `integrations/tests/test_new_adapter_types_fixtures.py`** (8 échecs) (AC: 1, 3, 4)
  - [x] Vérifier l'impact de la suppression de `RefPlatform` (31.9) sur les fixtures
  - [x] Vérifier l'impact du registry OCP (33.1) et du split ISP `BaseAdapter` → `ITriggerableAdapter`/`ICancellableAdapter` (34.15)
  - [x] Corriger les fixtures ou mocks qui utilisent les anciens types

- [x] **T1.4 — `executions/tests/test_rule_engine.py` + `test_policy_evaluator.py` + `test_policy_evaluator_clob.py`** (17 échecs) (AC: 1, 3, 4)
  - [x] Lire les erreurs — vérifier si `RuleEngine` ou `PolicyEvaluator` ont changé de module (refactoring 34.6/34.7)
  - [x] Corriger les chemins d'imports dans les patches et les imports de test
  - [x] Corriger le setup (`setUp`, fixtures) si des dépendances ont changé

- [x] **T1.5 — `inventory/tests/test_integration_multi_tables.py` + `test_views.py` + `test_environments.py`** (10 échecs) (AC: 1, 3, 4)
  - [x] Vérifier l'impact de `EnvironmentHelper` (26.7) — `normalize_environment()` a peut-être changé de signature
  - [x] Corriger les mocks et assertions sur les résultats d'environnement

- [x] **T1.6 — `catalog/tests/test_bug_be5_pagination_integration.py`** (5 échecs) (AC: 1, 3, 4)
  - [x] Vérifier l'impact de `CatalogActionViewSet.get_queryset` cache (30.14) et pagination (26.11)
  - [x] Corriger les assertions sur le format paginé si `standardize_pagination` a changé la clé de réponse

- [x] **T1.7 — `integrations/tests/test_integration_views.py`** (3 échecs) (AC: 1, 3, 4)
  - [x] Vérifier si les types d'intégration ou le registry ont changé (27.x, 33.1)
  - [x] Corriger fixtures et assertions

- [x] **T1.8 — `executions/tests/test_exception_handling.py`** (3 échecs) (AC: 1, 3, 4)
  - [x] Vérifier si les classes d'exception ont changé de chemin (refactoring 35.2 / 22.11)
  - [x] Corriger les imports ou les chemins de patch

- [x] **T1.9 — Tests isolés** (5 échecs au total) (AC: 1, 3, 4)
  - [x] `core/tests/test_bug_be3_integration_logs.py` — vérifier middleware structlog (m-8), corriger setup
  - [x] `tests/security/test_soc1_compliance.py::TestSecretValidation::test_no_hardcoded_secrets_in_settings` — vérifier settings modifiés
  - [x] `executions/tests/test_views_timezone.py::test_catalog_views_imports_ensure_utc_isoformat` — corriger chemin import de `ensure_utc_isoformat`
  - [x] `catalog/tests/test_rbac_service_di.py::test_catalog_rbac_service_get_permissions_uses_injected_profile_service` — vérifier DI `CatalogRBACService` (26.3)
  - [x] `catalog/tests/test_action_platform_integration_validation.py::test_platform_tower_integration_tower_ok` — vérifier type Tower (31.9 suppression `RefPlatform`)

### Phase 2 — Corrections frontend

- [x] **T2.1** — Lancer `pnpm test --run 2>&1 | grep "FAIL\|failed"` et lister les fichiers en échec (AC: 2)
- [x] **T2.2** — Pour chaque fichier en échec : corriger le setup/mock ou supprimer si obsolète (AC: 2, 3, 4)
  - Causes probables : changements de props dans les composants refactorisés (34.9, 34.10, 34.11, 34.12, 34.13, 34.14)
  - Pattern de fix : mettre à jour les mocks de hooks/services selon les nouvelles interfaces

### Phase 3 — Validation finale

- [x] **T3.1** — Lancer la suite complète backend : `pytest --tb=short -q` → doit retourner 0 failed (AC: 1)
- [x] **T3.2** — Lancer la suite complète frontend : `pnpm test --run` → doit retourner 0 failed (AC: 2)
- [x] **T3.3** — Mettre à jour `tests/KNOWN_ISSUES.md` : Total, Passed, Failed=0, Skipped, date (AC: 6)
- [x] **T3.4** — Vérifier que les tests skipped existants restent justifiés (voir section Skipped)

## Dev Notes

### Contexte du refactoring — Causes racines des échecs

Les 93 échecs backend ont été introduits par les refactorings des Epics 33 et 34 :

| Epic/Story | Refactoring | Impact probable |
|-----------|-------------|-----------------|
| 33.1 | OCP registry pattern adapters | Chemins d'import des adapters changés |
| 33.2 | SRP — split `executions/tasks.py` | Imports tâches Celery changés |
| 33.4 | DIP — injection dépendances services | Constructeurs de services changés, DI |
| 34.5 | Poller générique unifié | `GenericPoller` refactorisé — adapters tests |
| 34.6 | Éclater `executions/utils.py` | Fonctions utils déplacées dans sous-modules |
| 34.7 | Décomposer `workflow_runtime.py` | Classes runtime déplacées |
| 34.8 | Décomposer `inventory/services.py` | Services inventaire découpés |
| 34.15 | ISP — `BaseAdapter` → `ITriggerableAdapter` + `ICancellableAdapter` | Interface adapters changée |
| 35.2 | Audit exceptions — corrections ciblées | Chemins gestion exceptions |
| 35.3 | Migration DIP services Phase 1 | Hooks custom, service injection props/context |

### Patterns de fix fréquents

**1. Import déplacé** (le plus fréquent)
```python
# Avant
from executions.services import PolicyEvaluator
# Après (si déplacé dans sous-module)
from executions.policy.evaluator import PolicyEvaluator
```

**2. Patch path cassé**
```python
# Vérifier le chemin exact du symbole à mocker
@patch('executions.services.some_function')  # ancien
@patch('executions.utils.validation.some_function')  # nouveau (si déplacé)
```

**3. Changement de constructeur (DIP)**
```python
# Service avec DI — fournir le mock en paramètre
service = CatalogRBACService(profile_service=mock_profile_service)
```

**4. Fixtures `RefPlatform` supprimées (31.9)**
```python
# RefPlatform supprimé → utiliser IntegrationTypeCatalogue(role='platform')
# Les tests qui créaient RefPlatform doivent utiliser la table catalogue
```

**5. Format réponse API paginée (26.11)**
```python
# Vérifier que les assertions utilisent le bon format standardisé
# {'results': [...], 'count': N, 'next': ..., 'previous': ...}
```

### Règles de décision : corriger vs supprimer

| Situation | Action |
|-----------|--------|
| Test vérifie un comportement métier ou une régression utile | **Corriger** |
| Test vérifie un détail d'implémentation interne (ex. nom d'une méthode privée désormais renommée) | **Supprimer** (noter dans commit) |
| Test duplique exactement un autre test qui passe déjà | **Supprimer** |
| Test ne peut pas fonctionner sans infra externe (Celery, Oracle) | **Skip avec justification** |
| Erreur de setup (trailing slash, UserFactory, profile, etc.) | **Corriger** |

### Règles anti-régression

Voir `tests/KNOWN_ISSUES.md` et `tests/README.md` pour les guidelines établies :
- Toujours utiliser `UserFactory` (jamais `User.objects.create(is_staff=True)`)
- Toujours utiliser `ActionFactory` pour les actions avec champs JSON
- URLs avec trailing slash : `/api/v1/executions/`
- Créer `RefEngine` + `IntegrationTypeCatalogue(role='platform')` avant les tests admin API
- `user.profile = 'dbops'` pour les endpoints admin
- `@override_settings(RATELIMIT_ENABLED=True)` dans les tests de rate limiting

### Project Structure Notes

- Backend Django : `idp-portal/django_backend/`
- Test settings : `idp_backend/test_settings.py` (via `pytest.ini`)
- Runner backend : `.venv/bin/python -m pytest` (depuis `django_backend/`)
- Tests isolés (hors app) : `tests/security/`, `tests/integration/`
- Frontend : `idp-portal/frontend/`
- Runner frontend : `pnpm test --run` (depuis `frontend/`)
- KNOWN_ISSUES.md : `django_backend/tests/KNOWN_ISSUES.md`

### References

- [Source: `_bmad-output/planning-artifacts/epic-35-codebase-review-points-restants-post-refactoring.md`#35.5]
- [Source: `django_backend/tests/KNOWN_ISSUES.md`] — état baseline (2026-02-13 : 0 échec atteint en Story 26.14)
- [Source: stories 33.1–33.5] — refactoring SOLID qui ont pu introduire les régressions
- [Source: stories 34.5–34.15] — décomposition modules backend
- [Source: story 31.9] — suppression `RefPlatform`
- [Source: story 26.11] — standardisation pagination
- [Source: story 26.3] — `CatalogRBACService` DI

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

N/A

### Completion Notes List

- **Backend : 93 → 0 échecs** (3488 passed, 4 skipped). Toutes les causes racines identifiées et corrigées.
- **Frontend : 113 → 0 échecs** (2440 tests, 180 fichiers). Toutes les régressions post-refactoring corrigées.
- `tests/KNOWN_ISSUES.md` mis à jour avec les nouveaux totaux et patterns documentés.
- Aucun test supprimé — tous les échecs corrigés (comportements métier validés).
- 6 fichiers de production annotés `# noqa: BLE001` pour les `except Exception` intentionnels (AC3 : raison explicite) — annotation ajoutée dans cette story.
- `tests/factories.py` corrigé (ActionFactory : objets Python natifs au lieu de json.dumps) — corrige les échecs de test_container_workflow_runtime.py et autres tests utilisant ActionFactory.

### File List

**Backend — Tests corrigés :**
- `inventory/tests/test_views_multi_tables.py`
- `integrations/tests/test_new_adapter_types_fixtures.py`
- `executions/tests/test_rule_engine.py`
- `executions/tests/test_policy_evaluator.py`
- `executions/tests/test_policy_evaluator_clob.py`
- `inventory/tests/test_integration_multi_tables.py`
- `inventory/tests/test_environments.py`
- `inventory/tests/test_views.py`
- `catalog/tests/test_bug_be5_pagination_integration.py`
- `integrations/tests/test_integration_views.py`
- `executions/tests/test_exception_handling.py`
- `core/tests/test_bug_be3_integration_logs.py`
- `catalog/tests/test_action_platform_integration_validation.py`
- `tests/security/test_soc1_compliance.py`
- `catalog/tests/test_rbac_service_di.py`

**Backend — Factories et helpers de test :**
- `tests/factories.py` (ActionFactory : json.dumps → objets Python natifs — corrige test_container_workflow_runtime.py et autres tests utilisant ActionFactory)

**Backend — Production (corrections rétrocompatibilité + annotations) :**
- `core/splunk_logging_handler.py` — `# noqa: BLE001`
- `core/db_resilience.py` — `# noqa: BLE001`
- `catalog/rbac_service.py` — `# noqa: BLE001`
- `executions/container_workflow_runtime.py` — `# noqa: BLE001`
- `profiles/cache.py` — `# noqa: BLE001`
- `services/vault_service.py` — `# noqa: BLE001`
- `catalog/views/__init__.py` — re-export `ensure_utc_isoformat` pour rétrocompatibilité tests (`test_views_timezone.py`)

**Frontend — Tests corrigés :**
- `src/components/catalog/ConfirmationStep.test.tsx`
- `src/components/catalog/TargetSelectionStep.test.tsx`
- `src/hooks/__tests__/useExecutionRestart.test.ts`
- `src/hooks/__tests__/useEditExecution.test.tsx`
- `src/services/__tests__/execution_service.test.ts`
- `src/hooks/useAAPTemplates.test.ts`
- `src/pages/ExecutionsPage.test.tsx`
- `src/components/admin/ActionForm.test.tsx`
- `src/components/admin/ActionWizard.test.tsx`
- `src/pages/AdminPage.story18_1.test.tsx`
- `src/__tests__/ExecutionsPage.compact.test.tsx`
- `src/components/admin/BusinessRulePolicyModal.test.tsx`
- `src/utils/executionRenderers.test.tsx`

**Documentation :**
- `django_backend/tests/KNOWN_ISSUES.md`
