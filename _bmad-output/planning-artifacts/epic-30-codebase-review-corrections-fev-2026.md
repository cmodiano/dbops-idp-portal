# Epic 30 : Corrections exhaustives — Codebase Review IDP Portal (16 février 2026)

**En tant que** équipe de développement,  
**je veux** corriger l'intégralité des 65 findings identifiés dans la revue exhaustive du codebase IDP Portal (CODEBASE-REVIEW.md),  
**afin de** supprimer les bugs, renforcer la sécurité, homogénéiser les API, améliorer la robustesse et l'accessibilité.

---

## Contexte

**Source :** `idp-portal/CODEBASE-REVIEW.md` (16 février 2026)

**Périmètre :** Backend Django + Frontend React (IDP Portal)

**Répartition des findings :**
- Critical : 5
- High : 16
- Medium : 23
- Low : 21  
**Total : 65 findings**

---

## Stories

### Story 30.1 — CRITICAL : Endpoints manquants (approve/reject) + Bug filtres catalogue + Config sécurité par défaut

**En tant que** utilisateur et opérateur,  
**je veux** que les workflows d'approbation/rejet fonctionnent, que les filtres catalogue ne soient pas écrasés, et que la config par défaut ne soit jamais dangereuse en production,  
**afin de** éviter des 404 systématique, des résultats catalogue incorrects et des fuites de données.

**Issues :** API-MISS-1, API-MISS-2, BUG-BE-1, SEC-1, SEC-2, SEC-3

**Acceptance Criteria:**
- **Given** le frontend appelle `POST /executions/{id}/approve` et `POST /executions/{id}/reject`
- **When** le backend est déployé
- **Then** ces endpoints existent et mettent à jour le statut d'approbation de l'exécution
- **And** dans `catalog/services.py`, quand `tags_filter` est fourni, le queryset est chaîné : `queryset = queryset.search_by_tags(tags_filter)` (pas de remplacement)
- **And** `DEBUG` default = `False` dans `idp_backend/settings.py` (opt-in explicite)
- **And** absence de `DJANGO_SECRET_KEY` ou `JWT_SECRET_KEY` lève `ImproperlyConfigured` au chargement
- **And** aucun fallback hardcodé pour `SECRET_KEY` ou `JWT_SECRET_KEY`

**Fichiers :** `executions/views` (nouveaux endpoints ou extension), `catalog/services.py`, `idp_backend/settings.py`

---

### Story 30.2 — Endpoints manquants : remediation, export dashboard

**En tant que** utilisateur,  
**je veux** accéder aux suggestions de remédiation et aux exports CSV/PDF du dashboard,  
**afin de** exploiter les données d'exécution et le reporting.

**Issues :** API-MISS-3, API-MISS-4, API-MISS-5, API-MISS-6

**Acceptance Criteria:**
- **Given** le frontend appelle les endpoints listés
- **When** le backend est déployé
- **Then** les endpoints suivants existent et répondent de façon cohérente avec le reste de l'API :
  - `GET /executions/{id}/remediation`
  - `GET /executions/{id}/remediation-context`
  - `GET /dashboard/export/csv`
  - `GET /dashboard/export/pdf`
- **And** les réponses respectent le format standard (ex. `{"data": ...}` si applicable)

**Fichiers :** `executions/views`, `dashboard` (ou module équivalent), `*_service.ts` (alignement frontend si besoin)

---

### Story 30.3 — Bugs logiques Backend

**En tant que** développeur et utilisateur,  
**je veux** que les bugs backend identifiés soient corrigés (secret_service_id, structlog, récurrence, cache/pagination, code mort, doublon),  
**afin de** avoir un comportement prévisible et des logs exploitables.

**Issues :** BUG-BE-2, BUG-BE-3, BUG-BE-4, BUG-BE-5, BUG-BE-6, BUG-BE-7

**Acceptance Criteria:**
- **Given** une création d'intégration avec `secret_service_id`
- **When** l'intégration est créée
- **Then** `secret_service_id` est passé à `Integration.objects.create()`
- **And** le middleware structlog bind `user_id` **avant** `get_response(request)` (ordre ou middleware dédié)
- **And** le calcul de `next_execution_date` pour les patterns récurrents utilise `pattern_type` et `cron_expression` (plus de placeholder +1 jour)
- **And** le cache catalogue applique la pagination systématiquement (avant ou après cache)
- **And** le code mort `if not action` après `Action.objects.get()` est supprimé (`idp_auth/services.py`)
- **And** la ligne dupliquée `se.environment = ...` est supprimée (`executions/views/scheduled_views.py`)

**Fichiers :** `integrations/services.py`, `core/middleware.py`, `executions/services.py`, `catalog/views.py`, `idp_auth/services.py`, `executions/views/scheduled_views.py`

---

### Story 30.4 — Bugs logiques Frontend (notifications, Alert, rowKey, hooks)

**En tant que** utilisateur,  
**je veux** voir les titres des notifications et des Alertes, et ne pas subir de remontages/flickering ou de boucles infinies,  
**afin de** avoir une UX cohérente et stable.

**Issues :** BUG-FE-1, BUG-FE-2, BUG-FE-3, BUG-FE-4, BUG-FE-5

**Acceptance Criteria:**
- **Given** tout appel à `notification.success/error/warning`
- **When** la prop utilisée pour le titre est `title`
- **Then** elle est remplacée par `message` (Ant Design) — 42+ occurrences
- **And** tout `<Alert title=` est remplacé par `<Alert message=` — 14+ occurrences
- **And** dans `ActionTable.tsx`, `rowKey` utilise un identifiant stable (ex. `record.id ?? \`temp-${record.name}\``), pas `Math.random()`
- **And** dans `useTargetInventory`, les dépendances du `useEffect` ne provoquent plus de boucle infinie (éviter objet en ref dans deps ou stabiliser la ref)
- **And** dans `useExecutionDetail`, `loadExecutionDetail` est ajouté au tableau de dépendances du `useEffect` ou la closure est sécurisée

**Fichiers :** multiples (hooks, pages admin, ExecutionWizard, ExecutionTimeline, ExecutionDetailDrawer, WorkflowStepsRenderer, AuditPage, etc.)

---

### Story 30.5 — Sécurité : auth frontend, uploads, dev bypass, CORS, credentials Celery, token fragment

**En tant que** opérateur sécurité,  
**je veux** que les appels sensibles passent par le client authentifié, que les uploads soient validés et sanitisés, que le bypass dev soit protégé en prod, et que les secrets ne circulent pas en clair dans le broker,  
**afin de** réduire les risques XSS, injection et exposition de secrets.

**Issues :** SEC-4, SEC-5, SEC-6, SEC-7, SEC-8, SEC-9, SEC-10, SEC-11

**Acceptance Criteria:**
- **Given** `fetchInventoryItems` dans `execution_service.ts`
- **When** l'appel est effectué
- **Then** il utilise `apiFetchRaw()` (ou équivalent avec token et correlation ID), pas `fetch()` nu
- **And** upload icons : allowlist d'extensions (ex. `.png`, `.jpg`, `.jpeg`, `.svg`, `.gif`) ; validation du contenu (ex. magic bytes) ; SVG sanitisés (strip `<script>`, event handlers) ou servis en `Content-Disposition: attachment`
- **And** si `APP_ENV=production`, le bypass `AUTH_DEV_BYPASS` ne crée pas d'user full-privilege (guard explicite)
- **And** les tâches Celery ne reçoivent pas les credentials en clair en paramètre ; résolution des secrets dans la tâche (ex. via Vault)
- **And** `X-Correlation-ID` (ou le nom utilisé côté frontend) est autorisé dans `CORS_ALLOW_HEADERS`
- **And** (backlog) documenter ou planifier le passage du token d'accès du fragment URL vers un flow code d'autorisation si applicable

**Fichiers :** `frontend/src/services/execution_service.ts`, `integrations/upload_views.py`, `idp_auth/views.py`, `executions/tasks.py`, `idp_backend/settings.py`

---

### Story 30.6 — Incohérences API (format de réponse)

**En tant que** développeur frontend,  
**je veux** un format de réponse API cohérent (ex. `{"data": ...}`, pagination quand attendue),  
**afin de** éviter les `undefined` et les branches de code compensatoires.

**Issues :** APIFMT-1, APIFMT-2, APIFMT-3, APIFMT-4

**Acceptance Criteria:**
- **Given** les endpoints `validateIntegration` et `validateAllIntegrations`
- **When** le backend répond
- **Then** le frontend reçoit l'objet attendu (soit backend wrap dans `{"data": ...}`, soit frontend utilise `apiFetchRaw` et les deux sont alignés)
- **And** les endpoints `/reference/*` retournent un format aligné avec le reste (ex. `{"data": [...]}`)
- **And** la liste catalogue retourne `pagination` lorsque applicable (aligné avec les autres listes)

**Fichiers :** `integrations/views.py`, `integrations_service.ts`, `reference/views.py`, `catalog/views.py`

---

### Story 30.7 — Race conditions, Celery polling, caches partagés

**En tant que** opérateur,  
**je veux** que le polling Celery ait une limite de retry, que les mises à jour concurrentes du catalogue soient sérialisées, et que les caches soient cohérents entre workers (ou le comportement documenté),  
**afin de** éviter les boucles infinies et les corruptions silencieuses.

**Issues :** RACE-1, RACE-2, RACE-3, CELERY-3, CELERY-4, CELERY-5

**Acceptance Criteria:**
- **Given** les tâches de polling (AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud)
- **When** une erreur ou un timeout distant survient
- **Then** un `max_retries` est appliqué ; après dépassement, l'exécution passe en `FAILED` (pas de re-schedule infini)
- **And** dans `catalog/services.py`, les opérations `update_action`, `update_status`, `delete_action`, `deactivate_action` utilisent `select_for_update()` dans le bloc transactionnel où c'est pertinent
- **And** les caches module-level (`_catalog_cache`, `_tags_cache`, `_environments_cache`) sont soit migrés vers un cache partagé (ex. Redis), soit le comportement (par-worker) est documenté et TTL court accepté
- **And** (optionnel) utilisation de `asyncio.run()` au lieu de créer un nouvel event loop à chaque cycle de polling
- **And** après un gate timeout, le workflow continue ou est marqué explicitement en échec ; les steps en SKIPPED pour timeout ont un `error_message` explicite

**Fichiers :** `executions/tasks.py`, `catalog/services.py`, `catalog/views.py`, `inventory/services.py`

---

### Story 30.8 — Gestion d'erreurs (frontend et backend)

**En tant que** utilisateur et support,  
**je veux** que les erreurs ne soient pas avalées silencieusement et que les validations/signals d'audit soient cohérents,  
**afin de** pouvoir diagnostiquer et garantir l'audit.

**Issues :** ERR-1, ERR-2, ERR-3, ERR-4, ERR-5

**Acceptance Criteria:**
- **Given** `getExecutionSteps(executionId).then(...).catch(() => {})`
- **When** une erreur réseau ou API survient
- **Then** le catch log l'erreur et/ou affiche un feedback utilisateur (notification, état d'erreur), pas de swallow silencieux
- **And** `IntegrationUpdateSerializer` applique la même validation croisée que le serializer de création (vault, credential_ref, secret_service_id)
- **And** `create_action()` ne crée pas une action avec `integration=None` si `integration_id` est invalide (lever ou propager au lieu de `pass`)
- **And** les signals d'audit ne swallow pas les exceptions : en cas d'échec de création d'audit, soit le save du modèle échoue, soit la stratégie est documentée
- **And** après un gate timeout, le workflow n'est plus bloqué indéfiniment (voir 30.7)

**Fichiers :** `WorkflowExecutionGraph.tsx`, `integrations/serializers.py`, `catalog/services.py`, `integrations/signals.py`, `executions/tasks.py`

---

### Story 30.9 — Performance (N+1, regex, styles inline)

**En tant que** utilisateur et opérateur,  
**je veux** réduire les N+1, éviter de charger tous les workflows en mémoire pour une recherche, et limiter les allocations inutiles (regex, styles),  
**afin de** améliorer les temps de réponse et la stabilité.

**Issues :** PERF-1, PERF-2, PERF-3, PERF-4

**Acceptance Criteria:**
- **Given** `_resolve_user_names` dans `audit/views.py`
- **When** plusieurs user_id non-numériques sont traités
- **Then** les résolutions sont faites par batch ou requête optimisée (pas une requête par user)
- **And** `_find_workflows_referencing_action()` utilise un filtre côté DB (JSONField lookup ou requête raw) au lieu de charger tous les workflows en mémoire
- **And** les regex dans `sanitizeDescription()` (businessLanguage.ts) sont pré-compilées au niveau module
- **And** (backlog/low) les `<style>` inline dans les composants render sont déplacés vers CSS modules ou thème si possible

**Fichiers :** `audit/views.py`, `catalog/services.py`, `frontend/src/utils/businessLanguage.ts`, `ActionTable.tsx`, `ExecutionTimeline.tsx`

---

### Story 30.10 — Code mort et dépréciations

**En tant que** développeur,  
**je veux** supprimer le code mort et clarifier les dépréciations (backend et frontend),  
**afin de** réduire la dette et la confusion.

**Issues :** DEAD-BE-1 à DEAD-BE-5, DEAD-FE-1 à DEAD-FE-6, BUG-BE-6 (déjà couvert en 30.3)

**Acceptance Criteria:**
- **Given** les fonctions/fichiers listés dans la section 9 du CODEBASE-REVIEW
- **When** le nettoyage est effectué
- **Then** `normalize_tag_name()` inutilisée est supprimée ou utilisée de façon cohérente ; code mort après `get()` supprimé ; variable non assignée corrigée ; imports redondants supprimés
- **And** les symboles `@deprecated` frontend sont soit retirés et les appels migrés, soit documentés avec date de suppression prévue
- **And** les duplications `STEP_DESCRIPTIONS_SIMPLIFIED` sont factorisées dans un seul module

**Fichiers :** `catalog/models.py`, `idp_auth/services.py`, `executions/tasks.py`, `core/models.py`, `inventory/services.py` ; frontend : `catalog_service.ts`, `admin_service.ts`, `types/api.ts`, `utils/profileOptions.ts`, `impactRulesSchema.ts`, composants avec STEP_DESCRIPTIONS_SIMPLIFIED

---

### Story 30.11 — Accessibilité et thème (couleurs hardcodées)

**En tant que** utilisateur (thème clair/sombre) et utilisateur avec handicaps,  
**je veux** que les couleurs respectent le thème et le contraste,  
**afin de** ne pas avoir de zones illisibles selon le thème.

**Issues :** A11Y-1, A11Y-2, A11Y-3

**Acceptance Criteria:**
- **Given** `StepDetailDrawer`, badges de statut, `StructuredErrorCard`
- **When** le thème (clair/sombre) change
- **Then** les backgrounds et couleurs de texte utilisent les tokens du thème Ant Design (plus de `#1f1f1f`, `#e8e8e8`, `rgba(26,26,36,0.8)`, `#374151`, `#1f2937` en dur)
- **And** le contraste reste suffisant pour l'accessibilité

**Fichiers :** `StepDetailDrawer.tsx`, `utils/executionRenderers.tsx`, `StructuredErrorCard.tsx`

---

### Story 30.12 — Incohérences modèles et serializers (tags, audit, champs)

**En tant que** développeur,  
**je veux** une normalisation des tags unique, un audit fiable (hash, user_id), et des conventions de champs claires,  
**afin de** éviter les bugs subtils et les collisions d'audit.

**Issues :** INCON-1, INCON-2, INCON-3, INCON-4, INCON-5

**Acceptance Criteria:**
- **Given** la création/mise à jour de tags
- **When** le chemin d'exécution varie (modèle vs services)
- **Then** la même règle de normalisation s'applique (ex. espaces → underscore partout, ou documenter la différence)
- **And** l'audit des intégrations n'utilise pas un hash MD5 tronqué comme PK unique si les collisions sont possibles ; soit clé plus robuste, soit stratégie documentée
- **And** les signals d'audit renseignent le `user_id` réel quand disponible (plus de TODO "system" uniquement)
- **And** (documentation) les champs IntegerField pour booléens (Oracle) et `User.is_authenticated = True` sont documentés comme choix intentionnels ou corrigés si inadaptés

**Fichiers :** `catalog/models.py`, `catalog/services.py`, `integrations/signals.py`, `profiles/models.py`, `executions/models.py`, `idp_auth/models.py`

---

## Récapitulatif des stories

| Story   | Priorité principale | Issues couvertes |
|--------|----------------------|------------------|
| 30.1   | CRITICAL             | API-MISS-1/2, BUG-BE-1, SEC-1/2/3 |
| 30.2   | HIGH                 | API-MISS-3 à 6 |
| 30.3   | HIGH                 | BUG-BE-2 à BUG-BE-7 |
| 30.4   | HIGH                 | BUG-FE-1 à BUG-FE-5 |
| 30.5   | HIGH / MEDIUM        | SEC-4 à SEC-11 |
| 30.6   | HIGH                 | APIFMT-1 à 4 |
| 30.7   | HIGH / MEDIUM        | RACE-1/2/3, CELERY-3/4/5 |
| 30.8   | HIGH / MEDIUM        | ERR-1 à ERR-5 |
| 30.9   | MEDIUM / LOW         | PERF-1 à PERF-4 |
| 30.10  | LOW                  | DEAD-* (backend + frontend) |
| 30.11  | HIGH                 | A11Y-1 à A11Y-3 |
| 30.12  | MEDIUM / LOW         | INCON-1 à INCON-5 |

**Ordre recommandé :** 30.1 (critique + config) → 30.3, 30.4, 30.6, 30.8 (bugs et cohérence) → 30.2, 30.5, 30.7 (endpoints, sécurité, Celery) → 30.11 (A11Y) → 30.9, 30.10, 30.12 (perf, nettoyage, incohérences).

---

*Epic créée à partir de idp-portal/CODEBASE-REVIEW.md — 65 findings — 16 février 2026.*
