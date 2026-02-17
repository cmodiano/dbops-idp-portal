# Story 30.1: CRITICAL — Endpoints manquants (approve/reject) + Bug filtres catalogue + Config sécurité par défaut

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

**En tant que** utilisateur et opérateur,
**je veux** que les workflows d'approbation/rejet fonctionnent, que les filtres catalogue ne soient pas écrasés, et que la config par défaut ne soit jamais dangereuse en production,
**afin de** éviter des 404 systématiques, des résultats catalogue incorrects et des fuites de données.

## Acceptance Criteria

### AC1 — Endpoint `POST /executions/{id}/approve` existe et fonctionne
- **Given** le frontend appelle `POST /api/v1/executions/{id}/approve`
- **When** le backend est déployé
- **Then** l'endpoint existe et retourne HTTP 200
- **And** le statut de l'exécution passe de `PENDING_APPROVAL` → `SUBMITTED`
- **And** l'audit log enregistre l'action `EXECUTION_APPROVED` avec `user_id` et `correlation_id`
- **And** le format de réponse est cohérent : `{"data": ExecutionSerializer}`

### AC2 — Endpoint `POST /executions/{id}/reject` existe et fonctionne
- **Given** le frontend appelle `POST /api/v1/executions/{id}/reject`
- **When** le backend est déployé
- **Then** l'endpoint existe et retourne HTTP 200
- **And** le statut de l'exécution passe de `PENDING_APPROVAL` → `FAILED`
- **And** l'audit log enregistre l'action `EXECUTION_REJECTED` avec `user_id`, `correlation_id`, et raison du rejet (optionnelle)
- **And** le format de réponse est cohérent : `{"data": ExecutionSerializer}`
- **And** un champ optionnel `rejection_reason` peut être fourni dans le body de la requête

### AC3 — Bug filtres catalogue corrigé (tags_filter écrase queryset)
- **Given** `catalog/services.py:208-215` actuellement écrase le queryset quand `tags_filter` est fourni
- **When** `CatalogService.list_all()` est appelé avec `status`, `item_type` ET `tags_filter`
- **Then** la ligne 215 devient : `queryset = queryset.search_by_tags(tags_filter)` (chaîner au lieu de remplacer)
- **And** les filtres `status` et `item_type` sont préservés
- **And** les tests existants passent (aucune régression)
- **And** un test d'intégration valide la combinaison des 3 filtres simultanément

### AC4 — `DEBUG` par défaut à `False` (opt-in explicite)
- **Given** `idp_backend/settings.py:35` actuellement : `DEBUG = os.getenv('DEBUG', 'True')`
- **When** la variable d'environnement `DEBUG` n'est pas définie
- **Then** `DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'`
- **And** le mode DEBUG est désactivé par défaut (opt-in explicite requis)
- **And** la documentation `.env.production.template` précise clairement : `DEBUG=False` en production

### AC5 — `SECRET_KEY` : ImproperlyConfigured si absente
- **Given** `idp_backend/settings.py:30-32` actuellement a un fallback hardcodé
- **When** la variable d'environnement `SECRET_KEY` ou `DJANGO_SECRET_KEY` est absente ou vide
- **Then** Django lève `ImproperlyConfigured` au chargement des settings (fail-fast)
- **And** le message d'erreur indique explicitement : "SECRET_KEY or DJANGO_SECRET_KEY must be set in production"
- **And** le fallback dev est supprimé (pas de `'django-insecure-dev-fallback-will-be-validated'`)
- **And** la validation dans `startup_checks.py` (Story 17.5) est conservée comme garde-fou supplémentaire

### AC6 — `JWT_SECRET_KEY` : ImproperlyConfigured si absente
- **Given** `idp_backend/settings.py:346` actuellement : `JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', '')`
- **When** la variable d'environnement `JWT_SECRET_KEY` est absente ou vide
- **Then** Django lève `ImproperlyConfigured` au chargement des settings (fail-fast)
- **And** le message d'erreur indique explicitement : "JWT_SECRET_KEY must be set and non-empty"
- **And** aucun fallback hardcodé n'existe (pas de chaîne vide par défaut)

### AC7 — Tests de sécurité validant le fail-fast
- **Given** les nouvelles validations AC5 et AC6
- **When** les tests de sécurité sont exécutés
- **Then** un test unitaire valide que l'import de `settings.py` échoue si `SECRET_KEY` est absente
- **And** un test unitaire valide que l'import de `settings.py` échoue si `JWT_SECRET_KEY` est absente
- **And** un test d'intégration valide que le serveur Django refuse de démarrer sans ces secrets
- **And** les tests documentent comment mocker les env vars pour éviter les échecs en CI

## Tasks / Subtasks

- [x] **Task 1** — Implémenter endpoint `POST /executions/{id}/approve` (AC1)
  - [x] Créer la vue `ApproveExecutionView` dans `executions/views/approval_views.py`
  - [x] Ajouter la méthode `post()` avec validation du statut `PENDING_APPROVAL`
  - [x] Transition de statut : `PENDING_APPROVAL` → `SUBMITTED`
  - [x] Enregistrer l'audit log `EXECUTION_APPROVED` avec `user_id` et `correlation_id`
  - [x] Retourner `{"data": ExecutionSerializer(execution).data}`
  - [x] Ajouter la route dans `executions/urls.py` : `path('<int:id>/approve', ApproveExecutionView.as_view())`
  - [x] Ajouter `@extend_schema` pour la documentation OpenAPI (tag `executions`)
  - [x] Permissions : `IsAuthenticated` + `IsDBAOrDBOPS` (cohérent avec `PendingApprovalsView`)

- [x] **Task 2** — Implémenter endpoint `POST /executions/{id}/reject` (AC2)
  - [x] Créer la vue `RejectExecutionView` dans `executions/views/approval_views.py`
  - [x] Ajouter la méthode `post()` avec validation du statut `PENDING_APPROVAL`
  - [x] Accepter un body optionnel : `{"rejection_reason": "string"}`
  - [x] Transition de statut : `PENDING_APPROVAL` → `FAILED`
  - [x] Si `rejection_reason` fournie, la stocker dans `Execution.error_message`
  - [x] Enregistrer l'audit log `EXECUTION_REJECTED` avec `user_id`, `correlation_id`, et raison
  - [x] Retourner `{"data": ExecutionSerializer(execution).data}`
  - [x] Ajouter la route dans `executions/urls.py` : `path('<int:id>/reject', RejectExecutionView.as_view())`
  - [x] Ajouter `@extend_schema` pour la documentation OpenAPI (tag `executions`)
  - [x] Permissions : `IsAuthenticated` + `IsDBAOrDBOPS`

- [x] **Task 3** — Corriger bug filtres catalogue `tags_filter` (AC3)
  - [x] Ouvrir `catalog/services.py:208-215`
  - [x] Remplacer ligne 215 : `queryset = Action.objects.search_by_tags(tags_filter)` → `queryset = queryset.search_by_tags(tags_filter)`
  - [x] Vérifier que `Action.objects` est un custom manager avec la méthode `search_by_tags()` qui retourne un queryset chainable
  - [x] Si la méthode n'existe pas en tant que méthode de queryset, créer un custom queryset avec la méthode chainable
  - [x] Ajouter un test d'intégration validant : `status=ACTIVE` + `item_type=action` + `tags_filter=['database', 'oracle']` retourne les bons résultats
  - [x] Exécuter les tests existants du catalogue pour vérifier l'absence de régression

- [x] **Task 4** — Corriger `DEBUG` par défaut à `False` (AC4)
  - [x] Ouvrir `idp_backend/settings.py:35`
  - [x] Remplacer : `DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'` → `DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'`
  - [x] Vérifier `.env.production.template` contient : `DEBUG=False` avec commentaire explicite
  - [x] Vérifier `.env.example` contient : `DEBUG=True` avec commentaire "Dev only"
  - [x] Documenter dans `docs/security/secrets-configuration.md` : "DEBUG est False par défaut (fail-secure)"

- [x] **Task 5** — Corriger `SECRET_KEY` : fail-fast si absente (AC5)
  - [x] Ouvrir `idp_backend/settings.py:30-32`
  - [x] Supprimer les lignes 30-32 (fallback hardcodé)
  - [x] Ajouter `ImproperlyConfigured` import et validation fail-fast
  - [x] Vérifier que `startup_checks.py` (Story 17.5) conserve sa validation comme garde-fou
  - [x] Mettre à jour `.env.example` avec un exemple de `SECRET_KEY` généré aléatoirement
  - [x] Mettre à jour `.env.production.template` avec un commentaire de génération

- [x] **Task 6** — Corriger `JWT_SECRET_KEY` : fail-fast si absente (AC6)
  - [x] Ouvrir `idp_backend/settings.py:346`
  - [x] Remplacer par validation fail-fast `ImproperlyConfigured`
  - [x] Mettre à jour `.env.example` avec un exemple de `JWT_SECRET_KEY` différent de `SECRET_KEY`
  - [x] Mettre à jour `.env.production.template` avec commentaire de génération
  - [x] Documenter dans `docs/security/secrets-configuration.md` : "JWT_SECRET_KEY doit être différente de SECRET_KEY"

- [x] **Task 7** — Tests unitaires endpoints approve/reject (AC1, AC2)
  - [x] Créer `executions/tests/test_approval_endpoints.py`
  - [x] Test approve : statut valide `PENDING_APPROVAL` → `SUBMITTED`, audit log créé, retour HTTP 200
  - [x] Test approve : statut invalide (ex. `RUNNING`) → HTTP 400 avec message d'erreur
  - [x] Test approve : exécution inexistante → HTTP 404
  - [x] Test approve : utilisateur non autorisé (ni DBA ni DBOPS) → HTTP 403
  - [x] Test reject : statut valide + `rejection_reason` → `FAILED`, raison stockée dans `error_message`, audit log
  - [x] Test reject : statut valide sans `rejection_reason` → `FAILED`, `error_message` vide ou message par défaut
  - [x] Test reject : statut invalide → HTTP 400
  - [x] Test reject : exécution inexistante → HTTP 404
  - [x] Test reject : utilisateur non autorisé → HTTP 403
  - [x] Test : format réponse cohérent `{"data": {...}}` pour approve et reject

- [x] **Task 8** — Tests unitaires bug filtres catalogue (AC3)
  - [x] Créer `catalog/tests/test_catalog_filters_fix.py`
  - [x] Test : `list_all(status='published')` retourne seulement les actions publiées
  - [x] Test : `list_all(item_type='action')` retourne seulement les actions (pas workflows)
  - [x] Test : `list_all(tags_filter=['database'])` retourne seulement les actions avec tag 'database'
  - [x] Test : **COMBINAISON** `list_all(status='published', item_type='action', tags_filter=['database', 'oracle'])` retourne l'intersection correcte
  - [x] Test : régression non introduite sur les autres cas (status seul, tags seuls, etc.)

- [x] **Task 9** — Tests de sécurité fail-fast secrets (AC7)
  - [x] Créer `core/tests/test_security_settings.py`
  - [x] Test unitaire : import de `settings.py` avec `SECRET_KEY` absente lève `ImproperlyConfigured`
  - [x] Test unitaire : import de `settings.py` avec `JWT_SECRET_KEY` absente lève `ImproperlyConfigured`
  - [x] Test unitaire : import de `settings.py` avec `SECRET_KEY=''` (vide) lève `ImproperlyConfigured`
  - [x] Test unitaire : import de `settings.py` avec `JWT_SECRET_KEY=''` (vide) lève `ImproperlyConfigured`
  - [x] Test d'intégration : démarrage du serveur Django sans secrets → échec gracieux avec message clair
  - [x] Documenter dans le test comment mocker `os.getenv()` pour isoler les tests CI
  - [x] Vérifier que les tests CI passent avec les secrets mockés ou fournis via env vars

- [x] **Task 10** — Documentation et mise à jour templates config (AC4, AC5, AC6)
  - [x] Créer `.env.example` : `DEBUG=True`, `SECRET_KEY=<example>`, `JWT_SECRET_KEY=<example>`
  - [x] Mettre à jour `.env.production.template` : `DEBUG=False`, instructions de génération des secrets
  - [x] Créer `docs/security/secrets-configuration.md` :
    - Section "Configuration sécurisée" avec fail-fast secrets
    - Section "Mode DEBUG" avec opt-in explicite
    - Section "Génération des secrets" avec commande Django
  - [x] Vérifier que `docker-compose.yml` ne contient pas de secrets hardcodés manquants (ajouté JWT_SECRET_KEY)

## Dev Notes

### Architecture et contraintes

**Backend Django :**
- **Fichiers clés :**
  - `executions/views/approval_views.py` : contient déjà `PendingApprovalsView` → ajouter `ApproveExecutionView` et `RejectExecutionView` dans le même module
  - `catalog/services.py:208-215` : bug ligne 215 écrase le queryset au lieu de le chaîner
  - `idp_backend/settings.py` : lignes 35 (DEBUG), 30-32 (SECRET_KEY), 346 (JWT_SECRET_KEY)

**Modèles et statuts :**
- `Execution.status` : enum `ExecutionStatus` avec valeurs `PENDING_APPROVAL`, `SUBMITTED`, `FAILED`
- `Execution.error_message` : champ texte pour stocker la raison de rejet (optionnel)
- Audit log : utiliser `AuditLog.objects.create()` avec `action_type` = `EXECUTION_APPROVED` ou `EXECUTION_REJECTED`

**Permissions RBAC :**
- Utiliser `IsDBAOrDBOPS` permission (déjà implémentée dans Story 26.8)
- Cohérent avec `PendingApprovalsView` : seuls DBA et DBOPS peuvent approuver/rejeter

**Format de réponse API :**
- Standard DRF : `{"data": ExecutionSerializer(execution).data}`
- Utiliser `ExecutionSerializer` existant (pas besoin de nouveau serializer)
- Pagination non nécessaire pour les endpoints approve/reject (opération unitaire)

**Gestion des erreurs :**
- HTTP 400 si statut invalide (ex. approuver une exécution déjà `RUNNING`)
- HTTP 404 si exécution inexistante
- HTTP 403 si utilisateur non autorisé (automatique via `IsDBAOrDBOPS`)

### Références techniques

**Stories liées :**
- **Story 7.4** : workflow d'approbation pour la production (logique métier des approbations)
- **Story 26.8** : création de la permission `IsDBAOrDBOPS` (utilisée ici)
- **Story 26.11** : standardisation de la pagination (utiliser `paginate_queryset` si besoin)
- **Story 17.5** : sécurisation gestion secrets (validation `startup_checks.py` conservée)
- **Story 22.20** : intégration drf-spectacular (utiliser `@extend_schema` pour les nouveaux endpoints)

**Documentation :**
- [Source: idp-portal/CODEBASE-REVIEW.md#1-endpoints-manquants-frontend--backend]
- [Source: idp-portal/CODEBASE-REVIEW.md#2-bugs-logiques--backend]
- [Source: idp-portal/CODEBASE-REVIEW.md#4-problèmes-de-sécurité]
- [Source: _bmad-output/planning-artifacts/epic-30-codebase-review-corrections-fev-2026.md#story-301]

**Bibliothèques et versions :**
- Django 5.2
- Django REST Framework 3.16
- drf-spectacular (pour OpenAPI/Swagger)
- Oracle DB (via cx_Oracle ou oracledb)

**Patterns établis :**
- Fichier `approval_views.py` déjà existant avec `PendingApprovalsView` → ajouter les nouvelles vues dans le même module
- Utiliser `@extend_schema` pour tous les endpoints (Story 22.20)
- Utiliser `structlog` pour le logging structuré avec `correlation_id` et `user_id`
- Audit log : créer une entrée pour chaque action critique (approve/reject)

### Pièges à éviter

1. **Ne pas oublier l'audit log** : EXECUTION_APPROVED et EXECUTION_REJECTED doivent être enregistrés avec `user_id` et `correlation_id`
2. **Validation du statut** : seules les exécutions en `PENDING_APPROVAL` peuvent être approuvées/rejetées
3. **Chaîner le queryset** : ligne 215 de `catalog/services.py` doit chaîner `.search_by_tags()` sur le queryset existant, pas créer un nouveau queryset
4. **Fail-fast secrets** : `ImproperlyConfigured` doit être levée **au chargement de settings.py**, pas au runtime
5. **Tests CI** : mocker `os.getenv()` pour les tests de sécurité sinon les tests échoueront si les secrets ne sont pas définis
6. **DEBUG False par défaut** : inverser la logique actuelle (`'True'` → `'False'`) pour opt-in explicite
7. **Différencier SECRET_KEY et JWT_SECRET_KEY** : ce sont deux secrets distincts, ne pas utiliser la même valeur

### Hypothèses et décisions

**Décision 1 — Transitions de statut :**
- Approve : `PENDING_APPROVAL` → `SUBMITTED` (cohérent avec Story 7.4)
- Reject : `PENDING_APPROVAL` → `FAILED` (marque l'exécution comme terminée en échec)

**Décision 2 — Stockage de la raison de rejet :**
- Utiliser le champ existant `Execution.error_message` pour stocker `rejection_reason`
- Si `rejection_reason` non fournie, laisser `error_message` vide ou message par défaut : "Execution rejected by user"

**Décision 3 — Permissions :**
- Seuls DBA et DBOPS peuvent approuver/rejeter (cohérent avec `PendingApprovalsView`)
- Pas de vérification supplémentaire (ex. "initiateur peut approuver") pour simplifier et aligner sur Story 7.4

**Décision 4 — Fail-fast vs fallback dev :**
- Supprimer tous les fallbacks hardcodés pour `SECRET_KEY` et `JWT_SECRET_KEY`
- Mode dev : définir les secrets dans `.env` (générer avec Django `get_random_secret_key()`)
- Mode production : secrets requis via env vars, sinon échec au démarrage (fail-secure)

**Hypothèse 1 — Types audit :**
- `EXECUTION_APPROVED` n'existait pas dans `AuditActionType` enum → ajouté dans `core/models.py`
- `EXECUTION_REJECTED` existait déjà

**Hypothèse 2 — Frontend alignement :**
- Le frontend appelle déjà `POST /executions/{id}/approve` et `POST /executions/{id}/reject` (cf. `execution_service.ts:229,256`)
- Pas de modification frontend requise, juste implémenter les endpoints backend manquants

**Hypothèse 3 — Tests existants :**
- Les tests du catalogue passent actuellement (même avec le bug) car ils n'utilisent pas la combinaison des 3 filtres simultanément
- Le fix ne devrait pas introduire de régression, mais exécuter tous les tests catalogue pour valider

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- Story générée automatiquement via workflow create-story (BMAD)
- Analyse exhaustive de CODEBASE-REVIEW.md (65 findings)
- Contexte Epic 30 : corrections critiques avant release
- Implémentation : 2026-02-16

### Completion Notes List

**Story implémentée le** : 2026-02-16

**Issues résolues** :
- API-MISS-1 : `POST /executions/{id}/approve` → `ApproveExecutionView` créée, route ajoutée, 6 tests
- API-MISS-2 : `POST /executions/{id}/reject` → `RejectExecutionView` créée, route ajoutée, 7 tests
- BUG-BE-1 : `tags_filter` écrasait le queryset → chaîné correctement, 5 tests d'intégration
- SEC-1 : `DEBUG=True` par défaut → `DEBUG=False` (opt-in explicite)
- SEC-2 : `SECRET_KEY` fallback hardcodé → `ImproperlyConfigured` (fail-fast)
- SEC-3 : `JWT_SECRET_KEY` vide par défaut → `ImproperlyConfigured` (fail-fast)

**EXECUTION_APPROVED ajouté** : Le type d'audit `EXECUTION_APPROVED` n'existait pas dans `AuditActionType` → ajouté dans `core/models.py`

**test_settings.py adapté** : Les secrets sont maintenant définis via `os.environ.setdefault()` AVANT l'import de `settings.py` pour éviter `ImproperlyConfigured` en mode test.

**Tests ajoutés** : 24 tests au total (13 approve/reject + 5 filtres catalogue + 6 sécurité secrets), tous passent.

**Régression** : 1192 tests existants passent (17 échecs pré-existants non liés — policy evaluator, rule engine, exception handling scanner).

### Code Review (2026-02-16)

**Status:** ✅ Reviewed and fixed

**Review findings:** 6 issues trouvés (1 HIGH, 3 MEDIUM, 2 LOW) — **tous corrigés automatiquement**

1. **HIGH-2** — `catalog/models.py:90` : `search_by_tags()` écrasait le queryset au lieu de chaîner → **CORRIGÉ** (préserve maintenant les filtres existants)
2. **MEDIUM-1** — `approval_views.py` : Race condition possible (pas de locking) → **CORRIGÉ** (`select_for_update()` + `@transaction.atomic`)
3. **MEDIUM-2** — `test_approval_endpoints.py` : Tests de concurrence manquants → **AJOUTÉ** (2 tests, skipped car limitation SQLite)
4. **MEDIUM-3** — `.env.example/.env.production.template` : Documentation secrets insuffisante → **AMÉLIORÉ** (explique pourquoi JWT_SECRET_KEY ≠ SECRET_KEY)
5. **LOW-1** — `approval_views.py` : Code dupliqué (validation exécution) → **REFACTORISÉ** (helper `_get_and_validate_pending_execution()`)
6. **LOW-2** — `catalog/services.py:215` : Manque de logging observabilité → **AJOUTÉ** (logs debug avant/après filtres tags)

**Post-review tests:** 24 passed + 2 skipped (concurrence SQLite), 0 régression

### Change Log

- 2026-02-16 : Implémentation complète Story 30.1 — 10 tasks, 24 tests, 0 régression
- 2026-02-16 : Code Review — 6 issues trouvés et corrigés, +2 tests concurrence (skipped SQLite), +logging, +refactoring, +doc

### File List

**Fichiers modifiés :**
- `idp-portal/django_backend/executions/views/approval_views.py` — Ajout `ApproveExecutionView` + `RejectExecutionView` + helper `_get_and_validate_pending_execution()` (Code Review: race condition fix)
- `idp-portal/django_backend/executions/views/__init__.py` — Export des nouvelles vues
- `idp-portal/django_backend/executions/urls.py` — Routes approve/ et reject/
- `idp-portal/django_backend/catalog/services.py` — Fix ligne 215: `queryset = queryset.search_by_tags(tags_filter)` + logging debug (Code Review: observabilité)
- `idp-portal/django_backend/catalog/models.py` — Fix `search_by_tags()` : préserve queryset chain au lieu d'écraser (Code Review HIGH-2)
- `idp-portal/django_backend/idp_backend/settings.py` — DEBUG=False, SECRET_KEY fail-fast, JWT_SECRET_KEY fail-fast
- `idp-portal/django_backend/idp_backend/test_settings.py` — Secrets via `os.environ.setdefault()` avant import
- `idp-portal/django_backend/core/models.py` — Ajout `EXECUTION_APPROVED` dans `AuditActionType`
- `idp-portal/django_backend/.env.production.template` — Commentaires sécurité améliorés (Code Review: doc defense-in-depth)
- `idp-portal/django_backend/.env.example` — Commentaires JWT_SECRET_KEY vs SECRET_KEY (Code Review: doc)
- `idp-portal/docker-compose.yml` — Ajout `JWT_SECRET_KEY` manquant

**Fichiers créés :**
- `idp-portal/django_backend/executions/tests/test_approval_endpoints.py` — 15 tests (13 approve/reject + 2 concurrence skipped)
- `idp-portal/django_backend/catalog/tests/test_catalog_filters_fix.py` — 5 tests (filtres combinés)
- `idp-portal/django_backend/core/tests/test_security_settings.py` — 6 tests (fail-fast secrets)
- `idp-portal/django_backend/.env.example` — Configuration dev locale
- `idp-portal/django_backend/docs/security/secrets-configuration.md` — Documentation sécurité secrets
