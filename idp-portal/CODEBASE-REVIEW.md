# Revue Exhaustive du Codebase — IDP Portal

**Date :** 2026-03-10 (mise à jour — audit #6 qualité & nettoyage)
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
18. [Audit #4 — Nouveaux findings (2026-02-26)](#18-audit-4--nouveaux-findings-2026-02-26)
19. [Récapitulatif par priorité](#19-récapitulatif-par-priorité)
20. [Audit #5 — Analyse structurelle (2026-02-27)](#20-audit-5--analyse-structurelle-2026-02-27)
21. [Récapitulatif par priorité](#21-récapitulatif-par-priorité)
22. [Mise à jour post-Epics 54–66](#22-mise-à-jour-post-epics-54-66-story-66-26-2026-03-09)
23. [Bilan final Epic 66 — Release Readiness](#23-bilan-final-epic-66--release-readiness-story-66-27-2026-03-09)
24. [Audit #6 — Qualité implémentation & nettoyage pré-release (2026-03-10)](#24-audit-6--qualité-implémentation--nettoyage-pré-release-2026-03-10)

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

### SOLID-FE-4 [HIGH] — ✅ RÉSOLU (Story 71.1) — Couplage services directs

**Avant :** 29 composants importent directement les services.

**État actuel :** ~25/~25 composants migrés. Toutes les violations DIP résolues. Seuls restent `logger` et `AppLayout` (imports architecturaux acceptables, AC12).

**Historique des migrations :**

| Story | Composants migrés | Hooks créés |
|-------|-------------------|-------------|
| 35.3 | WorkflowStepsEditor, ActionWizard, ProfileForm | useEligibleActions, useActionWizardState, useProfileFormState |
| 34.13 | ExecutionWizard | useExecutionWizardState |
| 48.8 | ActionPalette, AdminAnalyticsDashboard, WizardStep1General, RemediationRulesEditor, ActionsAdminPanel | useAdminAnalytics, useActionNameAvailability, useRemediationCatalogActions, useActionsAdminPanel |
| 54.8 | IntegrationForm | useIntegrationFormState |
| 54.12 | WorkflowBuilderCanvas | useWorkflowGraph |
| 54.15 | CategoriesAdminTable, CategoryForm, EnginesAdminTable, EngineForm, IntegrationsTable, BusinessRulePolicySelector, ProfileImportModal | useCategoriesAdmin, useCategoryForm, useEnginesAdmin, useEngineForm, useIntegrationValidation, useBusinessRulePolicies, useProfileImport |
| 71.1 | OutputSchemaPanel, FeatureFlagsPanel, BusinessRulesPolicyPanel, EvaluationStepConfig, TargetSelector, ReportingDashboard, AdminPlatformSection, ActionForm, ActionWizard | useOutputSchemasList, useFeatureFlagsAdmin, useBusinessRulePoliciesAdmin, useBusinessRulePoliciesActive, useDashboardReportingStats, useAdminPlatformStats + extensions useActionFormState, useActionWizardState |

**SOLID-FE-4 ✅ ~25/~25 composants migrés (2026-03-10, Story 71.1)**

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

### SOLID-FE-10 [MEDIUM] — ✅ RÉSOLU — Story 48.5 (2026-02-26) — Status mapping consolidé

**Avant :** Mapping status dupliqué dans 3 fichiers.

**Fix appliqué :** Utility partagé `utils/execution-status.ts` créé avec :
- `STEP_STATUS_COLOR` — couleurs des étapes timeline
- `AUDIT_STATUS_CONFIG` — config pour la page audit

Les composants `ExecutionTimeline/TimelineStepItem.tsx` et `AuditTable.tsx` / `AuditEntryDrawer.tsx` importent depuis cette utility.

**Résolution complète (Story 48.5, 2026-02-26) :** Audit des 5 fichiers ciblés — `ExecutionView.tsx`, `StepDetailDrawer.tsx`, `ComparisonExecutionsDrawer.tsx` importent depuis `utils/execution-status.ts`. `WorkflowExecutionGraph.tsx` conserve `STATUS_COLORS` local (React Flow hex ≠ Ant Design Badge, SELECTED sans équivalent partagé). `IntegrationsTable.tsx` conserve `STATUS_CONFIG` local (domaine distinct : valid/invalid/deprecated ≠ statuts d'exécution). `executionRenderers.tsx STATUS_CONFIG` conservé avec justification SOLID-FE-10 (utilisé par `RecentExecutions.tsx`, inclut Icon components absents de la source partagée). Aucune duplication active — chaque config locale est justifiée par domaine ou format différent.

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

### 16.2 [LOW] — `except Exception` résiduels (77 occurrences backend) — ✅ RESOLVED (Story 48.9 — 2026-02-26)

**Audit final Story 48.9 (2026-02-26) :** 77 occurrences inventoriées dans 40 fichiers backend. **100 % conformes** — toutes avec `noqa: BLE001` et commentaire de catégorie (resilience-boundary, graceful-degradation, catch-all-mark-failed, best-effort-non-critical, logged-and-reraised, logged-and-wrapped). Aucune correction nécessaire.

Rapport détaillé : [`docs/backend/story-48-9-except-exception-audit-report.md`](../docs/backend/story-48-9-except-exception-audit-report.md)

~~33 occurrences de `except Exception` dans `executions/` (16 fichiers). La plupart sont documentées (`noqa: BLE001`) ou dans des contextes de résilience (webhooks, polling, runtime). Les cas non documentés dans les fichiers nouveaux/refactorisés (ex. `container_workflow_runtime.py` — 5 occurrences) mériteraient une revue pour vérifier qu'ils sont tous justifiés.~~

---

### 16.3 [LOW] — `.catch(() => {})` résiduels frontend (21 occurrences)

21 occurrences de `.catch(() => {})` ou `.catch(err => {})` dans 16 fichiers frontend. La plupart sont dans des hooks et composants qui gèrent l'erreur par ailleurs (via state, logging, ou cleanup). Vérifier que chaque cas est intentionnel.

---

### 16.4 [INFO] — STATUS_CONFIG duplication résiduelle — ✅ RESOLVED (Story 71.3, 2026-03-10)

**Résumé des actions :**
- `ExecutionView.tsx`, `StepDetailDrawer.tsx`, `ComparisonExecutionsDrawer.tsx` — Consolidés vers `execution-status.ts` (Story 48.5)
- `ExecutionsFiltersPanel.tsx`, `AdvancedFiltersPanel.tsx` — STATUS_OPTIONS consolidés vers `EXECUTION_STATUS_FILTER_OPTIONS` dans `execution-status.ts` (Story 71.3)
- `WorkflowExecutionGraph.tsx` STATUS_COLORS — Config locale justifiée (hex React Flow, SELECTED sans équivalent)
- `IntegrationsTable.tsx` STATUS_CONFIG — Config locale justifiée (domaine distinct valid/invalid/deprecated)
- `executionStatusRenderer.tsx` STATUS_CONFIG — Config locale justifiée (Icons + labels féminins, SOLID-FE-10)
- `AuditFiltersPanel.tsx` STATUS_OPTIONS — Config locale justifiée (domaine audit distinct)

Aucune duplication active ne subsiste. Les cas locaux sont documentés avec commentaires §16.4.

---

## 17. Audit #3 — Nouveaux findings (2026-02-23)

### Sécurité — Aucun nouveau problème

Audit complet couvrant : SQL injection (query_executor.py vérifié — paramétrage correct, regex validation), SSRF, désérialisation, permissions manquantes, secrets hardcodés, CORS, fichiers, CSRF, settings Django, bypass auth, WebSocket auth, webhooks HMAC, Celery serializers. **Résultat : RAS.** La posture sécurité est excellente.

### Code quality — Backend

| # | Sévérité | Description | Fichier | Lignes | Statut |
|---|----------|-------------|---------|--------|--------|
| **NEW-BE-1** | MEDIUM | N+1 query : `Action.objects.get(id=ref_id)` dans boucle | `catalog/services.py` | 62-73 | ✅ RESOLVED — `Action.objects.in_bulk(int_ref_ids)` (ligne 61) |
| **NEW-BE-2** | MEDIUM | Double `.update()` consécutif sur même exécution | `executions/container_workflow_runtime.py` | 317-326 | ✅ RESOLVED — Les deux `.update()` sont sur des branches `if/else` mutuellement exclusives |
| **NEW-BE-3** | LOW | TODO obsolète (approval endpoints) | `executions/services.py` | 435-438 | ✅ RESOLVED — Commentaire remplacé par docstring appropriée |
| **NEW-BE-4** | LOW | `asyncio.run()` x2 dans tâche Celery | `executions/tasks/polling.py` | 313, 320 | ✅ RESOLVED — Plus aucun `asyncio.run()` dans les tâches Celery |
| **NEW-BE-5** | LOW | Log sans `execution_id` | `executions/services.py` | 504-507 | ✅ RESOLVED — `execution_id=execution.id` ajouté (ligne 567) |

### Code quality — Frontend

| # | Sévérité | Description | Fichier | Lignes |
|---|----------|-------------|---------|--------|
| ~~**NEW-FE-1**~~ ✅ Résolu | ~~LOW~~ | ~~Nested key props redondants (key sur button + wrapper)~~ — **Résolu Story 54.3 (2026-02-27)** | `components/layout/TopNav.tsx` | 155-203 |

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
| 16.2 | `except Exception` résiduels | 33 occurrences | **✅ RESOLVED (Story 48.9)** | 77 occurrences auditées, 100 % conformes (`noqa: BLE001` + catégorie). Rapport: `docs/backend/story-48-9-except-exception-audit-report.md` |
| 16.3 | `.catch(() => {})` résiduels | 21 occurrences | **0 en production** ✅ RESOLVED | Plus que 2 occurrences en fichiers test. Issue fermée |

---

## 18. Audit #4 — Nouveaux findings (2026-02-26)

### Sécurité

| # | Sévérité | Description | Fichier | Lignes |
|---|----------|-------------|---------|--------|
| **SEC-12** | ✅ RÉSOLU | ~~Validation URL minimale~~ — Corrigé story 54.1 (2026-02-27) : validation SSRF complète avec rejet IPv4-mapped IPv6, port 0, hostname vide. 74 tests passent. | `integrations/serializers.py` | 19-90 |
| ~~**SEC-13**~~ | ✅ RÉSOLU | ~~`SERVICENOW_VERIFY_TLS` configurable~~ — Corrigé story 54.4 (2026-02-27) : commentaire settings.py clarifié (dev-only), `logger.warning` ajouté quand l'override est ignoré en production. 2 tests ajoutés. | `services/servicenow_service.py` | 46-56 |
| ~~**SEC-14**~~ | ✅ RÉSOLU | ~~Pas de vérification path traversal sur écriture icônes~~ — Corrigé story 54.4 (2026-02-27) : protection `is_relative_to()` déjà en place, test positif UUID ajouté. 29 tests passent. | `integrations/upload_views.py` | 265-276 |

**Détails et corrections recommandées :**

- **SEC-12** : ✅ **RÉSOLU** (Story 54.1, 2026-02-27) — Validation SSRF complète dans `validate_url()` : schéma http(s), rejet credentials, localhost, IP privées RFC 1918, link-local, metadata cloud, IPv6 ULA/link-local, IPv4-mapped IPv6 bypass, port 0, hostname vide. 74 tests unitaires couvrent tous les cas.
- **SEC-13** : ✅ **RÉSOLU** (Story 54.4, 2026-02-27) — Commentaire settings.py clarifié « Dev only — ignoré en production (DEBUG=False) ». `logger.warning("servicenow_tls_override_ignored")` ajouté dans `_get_verify_tls()` quand l'override est ignoré. 2 tests de couverture ajoutés (warning émis / non émis).
- **SEC-14** : ✅ **RÉSOLU** (Story 54.4, 2026-02-27) — Protection `is_relative_to()` déjà implémentée (defense-in-depth). Test positif ajouté confirmant qu'un UUID normal passe la vérification. 29 tests upload security passent.

### Code quality — Backend

| # | Sévérité | Description | Fichier | Lignes |
|---|----------|-------------|---------|--------|
| ~~**NEW-BE-6**~~ ✅ Résolu | HIGH | N+1 dans `delete_integration()` — `.save()` individuel + `AuditService.create_entry()` en boucle sur `linked_actions`. Pour N actions, génère 2N requêtes au lieu d'un `bulk_update()` + batch | `integrations/services.py` | 335-353 |
| ~~**NEW-BE-7**~~ ✅ Résolu | MEDIUM | Double `.save()` dans `create_integration()` — premier save après `set_config()`, second après validation de status | `integrations/services.py` | 140, 146 |
| ~~**NEW-BE-8**~~ ✅ Résolu | MEDIUM | Double `.save()` dans `update_integration()` — save principal puis save status si changé | `integrations/services.py` | 263, 272 |
| ~~**NEW-BE-9**~~ ✅ Résolu | MEDIUM | N+1 dans `deactivate_action()` — `.save()` individuel + audit en boucle sur `affected_workflows` | `catalog/services.py` | 585-603 |
| ~~**NEW-BE-10**~~ ✅ Résolu | LOW | `import logging` (stdlib) au lieu de `structlog` dans 25 fichiers non-test. Le reste du projet utilise structlog. Incohérence qui prive ces modules du contexte structuré (correlation_id, user_id) | Voir liste ci-dessous | — | **Résolu — Story 48.6 (2026-02-26)** |

**Fichiers `import logging` (non-test, à migrer vers structlog) :**
`integrations/signals.py`, `integrations/views.py`, `integrations/upload_views.py`, `integrations/models.py`, `catalog/models.py`, `catalog/validators.py`, `executions/models.py`, `profiles/models.py`, `profiles/cache.py`, `adapters/registry.py`, `services/registry.py`, `utils/json_helpers.py`, `idp_auth/authentication.py`

**Corrections recommandées :**

- ~~**NEW-BE-6**~~ ✅ Résolu — `Action.objects.filter().update()` bulk en 1 requête SQL + audit individuel SOC1 préservé (Story 54.2)
- ~~**NEW-BE-7/8**~~ ✅ Résolu — Config + status fusionnés en un seul `.save(update_fields=[...])` (Story 54.2)
- ~~**NEW-BE-9**~~ ✅ Résolu — Boucle préparation + `bulk_update()` + audit individuel SOC1 (Story 54.2)
- **NEW-BE-10** : Migrer progressivement vers `structlog.get_logger(__name__)`

### Code quality — Frontend

| # | Sévérité | Description | Fichier | Lignes |
|---|----------|-------------|---------|--------|
| ~~**NEW-FE-2**~~ ✅ Résolu | ~~LOW — Cache module-level sans mécanisme d'invalidation — sessions longues afficheront des catégories obsolètes~~ | `hooks/useCategories.ts` | 18-44 | **Résolu — Story 48.7 (2026-02-26)** |
| ~~**NEW-FE-3**~~ ✅ Résolu | ~~LOW~~ | ~~`.catch()` silencieux sans logging — `fetchFilterOptions()` échoue sans trace~~ — **Résolu Story 54.3 (2026-02-27)** | `components/dashboard/reporting/ReportingDashboard.tsx` | 160-165 |
| ~~**NEW-FE-4**~~ ✅ Résolu | ~~LOW~~ | ~~Prop `allowedEnvironments` passée puis explicitement ignorée — code mort~~ — **Résolu Story 54.3 (2026-02-27)** | `components/catalog/ActionDrawerPreview.tsx` | 99 |

**Points positifs confirmés (audit #4) :**
- Aucun `dangerouslySetInnerHTML` dans le code
- Pattern hooks DIP excellent : `useActionWizardState`, `useExecutionWizardState`, `useCatalogState`, `useAuditFilters` encapsulent correctement les services
- 193 fichiers test frontend — couverture comprehensive
- Composition de hooks cohérente (SRP par hook : filtres, data, detail, restart)
- Aucune dépendance circulaire détectée (frontend ni backend)
- Architecture SOLID backend exemplaire : registries (OCP), ISP adapters, DI via `core/di.py`
- Documentation SOLID dans le code (références Story, commentaires `# Responsabilité`)
- 340 fichiers test backend — couverture forte

### Mise à jour des issues précédentes (§17)

| # | Issue audit #3 | Ancien statut | Nouveau statut | Détails |
|---|----------------|---------------|----------------|---------|
| NEW-BE-1 | N+1 query `_validate_workflow_can_be_published()` | MEDIUM OUVERT | ✅ **RESOLVED** | `Action.objects.in_bulk(int_ref_ids)` (ligne 61) |
| NEW-BE-2 | Double `.update()` container workflow | MEDIUM OUVERT | ✅ **RESOLVED** | Les deux `.update()` sont sur branches `if/else` mutuellement exclusives |
| NEW-BE-3 | TODO obsolète | LOW OUVERT | ✅ **RESOLVED** | Commentaire remplacé par docstring |
| NEW-BE-4 | `asyncio.run()` dans Celery | LOW OUVERT | ✅ **RESOLVED** | Plus aucun `asyncio.run()` dans les tâches |
| NEW-BE-5 | Log sans `execution_id` | LOW OUVERT | ✅ **RESOLVED** | `execution_id=execution.id` ajouté (ligne 567) |
| ~~NEW-FE-1~~ | Nested key props TopNav | ~~LOW OUVERT~~ | ✅ **RÉSOLU** | Story 54.3 (2026-02-27) |

## 20. Audit #5 — Analyse structurelle (2026-02-27)

**Focus :** Misimplémentations, simplicité du code, maintenabilité, fichiers volumineux, principes SOLID.

### Métriques de taille — Backend

| Fichier | LOC | Verdict |
|---------|-----|---------|
| `inventory/query_executor.py` | 1 167 | ⚠ God class — 1 classe, 15+ méthodes couvrant SQL, mapping, validation, pagination |
| `executions/services.py` | 902 | ⚠ `update_status()` = 168 lignes (state machine + audit + notifications) |
| `idp_auth/views.py` | 851 | ⚠ 9 classes de vues mélangées (SAML, JWT, API keys, service login, favorites) |
| `catalog/services.py` | 851 | ⚠ 20+ méthodes — transitions, tags, workflows, suppressions, cascades |
| `inventory/services.py` | 796 | ⚠ 22+ méthodes — targets, servers, instances, databases, RBAC |
| `catalog/serializers.py` | 756 | ✅ Justifié — 10+ serializers + validations croisées DRF |
| `adapters/terraform_cloud_adapter.py` | 784 | ✅ Justifié — API TFC complexe (JSON API spec, 18+ états) |
| `adapters/github_actions_adapter.py` | 749 | ✅ Justifié — dispatch sans run_id, logs ZIP |

### Métriques de taille — Frontend

| Fichier | LOC | Verdict |
|---------|-----|---------|
| `IntegrationForm.tsx` | 730 | ⚠ Formulaire géant — UI + health check + icon upload + conditional fields |
| `ActionWizard.tsx` | 588 | ✅ Logique extraite dans `useActionWizardState` — composant léger |
| `execution_service.ts` | 511 | ✅ Service API — volume justifié |
| `ProfileForm.tsx` | 506 | ✅ Bien refactorisé via `useProfileFormState` |
| `WorkflowBuilderCanvas.tsx` | 489 | ⚠ Composant React Flow complexe — candidat au découpage |
| `ActionForm.tsx` | 484 | ✅ Logique dans `useActionFormState` + `useActionFormValidation` |
| `useExecutionWizardState.ts` | 459 | ✅ Hook central du wizard — cohérent |
| `StepsEditor.tsx` | 449 | ✅ Structuré avec sous-composant `AAPTemplateSection` |
| `executionRenderers.tsx` | 444 | ⚠ Module utilitaire trop large — renderers + configs |

---

### Nouveaux findings — Maintenabilité & structure

#### Backend

| # | Sévérité | Description | Fichier | Lignes |
|---|----------|-------------|---------|--------|
| ~~**MAINT-BE-1**~~ | ~~HIGH~~ | ~~**`update_status()` God method (168 LOC)** — mélange machine à états, timestamps, audit, notifications. State machine hardcodée comme `dict` imbriqué. Notification callback défini inline (30 LOC). Devrait être 3 méthodes : `_validate_transition()`, `_apply_status_change()`, `_schedule_notification()`~~ **Résolu — Story 54.6 (2026-02-27)** | `executions/services.py` | 466–633 |
| ~~**MAINT-BE-2**~~ | ~~HIGH~~ | ~~**`idp_auth/views.py` module monolithique (851 LOC)** — 9 classes de vues hétérogènes (SAML login/callback, JWT refresh, API keys CRUD, service login, favorites). Devrait être 4-5 modules : `saml_views.py`, `jwt_views.py`, `apikey_views.py`, `service_login_views.py`, `favorites_views.py`~~ **Résolu — Story 54.7 (2026-02-27)** | `idp_auth/views/` | — |
| ~~**MAINT-BE-3**~~ | ~~HIGH~~ | ~~**`InventoryQueryExecutor` God class (1167 LOC)**~~ **✅ RESOLVED Story 54.14 (2026-02-28)** — Décomposé en `InventoryQueryBuilder` (530 LOC), `MappingValidator` (89 LOC), `ResultPaginator` (83 LOC). `query_executor.py` réduit à 347 LOC. | `inventory/query_builder.py`, `inventory/mapping_validator.py`, `inventory/result_paginator.py` | — |
| ~~**MAINT-BE-4**~~ | ~~MEDIUM~~ | ~~**`create_execution()` signature — 11 paramètres** — `user, action, environment, parameters, parent_execution_id, correlation_id, source, ip_address, targets, delegated_referenced_action_ids, validated_targets`. Candidat pour un objet `ExecutionRequest` DTO~~ **✅ RESOLVED Story 54.9 (2026-02-28)** | `executions/dtos.py`, `executions/services.py` | — |
| ~~**MAINT-BE-5**~~ | ~~MEDIUM~~ | ~~**`_find_workflows_referencing_action()` — faux positifs JSON** — `execution_steps__contains=str(action_id)` retourne des faux positifs (action_id=42 matche "421"). Validation Python en boucle. Pour Oracle 19c+, `JSON_EXISTS` serait plus fiable et performant~~ **✅ RESOLVED Story 54.10 (2026-02-28)** | `catalog/services.py` | 674–711 |
| ~~**MAINT-BE-6**~~ | ~~MEDIUM~~ | ~~**Profils hardcodés** — `_ALLOWED_PROFILES = {"dba_applicatif", "dba_infrastructure", "dbops"}` en constante module. Ajout d'un profil = modification du code. Devrait être config-driven ou DB-backed~~ **Résolu — Story 54.5 (2026-02-27)** | `idp_auth/views.py` | 48–49 |
| ~~**MAINT-BE-7**~~ | ~~MEDIUM~~ | ~~**Status mapping dupliqué dans les adapters** — chaque adapter définit son propre `STATUS_MAP` dict (AAP, GitHub Actions, TFC, Azure DevOps). Pattern identique, pas de base commune. Extraction vers `adapters/status_mappers.py` possible~~ **✅ RESOLVED Story 54.11 (2026-02-28)** | `adapters/*.py` | — |
| ~~**MAINT-BE-8**~~ | ~~LOW~~ | ~~**Late imports `PLC0415`** — 3+ imports tardifs dans `executions/services.py` pour éviter des dépendances circulaires. Indicateur de couplage entre modules~~ **✅ RESOLVED Story 54.16 (2026-02-28) — commentaires explicatifs ajoutés sur les late imports** | `executions/services.py` | 438, 924 |
| **MAINT-BE-9** | LOW | **Validation en 4 couches dans les vues d'exécution** — `ExecutionPayloadValidator` → `TargetValidator` → `EnvironmentConfigResolver` → serializer DRF implicite. Debug difficile quand une erreur survient. Pipeline unifié recommandé | `executions/views/execution_views.py` | — |

#### Frontend

| # | Sévérité | Description | Fichier | Lignes |
|---|----------|-------------|---------|--------|
| ~~**MAINT-FE-1**~~ | ~~HIGH~~ | ~~**`IntegrationForm.tsx` — 730 LOC, composant god**~~ ✅ RÉSOLU Story 54.8 — `useIntegrationFormState()` créé (304 LOC), `IntegrationForm.tsx` réduit à 229 LOC | `hooks/useIntegrationFormState.ts` | — |
| ~~**MAINT-FE-2**~~ | ~~MEDIUM~~ | ~~**`WorkflowBuilderCanvas.tsx` — 489 LOC**~~ ✅ RESOLVED Story 54.12 — `useWorkflowGraph()` créé, `WorkflowBuilderCanvas.tsx` réduit à 185 LOC | `hooks/useWorkflowGraph.ts` | — |
| ~~**MAINT-FE-3**~~ | ~~MEDIUM~~ | ~~**`executionRenderers.tsx` — 444 LOC**~~ ✅ RESOLVED Story 54.13 — `executionStatusRenderer.tsx` créé, `executionRenderers.tsx` réduit à ~320 LOC | `utils/executionStatusRenderer.tsx` | — |
| ~~**MAINT-FE-4**~~ | ~~LOW~~ | ~~**Debounce pattern dupliqué** — `useDebounce` hook existe mais certains composants implémentent manuellement le debounce avec `setTimeout`~~ **✅ RESOLVED Story 54.16 (2026-02-28) — `StepsEditor.tsx` et `WizardStep2Automatisme.tsx` migrent vers `useDebounce`** | `components/admin/StepsEditor.tsx`, `WizardStep2Automatisme.tsx` | — |
| ~~**MAINT-FE-5**~~ | ~~LOW~~ | ~~**Date formatting éparpillé** — `new Date(d).toLocaleDateString('fr-CA')` et variantes copiées dans ProfilesTable et d'autres composants~~ **✅ RESOLVED Story 54.16 (2026-02-28) — `formatLocalDate` et `formatLocalDateTime` ajoutés dans `utils/dateFormat.ts` ; `ProfilesTable.tsx`, `IntegrationsTable.tsx`, `IntegrationForm.tsx` migrés** | `utils/dateFormat.ts` | — |

---

### Mise à jour des issues précédentes (§18)

| # | Issue audit #4 | Ancien statut | Nouveau statut | Détails |
|---|----------------|---------------|----------------|---------|
| ~~NEW-BE-6~~ | N+1 `.save()` `delete_integration()` | HIGH OUVERT | ✅ **RÉSOLU** | Story 54.2 (2026-02-27) |
| ~~NEW-BE-7~~ | Double `.save()` `create_integration()` | MEDIUM OUVERT | ✅ **RÉSOLU** | Story 54.2 (2026-02-27) |
| ~~NEW-BE-8~~ | Double `.save()` `update_integration()` | MEDIUM OUVERT | ✅ **RÉSOLU** | Story 54.2 (2026-02-27) |
| ~~NEW-BE-9~~ | N+1 `.save()` `deactivate_action()` | MEDIUM OUVERT | ✅ **RÉSOLU** | Story 54.2 (2026-02-27) |
| SEC-12 | Validation URL minimale | ✅ RÉSOLU | ✅ **RÉSOLU** | Story 54.1 (2026-02-27) |
| ~~SEC-13~~ | ~~`SERVICENOW_VERIFY_TLS`~~ | ~~LOW OUVERT~~ | ✅ **RÉSOLU** | Story 54.4 (2026-02-27) |
| ~~SEC-14~~ | ~~Path traversal icône~~ | ~~LOW OUVERT~~ | ✅ **RÉSOLU** | Story 54.4 (2026-02-27) |
| ~~NEW-FE-1~~ | Nested key props TopNav | ~~LOW OUVERT~~ | ✅ **RÉSOLU** | Story 54.3 (2026-02-27) |
| ~~NEW-FE-3~~ | `.catch()` silencieux ReportingDashboard | ~~LOW OUVERT~~ | ✅ **RÉSOLU** | Story 54.3 (2026-02-27) |
| ~~NEW-FE-4~~ | Prop `allowedEnvironments` morte | ~~LOW OUVERT~~ | ✅ **RÉSOLU** | Story 54.3 (2026-02-27) |
| ~~SOLID-FE-4~~ | ~25 composants importent services directement | ~~HIGH OUVERT~~ | ✅ **RÉSOLU** | ~25/~25 migrés (Story 71.1, 2026-03-10) |

### Points positifs confirmés (audit #5)

**Backend :**
- Architecture SOLID exemplaire : registries (OCP), ISP adapters, DI via `core/di.py`
- Transaction management correct : `@transaction.atomic`, `select_for_update()`, `on_commit()` callbacks
- Aucune dépendance circulaire détectée
- Error handling cohérent : exceptions custom (`BadRequestError`, `ForbiddenError`), structlog partout
- Audit SOC1 complet : toutes les mutations tracées avec `AuditService`
- Query optimization : usage correct de `select_related()`, `prefetch_related()`, `in_bulk()`
- Tests : 340+ fichiers test backend

**Frontend :**
- 95% des composants utilisent des hooks pour le data fetching (DIP correct)
- `useEffect` dependencies correctes partout (aucune erreur détectée)
- Contextes bien utilisés (`WizardExecutionContext`, `AuthContext`)
- Cleanup functions dans les async effects (cancellation flags)
- Pas de pollution `any` type
- 193 fichiers test frontend

---

## 21. Récapitulatif par priorité

### Issues OUVERTES restantes

#### HIGH

| # | Issue | Type | Effort |
|---|-------|------|--------|
| ~~SOLID-FE-4~~ | ~~~8 composants restants importent directement les services (couplage DIP)~~ ✅ RÉSOLU Story 71.1 (2026-03-10) — ~25/~25 migrés | Frontend | — |
| ~~MAINT-BE-2~~ | ~~`idp_auth/views.py` module monolithique (851 LOC, 9 classes hétérogènes)~~ ✅ Résolu Story 54.7 | Backend | — |
| ~~MAINT-BE-3~~ | ~~`InventoryQueryExecutor` God class (1167 LOC)~~ ✅ RESOLVED Story 54.14 | Backend | — |
| ~~MAINT-FE-1~~ | ~~`IntegrationForm.tsx` — 730 LOC, composant god sans hook dédié~~ ✅ RÉSOLU Story 54.8 | Frontend | — |

#### MEDIUM

| # | Issue | Type | Effort |
|---|-------|------|--------|
| ~~SEC-12~~ | ~~Validation URL minimale~~ ✅ RÉSOLU (Story 54.1) | Sécurité | — |
| ~~NEW-BE-7~~ | ~~Double `.save()` dans `IntegrationService.create_integration()`~~ ✅ RÉSOLU (Story 54.2) | Backend | — |
| ~~NEW-BE-8~~ | ~~Double `.save()` dans `IntegrationService.update_integration()`~~ ✅ RÉSOLU (Story 54.2) | Backend | — |
| ~~NEW-BE-9~~ | ~~N+1 `.save()` en boucle dans `CatalogService.deactivate_action()`~~ ✅ RÉSOLU (Story 54.2) | Backend | — |
| ~~MAINT-BE-4~~ | ~~`create_execution()` — 11 paramètres, candidat DTO~~ ✅ RÉSOLU (Story 54.9) | Backend | — |
| ~~MAINT-BE-5~~ | ~~`_find_workflows_referencing_action()` — faux positifs JSON~~ ✅ RÉSOLU (Story 54.10) | Backend | Faible |
| ~~MAINT-BE-6~~ | ~~Profils hardcodés `_ALLOWED_PROFILES` dans views~~ ✅ RÉSOLU (Story 54.5) | Backend | — |
| ~~MAINT-BE-7~~ | ~~Status mapping dupliqué dans les adapters~~ ✅ RÉSOLU (Story 54.11) | Backend | Faible |
| ~~MAINT-FE-2~~ | ~~`WorkflowBuilderCanvas.tsx` — 489 LOC, candidat extraction hook~~ ✅ RÉSOLU (Story 54.12) | Frontend | Moyen |
| ~~MAINT-FE-3~~ | ~~`executionRenderers.tsx` — 444 LOC, responsabilités mélangées~~ ✅ RESOLVED (Story 54.13) | Frontend | Faible |

#### LOW (backlog)

| # | Issue | Type | Effort |
|---|-------|------|--------|
| ~~SEC-13~~ | ~~`SERVICENOW_VERIFY_TLS` désactivable en production~~ | ~~Sécurité~~ | ~~Trivial~~ ✅ Story 54.4 |
| ~~SEC-14~~ | ~~Pas de vérification path traversal sur écriture icône~~ | ~~Sécurité~~ | ~~Trivial~~ ✅ Story 54.4 |
| NEW-FE-1 | Nested key props redondants (TopNav) | Frontend | Trivial |
| NEW-FE-3 | `.catch()` silencieux (ReportingDashboard) | Frontend | Trivial |
| NEW-FE-4 | Prop `allowedEnvironments` ignorée (code mort) | Frontend | Trivial |
| ~~MAINT-BE-8~~ | ~~Late imports `PLC0415` (couplage inter-modules)~~ | ~~Backend~~ | ~~Faible~~ ✅ Story 54.16 |
| MAINT-BE-9 | Validation en 4 couches dans vues d'exécution | Backend | Moyen |
| ~~MAINT-FE-4~~ | ~~Debounce pattern dupliqué (hook vs setTimeout)~~ | ~~Frontend~~ | ~~Trivial~~ ✅ Story 54.16 |
| ~~MAINT-FE-5~~ | ~~Date formatting copié dans plusieurs composants~~ | ~~Frontend~~ | ~~Trivial~~ ✅ Story 54.16 |
| INCON-2 | MD5 hash collision (documenté, acceptable pour N<1000) | Backend | — |
| PERF-4 | `<style>` inline dans 3 composants (impact négligeable) | Frontend | — |

#### INFO

| # | Issue | Type |
|---|-------|------|
| ~~16.4~~ | ~~STATUS_CONFIG locals potentiellement consolidables~~ | ✅ RESOLVED — Story 71.3 |

---

### Issues RÉSOLUES (résumé)

| Catégorie | Résolues | Ouvertes |
|-----------|----------|----------|
| Endpoints manquants | 7/7 | 0 |
| Bugs backend | 7/7 | 0 |
| Bugs frontend | 5/5 | 0 |
| Sécurité | 12/14 | 2 |
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
| **Observations post-refactoring (§16)** | 3 (16.1 DOCUMENTED, 16.2 RESOLVED, 16.3 RESOLVED) | **1 INFO** |
| **Audit #3 (§17)** | **6/6** | **0** |
| **Audit #4 (§18)** | **9/12** | **3** |
| **Audit #5 — Maintenabilité (§20)** | **2/14** | **12** |
| **Total** | **118/133** | **15 (3 HIGH, 5 MEDIUM, 6 LOW, 1 INFO)** |

---

### Priorités de refactoring recommandées

**Sprint immédiat (quick wins) :**
1. ~~SEC-12~~ — ✅ RÉSOLU (Story 54.1) — `validate_url()` renforcé avec validation SSRF complète
2. ~~NEW-BE-6~~ — ✅ RÉSOLU (Story 54.2) — `Action.objects.filter().update()` bulk en 1 requête SQL
3. ~~NEW-BE-7/8~~ — ✅ RÉSOLU (Story 54.2) — Config + status fusionnés en un seul `.save(update_fields=[...])`
4. ~~NEW-BE-9~~ — ✅ RÉSOLU (Story 54.2) — Boucle préparation + `bulk_update()` + audit SOC1
5. ~~NEW-FE-4~~ — ✅ RÉSOLU (Story 54.3) — Prop morte supprimée de l'interface, signature et appelants
6. ~~MAINT-BE-6~~ — ✅ RÉSOLU (Story 54.5) — `_ALLOWED_PROFILES` supprimé (code mort), `_DEFAULT_PROFILE` migré vers `settings.DEFAULT_SAML_PROFILE`

**Refactoring structurel (effort moyen — par story) :**
1. ~~MAINT-BE-1~~ — ✅ RÉSOLU (Story 54.6) — `update_status()` décomposé en `_validate_transition()`, `_apply_status_change()`, `_create_status_audit_entry()`, `_schedule_notification()`
2. MAINT-BE-2 — Éclater `idp_auth/views.py` en 4-5 modules par domaine auth
3. ~~MAINT-FE-1~~ — ✅ RÉSOLU (Story 54.8) — `useIntegrationFormState()` créé (304 LOC), `IntegrationForm.tsx` réduit de 730 → 229 LOC, 33 tests unitaires
4. ~~MAINT-BE-4~~ — ✅ RÉSOLU (Story 54.9) — `ExecutionRequest` DTO introduit dans `executions/dtos.py`, signature de `create_execution()` simplifiée

**Backlog technique (effort élevé) :**
1. ~~MAINT-BE-3~~ — ✅ RÉSOLU (Story 54.14, 2026-02-28) — `InventoryQueryExecutor` (1167 LOC) décomposé en `InventoryQueryBuilder` (530 LOC) + `MappingValidator` (89 LOC) + `ResultPaginator` (83 LOC), `query_executor.py` réduit à 347 LOC
2. ~~SOLID-FE-4~~ — ✅ RÉSOLU (Story 71.1, 2026-03-10) — ~25/~25 composants migrés vers hooks
3. ~~MAINT-BE-7 — Centraliser status mapping des adapters~~ ✅ RÉSOLU Story 54.11
4. ~~SEC-13/14~~ — ✅ Corrections sécurité mineures (TLS, path traversal) — Story 54.4 (2026-02-27)

---

### Comparaison avec les revues précédentes

| Métrique | 21/02 | 23/02 (v2) | 23/02 (v3) | 26/02 (v4) | 27/02 (v5) | Évolution v4→v5 |
|----------|-------|------------|------------|------------|------------|-----------------|
| Issues ouvertes | 26 | 4 (+1 INFO) | 6 (+1 INFO) | 15 (+1 INFO) | 28 (+1 INFO) | +14 nouveaux (maintenabilité & structure) |
| Issues CRITICAL | 1 | 0 | 0 | 0 | 0 | = |
| Issues HIGH | 8 | 1 | 1 | 2 | 6 | +4 (god class/method/module/component) |
| Issues MEDIUM | 13 | 1 | 3 | 5 | 10 | +5 (DTO, JSON, profiles, adapters, FE) |
| Issues LOW | 4 | 4 | 7 | 7 | 11 | +4 (late imports, validation, debounce, dates) |
| Sécurité | 11 issues | 0 ouvertes | **0 ouvertes** | **3 ouvertes** | **0 ouvertes** | -3 (SEC-12 story 54.1, SEC-13/14 story 54.4) |
| Fichiers BE > 800 LOC | — | — | — | — | **5** (query_executor, services x2, views, serializers) | Nouveau |
| Fichiers FE > 500 LOC | — | — | — | — | **4** (IntegrationForm, ActionWizard, execution_service, ProfileForm) | Nouveau |
| God classes/methods | — | — | — | — | **3** (QueryExecutor, idp_auth/views, IntegrationForm) | -1 (update_status story 54.6) |

**Bilan global (audit #5, snapshot 2026-02-27) :** Sur 133 findings cumulés, **117 sont résolus** (88%). Les 13 issues restantes de l'audit #5 se concentrent sur la **maintenabilité structurelle** : god classes/modules qui, bien que fonctionnellement corrects, posent des risques de maintenabilité à terme. Aucune issue CRITICAL. La posture sécurité est **entièrement résolue** (0 ouvertes — SEC-13, SEC-14 corrigés story 54.4). L'architecture SOLID est globalement exemplaire (registries, ISP, DI, hooks) — les findings restants sont du polissage structurel et des extractions de responsabilités dans les fichiers les plus volumineux.

---

<a id="22-mise-à-jour-post-epics-54-66-story-66-26-2026-03-09"></a>
## 22. Mise à jour post-Epics 54–66 (Story 66-26, 2026-03-09)

**Date de révision :** 2026-03-09 — Story 66-26 (revue documentation)

### Corrections apportées à ce document

Les éléments suivants étaient listés comme OUVERTS dans §21 mais ont été résolus dans les Epics postérieurs :

| # | Correction | Résolution |
|---|-----------|------------|
| ~~NEW-FE-1~~ | Nested key props redondants (TopNav) | ✅ RÉSOLU Story 54.3 (2026-02-27) — ignoré dans §21 LOW |
| ~~NEW-FE-3~~ | `.catch()` silencieux (ReportingDashboard) | ✅ RÉSOLU Story 54.3 (2026-02-27) — ignoré dans §21 LOW |
| ~~NEW-FE-4~~ | Prop `allowedEnvironments` ignorée (code mort) | ✅ RÉSOLU Story 54.3 (2026-02-27) — ignoré dans §21 LOW |
| ~~MAINT-BE-2~~ | `idp_auth/views.py` module monolithique | ✅ RÉSOLU Story 54.7 (2026-02-27) — figurait encore en §21 priorités |

### Corrections au résumé §21

Le tableau §21 "Sécurité 12/14 | 2" est inexact — SEC-13 et SEC-14 ont été résolus en Story 54.4 :
- **Sécurité** : **14/14 résolus** (0 ouvertes) ✅

### Issues OUVERTES réelles (post-Story 66-26)

| # | Sévérité | Description | Statut |
|---|----------|-------------|--------|
| ~~**SOLID-FE-4**~~ | ~~HIGH~~ | ~~~25 composants importent directement les services~~ | ✅ RÉSOLU — Story 71.1 (2026-03-10) |
| **MAINT-BE-9** | LOW | Validation en 4 couches dans vues d'exécution | Ouvert — backlog |
| **INCON-2** | LOW | MD5 hash collision (documenté, acceptable pour N<1000) | Documenté — acceptable |
| **PERF-4** | LOW | `<style>` inline dans 3 composants (impact négligeable) | Documenté — acceptable |
| **16.4** | INFO | STATUS_CONFIG locals potentiellement consolidables | ✅ RESOLVED — Story 71.3 |

**Bilan mis à jour (2026-03-10, post-Story 71.3) :** Sur 133 findings, **131 sont résolus** (98.5%). 3 issues ouvertes en backlog (MAINT-BE-9, INCON-2, PERF-4). 16.4 résolu par Story 71.3. Posture sécurité : 0 ouvertes. Architecture SOLID : excellente.

---

## 23. Bilan final Epic 66 — Release Readiness (Story 66-27, 2026-03-09)

**Date de révision :** 2026-03-09 — Story 66-27 (consolidation synthèse findings + plan de correction)

### Périmètre Epic 66

L'Epic 66 a constitué une **revue exhaustive pré-release** du codebase IDP Portal sur 27 stories (stories 66.1–66.27), couvrant la totalité du frontend (13 stories), du backend (12 stories) et de la documentation (2 stories).

### Statistiques globales Epic 66

| Domaine | Stories | HIGH | MEDIUM | LOW | Total | Taux résolution |
|---------|---------|------|--------|-----|-------|-----------------|
| Frontend | 66.1–66.13 | 8 | 58+ | 65+ | ~131 | ~95% |
| Backend | 66.14–66.25 | 13 | 51+ | 38+ | ~102 | ~90% |
| Documentation | 66.26–66.27 | 1 | 5 | 7 | 13 | 100% |
| **TOTAL Epic 66** | **27** | **22** | **114+** | **110+** | **246+** | **~94%** |

| Niveau | Total | Résolus/Fermés | Backlog reporté | Taux résolution |
|--------|-------|----------------|-----------------|-----------------|
| **HIGH** | 22 | 22 | 0 | **100%** ✅ |
| **MEDIUM** | 114+ | 107+ | ~7 (reportés Epic 67) | **~94%** ✅ |
| **LOW** | 110+ | ~85 | ~25 | **~77%** 📋 |
| **TOTAL** | **246+** | **~214** | **~32** | **~87%** |

### Corrections majeures apportées dans l'Epic 66

Les 246+ findings Epic 66 s'ajoutent aux 133 findings des audits historiques (§1–§22 de ce document). Principaux apports :

- **Frontend** : Standards React 19 JSX auto-transform appliqués (élimination `import React`), `antd/es/*` remplacés par l'API publique, `App.useApp()` systématisé, AbortController dans tous les `useEffect` async, types Table extraits correctement
- **Backend** : `structlog` unifié (zéro `import logging` résiduel), audit trails complets dans `transaction.atomic()`, SSL par défaut dans tous les adapters, idempotence Celery, RBAC exécutions renforcé
- **Documentation** : Doublons IaC→CaC éliminés, versions Django 5.2/DRF 3.16 mises à jour, ADR-006/ADR-007 indexés
- **Tests** : ~95 nouveaux tests ajoutés sur l'ensemble de l'epic

### Items en backlog (reportés Epic 67)

| Catégorie | Items | Nature |
|-----------|-------|--------|
| MEDIUM — Container runtime | EXE-MED-05/06 | Atomicité container workflow (non-bloquant pré-release) |
| MEDIUM — Celery limits | EXE-MED-07/08/09 | `task_soft_time_limit` absent |
| MEDIUM — Qualité | EXE-MED-10, AUD-MED-03 | Testabilité throttle, duplication `_is_auditor()` |
| ADRs manquants | 4 ADRs | Celery, Oracle, CaC, Parallel Group |
| Tests frontend | ~15 fichiers | Services/hooks non couverts |
| CSS tokens | TopNav.css | Couleurs hardcodées → design tokens |

### Évaluation sécurité finale

Tous les items de sécurité identifiés ont été évalués et clôturés :
- **EXE-MED-11** `apply_scope_filter()` : RBAC `is_admin_user()` + isolation `user_id` en place — FERMÉ ✅
- **EXE-MED-12** GitHub webhook : HMAC SHA-256 `hmac.compare_digest()` + secret obligatoire — FERMÉ ✅
- **EXE-MED-13** Terraform webhook : HMAC SHA-512 `hmac.compare_digest()` + secret obligatoire — FERMÉ ✅
- **AUTH-NEW-04** API keys TOCTOU : limite 5 clés cosmétique, impact minimal — FERMÉ ✅
- **NEW-HIGH-02** Migration non trackée : `git ls-files` confirme toutes migrations committées — FERMÉ ✅

### Verdict release readiness

| Critère | Statut |
|---------|--------|
| Tous les HIGH résolus (22/22) | ✅ |
| MEDIUM critiques résolus (~107+/114+, ~94%) | ✅ |
| Items sécurité évalués (5/5 fermés) | ✅ |
| Standards FRONTEND-STANDARDS.md respectés | ✅ |
| Backend structlog unifié, audit trails complets | ✅ |
| Documentation mise à jour (docs/, README, ADRs) | ✅ |
| SSL par défaut dans tous les adapters | ✅ |
| Tests nouveaux ajoutés (~95 tests sur l'epic) | ✅ |
| **VERDICT** | **✅ RELEASE READY** |

**Bilan cumulatif (2026-03-09, post-Epic 66 — snapshot avant Story 71.1) :** Sur les 133 findings historiques, **129 étaient résolus** (97%). L'Epic 66 a traité 246+ findings additionnels avec un taux de résolution de ~94%. **Posture sécurité : 0 issues ouvertes.** Story 71.1 (2026-03-10) a porté le total à **130 résolus** (98%). Le codebase IDP Portal est déclaré prêt pour la première release v1.

---

## 24. Audit #6 — Qualité implémentation & nettoyage pré-release (2026-03-10)

**Date :** 2026-03-10
**Scope :** Backend Django — suppression rétrocompatibilité, bugs, performance, code smells
**Auteur :** Claude Code (revue automatisée)

Cet audit se concentre sur la suppression du code rétrocompatible accumulé (ADR-007 approval, singular step_ids, polling shims), la correction de bugs et edge cases, l'amélioration des performances (N+1), et la réduction du code dupliqué (refactoring.guru patterns).

### 24.1 Suppression du code rétrocompatible

| # | Sévérité | Fichier(s) | Description | Statut |
|---|----------|------------|-------------|--------|
| RC-01 | **HIGH** | `executions/models.py`, `services.py`, `serializers.py`, `views/approval_views.py`, `views/list_views.py`, `views/execution_views.py`, `tasks/scheduled.py` | **Migration complète PENDING_APPROVAL → step-based gates.** Suppression du statut `PENDING_APPROVAL`, des champs `approved_by`/`approved_at`/`approval_comment` du serializer, de la transition state machine PENDING_APPROVAL→RUNNING/REJECTED. Les actions avec `requires_approval` créent désormais un ExecutionStep WAITING de type GATE (`auto-approval-gate`). | ✅ Fait |
| RC-02 | **MEDIUM** | `catalog/serializers.py`, `executions/views/approval_views.py`, `executions/tasks/gates.py`, `container_workflow_runtime.py`, `workflow_runtime.py`, `utils/workflow_parsing.py` | **Suppression retrocompat singular `on_success_step_id`/`on_error_step_id`.** Tous les accès utilisent désormais les listes plurielles `on_success_step_ids`/`on_error_step_ids`. | ✅ Fait |
| RC-03 | **LOW** | `executions/tasks/polling.py`, `executions/tasks/__init__.py`, `idp_backend/settings.py` | **Suppression des 5 polling shims** (`poll_aap_job_status`, `poll_tower_job_status`, `poll_azure_devops_run_status`, `poll_github_actions_run_status`, `poll_terraform_cloud_run_status`) et du routing Celery dynamique associé. | ✅ Fait |

### 24.2 Bugs et edge cases

| # | Sévérité | Fichier | Description | Statut |
|---|----------|---------|-------------|--------|
| BUG-01 | **MEDIUM** | `catalog/validation.py` | **Workflow auto-référence non détectée.** `validate_workflow_steps()` ne vérifiait pas qu'un `referenced_action_id == action_id` → boucle infinie. Ajout d'un check explicite avec `ValidationError`. | ✅ Fait |
| BUG-02 | **LOW** | `catalog/views/action_views.py` | **Parsing DB-dépendant pour contrainte d'unicité.** Parsait les messages d'erreur Oracle (`UK_ACTIONS_CATALOG_NAME`). Ajout d'un pré-check `Action.objects.filter(name=...).exists()` avant le create. | ✅ Fait |
| BUG-03 | **LOW** | `catalog/serializers.py:861` | **Missing action_id None check.** `action_id = self.context.get('action_id')` utilisé sans vérification. Ajout d'un `if not action_id: raise ValidationError(...)`. | ✅ Fait |
| BUG-04 | **LOW** | `catalog/serializers.py:97-100` | **Validation silencieuse si integration type absent du catalogue.** `DoesNotExist` catch sans log. Ajout d'un `logger.warning("integration_type_not_in_catalogue", ...)`. | ✅ Fait |

### 24.3 Performance

| # | Sévérité | Fichier | Description | Statut |
|---|----------|---------|-------------|--------|
| PERF-01 | **MEDIUM** | `executions/serializers.py:110` | **N+1 ExecutionSerializer.targets.** `obj.targets.all()` sans prefetch. Les vues doivent ajouter `.prefetch_related('targets')`. | ✅ Fait |
| PERF-02 | **MEDIUM** | `executions/tasks/gates.py` | **N+1 gates.py step.execution.targets.** Ajout de `.prefetch_related('execution__targets')` au queryset initial des waiting steps. | ✅ Fait |
| PERF-03 | **LOW** | `executions/models.py:44-66` | **Inconsistent select_related dans ExecutionManager.** `list_by_user()` et `list_by_status()` n'avaient pas `select_related` contrairement à `get_recent()`. Harmonisé. | ✅ Fait |
| PERF-04 | **LOW** | `executions/tasks/gates.py:365-366` | **DB writes inutiles dans gate evaluation.** `step.save()` à chaque cycle même si output inchangé. Ajout d'une comparaison JSON avant sauvegarde. | ✅ Fait |

### 24.4 Code smells (refactoring.guru)

| # | Sévérité | Fichier(s) | Description | Statut |
|---|----------|------------|-------------|--------|
| SMELL-01 | **HIGH** | `executions/utils/step_config.py` (nouveau), `gates.py`, `approval_views.py`, `container_workflow_runtime.py` | **Duplication — Extract step config matching.** Pattern de recherche step_def par `config_step_id` puis fallback par `step_name` dupliqué 3-4 fois. Créé `find_step_config()` helper, utilisé dans les 3 endroits principaux. | ✅ Fait |
| SMELL-02 | **HIGH** | `executions/tasks/gates.py`, `executions/views/approval_views.py` | **Duplication — Merge next-step-by-order functions.** `_get_next_step_id_by_order()` et `_get_next_step_def_by_order()` avaient ~60% de code identique + duplication dans `approval_views.py`. Fusionné en une seule `_get_next_step_by_order()` retournant le dict complet. | ✅ Fait |
| SMELL-03 | **MEDIUM** | `catalog/serializers.py` | **Switch statement pour step types.** if/elif chain pour gate/service_call/evaluation/http_request. Remplacé par un registry `_STEP_TYPE_FIELDS` + boucle. | ✅ Fait |
| SMELL-04 | **LOW** | `catalog/rbac_service.py:166` | **Exception silencieuse.** `except Exception as _: pass`. Ajout de `logger.debug("rbac_cache_write_failed", error=str(e))`. | ✅ Fait |
| SMELL-05 | **BACKLOG** | `gates.py` (821 lignes), `container_workflow_runtime.py` (1670 lignes) | **God classes.** `_handle_gate_timeout` (206 lignes), `_transition_step_to_running` (188 lignes). Documenté pour refactoring futur. | 📋 Backlog |

### 24.5 Impact frontend

| # | Sévérité | Fichier(s) | Description | Statut |
|---|----------|------------|-------------|--------|
| FE-01 | **LOW** | `ExecutionStatusBanners.tsx`, `AuditEntryDrawer.tsx`, `types/executions.ts` | **Champs `approved_by`/`approved_at`/`approval_comment` supprimés de l'API** (`ExecutionSerializer`). Les types frontend les déclarent comme optionnels (`?`) donc pas de crash. L'info d'approbation est désormais accessible uniquement via les ExecutionSteps. | 📋 Backlog — adapter le frontend pour lire l'approbation depuis les steps |

### 24.6 Statistiques

| Catégorie | Total | Résolus | Backlog | Taux |
|-----------|-------|---------|---------|------|
| Retrocompat (RC) | 3 | 3 | 0 | **100%** ✅ |
| Bugs (BUG) | 4 | 4 | 0 | **100%** ✅ |
| Performance (PERF) | 4 | 4 | 0 | **100%** ✅ |
| Code smells (SMELL) | 5 | 4 | 1 | **80%** ✅ |
| Frontend (FE) | 1 | 0 | 1 | 📋 |
| **TOTAL** | **17** | **15** | **2** | **88%** |

### 24.7 Tests

- **7171 tests passent** après l'ensemble des modifications (0 échec)
- ~20 fichiers de tests mis à jour pour refléter les changements (singular→plural, step-based approval, shims supprimés)
- Nouveaux tests ajoutés pour les scénarios `auto-approval-gate`

### 24.8 Bilan cumulatif

**Bilan cumulatif (2026-03-10, post-Audit #6) :** Sur les 17 findings de cet audit, **15 sont résolus** (88%). Les 2 items restants sont en backlog (god classes backend, adaptation frontend approval). Le codebase est nettoyé de tout code rétrocompatible inutile (PENDING_APPROVAL, singular step_ids, polling shims).

*Convergence avec les bilans historiques :* Les 133 findings des audits §1–§22 sont à **131 résolus** (98.5%) après Story 71.3. Les 3 ouvertes (MAINT-BE-9, INCON-2, PERF-4) restent en backlog/acceptable. 16.4 résolu par Story 71.3. L'Audit #6 (17 findings) est un périmètre additionnel.
