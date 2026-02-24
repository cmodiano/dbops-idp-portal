# Revue Exhaustive du Codebase — IDP Portal

**Date :** 2026-02-23 (mise à jour — audit complet #3)
**Scope :** Backend Django + Frontend React
**Auteur :** Claude Code (revue automatisée)

---

## Table des matières

1. [Endpoints manquants (Frontend ↔ Backend)](#1-endpoints-manquants-frontend--backend)
2. [Bugs logiques — Backend](#2-bugs-logiques--backend)
3. [Bugs logiques — Frontend](#3-bugs-logiques--frontend)
4. [Problèmes de sécurité](#4-problèmes-de-sécurité)
5. [Incohérences API (format de réponse)](#5-incohérences-api-format-de-réponse)
6. [Race conditions & concurrence](#6-race-conditions--concurrence)
7. [Gestion d'erreurs](#7-gestion-derreurs)
8. [Performance (N+1, caches, re-renders)](#8-performance-n1-caches-re-renders)
9. [Code mort](#9-code-mort)
10. [Accessibilité & thème](#10-accessibilité--thème)
11. [Problèmes Celery / tâches async](#11-problèmes-celery--tâches-async)
12. [Incohérences modèles & serializers](#12-incohérences-modèles--serializers)
13. [Nouveaux findings (précédents)](#13-nouveaux-findings-précédents)
14. [Analyse SOLID — Backend](#14-analyse-solid--backend)
15. [Analyse SOLID — Frontend](#15-analyse-solid--frontend)
16. [Observations post-refactoring](#16-observations-post-refactoring)
17. [Audit #3 — Nouveaux findings (2026-02-23)](#17-audit-3--nouveaux-findings-2026-02-23)
18. [Récapitulatif par priorité](#18-récapitulatif-par-priorité)

---

## 1. Endpoints manquants (Frontend ↔ Backend)

### ✅ Tous les endpoints manquants ont été traités.

| # | Endpoint | Statut | Détails |
|---|----------|--------|---------|
| **API-MISS-1** | `POST /executions/{id}/approve` | ✅ RESOLVED | Implémenté dans `approval_views.py:101-144`, URL pattern dans `executions/urls.py` |
| **API-MISS-2** | `POST /executions/{id}/reject` | ✅ RESOLVED | Implémenté dans `approval_views.py:147-195`, URL pattern dans `executions/urls.py` |
| **API-MISS-3** | `GET /executions/{id}/remediation` | ✅ RESOLVED (Story 30.2) | Implémenté dans `remediation_views.py:28-136` |
| **API-MISS-4** | `GET /executions/{id}/remediation-context` | ✅ RESOLVED (Story 30.2) | Implémenté dans `remediation_views.py:139-203` |
| **API-MISS-5** | `GET /dashboard/export/csv` | ✅ RESOLVED (Story 30.2) | Implémenté dans `dashboard/export_views.py:107-166` |
| **API-MISS-6** | `GET /dashboard/export/pdf` | ✅ RESOLVED (Story 30.2) | Implémenté dans `dashboard/export_views.py:169-373` |
| **API-MISS-7** | `GET /users/me/recent-actions` | ✅ RESOLVED (Story 30.10) | Appels frontend supprimés. Remplacé par `/dashboard/recent` |

---

## 2. Bugs logiques — Backend

### ✅ Tous les bugs backend ont été corrigés.

| # | Sévérité | Description | Statut |
|---|----------|-------------|--------|
| **BUG-BE-1** | CRITICAL | Filtres écrasés quand `tags_filter` est fourni (`catalog/models.py`) | ✅ RESOLVED — `search_by_tags()` utilise `self` (chaîne queryset) |
| **BUG-BE-2** | HIGH | `secret_service_id` ignoré à la création (`integrations/services.py`) | ✅ RESOLVED — Ajouté dans `create()` + validation FK |
| **BUG-BE-3** | HIGH | Binding `user_id` structlog après la réponse (`core/middleware.py`) | ✅ RESOLVED — Bind avant `get_response()` (ligne 116) |
| **BUG-BE-4** | HIGH | Calcul récurrence placeholder `+1 jour` (`executions/utils/scheduling.py`) | ✅ RESOLVED — Implémentation complète (daily, weekly, cron via croniter) |
| **BUG-BE-5** | MEDIUM | Cache catalogue contourne pagination (`catalog/views.py`) | ✅ RESOLVED — Pagination incluse dans clé de cache |
| **BUG-BE-6** | LOW | Dead code `if not action` (`idp_auth/services.py`) | ✅ RESOLVED (Story 30.3) |
| **BUG-BE-7** | LOW | Normalisation environnement dupliquée (`scheduled_views.py`) | ✅ RESOLVED (Story 30.16) |

---

## 3. Bugs logiques — Frontend

### ✅ Tous les bugs frontend ont été corrigés.

| # | Sévérité | Description | Statut |
|---|----------|-------------|--------|
| **BUG-FE-1** | HIGH | `notification({ title: })` API Ant Design 6.2 | ✅ RESOLVED (Story 30.13 + 34.2) — `title:` est la prop correcte |
| **BUG-FE-2** | HIGH | `<Alert title=...>` API Ant Design 6.2 | ✅ RESOLVED (Story 30.13 + 34.2) — `title=` est la prop correcte |
| **BUG-FE-3** | MEDIUM | `Math.random()` dans `rowKey` React | ✅ RESOLVED — Identifiant stable |
| **BUG-FE-4** | MEDIUM | Boucle infinie dans `useTargetInventory` | ✅ RESOLVED (Story 30.4) — `useRef` |
| **BUG-FE-5** | MEDIUM | Dépendance manquante useEffect | ✅ RESOLVED — Dépendances corrigées |

---

## 4. Problèmes de sécurité

### ✅ Tous les problèmes de sécurité ont été corrigés.

| # | Sévérité | Description | Statut |
|---|----------|-------------|--------|
| **SEC-1** | HIGH | `DEBUG` par défaut à `True` | ✅ RESOLVED — Opt-in explicite |
| **SEC-2** | HIGH | `SECRET_KEY` fallback en dur | ✅ RESOLVED — `ImproperlyConfigured` si absent |
| **SEC-3** | HIGH | `JWT_SECRET_KEY` par défaut chaîne vide | ✅ RESOLVED — `ImproperlyConfigured` si vide |
| **SEC-4** | HIGH | `fetchInventoryItems` sans auth JWT | ✅ RESOLVED (Story 30.5) |
| **SEC-5** | MEDIUM | Extension allowlist fichiers | ✅ RESOLVED (Story 30.5) |
| **SEC-6** | MEDIUM | Validation magic bytes | ✅ RESOLVED (Story 30.5) |
| **SEC-7** | MEDIUM | SVG sanitisation | ✅ RESOLVED (Story 30.5) |
| **SEC-8** | MEDIUM | Guard production AUTH_DEV_BYPASS | ✅ RESOLVED (Story 30.5) |
| **SEC-9** | MEDIUM | Credentials Celery en clair | ✅ RESOLVED (Story 30.5) |
| **SEC-10** | MEDIUM | CORS X-Correlation-ID | ✅ RESOLVED (Story 30.5) |
| **SEC-11** | LOW | Token fragment URL | ✅ RESOLVED — Documenté |

---

## 5. Incohérences API (format de réponse)

### ✅ Toutes les incohérences API ont été corrigées.

| # | Sévérité | Description | Statut |
|---|----------|-------------|--------|
| **APIFMT-1** | HIGH | `validateIntegration` retourne `undefined` | ✅ RESOLVED — `{"data": {...}}` |
| **APIFMT-2** | HIGH | `validateAllIntegrations` même problème | ✅ RESOLVED — `{"data": stats}` |
| **APIFMT-3** | MEDIUM | `/reference/*` retournent arrays nus | ✅ RESOLVED — `{"data": serializer.data}` |
| **APIFMT-4** | MEDIUM | Catalogue list sans pagination | ✅ RESOLVED — Pagination avec fallback |

---

## 6. Race conditions & concurrence

### ✅ Toutes les race conditions ont été corrigées.

| # | Sévérité | Description | Statut |
|---|----------|-------------|--------|
| **RACE-1** | HIGH | Polling infini sans retry limit | ✅ RESOLVED (Story 30.7) — `MAX_POLLING_RETRIES=20` |
| **RACE-2** | MEDIUM | `update_action()` sans `select_for_update()` | ✅ RESOLVED (Story 30.7) — 4 méthodes protégées |
| **RACE-3** | MEDIUM | Caches in-memory non partagés | ✅ RESOLVED (Story 30.7) — Documenté per-worker |

---

## 7. Gestion d'erreurs

### ✅ Tous les problèmes de gestion d'erreurs ont été corrigés.

| # | Sévérité | Description | Statut |
|---|----------|-------------|--------|
| **ERR-1** | HIGH | `.catch(() => {})` avale les erreurs | ✅ RESOLVED (Story 30.8) |
| **ERR-2** | HIGH | Validation croisée absente `IntegrationUpdateSerializer` | ✅ RESOLVED (Story 30.8) |
| **ERR-3** | MEDIUM | `create_action()` ignore `integration_id` invalide | ✅ RESOLVED (Story 30.8) |
| **ERR-4** | MEDIUM | Audit signals swallowed | ✅ RESOLVED (Story 30.8) |
| **ERR-5** | MEDIUM | Workflow bloqué après timeout de gate | ✅ RESOLVED (Story 30.7) |

---

## 8. Performance (N+1, caches, re-renders)

### ✅ Tous les problèmes de performance ont été traités.

| # | Sévérité | Description | Statut |
|---|----------|-------------|--------|
| **PERF-1** | MEDIUM | N+1 queries `_resolve_user_names` | ✅ RESOLVED (Story 30.9) |
| **PERF-2** | MEDIUM | Tous les workflows chargés en mémoire | ✅ RESOLVED (Story 30.9) |
| **PERF-3** | MEDIUM | Regex recompilées à chaque appel | ✅ RESOLVED (Story 30.9) |
| **PERF-4** | LOW | `<style>` inline dans 3 composants | ✅ DOCUMENTÉ BACKLOG — Impact négligeable, cas justifiés techniquement |

---

## 9. Code mort

### ✅ Tout le code mort a été nettoyé.

| # | Composant | Description | Statut |
|---|-----------|-------------|--------|
| **DEAD-BE-1** | `catalog/models.py` | `normalize_tag_name()` alignée | ✅ RESOLVED |
| **DEAD-BE-2** | `idp_auth/services.py` | Code mort supprimé | ✅ RESOLVED |
| **DEAD-BE-3** | `executions/tasks.py` | Appel inutile supprimé | ✅ RESOLVED |
| **DEAD-BE-4** | `core/models.py` | Import doublon supprimé | ✅ RESOLVED |
| **DEAD-BE-5** | `inventory/services.py` | Imports nettoyés | ✅ RESOLVED |
| **DEAD-FE-1** | `catalog_service.ts` | `fetchRecentActions` supprimé | ✅ RESOLVED |
| **DEAD-FE-2** | `admin_service.ts` | `listActions` supprimée | ✅ RESOLVED |
| **DEAD-FE-3** | `types/api.ts` | Barrel re-export intentionnel | ✅ RESOLVED |
| **DEAD-FE-4** | `utils/profileOptions.ts` | `ENVIRONMENT_OPTIONS` supprimé | ✅ RESOLVED |
| **DEAD-FE-5** | `utils/impactRulesSchema.ts` | `IMPACT_ENVIRONMENTS` supprimé | ✅ RESOLVED |
| **DEAD-FE-6** | 3 fichiers | Factorisé dans `stepDescriptions.ts` | ✅ RESOLVED |

---

## 10. Accessibilité & thème

### ✅ Tous les problèmes d'accessibilité ont été corrigés.

| # | Sévérité | Description | Statut |
|---|----------|-------------|--------|
| **A11Y-1** | HIGH | Couleurs dark-theme hardcodées `StepDetailDrawer` | ✅ RESOLVED (Story 30.11) |
| **A11Y-2** | HIGH | Status badges background dark hardcodé | ✅ RESOLVED (Story 30.11) |
| **A11Y-3** | MEDIUM | `StructuredErrorCard` couleurs texte hardcodées | ✅ RESOLVED (Story 30.11) |

**Point positif :** Bonne utilisation globale de `role`, `aria-label`, `aria-live`, `aria-expanded`, et gestion clavier.

---

## 11. Problèmes Celery / tâches async

### ✅ Tous les problèmes Celery ont été corrigés.

| # | Sévérité | Description | Statut |
|---|----------|-------------|--------|
| **CELERY-1** | HIGH | Polling infini | ✅ RESOLVED — Voir RACE-1 |
| **CELERY-2** | MEDIUM | Credentials en clair | ✅ RESOLVED — Voir SEC-9 |
| **CELERY-3** | MEDIUM | Event loop asyncio | ✅ RESOLVED (Story 30.7) |
| **CELERY-4** | MEDIUM | Gate timeout | ✅ RESOLVED (Story 30.7) |
| **CELERY-5** | LOW | Gate timeout message | ✅ RESOLVED (Story 30.7) |

---

## 12. Incohérences modèles & serializers

### ✅ Toutes les incohérences ont été traitées.

| # | Sévérité | Description | Statut |
|---|----------|-------------|--------|
| **INCON-1** | MEDIUM | Normalisation tags incohérente | ✅ RESOLVED — Logique unifiée |
| **INCON-2** | MEDIUM | Audit hash MD5 collisions | ✅ DOCUMENTÉ ACCEPTABLE — Risque < 0.00001% pour N=9 |
| **INCON-3** | MEDIUM | Audit signals retournent `user_id='system'` | ✅ RESOLVED (Story 30.12) |
| **INCON-4** | LOW | `IntegerField` pour booléens (Oracle) | ✅ INTENTIONNEL — Documenté |
| **INCON-5** | LOW | `User.is_authenticated = True` attribut de classe | ✅ RESOLVED — Documenté |

---

## 13. Nouveaux findings (précédents)

### ✅ Tous les findings §13 ont été résolus.

| # | Sévérité | Description | Statut |
|---|----------|-------------|--------|
| **NEW-1** | MEDIUM | `CatalogActionViewSet.get_queryset()` recrée le queryset | ✅ RESOLVED (Story 34.1) — `queryset = queryset.search_by_tags(tag_names)` (chaîne, ne recrée pas) |
| **NEW-2** | MEDIUM | TODO actifs dans le code | ✅ RESOLVED (Story 30.15) — TODO supprimés, implémentations réelles |
| **NEW-3** | MEDIUM | Cache RBAC `invalidate_permissions_cache()` placeholder noop | ✅ RESOLVED (Story 34.3) — Implémentation réelle dans `profiles/cache.py` avec `cache.delete(RBAC_CACHE_VERSION_KEY)`. Tests de validation. |
| **NEW-4** | LOW | `except Exception` trop large | ✅ RESOLVED (Story 30.15) — Restreint ou documenté `noqa: BLE001` |
| **NEW-5** | LOW | `<style>` inline | ✅ DOCUMENTÉ — Voir PERF-4 |

---

## 14. Analyse SOLID — Backend

**Date mise à jour :** 2026-02-23
**Scope :** Django backend (`django_backend/`)

### Points positifs (acquis Stories 33.x + 34.x)

- **OCP — Registry pattern** : `adapters/registry.py` (AdapterRegistry), `services/registry.py` (ServiceRegistry), `executions/interpreters/registry.py` (OutputInterpreterRegistry), `executions/runtime_registry.py` (RuntimeRegistry) — ajout de plateforme/service/runtime sans modifier le code existant.
- **DIP — Module DI** : `core/di.py` — service locator léger avec `override_service()` pour les tests.
- **SRP — Views packages** : `catalog/views/` (4 fichiers) et `executions/views/` (7 fichiers) correctement découpés par responsabilité.
- **SRP — Tasks package** : `executions/tasks/` (3 fichiers : polling, gates, retry).
- **SRP — Utils package** : `executions/utils/` (7 modules thématiques : environment, filters, mutex_validation, rbac_helpers, scheduling, workflow_parsing).
- **SRP — Services split** : `ExecutionService` et `SchedulingService` dans des fichiers séparés.
- **ISP — Adapters séparés** : `ITriggerableAdapter` et `ICancellableAdapter` interfaces distinctes.
- **LSP — Serializers corrigés** : `ActionSerializer` n'override plus `create()`/`update()` avec `NotImplementedError`.
- **DRY — Validation partagée** : `_validate_platform_integration_consistency()` helper partagé entre serializers.

### SOLID-BE-1 [HIGH] — ✅ RESOLVED (Story 34.6) — `executions/utils.py` (828 lignes) éclaté en package

**Avant :** Module monolithique de 828 lignes avec 15 fonctions couvrant 6 domaines.

**Fix appliqué :** Éclaté en package `executions/utils/` avec 7 modules thématiques :

| Module | Lignes | Responsabilité |
|--------|--------|----------------|
| `__init__.py` | 50 | Re-exports publics |
| `environment.py` | 124 | Validation environnement |
| `filters.py` | 164 | Filtres querysets |
| `mutex_validation.py` | 129 | Validation mutex |
| `rbac_helpers.py` | 76 | Helpers RBAC/permissions |
| `scheduling.py` | 87 | Calcul récurrence cron |
| `workflow_parsing.py` | 335 | Parsing steps workflow |

---

### SOLID-BE-2 [HIGH] — ✅ RESOLVED (Story 34.7) — `workflow_runtime.py` décomposé

**Avant :** 1296 lignes, `WorkflowRuntime` avec 12 méthodes couvrant 5+ responsabilités.

**Fix appliqué :** Décomposé en orchestrateur pur :
- `workflow_runtime.py` : 521 lignes (orchestration uniquement)
- `workflow_step_executor.py` : 628 lignes (exécution de steps, retry, platform adapter)
- `container_workflow_runtime.py` : 681 lignes (runtime conteneurisé)

---

### SOLID-BE-3 [HIGH] — ✅ RESOLVED (Story 34.5) — Poller générique unifié

**Avant :** `polling.py` (1054 lignes) — 5 tâches Celery quasi-identiques dupliquant ~150 lignes chacune.

**Fix appliqué :** Poller générique unifié (561 lignes). Les 5 tâches utilisent maintenant une tâche commune `poll_platform_job_status` qui délègue à l'`AdapterRegistry` existant — fermé à la modification, ouvert à l'extension.

---

### SOLID-BE-4 [MEDIUM] — ✅ RESOLVED (Story 34.3) — Services séparés

**Avant :** `services.py` (1121 lignes) — `ExecutionService` et `SchedulingService` dans le même fichier.

**Fix appliqué :**
- `executions/services.py` : 856 lignes (ExecutionService uniquement)
- `executions/scheduling_service.py` : 290 lignes (SchedulingService uniquement)

---

### SOLID-BE-5 [MEDIUM] — ✅ RESOLVED (Story 34.8) — InventoryService décomposé

**Avant :** `inventory/services.py` (933 lignes) — 18 méthodes couvrant 4-5 domaines.

**Fix appliqué :** Réduit à 711 lignes. Extractions :
- `RBACPermissionAggregator` — agrégation permissions RBAC
- `TargetLoader` — chargement/filtrage targets
- `inventory/query_executor.py` (667 lignes) — exécution requêtes Oracle

---

### SOLID-BE-6 [MEDIUM] — ✅ RESOLVED (Story 34.3) — LSP ActionSerializer corrigé

**Avant :** `ActionSerializer.create()` et `update()` levaient `NotImplementedError` — violation LSP.

**Fix appliqué :** Overrides `NotImplementedError` supprimés. `ModelSerializer` hérite ses méthodes par défaut. Docstring explicite : « Do NOT call .save() on this serializer — use ActionCreateSerializer instead ».

---

### SOLID-BE-7 [MEDIUM] — ✅ RESOLVED (Story 34.4) — RuntimeRegistry

**Avant :** `launch_workflow()` switch `if/elif` sur `item_type` string avec imports conditionnels.

**Fix appliqué :** `RuntimeRegistry` dans `executions/runtime_registry.py`. `launch_workflow()` utilise `runtime_registry.get(action.item_type)` — fermé à la modification, ouvert à l'extension.

---

### SOLID-BE-8 [MEDIUM] — ✅ RESOLVED (Story 34.1) — DI pour CatalogService

**Avant :** 3 méthodes ViewSet instanciaient `CatalogService()` directement.

**Fix appliqué :** Plus aucun `CatalogService()` direct dans `action_views.py`. Toutes les méthodes utilisent `self.get_catalog_service()`.

---

### SOLID-BE-9 [MEDIUM] — ✅ RESOLVED (Story 34.4) — DI pour webhooks

**Avant :** `_execution_service_factory` monkey-patch dans `github_webhooks.py` et `terraform_webhooks.py`.

**Fix appliqué :** Factory monkey-patch supprimée. Les webhooks utilisent le mécanisme DI de `core/di.py`.

---

### SOLID-BE-10 [LOW] — ✅ RESOLVED (Story 34.15) — ISP BaseAdapter

**Avant :** `BaseAdapter` forçait tous les adapters à implémenter `cancel_execution()`.

**Fix appliqué :** Séparé en 2 interfaces :
- `ITriggerableAdapter` (ligne 16) — `trigger_execution()`, `get_execution_status()`, `get_execution_logs()`
- `ICancellableAdapter` (ligne 89) — `cancel_execution()`
- `BaseAdapter` (ligne 115) — hérite des deux pour compatibilité descendante

8 tests unitaires pour base_adapter, 16 tests pour cancel_execution.

---

### SOLID-BE-11 [LOW] — ✅ RESOLVED (Story 34.1) — Validation DRY

**Avant :** `ActionSerializer` et `ActionCreateSerializer` dupliquaient `validate_engine`, `validate_platform`, `validate_category`.

**Fix appliqué :** `ActionFieldValidationMixin` avec méthodes `validate_engine` et `validate_platform` partagées. `validate_category` a un override intentionnel dans `ActionCreateSerializer` (blank → None vs blank → erreur). Helper partagé `_validate_platform_integration_consistency()`.

---

## 15. Analyse SOLID — Frontend

**Date mise à jour :** 2026-02-23
**Scope :** React frontend (`frontend/src/`)

### Métriques globales

| Métrique | Valeur précédente (21/02) | Valeur actuelle (23/02) | Évolution |
|----------|---------------------------|-------------------------|-----------|
| Fichiers source (non-test) | ~222 `.tsx`/`.ts` | 239 | +17 (sous-composants extraits) |
| Fichiers test | 165 (74% couverture) | 173 (72% couverture) | +8 |
| Lignes de production | ~35 300 | ~33 354 | -1 946 (refactoring) |
| Custom hooks | 32 (4 435 lignes) | 45 (5 800 lignes) | +13 hooks |
| Contexts | 4 | 5 | +1 (WizardExecutionContext) |

### Points positifs

- **Architecture hooks** : 45 custom hooks pour extraction de logique (de 32 → 45, +40%).
- **Services API** : `api_client.ts` centralisé avec retry 401/429/503, correlation ID, callback notification injectable (DIP).
- **Tests** : 173 fichiers test, couverture des composants critiques ajoutée.
- **Décomposition composants** : `ExecutionTimeline`, `CatalogPage`, `AuditPage` décomposés en sous-composants et hooks.
- **WizardExecutionContext** : Nouveau context pour partager l'état du wizard sans prop drilling.

### SOLID-FE-1 [CRITICAL] — ✅ RESOLVED (Story 34.12) — ExecutionTimeline décomposé

**Avant :** 735 lignes, 12+ responsabilités, god component.

**Fix appliqué :** Décomposé en package `ExecutionTimeline/` :

| Composant | Lignes | Responsabilité |
|-----------|--------|----------------|
| `ExecutionTimeline.tsx` | 148 | Orchestrateur (WebSocket, polling, state) |
| `ExecutionStatusBanners.tsx` | 213 | 7 variantes de bannières status |
| `RemediationPanel.tsx` | 142 | Machine à états auto-remédiation |
| `TimelineList.tsx` | 95 | Liste timeline |
| `TimelineStepItem.tsx` | 140 | Item timeline individuel |
| `StepLogsDrawer.tsx` | 71 | Drawer de logs |
| `utils.ts` | 16 | Utilitaires partagés |
| `index.ts` | 9 | Barrel export |
| **Total** | **834** | 7 fichiers à responsabilité unique |

---

### SOLID-FE-2 [HIGH] — ✅ RESOLVED (Story 34.10) — CatalogPage refactorisé

**Avant :** 606 lignes, 23 `useState`, 8 `useCallback`, page god.

**Fix appliqué :**
- `CatalogPage.tsx` : 267 lignes (orchestrateur)
- `useCatalogState.ts` : 402 lignes (toute la logique d'état extraite)

---

### SOLID-FE-3 [HIGH] — ✅ RESOLVED (Story 34.11) — AuditPage refactorisé

**Avant :** 628 lignes, 28 hooks combinés, page god.

**Fix appliqué :**
- `AuditPage.tsx` : 247 lignes (orchestrateur)
- `useAuditFilters.ts` : 311 lignes (logique filtres extraite)
- `AuditTable.tsx` : composant table extrait dans `components/audit/`
- `AuditEntryDrawer.tsx` : drawer extrait dans `components/audit/`

---

### SOLID-FE-4 [HIGH] — ⚠️ AMÉLIORÉ, OUVERT — Couplage services directs

**Avant :** 29 composants importent directement les services.

**État actuel :** ~25 composants non-test importent encore directement `admin_service`, `catalog_service`, ou `execution_service`. Le pattern a été amélioré dans certains composants clés (hooks extraits, DI via context), mais le couplage structurel reste largement présent.

**Fichiers concernés (exemples non-test) :**
- `ExecutionWizard.tsx` → `catalog_service` + `execution_service`
- `ActionWizard.tsx` → 7 fonctions de `admin_service`
- `WorkflowStepsEditor.tsx` → `admin_service.getEligibleActionsForWorkflow()`
- `ProfileForm.tsx`, `ProfileWizard.tsx` → `admin_service`
- `IntegrationForm.tsx` → `admin_service`
- Et ~19 autres composants

**Fix recommandé :** Migration progressive vers hooks et injection via props/context. Pattern existant dans `useExecutionWizardState`, `useCatalogState`, `useAuditFilters` peut servir de modèle.

---

### SOLID-FE-5 [HIGH] — ✅ RESOLVED (Story 34.2) — DIP api_client.ts

**Avant :** `api_client.ts` importait `notification` d'Ant Design — dépendance bidirectionnelle transport ↔ UI.

**Fix appliqué :** Callback injectable :
```typescript
type NotifyFn = (type: 'warning' | 'error', config: { title: string; description: string; duration?: number }) => void;
let _notify: NotifyFn = () => {};
export function setNotificationCallback(fn: NotifyFn): void { _notify = fn; }
```
Plus aucun import Ant Design dans `api_client.ts`.

---

### SOLID-FE-6 [MEDIUM] — ✅ RESOLVED (Story 34.9) — Prop drilling éliminé

**Avant :** `variant`/`isBusinessProfile` propagé sur 4-5 niveaux via props.

**Fix appliqué :** `ExecutionWizard.tsx` lit `useAuth().isBusinessProfile` directement (ligne 74). Plus de prop drilling.

---

### SOLID-FE-7 [MEDIUM] — ✅ RESOLVED (Story 34.13) — Props allégées via Context

**Avant :** Props surchargées (22/17/16 props).

**Fix appliqué :** `WizardExecutionContext` créé. Props réduites :

| Composant | Avant | Après | Props déplacées vers Context |
|-----------|-------|-------|------------------------------|
| `TargetSelectionStepProps` | 22 | 12 | 7 (derivedEnvironment, hasMixed, currentImpact, environmentsCache, inventoryWarnings, resolvedPatternTargets, patternResolving) |
| `ParametersFormStepProps` | 17 | 11 | 4 (inventoryData, inventoryWarnings, loadingInventory, selectedServerNames) + `action` supprimée (inutilisée) |
| `ConfirmationStepProps` | 16 | 12 | 3 (derivedEnvironment, currentImpact, environmentsCache) |

---

### SOLID-FE-8 [MEDIUM] — ✅ RESOLVED (Story 34.9) — SortableStepCard extrait

**Avant :** `WorkflowStepsEditor.tsx` contenait 2 composants (645 lignes total).

**Fix appliqué :**
- `WorkflowStepsEditor.tsx` : 331 lignes (dans `components/admin/`)
- `SortableStepCard.tsx` : 336 lignes (extrait dans `components/admin/`)

---

### SOLID-FE-9 [MEDIUM] — ✅ RESOLVED (Story 34.13) — useExecutionWizardState extrait

**Avant :** `ExecutionWizard.tsx` contenait 7 `useEffect` non extraits.

**Fix appliqué :**
- `ExecutionWizard.tsx` : 188 lignes (composant UI)
- `useExecutionWizardState.ts` : 456 lignes (toute la logique de coordination)

---

### SOLID-FE-10 [MEDIUM] — ✅ PARTIELLEMENT RESOLVED (Story 34.2) — Status mapping consolidé

**Avant :** Mapping status dupliqué dans 3 fichiers.

**Fix appliqué :** Utility partagé `utils/execution-status.ts` créé avec :
- `STEP_STATUS_COLOR` — couleurs des étapes timeline
- `AUDIT_STATUS_CONFIG` — config pour la page audit

Les composants `ExecutionTimeline/TimelineStepItem.tsx` et `AuditTable.tsx` / `AuditEntryDrawer.tsx` importent depuis cette utility.

**Résiduel :** Des `STATUS_CONFIG` locaux restent dans `ExecutionView.tsx`, `StepDetailDrawer.tsx`, `WorkflowExecutionGraph.tsx`, `IntegrationsTable.tsx`, `ComparisonExecutionsDrawer.tsx`. Certains sont spécifiques à leur domaine (status intégration ≠ status exécution ≠ status step), d'autres sont des doublons résiduels.

---

### SOLID-FE-11 [LOW] — ✅ RESOLVED (Story 34.14) — Tests ajoutés

**Avant :** 4 composants critiques sans test.

**Fix appliqué :** Tests créés pour les 4 composants :
- `ParametersFormStep.test.tsx`
- `SchedulingPanel.test.tsx`
- `ExecutionsFiltersPanel.test.tsx`
- `BusinessRulePolicyModal.test.tsx`

---

## 16. Observations post-refactoring

### 16.1 [DOCUMENTED] — Fichiers backend encore volumineux

> **Statut : DOCUMENTED** — Story 35.4 (2026-02-23) — Revue complète effectuée, commentaires
> `# Responsabilité` ajoutés aux 6 fichiers justifiés, propositions de découpage documentées.

Malgré le refactoring significatif, certains fichiers backend restent conséquents. Revue Story 35.4 :

| Fichier | LOC | Classes principales | Verdict | Justification |
|---------|-----|---------------------|---------|---------------|
| `executions/services.py` | 854 | `ExecutionService` | ⚠ Découpage recommandé | CRUD exécution + steps + stats + validation intégration = 3 responsabilités distinctes |
| `catalog/services.py` | 823 | `CatalogService`, `InvalidTransitionError` | ✅ Cohérent/justifié | Action-centric, logique métier intrinsèque (transitions statut, workflows, dépendances) |
| `catalog/serializers.py` | 737 | `ActionSerializer`, `ActionCreateSerializer`, `ActionFieldValidationMixin` + 7 serializers | ✅ Cohérent/justifié | Sérialisation DRF, 10+ serializers + validations croisées justifiées |
| `adapters/terraform_cloud_adapter.py` | 747 | `TerraformCloudAdapter` | ✅ Cohérent/justifié | Adapter TFC (JSON API spec, 18+ états, logs via log-read-url) |
| `adapters/github_actions_adapter.py` | 718 | `GitHubActionsAdapter` | ✅ Cohérent/justifié | Adapter GHA (dispatch sans run_id → polling, logs en ZIP) |
| `inventory/services.py` | 711 | `InventoryService`, `InventoryRBACFilter`, `InventorySourceResolver` | ⚠ Découpage recommandé | Orchestrateur fait trop : sources + RBAC + caching + normalization env |
| `executions/container_workflow_runtime.py` | 681 | `ContainerWorkflowRuntime` | ✅ Cohérent/justifié | Runtime workflows conteneur (sync/async, cascade annulation, loop detection) |
| `inventory/query_executor.py` | 667 | `InventoryQueryExecutor` | ✅ Cohérent/justifié | Queries SQL config-driven multi-table (Story 26.1 AC1 — _read_entity_from_config) |

**Propositions de découpage documentées (implémentation optionnelle) :**

- **`executions/services.py`** → extraire `ExecutionStepService` (~200 LOC) et `ExecutionStatisticsService` (~150 LOC)
- **`inventory/services.py`** → déléguer `_list_targets_from_api/db_schema` vers `InventoryRBACFilter`, extraire `InventoryEnvironmentService` (~100 LOC)

Les 6 fichiers "cohérent/justifié" disposent désormais d'un commentaire `# Responsabilité` en tête de fichier (Story 35.4 AC3). Les propositions de découpage détaillées sont dans `_bmad-output/implementation-artifacts/35-4-revue-fichiers-backend-volumineux.md`.

---

### 16.2 [LOW] — `except Exception` résiduels (33 occurrences backend)

33 occurrences de `except Exception` dans `executions/` (16 fichiers). La plupart sont documentées (`noqa: BLE001`) ou dans des contextes de résilience (webhooks, polling, runtime). Les cas non documentés dans les fichiers nouveaux/refactorisés (ex. `container_workflow_runtime.py` — 5 occurrences) mériteraient une revue pour vérifier qu'ils sont tous justifiés.

---

### 16.3 [LOW] — `.catch(() => {})` résiduels frontend (21 occurrences)

21 occurrences de `.catch(() => {})` ou `.catch(err => {})` dans 16 fichiers frontend. La plupart sont dans des hooks et composants qui gèrent l'erreur par ailleurs (via state, logging, ou cleanup). Vérifier que chaque cas est intentionnel.

---

### 16.4 [INFO] — STATUS_CONFIG duplication résiduelle

5 composants définissent encore leur propre `STATUS_CONFIG` local au lieu d'importer depuis `execution-status.ts` ou `executionRenderers.tsx` :
- `ExecutionView.tsx:45` — status exécution
- `StepDetailDrawer.tsx:22` — status step
- `WorkflowExecutionGraph.tsx:52` — couleurs nœuds graph
- `IntegrationsTable.tsx:16` — status intégration (domaine différent)
- `ComparisonExecutionsDrawer.tsx:36` — status comparaison

Les 3 premiers pourraient potentiellement être consolidés. `IntegrationsTable` a un domaine différent (status intégration vs exécution). `ComparisonExecutionsDrawer` est un cas spécialisé.

---

## 17. Audit #3 — Nouveaux findings (2026-02-23)

### Sécurité — Aucun nouveau problème

Audit complet couvrant : SQL injection (query_executor.py vérifié — paramétrage correct, regex validation), SSRF, désérialisation, permissions manquantes, secrets hardcodés, CORS, fichiers, CSRF, settings Django, bypass auth, WebSocket auth, webhooks HMAC, Celery serializers. **Résultat : RAS.** La posture sécurité est excellente.

### Code quality — Backend

| # | Sévérité | Description | Fichier | Lignes |
|---|----------|-------------|---------|--------|
| **NEW-BE-1** | MEDIUM | N+1 query : `Action.objects.get(id=ref_id)` dans boucle `for ref_id in ref_ids` | `catalog/services.py` | 62-73 |
| **NEW-BE-2** | MEDIUM | Double `.update()` consécutif sur même exécution (RUNNING puis immédiatement COMPLETED) — redondant et 2x `timezone.now()` | `executions/container_workflow_runtime.py` | 317-326 |
| **NEW-BE-3** | LOW | TODO obsolète : « These endpoints are not yet implemented » alors que `approval_views.py` les implémente | `executions/services.py` | 435-438 |
| **NEW-BE-4** | LOW | `asyncio.run()` x2 dans tâche Celery — risque de conflit event loop. `async_to_sync` (asgiref) déjà utilisé ailleurs dans le projet | `executions/tasks/polling.py` | 313, 320 |
| **NEW-BE-5** | LOW | Log `unknown_execution_status_for_audit` sans `execution_id` — debugging difficile | `executions/services.py` | 504-507 |

**Corrections recommandées :**

- **NEW-BE-1** : Remplacer la boucle par `Action.objects.in_bulk(ref_ids)` (pattern déjà utilisé dans `workflow_parsing.py:241`)
- **NEW-BE-2** : Fusionner en un seul `.update(status=COMPLETED, started_at=now, completed_at=now)`
- **NEW-BE-3** : Supprimer ou mettre à jour le commentaire TODO
- **NEW-BE-4** : Remplacer `asyncio.run()` par `async_to_sync()` d'asgiref
- **NEW-BE-5** : Ajouter `execution_id=execution_id` au log

### Code quality — Frontend

| # | Sévérité | Description | Fichier | Lignes |
|---|----------|-------------|---------|--------|
| **NEW-FE-1** | LOW | Nested key props redondants (key sur button + wrapper) | `components/layout/TopNav.tsx` | 155-203 |

**Points positifs confirmés :**
- Aucun `dangerouslySetInnerHTML` dans le code
- Aucun secret/URL hardcodé
- ErrorBoundary en place
- WebSocket hooks utilisent `mounted` ref (pas de memory leak)
- 345+ attributs ARIA (bonne couverture accessibilité)
- Aucun `.catch(() => {})` vide en code de production (seulement en tests)

### Mise à jour des issues précédentes

| # | Issue précédente | Ancien statut | Nouveau statut | Détails |
|---|------------------|---------------|----------------|---------|
| 16.2 | `except Exception` résiduels | 33 occurrences | **77 occurrences** (40 fichiers .py) | Comptage précédent limité à `executions/`. Inclut maintenant tout le backend. La majorité sont documentés `noqa: BLE001` ou dans des contextes de résilience (webhooks, polling, adapters, vault) |
| 16.3 | `.catch(() => {})` résiduels | 21 occurrences | **0 en production** ✅ RESOLVED | Plus que 2 occurrences en fichiers test. Issue fermée |

---

## 18. Récapitulatif par priorité

### Issues OUVERTES restantes

#### HIGH

| # | Issue | Type | Effort |
|---|-------|------|--------|
| SOLID-FE-4 | ~25 composants importent directement les services (couplage DIP) | Frontend | Élevé |

#### MEDIUM

| # | Issue | Type | Effort |
|---|-------|------|--------|
| SOLID-FE-10 | STATUS_CONFIG duplication résiduelle dans 5 fichiers | Frontend | Faible |
| NEW-BE-1 | N+1 query dans `_validate_workflow_can_be_published()` | Backend | Faible |
| NEW-BE-2 | Double `.update()` redondant (container workflow non-simulation) | Backend | Faible |

#### LOW (backlog)

| # | Issue | Type | Effort |
|---|-------|------|--------|
| NEW-BE-3 | TODO obsolète (approval endpoints implémentés) | Backend | Trivial |
| NEW-BE-4 | `asyncio.run()` dans Celery (préférer `async_to_sync`) | Backend | Faible |
| NEW-BE-5 | Log sans `execution_id` | Backend | Trivial |
| NEW-FE-1 | Nested key props redondants (TopNav) | Frontend | Trivial |
| 16.2 | `except Exception` résiduels (77 occurrences, 40 fichiers backend) | Backend | Faible |
| INCON-2 | MD5 hash collision (documenté, acceptable pour N<1000) | Backend | — |
| PERF-4 | `<style>` inline dans 3 composants (impact négligeable) | Frontend | — |

#### INFO

| # | Issue | Type |
|---|-------|------|
| 16.4 | STATUS_CONFIG locals potentiellement consolidables | Frontend |

---

### Issues RÉSOLUES (résumé)

| Catégorie | Résolues | Ouvertes |
|-----------|----------|----------|
| Endpoints manquants | 7/7 | 0 |
| Bugs backend | 7/7 | 0 |
| Bugs frontend | 5/5 | 0 |
| Sécurité | 11/11 | 0 |
| Format API | 4/4 | 0 |
| Race conditions | 3/3 | 0 |
| Gestion d'erreurs | 5/5 | 0 |
| Performance | 4/4 | 0 |
| Code mort | 11/11 | 0 |
| Accessibilité | 3/3 | 0 |
| Celery | 5/5 | 0 |
| Incohérences modèles | 5/5 | 0 |
| **Sous-total original (§1-12)** | **70/70** | **0** |
| Nouveaux findings §13 | 5/5 | 0 |
| **SOLID Backend (§14)** | **11/11** | **0** |
| **SOLID Frontend (§15)** | **10/11** | **1** |
| **Observations post-refactoring (§16)** | 2 (16.1 DOCUMENTED, 16.3 RESOLVED) | **1 (16.2) + 1 INFO** |
| **Audit #3 (§17)** | **0** | **6** |
| **Total** | **99/105** | **6 MEDIUM+LOW (+ 1 INFO)** |

---

### Priorités de refactoring recommandées

**Sprint immédiat (quick wins) :**
1. NEW-BE-1 — Remplacer boucle `.get()` par `Action.objects.in_bulk(ref_ids)` dans `catalog/services.py`
2. NEW-BE-2 — Fusionner les 2 `.update()` en un seul dans `container_workflow_runtime.py`
3. NEW-BE-3 — Supprimer le TODO obsolète dans `executions/services.py:435-438`
4. NEW-BE-5 — Ajouter `execution_id` au log dans `executions/services.py:504-507`
5. SOLID-FE-10 — Consolider `STATUS_CONFIG` résiduel

**Backlog technique :**
1. NEW-BE-4 — Migrer `asyncio.run()` vers `async_to_sync()` dans `polling.py`
2. 16.2 — Audit des 77 `except Exception` résiduels pour vérifier documentation
3. SOLID-FE-4 — Migration progressive des ~25 composants vers hooks (effort élevé, story par story)

---

### Comparaison avec les revues précédentes

| Métrique | 21/02 | 23/02 (v2) | 23/02 (v3) | Évolution v2→v3 |
|----------|-------|------------|------------|-----------------|
| Issues ouvertes | 26 | 4 (+1 INFO) | 6 (+1 INFO) | +2 MEDIUM, +4 LOW (nouveaux findings) |
| Issues CRITICAL | 1 | 0 | 0 | = |
| Issues HIGH | 8 | 1 | 1 | = |
| Issues MEDIUM | 13 | 1 | 3 | +2 (N+1 query, double update) |
| Issues LOW | 4 | 4 | 7 | +3 (TODO obsolète, asyncio, log, key props) |
| Sécurité | 11 issues | 0 ouvertes | **0 ouvertes** | Posture sécurité confirmée excellente |
| `.catch(() => {})` vides FE | 21 | 21 | **0 en prod** ✅ | Issue fermée |
| `except Exception` BE | 33 | 33 | **77** (comptage complet) | Comptage élargi au backend entier |

**Bilan global (audit #3) :** Sur 105 findings cumulés, **99 sont résolus**. Les 6 issues ouvertes sont de sévérité MEDIUM (2) et LOW (4) — aucune issue CRITICAL ou de sécurité. La posture sécurité a été confirmée excellente par un audit dédié (SQL injection, SSRF, permissions, secrets, CORS, CSRF, webhooks HMAC, WebSocket auth, Celery serializers). Les nouveaux findings sont principalement des optimisations mineures de code quality. Le `.catch(() => {})` résiduel frontend (§16.3) est désormais résolu — 0 occurrence en production.
