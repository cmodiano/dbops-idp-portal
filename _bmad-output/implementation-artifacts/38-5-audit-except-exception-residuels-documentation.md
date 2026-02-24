# Story 38.5: Audit except Exception résiduels (documentation)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a développeur backend,
I want auditer et documenter les 65 occurrences de `except Exception` dans le backend (37 fichiers),
so that chaque catch générique soit soit justifié avec `# noqa: BLE001` et un commentaire explicatif, soit remplacé par une exception plus spécifique, garantissant qu'aucune erreur n'est avalée silencieusement sans trace.

## Acceptance Criteria

1. **Tableau d'audit complet** — Chaque occurrence de `except Exception` dans le backend est listée avec son fichier, sa ligne, son pattern de gestion (log+reraise, log+fallback, log+continue, silent), et son verdict : OK (documenté/justifié) ou FIX (à corriger).
2. **Aucun except Exception avalant l'erreur sans trace** — Toute occurrence qui n'a ni log, ni reraise, ni commentaire `noqa: BLE001` avec justification est soit corrigée (ajout de log/reraise), soit documentée avec `# noqa: BLE001 — <justification>`.
3. **Les 48 occurrences sans `noqa: BLE001` sont traitées** — Pour chaque occurrence sans commentaire existant :
   - Si le pattern est correct (log + reraise ou log + fallback documenté) → ajouter `# noqa: BLE001 — <justification courte>`
   - Si le pattern avale l'erreur silencieusement → ajouter un `logger.warning()` ou `logger.error()` minimum, puis le `noqa`
   - Si une exception plus spécifique est clairement identifiable → remplacer `except Exception` par l'exception spécifique
4. **Les 17 occurrences déjà `noqa: BLE001` sont vérifiées** — Confirmer que chaque `noqa` existant a une justification inline (pas juste `# noqa: BLE001` sans explication). Compléter si manquant.
5. **Aucune régression** — Les tests existants passent après les modifications. Aucun changement de comportement fonctionnel.
6. **Fichier de synthèse** — Un tableau récapitulatif est ajouté dans la section Completion Notes de cette story avec le décompte final : X OK, Y FIX, Z remplacés par exception spécifique.

## Tasks / Subtasks

- [x] Task 1 — Auditer et documenter les fichiers `core/` (AC: #1, #2, #3, #4)
  - [x]1.1 `core/auth_utils.py:30` — log warning + return [] → ajouter noqa + justification
  - [x]1.2 `core/db_resilience.py:111` — déjà noqa → vérifier justification inline
  - [x]1.3 `core/db_resilience.py:236` — log warning + continue retry → ajouter noqa + justification
  - [x]1.4 `core/feature_flag_views.py:192` — log warning + return 500 → ajouter noqa + justification
  - [x]1.5 `core/feature_flags.py:116` — log error + return {} → ajouter noqa + justification
  - [x]1.6 `core/middleware.py:204` — log error + reraise → ajouter noqa + justification
  - [x]1.7 `core/splunk_logging_handler.py:49,159` — déjà noqa → vérifier justification inline
  - [x]1.8 `core/splunk_logging_handler.py:229` — log warning + drop → ajouter noqa + justification
  - [x]1.9 `core/views.py:78,108,138` — health checks, log error/warning → ajouter noqa + justification
- [x] Task 2 — Auditer et documenter les fichiers `executions/` (AC: #1, #2, #3, #4)
  - [x]2.1 `executions/cancellation_cache.py:46,75` — déjà noqa → vérifier justification inline
  - [x]2.2 `executions/consumers.py:63` — déjà noqa → vérifier justification inline
  - [x]2.3 `executions/container_workflow_runtime.py:290,362,434,568` — log error + mark FAILED → ajouter noqa + justification
  - [x]2.4 `executions/container_workflow_runtime.py:585` — déjà noqa → vérifier justification inline
  - [x]2.5 `executions/rule_engine.py:142` — log error + reraise → ajouter noqa + justification
  - [x]2.6 `executions/services.py:548,558` — log error (on_commit callback) → ajouter noqa + justification
  - [x]2.7 `executions/simulation_service.py:255` — log error + reraise → ajouter noqa + justification
  - [x]2.8 `executions/tasks/gates.py:96,117,375` — log error + persist/continue → ajouter noqa + justification
  - [x]2.9 `executions/tasks/polling.py:96,230,323` — log error → ajouter noqa + justification
  - [x]2.10 `executions/tasks/polling.py:170` — déjà noqa → vérifier justification inline
  - [x]2.11 `executions/tasks/retry.py:198` — déjà noqa → vérifier justification inline
  - [x]2.12 `executions/utils/rbac_helpers.py:41` — déjà noqa → vérifier justification inline
  - [x]2.13 `executions/views/approval_views.py:165` — log error + mark INTEGRATION_ERROR → ajouter noqa + justification
  - [x]2.14 `executions/views/execution_views.py:217,601` — log error → ajouter noqa + justification
  - [x]2.15 `executions/views/execution_views.py:417` — déjà noqa → vérifier justification inline
  - [x]2.16 `executions/views/github_webhooks.py:305` — déjà noqa → vérifier justification inline
  - [x]2.17 `executions/views/terraform_webhooks.py:320` — déjà noqa → vérifier justification inline
  - [x]2.18 `executions/workflow_step_executor.py:324,453` — log error + mark FAILED/fallback → ajouter noqa + justification
- [x] Task 3 — Auditer et documenter les fichiers restants (AC: #1, #2, #3, #4)
  - [x]3.1 `adapters/utils.py:151` — log error + raise BadRequestError → ajouter noqa + justification
  - [x]3.2 `catalog/rbac_service.py:86,167` — déjà noqa → vérifier justification inline
  - [x]3.3 `catalog/rbac_service.py:94,139` — log warning + return None → ajouter noqa + justification
  - [x]3.4 `idp_auth/views.py:311` — log error + set None → ajouter noqa + justification
  - [x]3.5 `idp_backend/__init__.py:29` — log warning (Oracle client init) → ajouter noqa + justification
  - [x]3.6 `integrations/signals.py:66,101` — log critical + reraise (SOC1) → ajouter noqa + justification
  - [x]3.7 `integrations/upload_views.py:64,142` — log error + raise InvalidStateError → ajouter noqa + justification
  - [x]3.8 `integrations/views.py:103,161` — log error + raise InvalidStateError → ajouter noqa + justification
  - [x]3.9 `inventory/permission_aggregator.py:79,98` — log error → ajouter noqa + justification
  - [x]3.10 `inventory/query_executor.py:122,250,543` — log error + raise InventoryServiceError → ajouter noqa + justification
  - [x]3.11 `inventory/services.py:283,375,467` — log error + raise InventoryServiceError → ajouter noqa + justification
  - [x]3.12 `profiles/cache.py:39` — déjà noqa → vérifier justification inline
  - [x]3.13 `services/jira_service.py:344,389` — déjà noqa → vérifier justification inline
  - [x]3.14 `services/notification_service.py:50,82,123,162` — log error (notification best-effort) → ajouter noqa + justification
  - [x]3.15 `services/vault_service.py:96` — déjà noqa → vérifier justification inline
- [x] Task 4 — Lancer les tests et rédiger la synthèse (AC: #5, #6)
  - [x]4.1 Lancer `.venv/bin/python -m pytest` (depuis django_backend/) pour vérifier 0 régression
  - [x]4.2 Rédiger le tableau récapitulatif dans Completion Notes : X OK, Y FIX, Z remplacés

## Dev Notes

### Contexte de l'audit (issue 16.2)

**Source :** `idp-portal/CODEBASE-REVIEW.md` §16.2 et §18 (récapitulatif par priorité).

L'audit #3 (2026-02-23) a identifié **77 occurrences** de `except Exception` dans 40 fichiers backend (comptage mis à jour par rapport à l'audit initial de 33 occurrences limité à `executions/`). L'audit subagent actuel en a trouvé **65 dans 37 fichiers source** (la différence s'explique par les fichiers de test et de migration exclus du comptage).

### État actuel détaillé

| Catégorie | Nombre | % |
|-----------|--------|---|
| Déjà `noqa: BLE001` | 19 | 27% |
| Sans commentaire (à traiter) | 51 | 73% |
| **Total** | **70** | 100% |

### Classification par pattern de gestion

| Pattern | Nombre | Action requise |
|---------|--------|----------------|
| Log error + reraise | 11 | Ajouter `noqa: BLE001 — logged and reraised` |
| Log error + return fallback/None | 18 | Ajouter `noqa: BLE001 — <justification fallback>` |
| Log error/warning + continue | 15 | Ajouter `noqa: BLE001 — <justification best-effort>` |
| Log error + mark FAILED | 12 | Ajouter `noqa: BLE001 — catch-all, marks execution FAILED` |
| Silent fallback (no-op) | 4 | Vérifier que le noqa existant a justification inline |
| Log + raise custom exception | 5 | Ajouter `noqa: BLE001 — wrapped in domain exception` |

### Catégories de justification à utiliser

Pour assurer la cohérence des commentaires `noqa`, utiliser ces catégories standardisées :

1. **`resilience-boundary`** — Webhooks, polling, tasks Celery : le code DOIT continuer même en cas d'erreur inattendue (ex. `github_webhooks.py`, `terraform_webhooks.py`)
2. **`catch-all-mark-failed`** — Runtime d'exécution : catch-all qui marque l'exécution FAILED et log l'erreur complète (ex. `container_workflow_runtime.py`)
3. **`best-effort-non-critical`** — Opérations non-critiques : cache, broadcast, notifications (ex. `cancellation_cache.py`, `notification_service.py`)
4. **`logged-and-reraised`** — Log pour observabilité puis reraise (ex. `middleware.py`, `rule_engine.py`, `integrations/signals.py`)
5. **`logged-and-wrapped`** — Catch-all qui wrappe dans une exception domaine (ex. `inventory/services.py` → `InventoryServiceError`)
6. **`graceful-degradation`** — Fallback documenté avec log (ex. `feature_flags.py` → return `{}`, `core/views.py` → health check degraded)

### Fichiers les plus sensibles (priorité haute)

1. **`executions/container_workflow_runtime.py`** — 5 occurrences, runtime critique
2. **`executions/tasks/polling.py`** — 4 occurrences, tâche Celery critique
3. **`executions/tasks/gates.py`** — 3 occurrences, gestion gates/timeouts
4. **`executions/workflow_step_executor.py`** — 2 occurrences, exécution des steps
5. **`services/notification_service.py`** — 4 occurrences, notifications multi-canal

### Ce qu'il ne faut PAS faire

- **Ne PAS changer la logique des catch** — cette story est de la documentation, pas du refactoring
- **Ne PAS remplacer `except Exception` par une exception spécifique** sauf si c'est trivial et évident (ex. `json.JSONDecodeError` au lieu de `Exception` pour un `json.loads`)
- **Ne PAS ajouter de logging là où il n'y en a pas** sauf si le catch avale silencieusement l'erreur sans aucune trace (les 4 cas "silent" déjà noqa)
- **Ne PAS modifier les tests** — seuls les fichiers source sont concernés
- **Ne PAS faire de refactoring cosmétique** (reformatage, réorganisation imports, etc.)

### Intelligence story précédente (38.4)

- Story 38.4 (NEW-BE-4 backend) terminée avec succès — remplacement `asyncio.run` → `async_to_sync`, 22/22 tests passent
- Commit récent : `d2c2cb7 refactor(backend): replace asyncio.run() with async_to_sync() in polling task (38-4)`
- Stories 38.1 (quick wins backend), 38.2 (STATUS_CONFIG frontend), 38.3 (key props TopNav) toutes terminées
- Pattern tests backend confirmé : pytest + `test_settings`, fichiers dans `tests/` sous chaque app

### Commits récents pertinents

```
d2c2cb7 refactor(backend): replace asyncio.run() with async_to_sync() in polling task (38-4)
adb8f83 fix(frontend): remove duplicate key prop on nested TopNav button element (NEW-FE-1)
0f21a08 refactor(frontend): consolidate duplicate status config into shared execution-status module (SOLID-FE-10)
3195fd7 fix(backend): quick wins N+1, double update, TODO obsolète, log execution_id
```

### Project Structure Notes

- Fichiers cibles : 37 fichiers `.py` dans `idp-portal/django_backend/` (voir liste complète dans Tasks)
- Python venv : `.venv/bin/python`
- Test runner : `.venv/bin/python -m pytest` (depuis `django_backend/`)
- Test settings : `idp_backend.test_settings` (via pytest.ini)
- Linter ruff : `BLE001` est la règle pour `except Exception` — `noqa: BLE001` supprime l'avertissement

### Inventaire complet des 65 occurrences par fichier

| # | Fichier | Ligne | Pattern | noqa existant |
|---|---------|-------|---------|---------------|
| 1 | adapters/utils.py | 151 | log error + raise BadRequestError | — |
| 2 | catalog/rbac_service.py | 86 | silent pass (cache) | ✓ noqa |
| 3 | catalog/rbac_service.py | 94 | log warning + return None | — |
| 4 | catalog/rbac_service.py | 139 | log warning + return None | — |
| 5 | catalog/rbac_service.py | 167 | silent pass (cache) | ✓ noqa |
| 6 | core/auth_utils.py | 30 | log warning + return [] | — |
| 7 | core/db_resilience.py | 111 | return True (mid-commit) | ✓ noqa |
| 8 | core/db_resilience.py | 236 | log warning + retry | — |
| 9 | core/feature_flag_views.py | 192 | log warning + return 500 | — |
| 10 | core/feature_flags.py | 116 | log error + return {} | — |
| 11 | core/middleware.py | 204 | log error + reraise | — |
| 12 | core/splunk_logging_handler.py | 49 | silent pass (import) | ✓ noqa |
| 13 | core/splunk_logging_handler.py | 159 | silent (handleError) | ✓ noqa |
| 14 | core/splunk_logging_handler.py | 229 | log warning + drop | — |
| 15 | core/views.py | 78 | log error (health check) | — |
| 16 | core/views.py | 108 | log warning (health check) | — |
| 17 | core/views.py | 138 | log warning (health check) | — |
| 18 | executions/cancellation_cache.py | 46 | log warning + DB fallback | ✓ noqa |
| 19 | executions/cancellation_cache.py | 75 | log warning (best-effort) | ✓ noqa |
| 20 | executions/consumers.py | 63 | log warning (cleanup) | ✓ noqa |
| 21 | executions/container_workflow_runtime.py | 290 | log error + mark FAILED | — |
| 22 | executions/container_workflow_runtime.py | 362 | log error + mark FAILED | — |
| 23 | executions/container_workflow_runtime.py | 434 | log error + mark FAILED | — |
| 24 | executions/container_workflow_runtime.py | 568 | log error + mark FAILED | — |
| 25 | executions/container_workflow_runtime.py | 585 | log error (cleanup) | ✓ noqa |
| 26 | executions/rule_engine.py | 142 | log error + reraise | — |
| 27 | executions/services.py | 548 | log error (on_commit) | — |
| 28 | executions/services.py | 558 | log error (on_commit) | — |
| 29 | executions/simulation_service.py | 255 | log error + reraise | — |
| 30 | executions/tasks/gates.py | 96 | log error + persist | — |
| 31 | executions/tasks/gates.py | 117 | log error (nested save) | — |
| 32 | executions/tasks/gates.py | 375 | log error (timeout) | — |
| 33 | executions/tasks/polling.py | 96 | log error (broadcast) | — |
| 34 | executions/tasks/polling.py | 170 | log warning (broadcast) | ✓ noqa |
| 35 | executions/tasks/polling.py | 230 | log error (update) | — |
| 36 | executions/tasks/polling.py | 323 | log error (adapter) | — |
| 37 | executions/tasks/retry.py | 198 | log exception + return | ✓ noqa |
| 38 | executions/utils/rbac_helpers.py | 41 | log warning + return {} | ✓ noqa |
| 39 | executions/views/approval_views.py | 165 | log error + INTEGRATION_ERROR | — |
| 40 | executions/views/execution_views.py | 217 | log error + INTEGRATION_ERROR | — |
| 41 | executions/views/execution_views.py | 417 | log warning (best-effort) | ✓ noqa |
| 42 | executions/views/execution_views.py | 601 | log error + raise ServiceUnavailableError | — |
| 43 | executions/views/github_webhooks.py | 305 | log error (webhook resilience) | ✓ noqa |
| 44 | executions/views/terraform_webhooks.py | 320 | log error (webhook resilience) | ✓ noqa |
| 45 | executions/workflow_step_executor.py | 324 | log error + mark FAILED | — |
| 46 | executions/workflow_step_executor.py | 453 | log CRITICAL + fallback | — |
| 47 | idp_auth/views.py | 311 | log error + set None | — |
| 48 | idp_backend/__init__.py | 29 | log warning (Oracle init) | — |
| 49 | integrations/signals.py | 66 | log critical + reraise (SOC1) | — |
| 50 | integrations/signals.py | 101 | log critical + reraise (SOC1) | — |
| 51 | integrations/upload_views.py | 64 | log error + raise InvalidStateError | — |
| 52 | integrations/upload_views.py | 142 | log error + raise InvalidStateError | — |
| 53 | integrations/views.py | 103 | log error + raise InvalidStateError | — |
| 54 | integrations/views.py | 161 | log error + raise InvalidStateError | — |
| 55 | inventory/permission_aggregator.py | 79 | log error | — |
| 56 | inventory/permission_aggregator.py | 98 | log error | — |
| 57 | inventory/query_executor.py | 122 | log error + raise InventoryServiceError | — |
| 58 | inventory/query_executor.py | 250 | log error + raise InventoryServiceError | — |
| 59 | inventory/query_executor.py | 543 | log error + raise InventoryServiceError | — |
| 60 | inventory/services.py | 283 | log error + raise InventoryServiceError | — |
| 61 | inventory/services.py | 375 | log error + raise InventoryServiceError | — |
| 62 | inventory/services.py | 467 | log error + raise InventoryServiceError | — |
| 63 | services/notification_service.py | 50 | log error (email) | — |
| 64 | services/notification_service.py | 82 | log error (Teams) | — |
| 65 | services/notification_service.py | 123 | log error (page API) | — |
| 66 | services/notification_service.py | 162 | log error (page DBA) | — |
| 67 | services/jira_service.py | 344 | silent fallback (text decode) | ✓ noqa |
| 68 | services/jira_service.py | 389 | log error + raise | ✓ noqa |
| 69 | services/vault_service.py | 96 | circuit breaker (silent) | ✓ noqa |
| 70 | profiles/cache.py | 39 | log warning (cache) | ✓ noqa |

### References

- [Source: idp-portal/CODEBASE-REVIEW.md §16.2 — except Exception résiduels]
- [Source: idp-portal/CODEBASE-REVIEW.md §18 — Récapitulatif par priorité, issue 16.2 LOW]
- [Source: _bmad-output/planning-artifacts/epic-38-codebase-review-audit-3-corrections.md — Story 38.5]
- [Source: _bmad-output/implementation-artifacts/38-4-backend-asyncio-run-to-async-to-sync-polling.md — story précédente]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Tests : 3542 passed, 4 skipped, 0 failures (146s)

### Completion Notes List

**Tableau récapitulatif — Audit `except Exception` (70 occurrences dans 37 fichiers)**

| Catégorie | Nombre | Action |
|-----------|--------|--------|
| Déjà `noqa: BLE001` avec justification → **standardisé** | 11 | ✅ OK — vérifié, format aligné sur catégories standard (review 38-5) |
| Déjà `noqa: BLE001` sans justification → **complété** | 8 | ✅ FIX — justification inline ajoutée |
| Sans `noqa` → **ajouté `noqa: BLE001` + justification** | 51 | ✅ FIX — noqa + justification ajoutés |
| Remplacés par exception spécifique | 0 | N/A (aucun cas trivial identifié) |
| **Total traités** | **70** | |

**Catégories de justification utilisées (toutes occurrences standardisées) :**
- `resilience-boundary` (12 occurrences) — webhooks, polling, tasks Celery, circuit breaker, Redis fallback
- `catch-all-mark-failed` (10 occurrences) — runtime d'exécution, marks execution FAILED
- `best-effort-non-critical` (16 occurrences) — cache, notifications, broadcast, logging, cleanup
- `logged-and-reraised` (6 occurrences) — log pour observabilité puis reraise
- `logged-and-wrapped` (13 occurrences) — catch-all qui wrappe dans exception domaine
- `graceful-degradation` (13 occurrences) — fallback documenté avec log

**Aucun changement de comportement fonctionnel.** Seuls des commentaires `# noqa: BLE001 — <justification>` ont été ajoutés ou standardisés sur les lignes `except Exception`.

### File List

- `idp-portal/django_backend/adapters/utils.py` (modifié)
- `idp-portal/django_backend/catalog/rbac_service.py` (modifié)
- `idp-portal/django_backend/core/auth_utils.py` (modifié)
- `idp-portal/django_backend/core/db_resilience.py` (modifié)
- `idp-portal/django_backend/core/feature_flag_views.py` (modifié)
- `idp-portal/django_backend/core/feature_flags.py` (modifié)
- `idp-portal/django_backend/core/middleware.py` (modifié)
- `idp-portal/django_backend/core/splunk_logging_handler.py` (modifié)
- `idp-portal/django_backend/core/views.py` (modifié)
- `idp-portal/django_backend/executions/container_workflow_runtime.py` (modifié)
- `idp-portal/django_backend/executions/rule_engine.py` (modifié)
- `idp-portal/django_backend/executions/services.py` (modifié)
- `idp-portal/django_backend/executions/simulation_service.py` (modifié)
- `idp-portal/django_backend/executions/tasks/gates.py` (modifié)
- `idp-portal/django_backend/executions/tasks/polling.py` (modifié)
- `idp-portal/django_backend/executions/views/approval_views.py` (modifié)
- `idp-portal/django_backend/executions/views/execution_views.py` (modifié)
- `idp-portal/django_backend/executions/workflow_step_executor.py` (modifié)
- `idp-portal/django_backend/idp_auth/views.py` (modifié)
- `idp-portal/django_backend/idp_backend/__init__.py` (modifié)
- `idp-portal/django_backend/integrations/signals.py` (modifié)
- `idp-portal/django_backend/integrations/upload_views.py` (modifié)
- `idp-portal/django_backend/integrations/views.py` (modifié)
- `idp-portal/django_backend/inventory/permission_aggregator.py` (modifié)
- `idp-portal/django_backend/inventory/query_executor.py` (modifié)
- `idp-portal/django_backend/inventory/services.py` (modifié)
- `idp-portal/django_backend/profiles/cache.py` (modifié)
- `idp-portal/django_backend/executions/cancellation_cache.py` (modifié — review: format noqa standardisé)
- `idp-portal/django_backend/executions/consumers.py` (modifié — review: format noqa standardisé)
- `idp-portal/django_backend/executions/tasks/retry.py` (modifié — review: format noqa standardisé)
- `idp-portal/django_backend/executions/utils/rbac_helpers.py` (modifié — review: format noqa standardisé)
- `idp-portal/django_backend/executions/views/github_webhooks.py` (modifié — review: format noqa standardisé)
- `idp-portal/django_backend/executions/views/terraform_webhooks.py` (modifié — review: format noqa standardisé)
- `idp-portal/django_backend/services/jira_service.py` (modifié — review: format noqa standardisé)
- `idp-portal/django_backend/services/notification_service.py` (modifié)
- `idp-portal/django_backend/services/vault_service.py` (modifié)

### Change Log

- **2026-02-23** — Audit et documentation des 70 occurrences `except Exception` dans 37 fichiers backend. Ajout de `# noqa: BLE001 — <justification>` sur 51 occurrences sans commentaire ; complétion de la justification inline sur 8 occurrences existantes avec `noqa` sans explication ; vérification des 11 occurrences déjà documentées. Aucun changement de comportement. Tests : 3542 passed, 0 failures.
- **2026-02-23** — [Review] Correction des décomptes dans Completion Notes (65→70 total, sous-totaux corrigés). Standardisation du format noqa sur 11 occurrences pré-existantes (`broad catch justified:` → catégories standardisées). 7 fichiers additionnels modifiés.
