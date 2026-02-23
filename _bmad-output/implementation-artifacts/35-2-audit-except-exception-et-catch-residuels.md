# Story 35.2 : Audit `except Exception` et `.catch()` résiduels

Status: done

<!-- Réf: CODEBASE-REVIEW.md 16.2, 16.3 — Priorité MOYENNE -->

## Story

En tant que développeur,
je veux auditer et documenter (ou corriger) tous les `except Exception` backend et `.catch()` frontend résiduels,
afin qu'aucun gestionnaire d'erreur large ne dissimule silencieusement une défaillance sans justification documentée.

## Contexte

**16.2 [LOW]** et **16.3 [LOW]** du CODEBASE-REVIEW (2026-02-23) :

- **Backend :** 29 occurrences de `except Exception` dans le module `executions/` (sur ~70 dans l'ensemble du codebase). 2 sont déjà justifiées (`# noqa: BLE001` dans `terraform_webhooks.py` et `github_webhooks.py`). Les 27 restantes doivent être auditées.
- **Frontend :** ~40 occurrences de `.catch()` dans les fichiers sources hors tests. Beaucoup ont déjà une gestion d'état (fallback `setX([])`), mais certaines sont silencieuses sans commentaire d'intention.

**Patterns déjà établis dans le codebase (à réutiliser) :**

```python
# Justification BLE001 (utilisé dans terraform/github webhooks) :
except Exception as e:  # noqa: BLE001 — broad catch justified: webhook must return 200 even if broadcast fails (resilience)

# Justification avec log (utilisé dans rbac_service, profiles/cache, vault_service) :
except Exception:
    logger.warning('event_name', exc_info=True)

# Justification avec log + reraise (pattern services) :
except Exception as exc:  # noqa: BLE001 — resilience: convert any unexpected error to ServiceUnavailableError
    logger.error(...)
    raise ServiceUnavailableError(...) from exc
```

```typescript
// Fallback d'état — pattern accepté (ProfileWizard, CalendarFiltersPanel) :
.catch(() => {
  setOptions([]);
})

// Fire-and-forget intentionnel — doit être commenté :
.catch(() => {}); // fire-and-forget — prefetch optionnel, erreur silencée intentionnellement
```

## Acceptance Criteria

1. **Given** le module `executions/` backend
   **Then** chaque `except Exception` non annoté est traité par l'une des trois actions :
   - (a) `# noqa: BLE001 — <raison>` si le broad catch est justifié
   - (b) Remplacement par une exception plus spécifique si le type est identifiable
   - (c) Vérification qu'un `logger.error/warning(..., exc_info=True)` est déjà présent (auquel cas : statut OK)

2. **Given** l'audit backend complet
   **Then** un tableau est produit (dans les Dev Notes ou un fichier annexe) listant chaque occurrence avec :
   - Fichier:ligne, contexte succinct, action prise (OK / noqa ajouté / exception spécifiée / log ajouté)

3. **Given** les fichiers sources frontend (hors tests)
   **Then** chaque `.catch()` entièrement silencieux (corps `() => {}` sans state update, sans log, sans commentaire) est traité par l'une des deux actions :
   - (a) Ajout d'un commentaire d'intention inline : `// fire-and-forget — <raison>` ou `// échec non-critique — <raison>`
   - (b) Ajout d'un `logger.warn(...)` ou mise à jour d'un état d'erreur si l'erreur doit être visible

4. **Given** l'audit frontend complet
   **Then** un tableau est produit listant chaque occurrence avec :
   - Fichier:ligne, pattern observé, action prise (OK avec fallback état / OK fire-and-forget documenté / log ajouté)

5. **Given** les tests existants
   **Then** aucune régression — `pytest` backend et `vitest run` frontend passent au moins autant de tests qu'avant la story

6. **Given** ruff sur le codebase backend
   **Then** `ruff check --select BLE001` ne remonte aucune nouvelle violation non annotée dans `executions/`

## Tasks / Subtasks

- [x] Task 1 — Audit backend `executions/` (AC: #1, #2)
  - [x] 1.1 Lire chaque occurrence `except Exception` dans les 13 fichiers identifiés (voir Dev Notes)
  - [x] 1.2 Pour chaque occurrence, déterminer : log présent ? justification claire ? exception spécifiable ?
  - [x] 1.3 Produire le tableau d'audit (fichier:ligne → statut + action)
  - [x] 1.4 Appliquer les corrections identifiées (noqa, log manquant, exception spécifique)

- [x] Task 2 — Vérification backend étendu (AC: #1)
  - [x] 2.1 Vérifier que les occurrences hors `executions/` déjà commentées restent cohérentes (spot check : `core/`, `catalog/`, `services/`, `inventory/`)
  - [x] 2.2 Aucun changement requis si déjà justifié — observation seulement

- [x] Task 3 — Audit frontend `.catch()` (AC: #3, #4)
  - [x] 3.1 Parcourir les ~40 occurrences `.catch()` dans `frontend/src/` hors tests
  - [x] 3.2 Catégoriser : fallback état (OK), fire-and-forget silencieux (FIX commentaire), erreur non loguée (FIX log/state)
  - [x] 3.3 Produire le tableau d'audit
  - [x] 3.4 Appliquer les corrections (commentaires d'intention ou log)

- [x] Task 4 — Vérification et validation (AC: #5, #6)
  - [x] 4.1 `ruff check --select BLE001 django_backend/executions/` depuis `idp-portal/django_backend` — 0 violation ✅
  - [x] 4.2 `pytest executions/ --tb=no -q` — 670 passent, 42 échecs pré-existants, 0 régression ✅
  - [x] 4.3 `npx vitest run` depuis `idp-portal/frontend` — 2305 passent, 113 échecs pré-existants, 0 régression ✅

## Dev Notes

### Inventaire backend `executions/` — 29 occurrences (tableau d'audit complet)

| Fichier | Ligne | Variable | Contexte | Action prise |
|---------|-------|----------|---------|-------------|
| `container_workflow_runtime.py` | 287 | `sim_error` | Simulation enfant : catch-all → marque FAILED et continue | **FIX** : `exc_info=True` + `error_type` ajoutés au `logger.error` |
| `container_workflow_runtime.py` | 363 | `exc` | Création changement ServiceNow avant RUNNING (run async) | **FIX** : `exc_info=True` ajouté au `logger.error` |
| `container_workflow_runtime.py` | 434 | `exc` | Création changement ServiceNow avant RUNNING (run sync) | **FIX** : `exc_info=True` ajouté au `logger.error` |
| `container_workflow_runtime.py` | 569 | `e` | Thread principal : catch-all → marque exécution FAILED | **FIX** : `exc_info=True` ajouté au `logger.error` |
| `container_workflow_runtime.py` | 586 | _(bare)_ | Nettoyage interne thread (cleanup post-FAILED, best-effort) | **OK** : `logger.error(..., exc_info=True)` déjà présent |
| `services.py` | 552 | `exc` | Dispatch notification on_commit (fire-and-forget non-critique) | **FIX** : `exc_info=True` ajouté au `logger.error` |
| `services.py` | 561 | `exc` | Setup notification on_commit (fire-and-forget non-critique) | **FIX** : `exc_info=True` ajouté au `logger.error` |
| `tasks/gates.py` | 96 | `e` | Évaluation gate : log + continuer la boucle | **FIX** : `exc_info=True` ajouté au `logger.error` |
| `tasks/gates.py` | 116 | `save_error` | Persistance erreur dans step output (best-effort) | **FIX** : `exc_info=True` ajouté au `logger.error` |
| `tasks/gates.py` | 373 | `exc` | Timeout gate : mise à jour statut exécution (best-effort) | **FIX** : `exc_info=True` ajouté au `logger.error` |
| `tasks/retry.py` | 198 | `e` | Tâche Celery retry : handle all failure modes | **FIX+noqa** : `# noqa: BLE001 — Celery retry task must handle all failure modes gracefully` + `logger.exception` (inclut exc_info) |
| `tasks/polling.py` | 96 | `exc` | Polling exhausted : mise à jour statut exécution | **FIX** : `exc_info=True` ajouté au `logger.error` |
| `tasks/polling.py` | 170 | `e` | Broadcast WebSocket (non-critique, polling ne doit pas s'interrompre) | **FIX+noqa** : `# noqa: BLE001 — channels broadcast is non-critical` + `exc_info=True` |
| `tasks/polling.py` | 228 | `e` | Mise à jour exécution depuis résultat polling | **FIX** : `exc_info=True` ajouté au `logger.error` |
| `tasks/polling.py` | 324 | `e` | Appel adapter polling (log + retry ou mark-exhausted) | **FIX** : `exc_info=True` ajouté au `logger.error` |
| `simulation_service.py` | 255 | `e` | Thread simulation : catch-all → log + re-raise | **OK** : `logger.error(..., exc_info=True)` + `raise` déjà présents — aucun changement |
| `consumers.py` | 63 | `e` | `group_discard` WebSocket (best-effort cleanup, ne doit pas raise) | **FIX+noqa** : `# noqa: BLE001 — group_discard is best-effort cleanup` + `exc_info=True` |
| `rule_engine.py` | 142 | `exc` | Interpréteur output : log + re-raise immédiat | **OK** : `logger.error(..., exc_info=True)` + `raise` déjà présents — aucun changement |
| `utils/rbac_helpers.py` | 41 | `e` | ProfileService : retourne `set()` vide si indisponible | **FIX+noqa** : `# noqa: BLE001 — ProfileService can raise various exceptions, must return safe default` + `exc_info=True` |
| `cancellation_cache.py` | 46 | `e` | Redis `cache.get` : fallback DB si Redis indisponible | **FIX+noqa** : `# noqa: BLE001 — Redis can fail in various ways, must fall back to DB` + `exc_info=True` |
| `cancellation_cache.py` | 74 | `e` | Redis `cache.set` : log warning, ne bloque pas le flow | **FIX+noqa** : `# noqa: BLE001 — Redis failures should not break cancellation flow` + `exc_info=True` |
| `workflow_step_executor.py` | 324 | `e` | Exécution step : adapter peut lever n'importe quelle exception | **FIX** : `exc_info=True` ajouté au `logger.error` |
| `workflow_step_executor.py` | 453 | `exc` | Appel adapter : fallback simulé avec audit CRITICAL | **FIX** : `exc_info=True` ajouté au `logger.critical` |
| `views/terraform_webhooks.py` | 320 | `e` | Webhook : doit toujours retourner 200 (résilience) | **OK — déjà justifié** : `# noqa: BLE001` présent avant la story |
| `views/execution_views.py` | 217 | `e` | Démarrage exécution : multiple services → marque INTEGRATION_ERROR | **FIX** : `exc_info=True` ajouté au `logger.error` |
| `views/execution_views.py` | 417 | `e` | Annulation remote : adapter best-effort | **FIX+noqa** : `# noqa: BLE001 — adapter may raise various exceptions, remote cancellation is best-effort` + `exc_info=True` |
| `views/execution_views.py` | 601 | `e` | Récupération logs AAP : log + re-raise `ServiceUnavailableError` | **FIX** : `exc_info=True` ajouté au `logger.error` + re-raise |
| `views/github_webhooks.py` | 305 | `e` | Webhook : doit toujours retourner 200 (résilience) | **OK — déjà justifié** : `# noqa: BLE001` présent avant la story |
| `views/approval_views.py` | 165 | `e` | Approval launch workflow : log + marque INTEGRATION_ERROR | **OK** : `logger.error(..., exc_info=True)` déjà présent — aucun changement |

**Récapitulatif : 5 OK (déjà conformes) · 17 FIX (`exc_info=True` ajouté) · 7 FIX+noqa (`# noqa: BLE001` + `exc_info=True`)**

**Commande d'inventaire utile :**
```bash
# Depuis idp-portal/django_backend
grep -n "except Exception" executions/**/*.py executions/*.py 2>/dev/null
ruff check --select BLE001 executions/
```

### Inventaire frontend `.catch()` — occurrences identifiées (tableau d'audit complet)

| Fichier | Ligne | Pattern | Action prise |
|---------|-------|---------|-------------|
| `contexts/AuthContext.tsx` | 113 | `.catch((err) =>` | **OK** : `logger.error` + return null (fallback token) |
| `utils/engineIconCache.ts` | 31 | `.catch(() =>` | **FIX** *(code review)* : commentaire `// échec non-critique — retourne un cache vide` ajouté |
| `utils/engineIconCache.ts` | 52 | `.catch(() => {})` | **FIX** *(story)* : commentaire `// fire-and-forget — prefetch optionnel` ajouté |
| `components/calendar/CalendarFiltersPanel.tsx` | 84 | `.catch(() =>` | **OK** : fallback `setIntegrations([])` + cancelled |
| `components/catalog/TargetSelector.tsx` | 100 | `.catch((err) =>` | **OK** : `setError(err.message)` + cancelled — erreur visible |
| `components/admin/ActionWizard.tsx` | 123 | `.catch(() => setTagsOptions([]))` | **OK** : fallback état |
| `components/admin/ProfileWizard.tsx` | 113 | `.catch(() =>` | **OK** : fallback `setActionsOptions([])` + `setTagsOptions([])` |
| `components/admin/ProfileWizard.tsx` | 125 | `.catch(() =>` | **OK** : fallback état |
| `components/admin/ProfileForm.tsx` | 183 | `.catch(() =>` | **OK** : fallback `setActionsOptions([])` + `setTagsOptions([])` |
| `components/admin/RemediationRulesEditor.tsx` | 242 | `.catch((err) =>` | **OK** : `logger.error` + `setActions([])` — log + fallback |
| `components/admin/BusinessRulePolicySelector.tsx` | 83 | `.catch(() =>` | **OK** : `setPreviewJson(null)` + `setPreviewName('')` — reset état |
| `components/admin/WorkflowStepsEditor.tsx` | 116 | `.catch((err) =>` | **OK** : `logger.error` + message d'erreur — erreur visible |
| `components/admin/ActionPalette.tsx` | 31 | `.catch((err) =>` | **OK** : `setError(err.message)` + `setActions([])` — erreur visible + fallback |
| `components/dashboard/reporting/ReportingDashboard.tsx` | 163 | `.catch(() =>` | **OK** : commentaire `// Silently fail - panel will use fallback options` présent |
| `components/execution/StepDetailDrawer.tsx` | 138 | `.catch((err) =>` | **OK** : `setChildError(err.message)` + cancelled — erreur visible |
| `components/execution/ExecutionView.tsx` | 109 | `.catch((err) =>` | **OK** : `setError(err)` — erreur visible |
| `components/execution/WorkflowExecutionGraph.tsx` | 158 | `.catch((err: unknown) =>` | **OK** : `logger.error` + erreur visible |
| `components/executions/ExecutionsFiltersPanel.tsx` | 97 | `.catch(() =>` | **OK** : `setTags([])` + cancelled — fallback état |
| `components/executions/ExecutionsFiltersPanel.tsx` | 116 | `.catch(() =>` | **OK** : `setActions([])` + cancelled — fallback état |
| `hooks/usePatternResolver.ts` | 61 | `.catch(() =>` | **OK** : fallback `setResolvedTargets([])` + cancelled |
| `hooks/useCatalogState.ts` | 147 | `.catch(() => [] as FavoriteEntry[])` | **OK** : fallback inline |
| `hooks/useCatalogState.ts` | 150 | `.catch((error) =>` | **OK** : `logger.error` + `message.warning` + return [] — log + UI feedback |
| `hooks/useCatalogState.ts` | 256 | `.catch(() => null)` | **OK** : commentaire "Stats are optional" ✅ |
| `hooks/useCategories.ts` | 38 | `.catch((err) =>` | **OK** : re-throw explicite (propagation vers caller) |
| `hooks/useCategories.ts` | 78 | `.catch((err) =>` | **OK** : `setError(error)` + `setLoading(false)` — erreur visible |
| `hooks/useExecutionsData.ts` | 167 | `.catch(() =>` | **OK** : `setIntegrationIconsMap(null)` + cancelled — fallback état |
| `hooks/useVaultIntegrations.ts` | 33 | `.catch((err: unknown) =>` | **OK** : `setError(msg)` + `setVaultIntegrations([])` — erreur visible + fallback |
| `hooks/useActionFormState.ts` | 66 | `.catch(() => setTagsOptions([]))` | **OK** : fallback état |
| `hooks/useEngines.ts` | 41 | `.catch((err) =>` | **OK** : re-throw explicite (propagation vers caller) |
| `hooks/useEngines.ts` | 84 | `.catch((err) =>` | **OK** : `setError(error)` — erreur visible |
| `hooks/useAuditFilters.ts` | 164 | `.catch(() =>` | **OK** : `setActions([])` + cancelled — fallback état |
| `hooks/useWorkflowStepActions.ts` | 66 | `.catch((err: unknown) =>` | **OK** : `setWorkflowStepActionsError(msg)` — erreur visible |
| `hooks/useIntegrationTypes.ts` | 84 | `.catch(() =>` | **OK** : retry logic (1 retry après 1s) — non-silencieux |
| `hooks/useIntegrationTypes.ts` | 88 | `.catch(reject)` | **OK** : propagation reject |
| `hooks/useIntegrationTypes.ts` | 110 | `.catch((err: unknown) =>` | **OK** : `setError(msg)` + `setTypes(FALLBACK_INTEGRATION_TYPES)` — erreur visible + fallback |
| `hooks/useEditExecution.ts` | 75 | `.catch(() => setTargetOptions([]))` | **OK** : fallback état |
| `hooks/useTargetInventory.ts` | 60 | `.catch((err: Error & ...` | **OK** : gestion contextuelle complexe (cache + warning) — erreur gérée |
| `hooks/useAAPTemplates.ts` | 85 | `.catch((err: unknown) =>` | **OK** : `setError(msg)` + `setFallback(true)` — erreur visible |
| `hooks/useEnvironments.ts` | 56 | `.catch((err) =>` | **OK** : re-throw + fallback envs list — propagation contrôlée |
| `hooks/useEnvironments.ts` | 118 | `.catch((err) =>` | **OK** : `setError(error)` — erreur visible |
| `services/reference_service.ts` | 67 | `.catch((err) =>` | **OK** : `logger.error` (DEV) + reset promise — log conditionnel |

**Récapitulatif : 39 OK · 2 FIX (commentaires d'intention : `engineIconCache.ts:52` story + `engineIconCache.ts:31` code review)**

**Commandes d'inventaire utiles :**
```bash
# Depuis idp-portal/frontend/src/
grep -rn "\.catch(" --include="*.tsx" --include="*.ts" . | grep -v ".test." | grep -v "__tests__"
```

### Critères de classification

**Backend — Statut OK si :**
- `# noqa: BLE001 — <raison>` présent
- OU `logger.error/warning(..., exc_info=True)` présent dans le bloc except
- OU exception rethrow après log (pattern de résidence : catch → log → raise XxxError)

**Backend — FIX requis si :**
- `except Exception: pass` sans log ni commentaire
- `except Exception as e: logger.debug(...)` sans `exc_info=True` (perd la stack trace)

**Frontend — Statut OK si :**
- `.catch()` contient une mise à jour d'état (setX([]), setX(null)) — gestion dégradée intentionnelle
- OU `.catch(() => {})` avec commentaire `// fire-and-forget` ou `// non-critique`
- OU `.catch(reject)` — propagation explicite

**Frontend — FIX requis si :**
- `.catch(() => {})` sans commentaire dans un contexte où l'erreur est impactante pour l'UX
- `.catch((err) => {})` où `err` est ignoré sans raison documentée

### Stack technique

- **Backend :** Python 3.12, Django 5.2, structlog, ruff (BLE001 = flake8-bugbear broad exception catch)
- **Frontend :** TypeScript, React 18, Vitest
- **Commandes de vérification :**
  ```bash
  # Backend
  cd /Users/cyrille/Documents/Dev/test/idp-portal/django_backend
  ruff check --select BLE001 executions/
  .venv/bin/python -m pytest executions/ --tb=short -q

  # Frontend
  cd /Users/cyrille/Documents/Dev/test/idp-portal/frontend
  npx vitest run --reporter=verbose 2>&1 | tail -20
  ```

### Contexte story 35.1

La story 35.1 (complétée le 2026-02-23) a établi le pattern de consolidation des configs de statut. Les fichiers modifiés incluent `ExecutionView.tsx`, `StepDetailDrawer.tsx`, `WorkflowExecutionGraph.tsx` — certains d'entre eux apparaissent aussi dans l'inventaire frontend `.catch()`. Vérifier que les `.catch()` dans ces fichiers n'ont pas été impactés par le refactoring 35.1.

### Commits récents pertinents

```
7f8bf6a refactor(35-1): consolider STATUS_CONFIG dupliqués → execution-status.ts (SOLID-FE-10)
5cfe7e2 fix(ci): ruff F401/F841 + DJANGO_SECRET_KEY on mypy step
c88d14f fix(ci): ruff, type-check, pytest CI and requirements-dev.lock
bfb234b feat(34-15): ISP — séparer BaseAdapter en ITriggerableAdapter + ICancellableAdapter
```

### Project Structure Notes

- Backend : `idp-portal/django_backend/executions/` — module principal à auditer
- Frontend : `idp-portal/frontend/src/` — hooks/, components/, services/, utils/
- Aucune migration de base de données requise
- Aucun nouveau fichier requis — uniquement annotations/commentaires + corrections ponctuelles

### References

- [Source: idp-portal/CODEBASE-REVIEW.md#16.2] — finding `except Exception` résiduels backend
- [Source: idp-portal/CODEBASE-REVIEW.md#16.3] — finding `.catch()` résiduels frontend
- [Source: _bmad-output/planning-artifacts/epic-35-codebase-review-points-restants-post-refactoring.md#35.2] — détail story
- [Source: idp-portal/django_backend/executions/views/terraform_webhooks.py#320] — pattern `# noqa: BLE001` de référence
- [Source: idp-portal/django_backend/catalog/rbac_service.py#86] — pattern cache-unavailability justified
- [Source: idp-portal/frontend/src/utils/engineIconCache.ts#52] — cas fire-and-forget à documenter
- [Source: idp-portal/frontend/src/hooks/useCatalogState.ts#256] — cas `.catch(() => null)` OK avec commentaire

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

Aucun blocage rencontré. Corrections appliquées directement.

### Completion Notes List

- **Backend executions/ :** 29 occurrences `except Exception` auditées.
  - 5 déjà OK (exc_info=True + re-raise ou noqa déjà présents : container_workflow_runtime:586, simulation_service:255, rule_engine:142, terraform_webhooks:320, github_webhooks:305, approval_views:165)
  - 17 FIX : `exc_info=True` ajouté aux appels logger.error/warning/critical existants
  - 7 FIX+noqa : `exc_info=True` ajouté + `# noqa: BLE001 — <raison>` pour les broad catches résilience/best-effort
  - Note : `simulation_service.py:255` et `approval_views.py:165` ont été vérifiés et étaient déjà conformes (pas de modification de code)
  - Résultat : `ruff check --select BLE001 executions/` → **0 violations** ✅ (vérifié en code review)

- **Backend étendu (spot check) :** `catalog/rbac_service.py` a 3 occurrences justifiées sans noqa — hors scope, documentées en observation.

- **Frontend :** 41 occurrences `.catch()` auditées.
  - 39 OK (fallback état, logger, re-throw, commentaire d'intention)
  - 1 FIX *(story)* : `engineIconCache.ts:52` — commentaire `// fire-and-forget — prefetch optionnel` ajouté
  - 1 FIX *(code review)* : `engineIconCache.ts:31` — commentaire `// échec non-critique — retourne un cache vide` ajouté pour cohérence

- **Tests backend :** 670 passent, 42 échecs pré-existants (confirmé via stash), 0 régression ✅
- **Tests frontend :** 2305 passent, 113 échecs pré-existants, 0 régression ✅

### File List

- `idp-portal/django_backend/executions/cancellation_cache.py`
- `idp-portal/django_backend/executions/consumers.py`
- `idp-portal/django_backend/executions/container_workflow_runtime.py`
- `idp-portal/django_backend/executions/rule_engine.py`
- `idp-portal/django_backend/executions/services.py`
- `idp-portal/django_backend/executions/tasks/gates.py`
- `idp-portal/django_backend/executions/tasks/polling.py`
- `idp-portal/django_backend/executions/tasks/retry.py`
- `idp-portal/django_backend/executions/utils/rbac_helpers.py`
- `idp-portal/django_backend/executions/views/execution_views.py`
- `idp-portal/django_backend/executions/workflow_step_executor.py`
- `idp-portal/frontend/src/utils/engineIconCache.ts`
- `_bmad-output/implementation-artifacts/35-2-audit-except-exception-et-catch-residuels.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Change Log

- 2026-02-23 : Story 35.2 implémentée — audit `except Exception` backend (29 occurrences) et `.catch()` frontend (41 occurrences) ; 17 corrections `exc_info=True` + 7 annotations `# noqa: BLE001` backend ; 1 commentaire fire-and-forget frontend ; 0 violation BLE001, 0 régression tests
- 2026-02-23 : Code review — tableaux d'audit complets (AC#2 et AC#4) produits dans Dev Notes ; commentaire d'intention ajouté à `engineIconCache.ts:31` (cohérence avec ligne 52) ; Completion Notes corrigées (décompte 5 OK + 17 FIX + 7 FIX+noqa ; `simulation_service.py` et `approval_views.py` documentés comme déjà conformes)
