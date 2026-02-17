# Story 25.5 : Mutex inter-actions (table ACTION_MUTEX et validation à la soumission)

Status: done

## Story

As a DBOPS,  
I want définir des exclusions mutuelles entre actions (ex. patching et backup sur la même base ne doivent pas tourner en parallèle),  
so that des opérations incompatibles ne soient jamais exécutées simultanément sur les mêmes cibles.

## Acceptance Criteria

### AC1: Table `ACTION_MUTEX` + règles `same_target`

**Given** une table `ACTION_MUTEX` (action_id, incompatible_with_id, same_target bool, description)  
**When** un DBOPS configure une règle de mutex entre l'action A et l'action B avec `same_target=True`  
**Then** au moment de la soumission d'une exécution pour l'action A sur des cibles données, le backend vérifie qu'aucune exécution en cours (`RUNNING`, `PENDING_APPROVAL`, `SUBMITTED`) pour l'action B ne cible les mêmes `target_id` (via `ExecutionTarget`)  
**And** si une telle exécution existe, la soumission est refusée avec une erreur explicite (`MutexViolationError` ou équivalent)

### AC2: Mutex global (`same_target=False`)

**Given** une règle de mutex avec `same_target=False`  
**When** une exécution pour l'action A est soumise  
**Then** le backend refuse la soumission si une exécution pour l'action B est déjà en cours, quelle que soit la cible

### AC3: Migration + API Admin

**And** une migration crée la table `ACTION_MUTEX` avec `unique_together (action, incompatible_with)` et les clés étrangères vers `ACTIONS_CATALOG` (ou équivalent)  
**And** l'API admin permet de créer/supprimer des règles de mutex entre actions (CRUD ou équivalent)

### AC4: Validation mutex appelée avant création

**And** la validation mutex est appelée systématiquement **avant** de créer une `Execution` et d'insérer les `ExecutionTarget`

## Tasks / Subtasks

- [x] **Task 1: Modèle + migrations DB (AC: 1, 3)**
  - [x] 1.1 Ajouter une migration Flyway `idp-portal/database/migrations/V070__create_action_mutex.sql` (numéro à confirmer) qui crée `ACTION_MUTEX`:
    - Colonnes: `ID` identity, `ACTION_ID`, `INCOMPATIBLE_WITH_ID`, `SAME_TARGET` (NUMBER(1) / boolean), `DESCRIPTION`, `CREATED_AT`
    - FKs vers `ACTIONS_CATALOG(ID)` (ou table action réelle) avec index sur `(ACTION_ID)` et `(INCOMPATIBLE_WITH_ID)` (+ composite si utile)
    - Contrainte unique `UQ_ACTION_MUTEX_ACTION_INCOMPATIBLE (ACTION_ID, INCOMPATIBLE_WITH_ID)`
  - [x] 1.2 Ajouter le modèle Django `ActionMutex` (recommandé dans `idp-portal/django_backend/catalog/models.py` **ou** `executions/models.py`, mais choisir UNE source de vérité)
    - `db_table = 'ACTION_MUTEX'`
    - `unique_together = ('action', 'incompatible_with')`
    - `same_target: bool`
    - `description: str`
  - [x] 1.3 Ajouter la migration Django correspondante (pour la DB de tests) dans l’app choisie

- [x] **Task 2: Service de validation mutex (AC: 1, 2, 4)**
  - [x] 2.1 Implémenter `validate_action_mutex(...)` (ex: dans `idp-portal/django_backend/executions/utils.py` ou un nouveau `executions/mutex_service.py`)
    - Entrées minimales: `action_id`, `target_ids` (ou `validated_targets`), `active_statuses=[RUNNING, PENDING_APPROVAL, SUBMITTED]`
    - Sortie: lève une exception métier (`BadRequestError` ou `ConflictError`) avec `code="MUTEX_VIOLATION"` + détails structurés
  - [x] 2.2 Couvrir les 2 modes:
    - `same_target=True`: rechercher des exécutions actives de l’action incompatible qui ont au moins un `ExecutionTarget.target_id` en intersection
    - `same_target=False`: rechercher toute exécution active de l’action incompatible (sans filtre cible)
  - [x] 2.3 **Symétrie de règle** (important pour éviter les trous):
    - Option A (recommandée): à la création d’une règle A→B, créer aussi B→A automatiquement (et rendre l’API idempotente)
    - Option B: supporter A→B uniquement, mais dans la validation vérifier `ActionMutex` dans les deux sens (action=current OR incompatible_with=current)
    - Choisir et documenter clairement
  - [x] 2.4 Performance / robustesse:
    - Utiliser `exists()` plutôt que charger des listes
    - Éviter les N+1 (prefetch/join via `ExecutionTarget` quand nécessaire)
    - Requêtes filtrées sur statuts et action_id

- [x] **Task 3: Brancher la validation au bon endroit (AC: 4)**
  - [x] 3.1 Dans `idp-portal/django_backend/executions/views.py` (`ExecutionsView.post`):
    - Après validation RBAC des cibles (et donc après calcul de `validated_targets` + `environment`)
    - **Avant** `ExecutionService().create_execution(...)` (qui crée `Execution` + `ExecutionTarget` dans `ExecutionService._create_execution_atomic`)
    - Appeler `validate_action_mutex(action, validated_targets, correlation_id, user_id)`
  - [x] 3.2 Définir le mapping d’erreur HTTP:
    - Suggestion: `409 CONFLICT` quand un mutex empêche l’opération (car c’est un conflit d’état), avec message FR explicite
  - [x] 3.3 Ajouter un log structuré `exec_logger.info/warning` sur blocage mutex (avec `action_id`, `incompatible_action_id`, `same_target`, `target_ids`, `correlation_id`)

- [x] **Task 4: API Admin CRUD (AC: 3)**
  - [x] 4.1 Ajouter des endpoints DRF sur `ActionViewSet` (`idp-portal/django_backend/catalog/views.py`):
    - `GET /api/v1/admin/actions/{id}/mutex/` (liste règles)
    - `POST /api/v1/admin/actions/{id}/mutex/` (créer règle)
    - `DELETE /api/v1/admin/actions/{id}/mutex/{rule_id}/` (supprimer règle)
    - (Option) `PUT/PATCH` pour modifier `same_target`/`description`
  - [x] 4.2 Serializer(s) dédiés (ex: `catalog/serializers.py`) + validation:
    - Empêcher `action_id == incompatible_with_id`
    - Empêcher doublons (idempotence)
    - (Option) Empêcher règles sur actions `disabled` si non souhaité
  - [x] 4.3 Tests admin API (ex: `catalog/tests/test_story_25_5_admin_mutex.py`):
    - CRUD minimal + permissions DBOPS only

- [x] **Task 5: Tests mutex à la soumission (AC: 1, 2, 4)**
  - [x] 5.1 Tests unitaires/service:
    - Création d’une exécution “incompatible” active (status RUNNING/SUBMITTED/PENDING_APPROVAL)
    - Ajout d’`ExecutionTarget` sur cette exécution
    - Soumission d’une exécution sur action A avec targets identiques → 409 + `MUTEX_VIOLATION`
  - [x] 5.2 Tests d’intégration API `POST /api/v1/executions/`:
    - Cas `same_target=True` (intersection) → refus
    - Cas `same_target=False` → refus même sans intersection
    - Cas statut incompatible non-actif (COMPLETED/FAILED/CANCELLED/REJECTED/INTEGRATION_ERROR) → autorisé
  - [x] 5.3 S’assurer que l’exécution n’est **pas** créée quand mutex bloque:
    - `Execution` count inchangé
    - `ExecutionTarget` non créé

## Dev Notes

### Contexte Epic 25 — Convergence DBOps → IDP Portal

Cette story implémente le **mutex inter-actions** décrit dans:
- `_bmad-output/implementation-artifacts/convergence-dbops-idp-portal.md` (section “Mutex inter-actions”, et tableau “Nouvelles tables”)  
- `_bmad-output/planning-artifacts/epics.md` (Epic 25, Story 25.5)

**Dépendances déjà en place (stories précédentes) :**
- Story 25.1 ✅: `ExecutionTarget` (`EXECUTION_TARGETS`) — fondation pour filtrer par cible
- Story 25.2 ✅: Statut `WAITING` sur `ExecutionStep` (sans impact direct ici)
- Story 25.3 ✅: Celery Beat evaluate_waiting_gates (sans impact direct ici)
- Story 25.4 ✅: Overrides par environnement (ne change pas la logique mutex, mais le flow de soumission est désormais bien structuré)

### Intelligence story précédente (25.4) à réutiliser

- Le flow de soumission est désormais centralisé dans `ExecutionsView.post` et appelle `ExecutionService().create_execution(...)`.
- Les cibles sont validées *avant* la création de l’exécution, et `validated_targets` est passé à `ExecutionService` pour créer `ExecutionTarget`.
- Les erreurs attendues côté API utilisent des `code` explicites (ex: `EXECUTION_NOT_ALLOWED_FOR_ENVIRONMENT`) et des messages FR.

### Où brancher (important)

- **Point d’entrée**: `idp-portal/django_backend/executions/views.py` → `ExecutionsView.post`
  - C’est là que les cibles sont validées via `InventoryService`, que `validated_targets` est calculé, et que l’appel à `ExecutionService().create_execution(...)` est effectué.
- **Création atomique**: `idp-portal/django_backend/executions/services.py` → `ExecutionService._create_execution_atomic`
  - Crée `Execution`, puis `ExecutionTarget` (Story 25.1).
- **Règle métier à respecter**: mutex doit être validé **avant** la création de l’exécution et l’insertion des `ExecutionTarget` (AC4).

### Developer Guardrails (anti-bugs / anti-regressions)

- **Ne pas réinventer la source des cibles**: la validation mutex doit utiliser `ExecutionTarget` (pas `Execution.parameters['_targets']`) pour être robuste et cohérente avec Epic 25.
- **Ne pas déplacer la création d’ExecutionTarget**: conserver `ExecutionService._create_execution_atomic` comme seul endroit qui insère `EXECUTION_TARGETS`.
- **Respecter les statuts actifs**: mutex ne doit regarder que `RUNNING`, `PENDING_APPROVAL`, `SUBMITTED` (AC). Ne pas bloquer sur les statuts terminaux.
- **Symétrie**: ne pas laisser un “trou” où A bloque B mais B ne bloque pas A. Choisir et garantir une stratégie.
- **Préserver l’observabilité**: inclure `correlation_id` dans les logs d’erreur mutex (pattern existant dans `executions/views.py`).

### Définition des “exécutions en cours”

Pour mutex, considérer comme “actives” exactement ces statuts (AC):
- `ExecutionStatus.RUNNING`
- `ExecutionStatus.PENDING_APPROVAL`
- `ExecutionStatus.SUBMITTED`

Ne pas bloquer sur des statuts terminaux (`COMPLETED`, `FAILED`, `CANCELLED`, `REJECTED`, `INTEGRATION_ERROR`).

### Query design (pour éviter les erreurs fréquentes)

- **same_target=True**:
  - Filtrer d’abord les exécutions actives de l’action incompatible.
  - Joindre `ExecutionTarget` et filtrer sur `target_id__in=<requested_target_ids>`.
  - Important: utiliser `ExecutionTarget.target_id` (snapshot du nom), car c’est ce qui est écrit dans `ExecutionService` aujourd’hui.
- **same_target=False**:
  - Pas de join: un `exists()` sur exécutions actives suffit.

### API et erreurs (contrat)

Si mutex bloque, retourner une erreur structurée (exemple attendu):
- **HTTP**: 409 CONFLICT (recommandé)
- **code**: `MUTEX_VIOLATION`
- **message**: FR claire (nom de l’action incompatible + “opération en cours”)
- **details**: `action_id`, `incompatible_action_id`, `same_target`, `conflicting_execution_ids?`, `conflicting_targets?` (optionnel selon coût)

### Sécurité / audit / observabilité

- Logger un événement structlog dédié au blocage mutex (niveau warning).
- (Optionnel) Ajouter un audit trail spécifique si requis par SOC1 (sinon log applicatif suffit).

### Git intelligence (patterns récents)

Commits récents (conventions à suivre):
- `feat(25-1): implement ExecutionTarget model and API...`
- `fix(25-2): code review fixes...`
- `fix(25-3): code review - ... issues corrigés ...`

Le style courant est donc `feat(25-5): ...` / `fix(25-5): ...` avec mention des fixes de revue si nécessaire.

## Dev Agent Record

### Agent Model Used

GPT-5.2

### Completion Notes List

- ✅ Story 25.5 implémentée avec succès — Toutes les tâches (1-5) complétées
- ✅ Migration Flyway V070 créée pour table ACTION_MUTEX (Oracle)
- ✅ Modèle Django ActionMutex + migration 0006 pour tests
- ✅ Service `validate_action_mutex()` implémenté dans executions/utils.py avec:
  - Validation bidirectionnelle (Option B: A→B et B→A vérifiés)
  - Support same_target=True (intersection cibles) et same_target=False (global)
  - Statuts actifs: RUNNING, PENDING_APPROVAL, SUBMITTED
  - Utilisation de `exists()` pour performance, `ConflictError` pour 409
- ✅ Validation branchée dans ExecutionsView.post (APRÈS RBAC, AVANT create_execution)
- ✅ API Admin CRUD complète sur ActionViewSet:
  - GET/POST /admin/actions/{id}/mutex/
  - DELETE /admin/actions/{id}/mutex/{rule_id}/
  - Création symétrique automatique (Option A: A→B crée aussi B→A)
  - Serializers avec validation (self-reference, duplicates, disabled actions)
- ✅ **23 tests créés** (11 admin API + 12 validation mutex incluant requires_target=False)
- ✅ Couverture tests complète: AC1-AC4 validés

### Code Review Fixes (2026-02-10)

**6 issues critiques/high corrigées:**
1. ✅ CRITICAL-1: Initialisation de `validated_targets=[]` pour actions sans targets (evite NameError)
2. ✅ CRITICAL-2: Suppression règles symétriques sans filtre strict `same_target` (gère incohérences DB)
3. ✅ CRITICAL-3: Ajout 2 tests pour actions `requires_target=False` avec mutex global
4. ✅ HIGH-1: Validation action principale non désactivée dans serializer mutex
5. ✅ HIGH-3: Description NULL autorisée (au lieu de forcer chaîne vide)
6. ✅ Amélioration logs: warning si multiples règles symétriques détectées

### File List

- `idp-portal/database/migrations/V070__create_action_mutex.sql`
- `idp-portal/django_backend/catalog/models.py`
- `idp-portal/django_backend/catalog/migrations/0006_create_action_mutex.py`
- `idp-portal/django_backend/catalog/serializers.py`
- `idp-portal/django_backend/catalog/views.py`
- `idp-portal/django_backend/executions/utils.py`
- `idp-portal/django_backend/executions/views.py`
- `idp-portal/django_backend/catalog/tests/test_story_25_5_admin_mutex.py`
- `idp-portal/django_backend/executions/tests/test_story_25_5_mutex_validation.py`
- `_bmad-output/implementation-artifacts/25-5-mutex-inter-actions-table-action-mutex-validation-soumission.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Change Log

- **2026-02-10:** Story 25.5 implémentée — Table ACTION_MUTEX, modèle Django, validation mutex avec ConflictError 409, API Admin CRUD, 23 tests
- **2026-02-10 (Code Review):** 6 fixes critiques/high appliqués — validated_targets init, suppression règles symétriques robuste, tests requires_target=False, validation action disabled, description NULL

