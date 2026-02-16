# Revue Exhaustive du Codebase — IDP Portal

**Date :** 2026-02-16
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
13. [Récapitulatif par priorité](#13-récapitulatif-par-priorité)

---

## 1. Endpoints manquants (Frontend ↔ Backend)

Le frontend appelle des endpoints qui **n'existent pas** côté backend.

| # | Endpoint | Fichier frontend | Impact |
|---|----------|-----------------|--------|
| **API-MISS-1** | `POST /executions/{id}/approve` | `execution_service.ts:229` | Workflow d'approbation cassé — 404 systématique |
| **API-MISS-2** | `POST /executions/{id}/reject` | `execution_service.ts:256` | Workflow de rejet cassé — 404 systématique |
| **API-MISS-3** | `GET /executions/{id}/remediation` | `execution_service.ts:351` | Suggestions de remédiation inaccessibles |
| **API-MISS-4** | `GET /executions/{id}/remediation-context` | `execution_service.ts:369` | Contexte de remédiation inaccessible |
| **API-MISS-5** | `GET /dashboard/export/csv` | `dashboard_service.ts:172` | Export CSV dashboard impossible |
| **API-MISS-6** | `GET /dashboard/export/pdf` | `dashboard_service.ts:189` | Export PDF dashboard impossible |
| **API-MISS-7** | `GET /users/me/recent-actions` | `catalog_service.ts:142` | Marqué `@deprecated` — faible impact |

**Action :** Implémenter les endpoints manquants côté backend (stories à créer pour API-MISS-1 à API-MISS-6), ou retirer les appels frontend si la fonctionnalité n'est pas prévue.

---

## 2. Bugs logiques — Backend

### BUG-BE-1 [CRITICAL] — Filtres écrasés quand `tags_filter` est fourni
**Fichier :** `catalog/services.py:208-215`
```python
queryset = Action.objects.all()
if status:
    queryset = queryset.filter(status=status)
if item_type:
    queryset = queryset.filter(item_type=item_type)
if tags_filter:
    queryset = Action.objects.search_by_tags(tags_filter)  # Écrase tout !
```
Le queryset filtré par `status`/`item_type` est remplacé par un nouveau queryset. Les filtres précédents sont perdus.

**Fix :** `queryset = queryset.search_by_tags(tags_filter)` (chaîner au lieu de remplacer).

---

### BUG-BE-2 [HIGH] — `secret_service_id` silencieusement ignoré à la création
**Fichier :** `integrations/services.py:100-108`

Le champ `secret_service_id` est accepté par le serializer mais jamais passé à `Integration.objects.create()`. Il sera toujours `None`.

**Fix :** Ajouter `secret_service_id=integration_data.get('secret_service_id')` dans le `create()`.

---

### BUG-BE-3 [HIGH] — Binding `user_id` dans structlog après la réponse
**Fichier :** `core/middleware.py:95-98`

Le `CorrelationIdMiddleware` bind `user_id` dans structlog contextvars **après** `self.get_response(request)`. Le user_id n'est donc jamais présent dans les logs de la requête.

**Fix :** Déplacer le bind avant `self.get_response(request)`, après l'authentification (utiliser un middleware séparé avec un ordre de priorité plus bas).

---

### BUG-BE-4 [HIGH] — Calcul récurrence placeholder `+1 jour`
**Fichier :** `executions/services.py:934-942`
```python
# For now, just add 1 day as a placeholder
pattern.next_execution_date = timezone.now() + timedelta(days=1)
```
Les exécutions planifiées hebdomadaires, mensuelles, ou cron auront toutes un `next_execution_date` incorrect.

**Fix :** Implémenter le vrai calcul basé sur `pattern.pattern_type` et `pattern.cron_expression`.

---

### BUG-BE-5 [MEDIUM] — Cache catalogue contourne la pagination
**Fichier :** `catalog/views.py:862-863`

Quand le cache a un hit, le résultat complet est retourné sans pagination. Même le code path sans cache ne pagine pas.

**Fix :** Appliquer la pagination systématiquement, avant ou après le cache.

---

### BUG-BE-6 [LOW] — `Action.objects.get()` suivi d'un `if not action` (dead code)
**Fichier :** `idp_auth/services.py:134-136`

`get()` lève `DoesNotExist`, ne retourne jamais `None`. Le `if not action` est du code mort.

---

### BUG-BE-7 [LOW] — Ligne dupliquée
**Fichier :** `executions/views/scheduled_views.py:386-387`
```python
se.environment = EnvironmentHelper.normalize(environment)
se.environment = EnvironmentHelper.normalize(environment)  # Doublon
```

---

## 3. Bugs logiques — Frontend

### BUG-FE-1 [HIGH] — `notification({ title: ... })` au lieu de `message` (42+ occurrences)

Ant Design `notification.success/error/warning` utilise `message` comme propriété de titre, pas `title`. La prop `title` est ignorée silencieusement → notifications sans titre visible.

**Fichiers affectés :**
- `hooks/useWorkflowExportImport.tsx` (8 occurrences)
- `pages/admin/ActionsAdminPanel.tsx` (13 occurrences)
- `pages/admin/ProfilesAdminPanel.tsx` (8 occurrences)
- `pages/admin/IntegrationsAdminPanel.tsx` (5 occurrences)
- `components/admin/ProfileImportModal.tsx` (2 occurrences)
- `components/admin/ProfileWizard.tsx` (1 occurrence)
- `components/admin/analytics/AdminAnalyticsDashboard.tsx` (1 occurrence)
- `components/catalog/ExecutionWizard.tsx` (1 occurrence)
- + autres

**Fix :** Rechercher-remplacer global : `title:` → `message:` dans tous les appels `notification.*()`.

---

### BUG-FE-2 [HIGH] — `<Alert title=...>` au lieu de `message=` (14+ occurrences)

Même problème avec le composant `<Alert>`. `title` devient un tooltip HTML natif au lieu du titre de l'alerte.

**Fichiers affectés :**
- `components/admin/ProfileForm.tsx:252,255`
- `components/admin/ActionWizard.tsx:754,757`
- `components/execution/ExecutionTimeline.tsx:222,235,254,302,334`
- `components/executions/ExecutionDetailDrawer.tsx:51,59,77`
- `components/catalog/WorkflowStepsRenderer.tsx:56,65`
- `pages/AuditPage.tsx:405,573`
- + autres

**Fix :** Rechercher-remplacer : `<Alert title=` → `<Alert message=`.

---

### BUG-FE-3 [MEDIUM] — `Math.random()` dans un `rowKey` React
**Fichier :** `components/catalog/ActionTable.tsx:312`
```tsx
rowKey={(record) => record.id ?? `temp-${record.name}-${Math.random()}`}
```
Provoque un remontage complet du composant à chaque render. Perte d'état, flickering.

**Fix :** Utiliser un identifiant stable : `record.id ?? \`temp-${record.name}\``.

---

### BUG-FE-4 [MEDIUM] — Boucle infinie potentielle dans `useTargetInventory`
**Fichier :** `hooks/useTargetInventory.ts:~150`

`inventoryData` dans les dépendances d'un `useEffect` qui appelle `setInventoryData`. Objet comparé par référence → re-trigger à chaque render.

---

### BUG-FE-5 [MEDIUM] — Dépendance manquante dans useEffect
**Fichier :** `hooks/useExecutionDetail.ts:96`

`loadExecutionDetail` absent du tableau de dépendances → closures stale possibles.

---

## 4. Problèmes de sécurité

### SEC-1 [HIGH] — `DEBUG` par défaut à `True`
**Fichier :** `idp_backend/settings.py:35`
```python
DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
```
Si `DEBUG` n'est pas défini en production, Django expose les stack traces, settings, et variables locales.

**Fix :** `os.getenv('DEBUG', 'False')`. Opt-in explicite.

---

### SEC-2 [HIGH] — `SECRET_KEY` fallback en dur
**Fichier :** `idp_backend/settings.py:32`
```python
SECRET_KEY = 'django-insecure-dev-fallback-will-be-validated'
```
Si `DJANGO_SECRET_KEY` n'est pas défini, Django tourne avec une clé connue.

**Fix :** `ImproperlyConfigured` au chargement des settings si env var absente.

---

### SEC-3 [HIGH] — `JWT_SECRET_KEY` par défaut à chaîne vide
**Fichier :** `idp_backend/settings.py:346`
```python
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', '')
```
Un secret JWT vide rend les tokens trivialement falsifiables.

**Fix :** Lever une erreur au chargement si vide.

---

### SEC-4 [HIGH] — ✅ RESOLVED (Story 30.5)
`fetchInventoryItems` migré vers `apiFetchRaw()` avec token JWT et correlation ID. 1 test frontend.

### SEC-5 [MEDIUM] — ✅ RESOLVED (Story 30.5)
Extension allowlist ajoutée : `.png`, `.jpg`, `.jpeg`, `.svg`, `.gif`. 11 tests.

### SEC-6 [MEDIUM] — ✅ RESOLVED (Story 30.5)
Validation magic bytes via `puremagic`. Fichiers avec contenu non-image rejetés. 5 tests.

### SEC-7 [MEDIUM] — ✅ RESOLVED (Story 30.5)
SVG sanitisé via `defusedxml` : `<script>`, event handlers, `javascript:` href supprimés. 11 tests.

### SEC-8 [MEDIUM] — ✅ RESOLVED (Story 30.5)
Guard production : log CRITICAL si `AUTH_DEV_BYPASS=True` + `DEBUG=False`. 5 tests.

### SEC-9 [MEDIUM] — ✅ RESOLVED (Story 30.5, validation)
Credentials Celery : déjà conforme. `credential_ref` (format `vault:...`) stocké, résolu via `VaultService` dans la tâche. 3 tests validation.

### SEC-10 [MEDIUM] — ✅ RESOLVED (Story 30.5)
CORS unifié sur `X-Correlation-ID` (middleware, CORS config, exception handlers). Fallback legacy `X-Idp-Request-Id` maintenu. 4 tests.

### SEC-11 [LOW] — ✅ RESOLVED (Story 30.5, documentation)
Token fragment URL documenté comme limitation connue (dev bypass only). Commentaire ajouté dans code + `docs/security-architecture.md`.

---

## 5. Incohérences API (format de réponse)

### APIFMT-1 [HIGH] — `validateIntegration` : `apiFetch` unwrap `.data` mais backend retourne objet nu
**Fichier frontend :** `integrations_service.ts:59`
**Fichier backend :** `integrations/views.py:261`

`apiFetch` extrait `body.data` → retourne `undefined` car le backend retourne l'objet directement.

**Fix :** Utiliser `apiFetchRaw` côté frontend, ou wrapper dans `{"data": ...}` côté backend.

---

### APIFMT-2 [HIGH] — `validateAllIntegrations` : même problème
**Fichier frontend :** `integrations_service.ts:64`
**Fichier backend :** `integrations/views.py:298`

---

### APIFMT-3 [MEDIUM] — Endpoints `/reference/*` retournent des arrays nus
**Fichier :** `reference/views.py:57,90,117`

Tous les endpoints reference retournent `Response(serializer.data)` (array direct) au lieu du format `{"data": [...]}` utilisé partout ailleurs. Le frontend utilise `apiFetchRaw` pour compenser — ça fonctionne mais c'est incohérent.

---

### APIFMT-4 [MEDIUM] — Catalogue list retourne `{"data": [...]}` sans info de pagination
**Fichier :** `catalog/views.py:862-876`

Les autres endpoints list retournent `{"data": [...], "pagination": {...}}`.

---

## 6. Race conditions & concurrence

### ✅ RACE-1 [HIGH] — Polling infini sans limite de retry — RESOLVED (Story 30.7)
**Fichier :** `executions/tasks.py` (5 tâches de polling)

~~Toutes les tâches de polling se re-planifient sur erreur sans compteur de retry.~~

**Résolu :** `retry_count` + `MAX_POLLING_RETRIES=20` ajoutés aux 5 tâches de polling. Après dépassement, l'exécution est marquée `FAILED` avec audit `EXECUTION_POLLING_EXHAUSTED`.

---

### ✅ RACE-2 [MEDIUM] — `update_action()` sans `select_for_update()` — RESOLVED (Story 30.7)
**Fichier :** `catalog/services.py`

~~Dans un `@transaction.atomic`, le `get()` n'acquiert pas de verrou.~~

**Résolu :** `select_for_update()` ajouté dans `update_action()`, `update_status()`, `delete_action()`, `deactivate_action()`.

---

### ✅ RACE-3 [MEDIUM] — Caches in-memory module-level non partagés entre workers — RESOLVED (Story 30.7)
**Fichiers :** `catalog/views.py` (`_catalog_cache`, `_tags_cache`), `inventory/services.py` (`_environments_cache`)

~~Données incohérentes entre requêtes routées vers différents workers.~~

**Résolu :** Comportement per-worker documenté et accepté (TTL 5min, données non-critiques). Voir `docs/architecture/caching-strategy.md`.

---

## 7. Gestion d'erreurs

### ✅ ERR-1 [HIGH] — `.catch(() => {})` avale les erreurs silencieusement — RESOLVED (Story 30.8)
**Fichier :** `frontend/src/components/execution/WorkflowExecutionGraph.tsx:146`
**Fix :** Error catch remplacé par logger.error + Alert UI avec message d'erreur. 2 tests ajoutés.

---

### ✅ ERR-2 [HIGH] — Validation croisée absente sur `IntegrationUpdateSerializer` — RESOLVED (Story 30.8)
**Fichier :** `integrations/serializers.py`
**Fix :** `IntegrationVaultValidationMixin` extrait, partagé entre Create et Update serializers. Merge instance data pour partial updates. 7 tests ajoutés.

---

### ✅ ERR-3 [MEDIUM] — `create_action()` ignore silencieusement un `integration_id` invalide — RESOLVED (Story 30.8)
**Fichier :** `catalog/services.py`
**Fix :** `pass` remplacé par `raise ValueError(...)` avec log structlog.warning dans create_action et update_action. 2 tests ajoutés.

---

### ✅ ERR-4 [MEDIUM] — Audit signals swallowed silencieusement — RESOLVED (Story 30.8)
**Fichier :** `integrations/signals.py`
**Fix :** Option A (strict SOC1) — Exception re-raised après logger.critical. Save échoue si audit échoue. 2 tests ajoutés.

---

### ✅ ERR-5 [MEDIUM] — Workflow bloqué après timeout de gate — RESOLVED (Story 30.7)
**Fichier :** `executions/tasks.py:506-522`
**Fix :** Story 30.7 (CELERY-4/5) — Après timeout: SKIPPED→next step triggered, FAILED→execution marked failed. Audit trail ajouté.

---

## 8. Performance (N+1, caches, re-renders)

### PERF-1 [MEDIUM] — ✅ RESOLVED (Story 30.9) — N+1 queries dans `_resolve_user_names`
**Fichier :** `audit/views.py:109-133`

~~Pour chaque user_id non-numérique, une requête SQL individuelle est exécutée.~~

**Fix appliqué :** Batch query avec `User.objects.filter(username__in=non_numeric_ids)` — 1 requête au lieu de N.

---

### PERF-2 [MEDIUM] — ✅ RESOLVED (Story 30.9) — Tous les workflows chargés en mémoire
**Fichier :** `catalog/services.py:559-582`

~~`_find_workflows_referencing_action()` charge TOUS les workflows actifs en mémoire puis itère en Python.~~

**Fix appliqué :** Filtre DB-side avec `execution_steps__contains` pré-filtre les candidats, validation Python pour exactitude.

---

### PERF-3 [MEDIUM] — ✅ RESOLVED (Story 30.9) — 80 RegExp créées à chaque appel de `sanitizeDescription()`
**Fichier :** `frontend/src/utils/businessLanguage.ts`

~~Regex compilées à chaque appel de la fonction.~~

**Fix appliqué :** Regex pré-compilées au niveau module (`SANITIZE_PATTERNS` et `DETECT_PATTERNS`).

---

### PERF-4 [LOW] — BACKLOG (Story 30.9) — `<style>` inline dans les fonctions render
**Fichiers :** `components/catalog/ActionTable.tsx:295-307`, `components/execution/ExecutionTimeline.tsx:670-675`

Tags `<style>` injectés dans le DOM à chaque render. Impact négligeable (pseudo-classes, media queries, keyframes). Reporté à Story 30.11 (A11Y).

---

## 9. Code mort

### Backend

| # | Fichier | Description |
|---|---------|-------------|
| DEAD-BE-1 | `catalog/models.py:51-55` | ✅ RESOLVED (Story 30.10) — `normalize_tag_name()` alignée sur normalisation services.py (espaces → `_`) |
| DEAD-BE-2 | `idp_auth/services.py:134-136` | ✅ RESOLVED (Story 30.3) — code mort déjà supprimé |
| DEAD-BE-3 | `executions/tasks.py:278` | ✅ RESOLVED (Story 30.10) — appel inutile `gate_status.get('action', 'FAILED')` supprimé |
| DEAD-BE-4 | `core/models.py:155` | ✅ RESOLVED (Story 30.10) — import json doublon supprimé |
| DEAD-BE-5 | `inventory/services.py:16,21,33` | ✅ RESOLVED (Story 30.10) — imports documentés comme backward compat (90+ tests patch via inventory.services), `re` inutilisé supprimé |

### Frontend

| # | Fichier | Description |
|---|---------|-------------|
| DEAD-FE-1 | `services/catalog_service.ts:141` | ✅ RESOLVED (Story 30.10) — `fetchRecentActions` et `RecentAction` supprimés |
| DEAD-FE-2 | `services/admin_service.ts` | ✅ RESOLVED (Story 30.10) — `listActions` supprimée, appelants migrés vers `getAdminActions()` |
| DEAD-FE-3 | `types/api.ts` | ✅ RESOLVED (Story 30.10) — barrel re-export intentionnel (213 imports), deprecation retirée, documentation clarifiée |
| DEAD-FE-4 | `utils/profileOptions.ts` | ✅ RESOLVED (Story 30.10) — `ENVIRONMENT_OPTIONS` deprecated supprimé, `MOCK_TARGET_OPTIONS` conservé (utilisé) |
| DEAD-FE-5 | `utils/impactRulesSchema.ts:87` | ✅ RESOLVED (Story 30.10) — `IMPACT_ENVIRONMENTS` supprimé, tests mis à jour |
| DEAD-FE-6 | 3 fichiers | ✅ RESOLVED (Story 30.10) — factorisé dans `utils/stepDescriptions.ts`, 3 composants migrés |

---

## 10. Accessibilité & thème

### A11Y-1 [HIGH] — ✅ RESOLVED (Story 30.11) — Couleurs dark-theme hardcodées dans `StepDetailDrawer`
**Fichier :** `components/execution/StepDetailDrawer.tsx`

~~`background: '#1f1f1f'`, `color: '#e8e8e8'` → illisible en thème clair.~~

**Fix appliqué :** `token.colorBgContainer`, `token.colorText`, `token.colorTextSecondary`, `token.colorBgElevated` via `theme.useToken()`.

---

### A11Y-2 [HIGH] — ✅ RESOLVED (Story 30.11) — Status badges avec background dark hardcodé
**Fichier :** `utils/executionRenderers.tsx`

~~`rgba(26, 26, 36, 0.8)` → invisible en thème clair.~~

**Fix appliqué :** `token.colorBgElevated` via composant `StatusIndicator` utilisant `theme.useToken()`.

---

### A11Y-3 [MEDIUM] — ✅ RESOLVED (Story 30.11) — `StructuredErrorCard` avec couleurs texte hardcodées
**Fichier :** `components/execution/StructuredErrorCard.tsx`

~~`#374151`, `#1f2937` → mauvais contraste en dark mode.~~

**Fix appliqué :** `token.colorTextSecondary`, `token.colorText` via `theme.useToken()`.

---

**Point positif :** Bonne utilisation globale de `role`, `aria-label`, `aria-live`, `aria-expanded`, et gestion clavier (Enter/Space) sur les éléments interactifs.

---

## 11. Problèmes Celery / tâches async

### CELERY-1 [HIGH] — Polling infini sans retry limit
Voir [RACE-1](#race-1-high--polling-infini-sans-limite-de-retry).

---

### CELERY-2 [MEDIUM] — Credentials en clair dans les arguments
Voir [SEC-9](#sec-9-medium--credentials-en-clair-dans-les-arguments-celery).

---

### ✅ CELERY-3 [MEDIUM] — Nouveau event loop asyncio créé à chaque cycle de polling — RESOLVED (Story 30.7)
**Fichier :** `executions/tasks.py`

~~`asyncio.new_event_loop()` + `set_event_loop()` à chaque poll.~~

**Résolu :** Remplacé par `asyncio.run()` dans les 5 tâches de polling.

---

### ✅ CELERY-4 [MEDIUM] — Gate timeout ne continue pas le workflow — RESOLVED (Story 30.7)

~~Après un timeout de gate, le workflow reste bloqué.~~

**Résolu :** SKIPPED → déclenche le step suivant via `retry_workflow_step`. FAILED → marque l'exécution en FAILED.

---

### ✅ CELERY-5 [LOW] — Gate timeout SKIPPED sans message d'erreur — RESOLVED (Story 30.7)
**Fichier :** `executions/tasks.py`

~~Step mise en `SKIPPED` sans `error_message`.~~

**Résolu :** `error_message = "Gate timeout exceeded after {hours}h"` ajouté pour tous les cas (SKIPPED et FAILED).

---

## 12. Incohérences modèles & serializers

### INCON-1 [MEDIUM] — Normalisation de tags incohérente
- `catalog/models.py:55` : remplace espaces par `""` (rien)
- `catalog/services.py:180` : remplace espaces par `"_"` (underscore)

Tags créés différemment selon le chemin d'exécution.

---

### INCON-2 [MEDIUM] — Audit : hash MD5 collisions pour les PK string
**Fichier :** `integrations/signals.py:40`
```python
entity_id = int(hashlib.md5(instance.code.encode()).hexdigest()[:8], 16) % (10**9)
```
Collisions possibles entre différents codes → requêtes d'audit peu fiables.

---

### INCON-3 [MEDIUM] — Audit signals retournent toujours `user_id='system'`
**Fichier :** `integrations/signals.py:19-27`

TODO non implémenté. Impossible de tracer quel utilisateur a modifié les catalogues d'intégration.

---

### INCON-4 [LOW] — `IntegerField` pour les booléens (compatibilité Oracle)
**Fichiers :** `profiles/models.py` (`is_admin`, `is_auditor`), `executions/models.py` (`RecurringPattern.is_active`)

Intentionnel pour Oracle `NUMBER(1)`, mais fragile : tout le code doit comparer `== 1` au lieu de truthiness.

---

### INCON-5 [LOW] — `User.is_authenticated = True` en attribut de classe
**Fichier :** `idp_auth/models.py:67`

`True` pour toutes les instances, y compris les users soft-deleted. Contrairement au User Django natif qui utilise une méthode.

---

## 13. Récapitulatif par priorité

### CRITICAL (à traiter immédiatement)

| # | Issue | Type | Effort |
|---|-------|------|--------|
| API-MISS-1/2 | Endpoints approve/reject manquants | Backend | Moyen |
| BUG-BE-1 | Filtres écrasés dans `CatalogService.list_all()` | Backend | Faible |
| SEC-1 | `DEBUG` par défaut à `True` | Config | Trivial |
| SEC-2 | `SECRET_KEY` fallback hardcodé | Config | Trivial |
| SEC-3 | `JWT_SECRET_KEY` vide par défaut | Config | Trivial |

### HIGH (à traiter cette semaine)

| # | Issue | Type | Effort |
|---|-------|------|--------|
| BUG-FE-1 | `notification({ title })` → `message` (42+ lieux) | Frontend | Faible (search-replace) |
| BUG-FE-2 | `<Alert title=...>` → `message=` (14+ lieux) | Frontend | Faible (search-replace) |
| SEC-4 | `fetchInventoryItems` sans auth token | Frontend | Faible |
| APIFMT-1/2 | `validateIntegration` retourne `undefined` | Frontend/Backend | Faible |
| RACE-1 | Polling Celery infini sans retry limit | Backend | Moyen |
| ERR-2 | Validation croisée manquante update integration | Backend | Faible |
| BUG-BE-2 | `secret_service_id` ignoré à la création | Backend | Trivial |
| BUG-BE-3 | user_id structlog bindé après la réponse | Backend | Faible |
| BUG-BE-4 | Récurrence placeholder `+1 jour` | Backend | Moyen |
| ~~A11Y-1/2~~ | ~~Couleurs hardcodées dark theme~~ ✅ Story 30.11 | Frontend | — |
| API-MISS-3/4 | Endpoints remediation manquants | Backend | Moyen |
| API-MISS-5/6 | Endpoints export dashboard manquants | Backend | Moyen |
| SEC-10 | CORS header `X-Correlation-ID` non autorisé | Config | Trivial |
| ERR-1 | `.catch(() => {})` avale les erreurs | Frontend | Trivial |

### MEDIUM (à planifier dans le sprint suivant)

| # | Issue | Type | Effort |
|---|-------|------|--------|
| SEC-5/6/7 | Upload fichiers : extension, MIME, SVG XSS | Backend | Moyen |
| SEC-8 | Dev bypass sans guard production | Backend | Faible |
| SEC-9 | Credentials Celery en clair | Backend | Moyen |
| RACE-2 | `select_for_update()` manquant | Backend | Faible |
| RACE-3 | Caches in-memory non partagés | Backend | Moyen |
| ERR-3/4/5 | Gestion d'erreurs silencieuse | Backend | Moyen |
| PERF-1/2 | N+1 queries audit/workflows | Backend | Moyen |
| PERF-3 | Regex recompilées à chaque appel | Frontend | Trivial |
| BUG-FE-3/4/5 | Math.random key, infinite loop, deps manquantes | Frontend | Faible |
| INCON-1/2/3 | Tags, audit hash, audit user | Backend | Moyen |
| APIFMT-3/4 | Format réponse incohérent | Backend | Moyen |
| ~~A11Y-3~~ | ~~Couleurs texte hardcodées~~ ✅ Story 30.11 | Frontend | — |

### LOW (backlog)

| # | Issue | Type |
|---|-------|------|
| BUG-BE-6/7 | Code mort, ligne dupliquée | Backend |
| DEAD-* | Code deprecated à nettoyer | Les deux |
| INCON-4/5 | IntegerField booleans, is_authenticated | Backend |
| CELERY-3/5 | Event loop, gate skip message | Backend |
| SEC-11 | Token dans fragment URL | Backend |
| PERF-4 | Style tags inline | Frontend |

---

**Total : 65 findings**
- Critical : 5
- High : 16
- Medium : 23
- Low : 21
