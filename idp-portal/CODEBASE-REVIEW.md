# Revue Exhaustive du Codebase — IDP Portal

**Date :** 2026-02-16 (mise à jour)
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
14. [Récapitulatif par priorité](#14-récapitulatif-par-priorité)

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

### BUG-BE-7 [LOW] — ENCORE PRÉSENT — Normalisation environnement dupliquée
**Fichier :** `executions/views/scheduled_views.py:366-386`

```python
if environment is not None:
    validate_environment_against_inventory(environment, user_id=request.user.id)
    se.environment = EnvironmentHelper.normalize(environment)  # Ligne 368

if target_names is not None:
    if len(target_names) == 0:
        # ...
        if environment is not None:
            validate_environment_against_inventory(environment, user_id=request.user.id)
            se.environment = EnvironmentHelper.normalize(environment)  # Ligne 386 — DOUBLON
```

Quand `target_names == []` ET `environment is not None`, la validation et normalisation sont exécutées deux fois. Impact faible (idempotent) mais coût de performance inutile (requête inventory doublée).

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
### PERF-4 [LOW] — BACKLOG — `<style>` inline dans les fonctions render

Tags `<style>` injectés dans le DOM à chaque render. Impact négligeable.

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

### INCON-4 [LOW] — INTENTIONNEL — `IntegerField` pour les booléens (compatibilité Oracle)
**Fichiers :** `profiles/models.py:106-107` (`is_admin`, `is_auditor`)

Intentionnel pour Oracle `NUMBER(1)` CHECK constraint. Properties `is_admin_bool` et `is_auditor_bool` fournies (lignes 118-126). Serializers convertissent en boolean (lignes 26, 94). Pas un bug.

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

## 14. Récapitulatif par priorité

### Issues OUVERTES restantes

#### HIGH (à traiter rapidement)

| # | Issue | Type | Effort |
|---|-------|------|--------|
| ~~BUG-FE-1~~ | ~~`notification({ title })` → `message`~~ ⚠️ INVALIDÉ — `title` est CORRECT en Ant Design 6.2 | Frontend | — |
| ~~BUG-FE-2~~ | ~~`<Alert title=...>` → `message=`~~ ⚠️ INVALIDÉ — `title` est CORRECT en Ant Design 6.2 | Frontend | — |
| BUG-FE-1b | `notification({ message: })` → `title:` — re-corriger 9 fichiers changés par 30-4 (API dépréciée) | Frontend | Trivial |
| BUG-FE-2b | `<Alert message=...>` → `title=` — re-corriger 15 occurrences changées par 30-4 (API dépréciée) | Frontend | Trivial |

#### MEDIUM (à planifier)

| # | Issue | Type | Effort |
|---|-------|------|--------|
| NEW-1 | `CatalogActionViewSet.get_queryset()` recrée le queryset | Backend | Faible |
| ~~NEW-2~~ | ~~TODO actifs : ServiceNow, platform adapter, simulated response~~ ✅ RESOLVED (Story 30.15) | Backend | — |
| NEW-3 | Cache RBAC invalidation placeholder | Backend | Moyen |
| INCON-2 | MD5 hash collision (documenté, acceptable pour N<1000) | Backend | — |

#### LOW (backlog)

| # | Issue | Type |
|---|-------|------|
| BUG-BE-7 | Normalisation environnement dupliquée | Backend |
| ~~NEW-4~~ | ~~`except Exception` trop larges (5 fichiers)~~ ✅ RESOLVED (Story 30.15) | Backend |
| PERF-4 | `<style>` inline dans render | Frontend |
| INCON-4 | IntegerField booleans (intentionnel Oracle) | Backend |

---

### Issues RÉSOLUES (résumé)

| Catégorie | Résolues | Ouvertes |
|-----------|----------|----------|
| Endpoints manquants | 7/7 | 0 |
| Bugs backend | 6/7 | 1 (LOW) |
| Bugs frontend | 3/5 | 2 (HIGH — INVALIDÉS, remplacés par BUG-FE-1b/2b) |
| Sécurité | 11/11 | 0 |
| Format API | 4/4 | 0 |
| Race conditions | 3/3 | 0 |
| Gestion d'erreurs | 5/5 | 0 |
| Performance | 3/4 | 1 (LOW) |
| Code mort | 11/11 | 0 |
| Accessibilité | 3/3 | 0 |
| Celery | 5/5 | 0 |
| Incohérences modèles | 4/5 | 1 (MEDIUM, documenté) |
| **Sous-total original** | **65/72** | **5** |
| Nouveaux findings | — | **4** |
| **Total** | **65** | **9** |

---

**Bilan global :** Sur les 65 findings originaux, **62 sont entièrement résolus** (BUG-FE-1/2 invalidés = non-bugs), **3 restent ouverts** (1 MEDIUM backend, 2 LOW). **6 nouveaux findings** ont été identifiés : 4 précédents + BUG-FE-1b et BUG-FE-2b (re-corriger les fichiers changés par 30-4 qui utilisent maintenant l'API dépréciée `message` au lieu de `title`).

**Priorité immédiate :** BUG-FE-1b et BUG-FE-2b — re-corriger les fichiers qui utilisent l'API dépréciée `message:` / `message=` (introduits par Story 30-4) → ramener vers `title:` / `title=`.
