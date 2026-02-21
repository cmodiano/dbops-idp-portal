# Revue Exhaustive du Codebase — IDP Portal

**Date :** 2026-02-21 (mise à jour — ajout audit SOLID)
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
13. [Nouveaux findings](#13-nouveaux-findings)
14. [Analyse SOLID — Backend](#14-analyse-solid--backend)
15. [Analyse SOLID — Frontend](#15-analyse-solid--frontend)
16. [Récapitulatif par priorité](#16-récapitulatif-par-priorité)

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

### BUG-BE-1 [CRITICAL] — ✅ RESOLVED — Filtres écrasés quand `tags_filter` est fourni
**Fichier :** `catalog/models.py:83-131`

~~Le queryset filtré par `status`/`item_type` est remplacé par un nouveau queryset.~~

**Fix appliqué :** `search_by_tags()` utilise maintenant `queryset = self` (chaîne au lieu de remplacer). Docstring explicite : « search_by_tags() now preserves queryset chain ».

---

### BUG-BE-2 [HIGH] — ✅ RESOLVED — `secret_service_id` silencieusement ignoré à la création
**Fichier :** `integrations/services.py:99-114`

~~Le champ `secret_service_id` n'était jamais passé à `create()`.~~

**Fix appliqué :** `secret_service_id=integration_data.get('secret_service_id')` ajouté dans le `create()` (ligne 113). Validation FK ajoutée (lignes 100-102).

---

### BUG-BE-3 [HIGH] — ✅ RESOLVED — Binding `user_id` dans structlog après la réponse
**Fichier :** `core/middleware.py:111-121`

~~Le `user_id` était bindé après `self.get_response(request)`.~~

**Fix appliqué :** Le bind est maintenant **avant** `self.get_response(request)` (ligne 116 avant ligne 121). Commentaire explicite en ligne 111.

---

### BUG-BE-4 [HIGH] — ✅ RESOLVED — Calcul récurrence placeholder `+1 jour`
**Fichier :** `executions/utils.py:667-719`

~~Toutes les récurrences utilisaient un placeholder `+1 day`.~~

**Fix appliqué :** Implémentation complète avec calcul spécifique par type :
- `daily` : calcul basé sur `hour`/`minute` (lignes 679-685)
- `weekly` : calcul basé sur `day_of_week` ISO (lignes 687-697)
- `cron` : utilisation de `croniter` pour expressions cron (lignes 699-713)

---

### BUG-BE-5 [MEDIUM] — ✅ RESOLVED — Cache catalogue contourne la pagination
**Fichier :** `catalog/views.py:862-908`

~~Le cache retournait le résultat complet sans pagination.~~

**Fix appliqué :** `page` et `page_size` inclus dans la clé de cache (lignes 870-871). Pagination appliquée via `self.paginate_queryset()` (ligne 884) avant mise en cache. Fallback avec info pagination manuelle (lignes 895-903).

---

### BUG-BE-6 [LOW] — ✅ RESOLVED (Story 30.3) — Dead code `if not action`
**Fichier :** `idp_auth/services.py:134`

~~`get()` suivi de `if not action` (dead code).~~

**Fix appliqué :** Code mort supprimé. `action` utilisé directement dans `get_or_create()`.

---

### ✅ BUG-BE-7 [LOW] — RESOLVED (Story 30.16) — Normalisation environnement dupliquée
**Fichier :** `executions/views/scheduled_views.py:366-368`

**Fix appliqué :** Suppression des lignes 384-386 (AVANT suppression) qui dupliquaient la validation/normalisation d'environnement déjà effectuée aux lignes 366-368. La validation s'exécute maintenant une seule fois en amont, avant le traitement de `target_names`.

**Impact du bug :** Double appel `validate_environment_against_inventory()` coûteux (requête inventaire RBAC) quand `target_names=[]` ET `environment≠null`.

---

## 3. Bugs logiques — Frontend

### BUG-FE-1 [HIGH] — ✅ RESOLVED (Story 30.13) — `notification({ title: ... })` est CORRECT en Ant Design 6.2

**Analyse initiale (erronée) :** On pensait que `title` était ignoré et qu'il fallait utiliser `message`.

**Réalité vérifiée dans le code source Ant Design 6.2.2 :**
- `antd/es/notification/interface.d.ts:27` : `message` porte l'annotation `/** @deprecated Please use 'title' instead */`
- `antd/es/notification/useNotification.js:150` : deprecation mapping `[['btn', 'actions'], ['message', 'title']]`
- **`title:` est la prop CORRECTE (nouvelle API)**. `message:` est la prop **dépréciée**.

**Fix appliqué (Story 30.13) :** 51 occurrences de `notification.*({{ message:` corrigées en `title:` dans 11 fichiers (ExecutionWizard.tsx, useEditExecution.ts, useWorkflowExportImport.tsx, BusinessRulesPolicyPanel.tsx, FeatureFlagsPanel.tsx, useExecutionRestart.ts, ProfilesAdminPanel.tsx, ExecutionsPage.tsx, ProfileImportModal.tsx, AdminAnalyticsDashboard.tsx, IntegrationsTable.tsx).

---

### BUG-FE-2 [HIGH] — ✅ RESOLVED (Story 30.13) — `<Alert title=...>` est CORRECT en Ant Design 6.2

**Analyse initiale (erronée) :** On pensait que `title=` devenait un tooltip HTML et qu'il fallait utiliser `message=`.

**Réalité vérifiée dans le code source Ant Design 6.2.2 :**
- `antd/es/alert/Alert.d.ts:43` : `message` porte l'annotation `/** @deprecated please use 'title' instead. */`
- `antd/es/alert/Alert.js:88` : deprecation mapping `[['closeText', 'closable.closeIcon'], ['message', 'title']]`
- **`title=` est la prop CORRECTE (nouvelle API)**. `message=` est la prop **dépréciée**.

**Fix appliqué (Story 30.13) :** 22 occurrences de `<Alert message=` corrigées en `title=` dans 10 fichiers (ExecutionDetailDrawer.tsx, ProfileForm.tsx, ActionWizard.tsx, AuditPage.tsx, WorkflowValidationAlert.tsx, ProfileWizard.tsx, CalendarPage.tsx, IntegrationForm.tsx, ActionPalette.tsx, BusinessRulePolicyModal.tsx).

---

### BUG-FE-3 [MEDIUM] — ✅ RESOLVED — `Math.random()` dans un `rowKey` React
**Fichier :** `components/catalog/ActionTable.tsx:312`

**Fix appliqué :** `rowKey={(record) => record.id ?? \`temp-${record.name}\`}` — identifiant stable.

---

### BUG-FE-4 [MEDIUM] — ✅ RESOLVED (Story 30.4) — Boucle infinie potentielle dans `useTargetInventory`
**Fichier :** `hooks/useTargetInventory.ts:47-49`

**Fix appliqué :** `inventoryDataRef = useRef(inventoryData)` utilisé pour lire `inventoryData` sans l'inclure dans les dépendances du `useEffect`. Commentaire `eslint-disable` avec justification.

---

### BUG-FE-5 [MEDIUM] — ✅ RESOLVED — Dépendance manquante dans useEffect
**Fichier :** `hooks/useExecutionDetail.ts:91-96`

**Fix appliqué :** `[openExecutionId, loadExecutionDetail]` — les deux dépendances sont maintenant correctement incluses.

---

## 4. Problèmes de sécurité

### SEC-1 [HIGH] — ✅ RESOLVED (Story 30.1) — `DEBUG` par défaut à `True`
**Fichier :** `idp_backend/settings.py:39`

**Fix appliqué :** `DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'` — opt-in explicite.

---

### SEC-2 [HIGH] — ✅ RESOLVED (Story 30.1) — `SECRET_KEY` fallback en dur
**Fichier :** `idp_backend/settings.py:28-35`

**Fix appliqué :** `ImproperlyConfigured` levée si `SECRET_KEY` ou `DJANGO_SECRET_KEY` absent de l'environnement. Plus de fallback hardcodé.

---

### SEC-3 [HIGH] — ✅ RESOLVED (Story 30.1) — `JWT_SECRET_KEY` par défaut à chaîne vide
**Fichier :** `idp_backend/settings.py:348-355`

**Fix appliqué :** `ImproperlyConfigured` levée si `JWT_SECRET_KEY` absent ou vide. Plus de chaîne vide par défaut.

---

### SEC-4 [HIGH] — ✅ RESOLVED (Story 30.5)
`fetchInventoryItems` migré vers `apiFetchRaw()` avec token JWT et correlation ID. Cache sessionStorage avec TTL 5min. Fallback 503.

### SEC-5 [MEDIUM] — ✅ RESOLVED (Story 30.5)
Extension allowlist : `.png`, `.jpg`, `.jpeg`, `.svg`, `.gif`. 11 tests.

### SEC-6 [MEDIUM] — ✅ RESOLVED (Story 30.5)
Validation magic bytes via `puremagic`. Taille max 2MB. 5 tests.

### SEC-7 [MEDIUM] — ✅ RESOLVED (Story 30.5)
SVG sanitisé via `defusedxml` : `<script>`, event handlers, `javascript:` href supprimés. 11 tests.

### SEC-8 [MEDIUM] — ✅ RESOLVED (Story 30.5)
Guard production : log CRITICAL si `AUTH_DEV_BYPASS=True` + `DEBUG=False` (ligne 82-86 dans `views.py`). 5 tests.

### SEC-9 [MEDIUM] — ✅ RESOLVED (Story 30.5, validation)
Credentials Celery : `credential_ref` (format `vault:...`) stocké, résolu via `VaultService` dans la tâche. 3 tests validation.

### SEC-10 [MEDIUM] — ✅ RESOLVED (Story 30.5)
CORS unifié sur `X-Correlation-ID`. Fallback legacy `X-Idp-Request-Id` maintenu. 4 tests.

### SEC-11 [LOW] — ✅ RESOLVED (Story 30.5, documentation)
Token fragment URL documenté comme limitation connue (dev bypass only, ligne 109-113 dans `views.py`).

---

## 5. Incohérences API (format de réponse)

### APIFMT-1 [HIGH] — ✅ RESOLVED — `validateIntegration` retourne `undefined`
**Fichier backend :** `integrations/views.py:261`

**Fix appliqué :** Backend retourne maintenant `{"data": {...}}` — compatible avec `apiFetch` qui unwrap `.data`.

---

### APIFMT-2 [HIGH] — ✅ RESOLVED — `validateAllIntegrations` : même problème
**Fichier backend :** `integrations/views.py:298`

**Fix appliqué :** `return Response({"data": stats})` — format cohérent.

---

### APIFMT-3 [MEDIUM] — ✅ RESOLVED — Endpoints `/reference/*` retournent des arrays nus
**Fichier :** `reference/views.py`

**Fix appliqué :** Tous les endpoints reference retournent `Response({"data": serializer.data})` (lignes 57, 90, 117). CREATE/UPDATE/DELETE aussi en format `{"data": ...}`.

---

### APIFMT-4 [MEDIUM] — ✅ RESOLVED — Catalogue list sans info de pagination
**Fichier :** `catalog/views.py:884-903`

**Fix appliqué :** Pagination via `get_paginated_response()` avec fallback `"pagination": {"page": 1, "page_size": total, "total": total, "total_pages": 1}`.

---

## 6. Race conditions & concurrence

### ✅ RACE-1 [HIGH] — Polling infini sans limite de retry — RESOLVED (Story 30.7)
`retry_count` + `MAX_POLLING_RETRIES=20` ajoutés aux 5 tâches de polling.

### ✅ RACE-2 [MEDIUM] — `update_action()` sans `select_for_update()` — RESOLVED (Story 30.7)
`select_for_update()` ajouté dans `update_action()`, `update_status()`, `delete_action()`, `deactivate_action()`. Confirmé dans `catalog/services.py`.

### ✅ RACE-3 [MEDIUM] — Caches in-memory non partagés entre workers — RESOLVED (Story 30.7)
Comportement per-worker documenté et accepté. Voir `docs/architecture/caching-strategy.md`.

---

## 7. Gestion d'erreurs

### ✅ ERR-1 [HIGH] — `.catch(() => {})` avale les erreurs — RESOLVED (Story 30.8)
### ✅ ERR-2 [HIGH] — Validation croisée absente sur `IntegrationUpdateSerializer` — RESOLVED (Story 30.8)
### ✅ ERR-3 [MEDIUM] — `create_action()` ignore silencieusement un `integration_id` invalide — RESOLVED (Story 30.8)
### ✅ ERR-4 [MEDIUM] — Audit signals swallowed silencieusement — RESOLVED (Story 30.8)
### ✅ ERR-5 [MEDIUM] — Workflow bloqué après timeout de gate — RESOLVED (Story 30.7)

---

## 8. Performance (N+1, caches, re-renders)

### ✅ PERF-1 [MEDIUM] — RESOLVED (Story 30.9) — N+1 queries dans `_resolve_user_names`
### ✅ PERF-2 [MEDIUM] — RESOLVED (Story 30.9) — Tous les workflows chargés en mémoire
### ✅ PERF-3 [MEDIUM] — RESOLVED (Story 30.9) — Regex recompilées à chaque appel
### ✅ PERF-4 [LOW] — DOCUMENTÉ BACKLOG (Story 30.16) — `<style>` inline dans les fonctions render

3 composants utilisent `<style>` inline pour des pseudo-classes, animations @keyframes et media queries (non exprimables en style object React natif `style={{...}}`). Migration possible vers CSS Modules ou CSS-in-JS mais nécessite refactoring (effort > bénéfice pour 3 composants).

Fichiers analysés :
- `frontend/src/components/execution/WorkflowExecutionGraph.tsx` — animation pulse nœud actif
- `frontend/src/components/catalog/ActionTable.tsx` — hover row et media query responsive
- `frontend/src/components/execution/ExecutionTimeline.tsx` — animation pulse étape en cours

Impact négligeable. Cas justifiés techniquement. ADR recommandé si migration CSS Modules prévue (backlog).

---

## 9. Code mort

### Backend

| # | Fichier | Description |
|---|---------|-------------|
| DEAD-BE-1 | `catalog/models.py:51-58` | ✅ RESOLVED (Story 30.10) — `normalize_tag_name()` alignée (espaces → `_`) |
| DEAD-BE-2 | `idp_auth/services.py` | ✅ RESOLVED (Story 30.3) — code mort supprimé |
| DEAD-BE-3 | `executions/tasks.py` | ✅ RESOLVED (Story 30.10) — appel inutile supprimé |
| DEAD-BE-4 | `core/models.py` | ✅ RESOLVED (Story 30.10) — import doublon supprimé |
| DEAD-BE-5 | `inventory/services.py` | ✅ RESOLVED (Story 30.10) — imports backward compat documentés, `re` supprimé |

### Frontend

| # | Fichier | Description |
|---|---------|-------------|
| DEAD-FE-1 | `services/catalog_service.ts` | ✅ RESOLVED (Story 30.10) — `fetchRecentActions` supprimé |
| DEAD-FE-2 | `services/admin_service.ts` | ✅ RESOLVED (Story 30.10) — `listActions` supprimée |
| DEAD-FE-3 | `types/api.ts` | ✅ RESOLVED (Story 30.10) — barrel re-export intentionnel (213 imports) |
| DEAD-FE-4 | `utils/profileOptions.ts` | ✅ RESOLVED (Story 30.10) — `ENVIRONMENT_OPTIONS` supprimé |
| DEAD-FE-5 | `utils/impactRulesSchema.ts` | ✅ RESOLVED (Story 30.10) — `IMPACT_ENVIRONMENTS` supprimé |
| DEAD-FE-6 | 3 fichiers | ✅ RESOLVED (Story 30.10) — factorisé dans `utils/stepDescriptions.ts` |

---

## 10. Accessibilité & thème

### ✅ A11Y-1 [HIGH] — RESOLVED (Story 30.11) — Couleurs dark-theme hardcodées dans `StepDetailDrawer`
### ✅ A11Y-2 [HIGH] — RESOLVED (Story 30.11) — Status badges avec background dark hardcodé
### ✅ A11Y-3 [MEDIUM] — RESOLVED (Story 30.11) — `StructuredErrorCard` avec couleurs texte hardcodées

**Point positif :** Bonne utilisation globale de `role`, `aria-label`, `aria-live`, `aria-expanded`, et gestion clavier.

---

## 11. Problèmes Celery / tâches async

### ✅ CELERY-1 [HIGH] — Polling infini → RESOLVED (Story 30.7) — Voir RACE-1
### ✅ CELERY-2 [MEDIUM] — Credentials en clair → RESOLVED (Story 30.5) — Voir SEC-9
### ✅ CELERY-3 [MEDIUM] — Event loop asyncio → RESOLVED (Story 30.7)
### ✅ CELERY-4 [MEDIUM] — Gate timeout → RESOLVED (Story 30.7)
### ✅ CELERY-5 [LOW] — Gate timeout message → RESOLVED (Story 30.7)

---

## 12. Incohérences modèles & serializers

### INCON-1 [MEDIUM] — ✅ RESOLVED — Normalisation de tags incohérente

**Fix appliqué :** Les deux fichiers utilisent maintenant la même logique : `name.strip().lower().replace(" ", "_")`. `catalog/services.py` importe `normalize_tag_name` depuis `catalog/models.py`.

---

### INCON-2 [MEDIUM] — DOCUMENTÉ ET ACCEPTABLE — Audit hash MD5 collisions
**Fichier :** `integrations/signals.py:50`

Le hash MD5 tronqué est toujours utilisé mais documenté dans le code (lignes 42-49) :
- 9 codes en production → probabilité collision < 0.00001%
- Pour N=1000 (futur) → ~0.0005%
- Test de détection de collisions en dev-time

---

### INCON-3 [MEDIUM] — ✅ RESOLVED (Story 30.12) — Audit signals retournent toujours `user_id='system'`
**Fichier :** `integrations/signals.py:19-31`

**Fix appliqué :** `_get_user_id_from_context()` utilise `get_current_user()` du middleware pour capturer l'utilisateur authentifié. Fallback `'system'` uniquement sans contexte utilisateur.

---

### ✅ INCON-4 [LOW] — INTENTIONNEL - DOCUMENTÉ (Story 30.16) — `IntegerField` pour les booléens (compatibilité Oracle)
**Fichiers :** `profiles/models.py:106-107` (`is_admin`, `is_auditor`)

Intentionnel pour Oracle `NUMBER(1)` CHECK constraint. Properties `is_admin_bool` et `is_auditor_bool` fournies (lignes 118-126). Serializers convertissent en boolean (lignes 26, 94). Pas un bug.

**Commentaire explicatif ajouté** dans `profiles/models.py` (lignes 106-109) documentant le choix Oracle, les properties booléennes et la conversion DRF automatique.

---

### INCON-5 [LOW] — ✅ RESOLVED (Story 30.12, documentation) — `User.is_authenticated = True` en attribut de classe
**Fichier :** `idp_auth/models.py:72`

Documenté dans le code : attribut de classe intentionnel pour compatibilité Django auth middleware. SAML 2.0 garantit l'identité, pas de soft-delete sur User. `AnonymousUser` retourne `False` automatiquement.

---

## 13. Nouveaux findings

### NEW-1 [MEDIUM] — `CatalogActionViewSet.get_queryset()` recrée le queryset après `search_by_tags`
**Fichier :** `catalog/views.py:793-806`

```python
if tags_filter:
    tag_names = [t.strip() for t in tags_filter.split(',')]
    queryset = Action.objects.search_by_tags(tag_names)           # Repart de zéro
    queryset = queryset.filter(status=ActionStatus.PUBLISHED).with_tags().with_creator()

if category and category.lower() not in ('tout', 'all', 'mes-actions'):
    tag_name = normalize_tag_name(category)
    if tag_name:
        queryset = Action.objects.search_by_tags([tag_name])      # Repart de zéro
        queryset = queryset.filter(status=ActionStatus.PUBLISHED).with_tags().with_creator()
```

Bien que `search_by_tags()` ait été corrigé pour chaîner dans `catalog/services.py`, le ViewSet `CatalogActionViewSet` recrée le queryset au lieu de chaîner. Les filtres `q`, `engine`, `environment` appliqués après seront préservés, mais la logique est fragile : si `category` ET `tags` sont fournis, seul `category` est appliqué (le queryset de `tags` est écrasé).

**Fix :** `queryset = queryset.search_by_tags(tag_names)` (chaîner, ne pas recréer).

---

### NEW-2 [MEDIUM] — ~~Fonctionnalités non implémentées derrière des TODO actifs~~ RESOLVED (Story 30.15)
**Fichiers :**
- `services/servicenow_service.py:32` — ✅ RESOLVED: TODO supprimé. Docstring mise à jour, méthodes stubs avec `NotImplementedError` explicite. ServiceNow n'est pas atteignable en production (placeholder uniquement en tests).
- `executions/workflow_runtime.py:708` — ✅ RESOLVED: TODO supprimé. Implémentation réelle via `get_platform_adapter()` + `build_auth_headers()`. Fallback CRITICAL si adapter indisponible avec audit trail.
- `executions/workflow_runtime.py:726` — ✅ RESOLVED: TODO supprimé. PolicyEvaluator reçoit maintenant la vraie réponse adapter (ou réponse simulée documentée avec flag `simulated=True`).

---

### NEW-3 [MEDIUM] — Cache RBAC invalidation placeholder (noop)
**Fichier :** `profiles/views.py:31-38`

```python
def invalidate_permissions_cache() -> None:
    """..."""
    # Placeholder - actual implementation will be added when RBAC service is migrated
    pass
```

Appelée après modification de profils mais ne fait rien → permissions RBAC potentiellement stales jusqu'à expiration du cache.

---

### NEW-4 [LOW] — ~~`except Exception as e:` trop large dans plusieurs fichiers~~ RESOLVED (Story 30.15)
**Fichiers :**
- `integrations/validation_service.py:62` — ✅ RESOLVED: Restreint à `except (DatabaseError, OperationalError)`. Erreurs DB distinguées des erreurs de validation.
- `services/jira_service.py:344` — ✅ RESOLVED: Documenté `noqa: BLE001` — httpx peut lever StreamClosed, DecodeError, etc. Fallback sûr (chaîne vide) ne masque pas l'erreur HTTP.
- `services/jira_service.py:389` — ✅ RESOLVED: Documenté `noqa: BLE001` — pattern résilience, converti en ServiceUnavailableError avec logging complet.
- `executions/views/github_webhooks.py:175` — ✅ RESOLVED: Restreint à `except (DatabaseError, OperationalError)`.
- `executions/views/github_webhooks.py:305` — ✅ RESOLVED: Documenté `noqa: BLE001` — webhook doit retourner 200 même si broadcast échoue (résilience).
- `executions/views/terraform_webhooks.py:184` — ✅ RESOLVED: Restreint à `except (DatabaseError, OperationalError)`.
- `executions/views/terraform_webhooks.py:320` — ✅ RESOLVED: Documenté `noqa: BLE001` — même pattern résilience que GitHub webhooks.

---

### NEW-5 [LOW] — `<style>` inline dans les fonctions render (déjà reporté PERF-4)
Inchangé. Impact négligeable.

---

## 14. Analyse SOLID — Backend

**Date :** 2026-02-21
**Scope :** Django backend (`django_backend/`)

### Points positifs (acquis des Stories 33.x)

- **OCP — Registry pattern** : `adapters/registry.py` (AdapterRegistry), `services/registry.py` (ServiceRegistry), `executions/interpreters/registry.py` (OutputInterpreterRegistry) — ajout de plateforme/service sans modifier le code existant.
- **DIP — Module DI** : `core/di.py` — service locator léger avec `override_service()` pour les tests.
- **SRP — Views packages** : `catalog/views/` (4 fichiers) et `executions/views/` (7 fichiers) correctement découpés par responsabilité.
- **SRP — Tasks package** : `executions/tasks/` (3 fichiers : polling, gates, retry).

### SOLID-BE-1 [HIGH] — SRP — `executions/utils.py` (828 lignes) — module « fourre-tout »

15 fonctions utilitaires non liées couvrant 6 domaines : validation d'environnement, parsing de steps workflow, helpers RBAC/permissions, utilitaires date/pagination, validation mutex, et scheduling cron. Un module devrait avoir une seule raison de changer.

**Fix recommandé :** Éclater en `executions/utils/environment.py`, `executions/utils/workflow_parsing.py`, `executions/utils/scheduling.py`, etc.

### SOLID-BE-2 [HIGH] — SRP — `executions/workflow_runtime.py` (1296 lignes)

`WorkflowRuntime` a 12 méthodes couvrant : exécution de steps, logique de retry (`_execute_step_with_retry`, `_is_retryable_error`), détection de boucles, gestion audit trail, évaluation de policy (`_evaluate_policy_if_needed`), appel adapter plateforme (`_call_platform_adapter`), et évaluation de gates. Au moins 5 responsabilités distinctes.

**Fix recommandé :** Extraire `RetryHandler`, `AuditTrailManager`, `PolicyEvaluator` (déjà ébauché à 75 lignes), `PlatformAdapterCaller` en classes dédiées.

### SOLID-BE-3 [HIGH] — OCP — `executions/tasks/polling.py` (1054 lignes) — 5 tâches quasi-identiques

5 tâches Celery (`poll_aap_job_status`, `poll_tower_job_status`, `poll_azure_devops_run_status`, `poll_github_actions_run_status`, `poll_terraform_cloud_run_status`) dupliquent chacune ~150 lignes de logique similaire : construction adapter, appel `get_status()`, `_update_execution_from_poll()`, re-schedule. Pour ajouter Jenkins, il faut ajouter une nouvelle fonction de 150 lignes.

**Fix recommandé :** Une seule tâche générique `poll_platform_job_status` qui délègue à l'`AdapterRegistry` existant — fermé à la modification, ouvert à l'extension.

### SOLID-BE-4 [MEDIUM] — SRP — `executions/services.py` (1121 lignes) — 2 classes sans rapport

`ExecutionService` (ligne 32) et `SchedulingService` (ligne 862) dans le même fichier. Entités différentes (`Execution` vs `ScheduledExecution`), aucun état partagé.

**Fix recommandé :** Séparer en `executions/execution_service.py` et `executions/scheduling_service.py`.

### SOLID-BE-5 [MEDIUM] — SRP — `inventory/services.py` (933 lignes) — `InventoryService` surchargé

18 méthodes couvrant : exécution requêtes Oracle, appels API externes, lecture statique de targets, agrégation permissions RBAC (`_aggregate_profile_permissions`), chargement/filtrage targets (`_load_targets`, `_apply_rbac_chain_for_user`). 4-5 domaines de responsabilité.

**Fix recommandé :** Extraire `InventoryQueryExecutor`, `RBACPermissionAggregator`, `TargetLoader` en classes dédiées.

### SOLID-BE-6 [MEDIUM] — LSP — `catalog/serializers.py:450-461`

`ActionSerializer.create()` et `update()` lèvent `NotImplementedError`, violant le contrat de `ModelSerializer` (toute appel à `serializer.save()` échoue). Violation LSP textbook.

**Fix recommandé :** Séparer en `ActionReadSerializer` (sans create/update) et `ActionWriteSerializer` (`ActionCreateSerializer` existant suffit).

### SOLID-BE-7 [MEDIUM] — OCP — `executions/services.py:392-408` — `launch_workflow()` switch sur `item_type`

```python
if action.item_type == "workflow":
    from executions.container_workflow_runtime import ContainerWorkflowRuntime
    ContainerWorkflowRuntime(execution).run()
elif getattr(settings, "SIMULATE_EXECUTION_DEV", False):
    from executions.simulation_service import SimulationService
```

Import conditionnel de classes concrètes + `if/elif` sur type string = violation OCP + DIP.

**Fix recommandé :** `RuntimeRegistry` avec enregistrement `workflow → ContainerWorkflowRuntime`, `action → StandardRuntime`, `simulation → SimulationService`.

### SOLID-BE-8 [MEDIUM] — DIP — `catalog/views/action_views.py:437,454,493`

`destroy()`, `deactivate()` et `reactivate()` instancient `CatalogService()` directement au lieu d'utiliser `self.get_catalog_service()` (déjà disponible ligne 67-69). Contourne le mécanisme DI dans les tests.

**Fix recommandé :** Remplacer `service = CatalogService()` par `service = self.get_catalog_service()` (3 occurrences).

### SOLID-BE-9 [MEDIUM] — DIP — Webhooks factory monkey-patch

`executions/views/github_webhooks.py:34` et `executions/views/terraform_webhooks.py:34` utilisent `_execution_service_factory = ExecutionService` au niveau module plutôt que le mécanisme DI de `core/di.py`. Fragile et thread-unsafe en tests.

### SOLID-BE-10 [LOW] — ISP — `adapters/base_adapter.py` — interface trop large

`BaseAdapter` force tous les adapters à implémenter `cancel_execution()`. Pas toutes les plateformes supportent l'annulation. ISP suggèrerait de séparer `ITriggerableAdapter` de `ICancellableAdapter`.

### SOLID-BE-11 [LOW] — DRY/ISP — `catalog/serializers.py` — validation dupliquée

`ActionSerializer` (lignes 248-281) et `ActionCreateSerializer` (lignes 487-509) contiennent des méthodes `validate_engine`, `validate_platform`, et `validate_category` identiques. Changement = modification en 2 endroits.

**Fix recommandé :** Mixin `ActionFieldValidationMixin` partagé entre les deux serializers.

---

## 15. Analyse SOLID — Frontend

**Date :** 2026-02-21
**Scope :** React frontend (`frontend/src/`)

### Métriques globales

| Métrique | Valeur |
|----------|--------|
| Fichiers source (non-test) | ~222 `.tsx`/`.ts` |
| Fichiers test | 165 (74% couverture fichier) |
| Lignes de production | ~35 300 |
| Custom hooks | 32 (4 435 lignes) |
| Contexts | 4 (AuthContext, FeatureFlagContext, ThemeContext, DashboardContext) |

### Points positifs

- **Architecture hooks** : 32 custom hooks pour extraction de logique — pattern sain globalement.
- **Services API** : `api_client.ts` centralisé avec retry 401/429/503, correlation ID, blob/formdata.
- **Tests** : 165 fichiers test, bonne co-location avec les composants.
- **Refactoring récent (Story 33.5)** : `ActionForm.tsx` refactorisé avec `useActionFormState` hook.

### SOLID-FE-1 [CRITICAL] — SRP — `ExecutionTimeline.tsx` (735 lignes) — God component

12+ responsabilités dans un seul composant :
1. Gestion connexion WebSocket (lignes 73-114)
2. Fallback polling automatique WebSocket→polling (lignes 79-84)
3. Machine à états auto-remédiation (lignes 89-177)
4. Fetch suggestions/contexte remédiation (lignes 126-136)
5. State expand/collapse des steps (ligne 138)
6. State drawer de logs (ligne 139)
7. Gestion du focus (lignes 157-162)
8. Annonces aria-live (lignes 185-194)
9. 7 variantes de bannières status (lignes 216-393)
10. Liste timeline elle-même (lignes 489-675)
11. Drawer de logs (lignes 678-732)
12. Tag `<style>` embarqué avec keyframe (lignes 670-675)
13. 59 objets `style={{...}}` inline

**Fix recommandé :** Découper en `ExecutionStatusBanners`, `RemediationPanel`, `TimelineList`, `TimelineStepItem`, `StepLogsDrawer`.

### SOLID-FE-2 [HIGH] — SRP — `CatalogPage.tsx` (606 lignes) — Page god

23 appels `useState`, 8 `useCallback`. Gère : catégories, filtres, liste d'actions, favoris, états de chargement, détail action sélectionnée, stats, environnements, drawer states, wizard d'exécution, ID exécution active, drawer ExecutionView, persistence localStorage.

**Fix recommandé :** Extraire `useCatalogState()` hook (comme fait pour `ActionForm` → `useActionFormState`).

### SOLID-FE-3 [HIGH] — SRP — `AuditPage.tsx` (628 lignes) — Page god

28 usages de hooks combinés. Gère : données table, pagination, chargement, erreur, 6 filtres distincts, tri, drawer avec fetch exécution + steps, export, définitions colonnes inline, squelettes inline.

**Fix recommandé :** Extraire `useAuditFilters()`, composants `AuditTable`, `AuditEntryDrawer`.

### SOLID-FE-4 [HIGH] — DIP — 29 composants importent directement les services

Exemples :
- `WorkflowStepsEditor.tsx` → `admin_service.getEligibleActionsForWorkflow()`
- `ActionWizard.tsx` → 7 fonctions de `admin_service`
- `ExecutionWizard.tsx` → `catalog_service` + `execution_service`

Couplage fort composant ↔ couche transport. Empêche le mocking sans interception au niveau module.

**Fix recommandé :** Passer les appels service via hooks ou props (pattern déjà appliqué dans `ActionForm` post-33.5).

### SOLID-FE-5 [HIGH] — DIP — `api_client.ts` dépend de `notification` (Ant Design)

```typescript
import { notification } from 'antd';
// ligne 182, 213 — notification.warning dans le client API
```

La couche transport API ne devrait pas dépendre du système de notification UI. Crée une dépendance bidirectionnelle.

**Fix recommandé :** Callback injectable pour les notifications de retry 503.

### SOLID-FE-6 [MEDIUM] — Prop drilling `variant` sur 4-5 niveaux

`CatalogPage` → `ActionCard` → `ActionDrawerPreview` → `ExecutionWizard` → `TargetSelectionStep` / `ParametersFormStep` / `ConfirmationStep` → `StructuredErrorCard`. Le flag `isBusinessProfile` est lu depuis `AuthContext` dans `CatalogPage` puis converti en prop string et propagé à travers 5 niveaux.

**Fix recommandé :** Chaque composant enfant lit `useAuth().isBusinessProfile` directement depuis le contexte.

### SOLID-FE-7 [MEDIUM] — ISP — Interfaces de props surchargées

| Composant | Nombre de props |
|-----------|-----------------|
| `TargetSelectionStepProps` | 22 |
| `ParametersFormStepProps` | 17 |
| `ConfirmationStepProps` | 16 |

Les props inventory (`inventoryData`, `inventoryWarnings`, `loadingInventory`, `selectedServerNames`) traversent depuis `ExecutionWizard` — ces données devraient vivre dans un hook ou context dédié.

### SOLID-FE-8 [MEDIUM] — SRP — `WorkflowStepsEditor.tsx` (645 lignes) — 2 composants

`SortableStepCard` (302 lignes) et `WorkflowStepsEditor` (263 lignes) dans le même fichier. `SortableStepCard` gère DnD, autocomplete actions, sélecteurs branches, configuration retry — le tout dans un seul render.

### SOLID-FE-9 [MEDIUM] — SRP — `ExecutionWizard.tsx` — 7 `useEffect` non extraits

Malgré le refactoring Story 17.2, le wizard conserve toute la logique de coordination inline (7 `useEffect`, 2 `eslint-disable-next-line react-hooks/exhaustive-deps`).

### SOLID-FE-10 [MEDIUM] — DRY — Mapping status dupliqué

Mapping status→couleur/label dupliqué indépendamment dans :
- `ExecutionTimeline.tsx` (lignes 24-31, `STATUS_COLOR`)
- `AuditPage.tsx` (lignes 61-66, `STATUS_CONFIG`)
- `pages/executions/executionsColumns.tsx`

**Fix recommandé :** Utility partagé `execution-status.ts`.

### SOLID-FE-11 [LOW] — Couverture test manquante sur composants critiques

| Composant | Lignes | Risque |
|-----------|--------|--------|
| `ParametersFormStep.tsx` | 142 | Step wizard critique, 0 test |
| `SchedulingPanel.tsx` | 327 | Logique scheduling complexe, 0 test |
| `ExecutionsFiltersPanel.tsx` | 280 | Panel filtres, 0 test |
| `BusinessRulePolicyModal.tsx` | 230 | Modal admin, 0 test |

---

## 16. Récapitulatif par priorité

### Issues OUVERTES restantes

#### CRITICAL

| # | Issue | Type | Effort |
|---|-------|------|--------|
| SOLID-FE-1 | `ExecutionTimeline.tsx` (735 lignes) — God component 12+ responsabilités | Frontend | Élevé |

#### HIGH

| # | Issue | Type | Effort |
|---|-------|------|--------|
| BUG-FE-1b | `notification({ message: })` → `title:` (API dépréciée Ant Design 6.2) | Frontend | Trivial |
| BUG-FE-2b | `<Alert message=...>` → `title=` (API dépréciée Ant Design 6.2) | Frontend | Trivial |
| SOLID-BE-1 | `executions/utils.py` (828 lignes) — module fourre-tout 6 domaines | Backend | Moyen |
| SOLID-BE-2 | `executions/workflow_runtime.py` (1296 lignes) — 5 responsabilités | Backend | Élevé |
| SOLID-BE-3 | `executions/tasks/polling.py` — 5 tâches dupliquées au lieu d'un poller générique | Backend | Moyen |
| SOLID-FE-2 | `CatalogPage.tsx` (606 lignes) — 23 useState, page god | Frontend | Moyen |
| SOLID-FE-3 | `AuditPage.tsx` (628 lignes) — 28 hooks, page god | Frontend | Moyen |
| SOLID-FE-4 | 29 composants importent directement les services (couplage DIP) | Frontend | Élevé |
| SOLID-FE-5 | `api_client.ts` dépend de `notification` Ant Design (DIP bidirectionnel) | Frontend | Faible |

#### MEDIUM

| # | Issue | Type | Effort |
|---|-------|------|--------|
| NEW-1 | `CatalogActionViewSet.get_queryset()` recrée le queryset | Backend | Faible |
| NEW-3 | Cache RBAC invalidation placeholder (noop) | Backend | Moyen |
| SOLID-BE-4 | `executions/services.py` — 2 classes non liées dans un module | Backend | Faible |
| SOLID-BE-5 | `inventory/services.py` (933 lignes) — InventoryService surchargé | Backend | Élevé |
| SOLID-BE-6 | `ActionSerializer.create()/update()` lèvent NotImplementedError (LSP) | Backend | Faible |
| SOLID-BE-7 | `launch_workflow()` switch sur item_type (OCP+DIP) | Backend | Moyen |
| SOLID-BE-8 | 3 méthodes ViewSet contournent le DI (`CatalogService()` direct) | Backend | Trivial |
| SOLID-BE-9 | Webhooks factory monkey-patch au lieu de DI | Backend | Faible |
| SOLID-FE-6 | Prop drilling `variant` sur 4-5 niveaux | Frontend | Faible |
| SOLID-FE-7 | Props surchargées (22/17/16 props) sur les step components | Frontend | Moyen |
| SOLID-FE-8 | `WorkflowStepsEditor.tsx` — 2 composants dans 1 fichier | Frontend | Faible |
| SOLID-FE-9 | `ExecutionWizard.tsx` — 7 useEffect non extraits | Frontend | Moyen |
| SOLID-FE-10 | Mapping status dupliqué dans 3 fichiers | Frontend | Faible |

#### LOW (backlog)

| # | Issue | Type | Effort |
|---|-------|------|--------|
| SOLID-BE-10 | `BaseAdapter` force `cancel_execution()` sur tous les adapters (ISP) | Backend | Faible |
| SOLID-BE-11 | Validation dupliquée entre ActionSerializer et ActionCreateSerializer | Backend | Trivial |
| SOLID-FE-11 | Tests manquants : ParametersFormStep, SchedulingPanel, ExecutionsFiltersPanel | Frontend | Moyen |
| INCON-2 | MD5 hash collision (documenté, acceptable pour N<1000) | Backend | — |

---

### Issues RÉSOLUES (résumé)

| Catégorie | Résolues | Ouvertes |
|-----------|----------|----------|
| Endpoints manquants | 7/7 | 0 |
| Bugs backend | 7/7 | 0 |
| Bugs frontend | 3/5 | 2 (BUG-FE-1b/2b) |
| Sécurité | 11/11 | 0 |
| Format API | 4/4 | 0 |
| Race conditions | 3/3 | 0 |
| Gestion d'erreurs | 5/5 | 0 |
| Performance | 4/4 | 0 |
| Code mort | 11/11 | 0 |
| Accessibilité | 3/3 | 0 |
| Celery | 5/5 | 0 |
| Incohérences modèles | 5/5 | 0 |
| **Sous-total original** | **68/72** | **2** |
| Nouveaux findings (§13) | 2/4 | 2 |
| **SOLID Backend** (§14) | — | **11** |
| **SOLID Frontend** (§15) | — | **11** |
| **Total** | **70** | **26** |

---

### Priorités de refactoring recommandées

**Sprint immédiat (quick wins) :**
1. SOLID-BE-8 — Remplacer `CatalogService()` direct par `self.get_catalog_service()` (3 lignes)
2. SOLID-BE-11 — Mixin validation partagé entre serializers
3. SOLID-FE-5 — Injecter callback notification dans `api_client.ts`
4. SOLID-FE-10 — Extraire `execution-status.ts` utility partagé
5. BUG-FE-1b/2b — Migration props dépréciées Ant Design

**Sprint suivant (impact structurel) :**
1. SOLID-BE-3 — Poller générique unifié (1054 → ~200 lignes)
2. SOLID-BE-4 — Séparer ExecutionService et SchedulingService
3. SOLID-FE-1 — Découper ExecutionTimeline (735 → 5 composants)
4. SOLID-FE-2 — Extraire `useCatalogState()` de CatalogPage
5. SOLID-FE-3 — Extraire hooks et sous-composants de AuditPage

**Backlog structurel :**
1. SOLID-BE-1 — Éclater `executions/utils.py` en sous-modules
2. SOLID-BE-2 — Décomposer WorkflowRuntime
3. SOLID-BE-5 — Décomposer InventoryService
4. SOLID-FE-4 — Migration progressive des 29 composants vers hooks pour les appels service

---

**Bilan global (2026-02-21) :** Sur les 72 findings originaux, **68 sont résolus**. L'audit SOLID identifie **22 nouveaux findings** (11 backend, 11 frontend) dont 1 CRITICAL, 8 HIGH, 13 MEDIUM, 4 LOW. Les quick wins (5 items, effort trivial à faible) peuvent être traités immédiatement. Les refactorings structurels (5 items) réduiraient significativement la dette technique sur les modules les plus complexes (`executions/`, `ExecutionTimeline`, `CatalogPage`).
