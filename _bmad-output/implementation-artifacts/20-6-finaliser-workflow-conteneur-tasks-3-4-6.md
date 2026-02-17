# Story 20.6 : Finaliser workflow conteneur — Tasks 3, 4, 6

Status: review

<!-- Note: Validation optionnelle. Exécuter validate-create-story pour contrôle qualité avant dev-story. -->

## Story

En tant que **développeur**,
je veux **compléter l'implémentation des workflows conteneurs en finalisant le moteur d'exécution, l'interface admin, et les tests**,
afin que **les workflows puissent être exécutés et gérés de bout en bout dans le portail**.

## Contexte

La Story 5.7 a introduit le concept de **workflow conteneur** : une entrée du catalogue qui enchaîne des actions existantes sans avoir de connecteur propre. Les Tasks 1, 2, et 5 ont été complétées (modèle de données backend, API, icônes frontend), mais les **Tasks 3, 4, et 6** restent à faire :

- **Task 3** : Moteur d'exécution backend pour orchestrer l'exécution des actions référencées par le workflow
- **Task 4** : Interface admin frontend pour créer/éditer des workflows (sélecteur d'actions, pas de connecteur)
- **Task 6** : Tests backend et frontend pour valider l'implémentation complète

Cette story consolide le travail restant pour rendre les workflows pleinement fonctionnels.

## Acceptance Criteria

### AC1 — Moteur d'exécution workflow (Task 3.1)
**Given** une exécution lancée sur une entrée de type **workflow**,
**When** le moteur traite les étapes,
**Then** chaque étape « référence action » (avec `referenced_action_id`) déclenche l'exécution de l'action référencée dans l'ordre, et le connecteur est celui de l'action, pas du workflow.

### AC2 — Gestion des sous-exécutions (Task 3.2)
**Given** un workflow avec plusieurs étapes référençant des actions,
**When** le workflow s'exécute,
**Then** chaque action référencée crée une exécution enfant (avec `parent_execution_id`), permettant la traçabilité, l'annulation en cascade, et l'agrégation des logs.

### AC3 — Workflow step parameters (Task 3.2 étendu)
**Given** un workflow avec des paramètres par étape (Story 4.12),
**When** une étape s'exécute,
**Then** les `workflow_step_parameters` de l'étape sont injectés dans les paramètres de l'action référencée (fusionnés avec les paramètres globaux du workflow).

### AC4 — Échec/annulation propagée (Task 3.2)
**Given** une action référencée échoue ou est annulée,
**When** le workflow détecte ce statut,
**Then** le workflow passe en `FAILED` ou `CANCELLED`, et les étapes suivantes ne sont pas exécutées (sauf si logique de branches conditionnelles s'applique, mais hors scope pour cette story).

### AC5 — Interface admin workflow (Task 4.1)
**Given** un DBOPS crée ou édite une entrée dans l'admin,
**When** il choisit le type **workflow**,
**Then** l'interface masque/désactive les champs connecteur et plateforme, et affiche l'éditeur d'étapes « référence à une action ».

### AC6 — Éditeur d'étapes workflow (Task 4.2)
**Given** un DBOPS édite un workflow,
**When** il configure les étapes,
**Then** chaque étape propose un sélecteur d'**action existante** (liste ou autocomplete par nom/id), avec ordre et libellé d'affichage optionnel, sans choix de connecteur.

### AC7 — Validation frontend (Task 4.3)
**Given** un DBOPS sauvegarde un workflow,
**When** l'API retourne une erreur de validation (boucle, étape avec connecteur),
**Then** le frontend affiche un message d'erreur clair et bloque la sauvegarde.

### AC8 — Tests backend (Task 6.1)
**Given** l'implémentation du moteur d'exécution,
**When** les tests sont exécutés,
**Then** les tests unitaires et d'intégration valident : (1) création/mise à jour workflow, (2) validation boucles, (3) exécution workflow avec enchaînement d'actions, (4) échec/annulation propagée, (5) injection de workflow_step_parameters.

### AC9 — Tests frontend (Task 6.2)
**Given** l'implémentation de l'interface admin,
**When** les tests sont exécutés,
**Then** les tests valident : (1) éditeur d'étapes workflow (sélecteur d'action, pas de connecteur), (2) affichage de l'icône workflow dans le catalogue, (3) validation côté frontend.

### AC10 — Non-régression
**Given** l'implémentation complète des workflows,
**When** les tests existants sont exécutés,
**Then** tous les tests catalogue, admin, et execution restent verts ; les données de test avec `item_type: "action"` par défaut ne cassent rien.

## Tasks / Subtasks

- [x] Task 3 : Backend — Moteur d'exécution (AC1, AC2, AC3, AC4)
  - [x] 3.1 Détecter type workflow au démarrage d'exécution : lire `action.item_type`, brancher vers moteur workflow si `item_type == 'workflow'`
  - [x] 3.2 Moteur workflow : pour chaque étape (ordre), charger l'action référencée (via `referenced_action_id`), lancer une exécution enfant (avec `parent_execution_id`), attendre la fin (polling ou callback), propager échec/annulation
  - [x] 3.3 Injection de workflow_step_parameters : fusionner `workflow_step_parameters` de l'étape avec les paramètres globaux du workflow avant de lancer l'exécution de l'action référencée
  - [x] 3.4 Gestion des statuts : mettre à jour le statut du workflow parent en fonction des statuts des exécutions enfants (RUNNING, COMPLETED, FAILED, CANCELLED)
  - [x] 3.5 Intégration avec WorkflowRuntime existant (Story 16.3, 20.3) : moteur séparé `ContainerWorkflowRuntime` pour ne pas interférer avec le moteur de branches conditionnelles

- [x] Task 4 : Frontend — Admin workflow (AC5, AC6, AC7)
  - [x] 4.1 ActionWizard : au choix du type **workflow**, masquer les champs connecteur/plateforme, afficher l'éditeur d'étapes workflow (déjà implémenté Stories 9.5, 16.5)
  - [x] 4.2 Éditeur d'étapes workflow : `WorkflowStepsEditor` composant dédié avec sélecteur d'action via AutoComplete (déjà implémenté Story 9.5)
  - [x] 4.3 Validation frontend : bloquer la sauvegarde si étape sans action ; afficher les erreurs API (déjà implémenté Story 16.7)
  - [x] 4.4 UX : message d'aide contextuel ajouté dans ActionWizard expliquant le fonctionnement des workflows

- [x] Task 6 : Tests (AC8, AC9, AC10)
  - [x] 6.1 Backend : 22 tests unitaires pour exécution workflow (ordre, statuts, injection workflow_step_parameters, propagation échec/annulation)
  - [x] 6.2 Backend : 5 tests d'intégration API (exécution complète, child executions, step parameters, non-régression)
  - [x] 6.3 Frontend : 14 tests WorkflowStepsEditor (ajout/suppression/réordonnancement, sélecteur d'action, retry, validation, accessibilité)
  - [x] 6.4 Frontend : 3 tests ActionCard pour icône workflow + 8 tests iconHelpers (ApartmentOutlined pour workflows)
  - [x] 6.5 Non-régression : 27/27 backend, 47/47 frontend nouveaux tests verts ; aucun nouvel échec dans la suite existante

## Dev Notes

### Contexte technique

- **Epic 20** : Action items et suivi — Restant des stories "done". Cette story finalise les tâches en suspens de la Story 5.7 (workflows conteneurs).
- **Story 5.7** : Workflow — conteneur d'actions et icône identifiable dans le catalogue. Tasks 1, 2, 5 complétées (backend model, API, frontend icons). Tasks 3, 4, 6 en suspens.
- **Modèle actuel** : `Action.item_type` (action | workflow), `Action.workflow_steps` dans `execution_steps` CLOB JSON (format : `[{"order": 1, "name": "Step 1", "referenced_action_id": 123}]`). Les workflows n'ont pas de `connector_type` / `platform` sur les étapes.
- **Moteur d'exécution** : `executions/workflow_runtime.py` (Story 16.3, 20.3) gère déjà les branches conditionnelles (`on_success_step_id`, `on_error_step_id`) et le retry. Il faut étendre ce moteur pour supporter les workflows conteneurs (étapes = références d'actions), ou créer un moteur séparé.
- **Migration Django** : Epic M (Migration FastAPI → Django REST) complété. Le backend est maintenant Django 5.2 + DRF 3.16, Oracle DB.

### Architecture Compliance

- [Source: architecture.md] **Repository Pattern** : Utiliser `catalog.models.Action` et `executions.models.Execution` (Django ORM). Pas de SQL ad hoc.
- [Source: architecture.md] **API format** : snake_case JSON, wrapper DRF standard (`{ "data": ... }` / `{ "error": ... }` si custom). Les réponses catalogue doivent inclure `item_type` pour que le frontend affiche l'icône.
- [Source: architecture.md] **Execution facade** : `executions/services.py` (`ExecutionService`) et `executions/workflow_runtime.py` (`WorkflowRuntime`) orchestrent les exécutions. Pour un workflow conteneur, le moteur doit résoudre les étapes en « références action » puis lancer une exécution enfant par action référencée (avec `parent_execution_id`).
- [Source: idp-portal] **EXECUTION_STEPS** : CLOB JSON dans `ACTIONS_CATALOG.EXECUTION_STEPS` (V003, V008, V027). Format actuel workflow : `[{"order", "name", "referenced_action_id"}]`. Le moteur doit distinguer étapes à connecteur (actions) vs étapes à référence (workflows).
- [Source: idp-portal] **EXECUTIONS / EXECUTION_STEPS** (table) : `executions.models.Execution` (V023), `executions.models.ExecutionStep` (V025). Pour un workflow, créer une exécution parent + N exécutions enfants (avec `parent_execution_id`) pour traçabilité, annulation, logs.
- [Source: Story 20.3] **Celery retry** : Le retry asynchrone utilise Celery (`apply_async(countdown=...)`). Le moteur workflow doit s'intégrer avec ce mécanisme si besoin.
- [Source: Story 4.12] **workflow_step_parameters** : Chaque étape peut avoir des paramètres spécifiques à injecter dans l'action référencée. Le moteur doit fusionner `workflow_step_parameters` avec les paramètres globaux du workflow.

### Technical Requirements

- **Détection type workflow** : Au démarrage d'exécution, lire `action.item_type`. Si `workflow`, brancher vers le moteur workflow au lieu du moteur standard.
- **Moteur workflow** :
  1. Charger les étapes workflow depuis `action.execution_steps` (format : `[{"order": 1, "name": "Step 1", "referenced_action_id": 123, "workflow_step_parameters": {...}}]`)
  2. Pour chaque étape dans l'ordre :
     - Charger l'action référencée (via `referenced_action_id`)
     - Fusionner `workflow_step_parameters` avec les paramètres globaux du workflow
     - Lancer une exécution enfant (via `ExecutionService.create_execution` avec `parent_execution_id`)
     - Attendre la fin (polling ou callback) — statut `COMPLETED`, `FAILED`, ou `CANCELLED`
     - Si `FAILED` ou `CANCELLED`, faire échouer le workflow ; sinon étape suivante
  3. Mettre à jour le statut du workflow parent en fonction des statuts enfants
- **Intégration WorkflowRuntime** : Le `WorkflowRuntime` existant gère déjà les branches conditionnelles et le retry. Décider si : (a) étendre `WorkflowRuntime` pour supporter les deux modes (branches conditionnelles + référence d'actions), ou (b) créer un moteur séparé `WorkflowContainerRuntime`. Recommandation : (a) pour réutiliser la logique de state management, loop detection, audit trail.
- **RBAC** : L'utilisateur doit avoir le droit d'exécuter le workflow ET chaque action référencée (vérifier les permissions lors de la création de chaque exécution enfant).
- **Annulation en cascade** : Si le workflow parent est annulé, annuler toutes les exécutions enfants en cours (via `executions.cancellation_cache.py` ou mécanisme similaire).

### Library / Framework Requirements

- **Backend** : Django 5.2+, DRF 3.16+, Python 3.12+. Réutiliser `executions/services.py` (`ExecutionService`), `executions/workflow_runtime.py` (`WorkflowRuntime`), `catalog.models.Action`.
- **Frontend** : React 18+, Ant Design 6.x, TypeScript. Composants existants : `ActionWizard` (admin/ActionWizard.tsx), `StepsEditor` (admin/StepsEditor.tsx). Étendre pour type workflow : choix type dans le wizard, éditeur d'étapes « référence action » (Select/AutoComplete vers GET /api/v1/admin/actions/eligible-for-workflow).
- **Icônes** : `@ant-design/icons` (`ApartmentOutlined` pour workflows, déjà implémenté dans Story 5.7 Task 5).
- **Tests** : pytest (backend), Vitest + React Testing Library (frontend).

### Project Structure Notes

- **Backend** :
  - `catalog/models.py` : `Action.item_type`, `Action.execution_steps` (workflow steps si `item_type == 'workflow'`)
  - `executions/services.py` : `ExecutionService.create_execution` (déjà supporte `parent_execution_id`)
  - `executions/workflow_runtime.py` : Étendre `WorkflowRuntime` pour supporter les workflows conteneurs (ou créer `WorkflowContainerRuntime`)
  - `executions/views.py` : POST `/api/v1/executions` — brancher vers le moteur approprié selon `action.item_type`
  - Tests : `executions/tests/test_workflow_container_execution.py` (nouveau), `catalog/tests/test_workflow_admin.py` (nouveau)
- **Frontend** :
  - `src/types/api.ts` : `ItemType`, `WorkflowStep` (déjà définis dans Story 5.7)
  - `src/components/admin/ActionWizard.tsx` : Étendre pour masquer connecteur/plateforme si type workflow
  - `src/components/admin/WorkflowStepsEditor.tsx` : Nouveau composant (ou extension de StepsEditor) pour éditer les étapes workflow (sélecteur d'actions)
  - Tests : `src/components/admin/__tests__/WorkflowStepsEditor.test.tsx` (nouveau), `src/components/catalog/__tests__/ActionCard.test.tsx` (déjà teste l'icône workflow)
- **Alignement** : Ne pas casser les appels existants. Les workflows sont un type d'action, donc les endpoints catalogue/admin doivent continuer à fonctionner pour les actions standards.

### Référence story précédente (5.7)

- **Story 5.7** : Workflow — conteneur d'actions et icône identifiable dans le catalogue. Fichiers modifiés :
  - Backend : `catalog/models.py`, `catalog/admin.py`, migration V027, tests backend
  - Frontend : `src/types/api.ts`, `ActionCard.tsx`, `ActionDrawerPreview.tsx`
  - Tasks 1, 2, 5 complétées ; Tasks 3, 4, 6 en suspens (cette story)
- **Fichiers à réutiliser** :
  - `catalog/models.py` : `ActionItemType`, `Action.item_type`, validation boucles (`validate_workflow_steps`, `_detect_workflow_loop`)
  - API : GET `/api/v1/admin/actions/eligible-for-workflow` (déjà implémenté pour lister les actions éligibles)
- **Contexte Git récent** :
  - `ef02b9c` : feat(20-5): add comprehensive project documentation and quality standards
  - `cfd46a4` : feat(20-4): refactor ExecutionWizard with performance optimizations and better maintainability
  - `2c2af1e` : feat(20-3): migrate workflow retry mechanism to asynchronous Celery tasks
  - Contexte : Epic M (migration Django) complété, Epic 20 (action items) en cours

### Testing Requirements

- **Backend** :
  - Tests unitaires : (1) Détection type workflow au démarrage, (2) Chargement des étapes workflow, (3) Lancement d'exécutions enfants, (4) Injection workflow_step_parameters, (5) Propagation échec/annulation
  - Tests d'intégration : (1) Exécution complète d'un workflow avec 2-3 actions, (2) Annulation en cascade, (3) Échec d'une action référencée fait échouer le workflow, (4) Vérification RBAC (utilisateur doit avoir droits sur toutes les actions)
  - Mock : Utiliser `unittest.mock` ou `pytest-mock` pour mocker les exécutions enfants (éviter d'exécuter de vraies actions AAP/Terraform dans les tests)
- **Frontend** :
  - Tests composants : (1) ActionWizard affiche éditeur workflow si type workflow, (2) WorkflowStepsEditor ajoute/supprime/réordonne des étapes, (3) Sélecteur d'action appelle GET /api/v1/admin/actions/eligible-for-workflow, (4) Validation bloque sauvegarde si erreur API
  - Tests snapshot : (1) Icône workflow dans ActionCard, (2) Badge workflow dans drawer
  - Mock API : Utiliser `msw` ou `vitest.mock` pour mocker les endpoints
- **Non-régression** : Exécuter tous les tests existants (catalog, admin, execution, integrations) et vérifier 0 échecs nouveaux

### Project Context Reference

- [Source: _bmad-output/planning-artifacts/architecture.md] Stack backend (Django 5.2, python-oracledb), Repository Pattern, API snake_case, structure dossiers
- [Source: idp-portal/django_backend/catalog/models.py] `Action`, `ActionItemType`, `execution_steps` (CLOB JSON)
- [Source: idp-portal/django_backend/executions/models.py] `Execution`, `ExecutionStep`, `parent_execution_id`
- [Source: idp-portal/django_backend/executions/services.py] `ExecutionService.create_execution` (supporte `parent_execution_id`)
- [Source: idp-portal/django_backend/executions/workflow_runtime.py] `WorkflowRuntime`, `WorkflowExecutionState`, `StepResult`
- [Source: Story 5.7 Dev Notes] Loop detection : `catalog_repository.validate_workflow_steps`, `_detect_workflow_loop`
- [Source: Story 4.12] workflow_step_parameters : Injection de paramètres par étape dans l'action référencée
- [Source: Story 20.3] Celery retry asynchrone : `executions/tasks.py`, `apply_async(countdown=...)`

### Known Issues / Follow-ups (from Story 5.7)

- **Story 5.7 code review** : 10 issues corrigés (HIGH : ITEM_TYPE missing from SQL queries, MEDIUM : item_type filter not applied, LOW : test fixtures). Tous fixés, 74 catalog + 37 admin + 443 frontend tests pass.
- **Tasks 3, 4, 6 pending** : Moteur d'exécution, admin UI, tests — c'est l'objet de cette story.
- **Décision architecture** : Story 5.7 a documenté deux options pour les exécutions workflow : (1) exécution parent + N exécutions enfants, (2) exécution unique avec steps virtuels. Recommandation : (1) pour meilleure traçabilité, annulation, logs (cette story implémente l'option 1).

### Migration Django context (Epic M)

- **Epic M complété** : FastAPI → Django REST. Backend maintenant Django 5.2 + DRF 3.16.
- **Modèles Django** : `catalog.models.Action`, `executions.models.Execution`, `idp_auth.models.User`.
- **ORM Django** : Utiliser `select_related`, `prefetch_related` pour optimiser les requêtes (éviter N+1).
- **Serializers DRF** : `catalog/serializers.py`, `executions/serializers.py` — utiliser pour valider/sérialiser les données.
- **Tests pytest** : Configuration dans `pytest.ini`, settings `idp_backend.test_settings`, runner `.venv/bin/python -m pytest`.
- **Known issues** : 298+ tests existants échouent (fixtures DB manquantes) — pré-existant, pas causé par cette story. Focus sur les tests nouveaux pour cette story.

### References

- [Source: Story 5.7] Dev Notes, File List, Change Log — contexte complet de l'implémentation partielle
- [Source: Story 16.3] WorkflowRuntime — moteur de branches conditionnelles à réutiliser/étendre
- [Source: Story 20.3] Celery retry asynchrone — intégration avec le moteur workflow si besoin
- [Source: Story 4.12] workflow_step_parameters — injection de paramètres par étape
- [Source: idp-portal/django_backend/executions/workflow_runtime.py] Implémentation actuelle du WorkflowRuntime
- [Source: idp-portal/django_backend/executions/services.py] ExecutionService — création d'exécutions avec parent_execution_id
- [Source: idp-portal/django_backend/catalog/models.py] Action model, item_type, execution_steps

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

- OracleJSONField ne désérialise pas en mémoire (seulement via `from_db_value` au chargement DB) → tests doivent passer des listes Python, pas `json.dumps()`
- `validate_json_schema()` (fallback sans jsonschema) ne gère pas les propriétés scalaires → utiliser `{"type": "object"}` sans `properties` dans les schemas de test

### Completion Notes List

- Moteur séparé `ContainerWorkflowRuntime` créé (plutôt qu'étendre `WorkflowRuntime`) pour isolation et clarté
- Tasks 4.1-4.3 étaient déjà implémentées par les Stories 9.5, 16.5, 16.7 — vérification et ajout du message d'aide contextuel (4.4)
- 5 échecs ActionWizard.test.tsx confirmés pré-existants (identiques avant/après changements)
- 64 échecs frontend et 298+ échecs backend sont tous pré-existants (fixtures DB manquantes, etc.)

### File List

#### Fichiers créés
- `idp-portal/django_backend/executions/container_workflow_runtime.py` — Moteur d'exécution workflow conteneur (AC1, AC2, AC3, AC4)
- `idp-portal/django_backend/executions/tests/test_container_workflow_runtime.py` — 22 tests unitaires (AC8)
- `idp-portal/django_backend/executions/tests/test_container_workflow_integration.py` — 5 tests d'intégration API (AC8, AC10)

#### Fichiers modifiés
- `idp-portal/django_backend/executions/views.py` — Branchement vers ContainerWorkflowRuntime pour `item_type == 'workflow'` (lignes ~841-858)
- `idp-portal/frontend/src/components/admin/ActionWizard.tsx` — Message d'aide contextuel workflow (Task 4.4)
- `idp-portal/frontend/src/components/catalog/ActionCard.test.tsx` — 3 tests ajoutés pour icône workflow (AC9)

#### Fichiers existants vérifiés (non modifiés)
- `idp-portal/frontend/src/components/admin/WorkflowStepsEditor.test.tsx` — 14 tests existants couvrent AC9
- `idp-portal/frontend/src/utils/iconHelpers.test.tsx` — 8 tests existants couvrent icône workflow

### Change Log

| Fichier | Changement | AC |
|---|---|---|
| `executions/container_workflow_runtime.py` | Nouveau : moteur d'exécution séquentiel pour workflows conteneurs | AC1, AC2, AC3, AC4 |
| `executions/views.py` | Modifié : détection `item_type == 'workflow'` et branchement vers `ContainerWorkflowRuntime` | AC1 |
| `frontend/src/components/admin/ActionWizard.tsx` | Modifié : ajout Alert d'aide contextuelle pour workflows | AC5 |
| `executions/tests/test_container_workflow_runtime.py` | Nouveau : 22 tests unitaires backend | AC8 |
| `executions/tests/test_container_workflow_integration.py` | Nouveau : 5 tests d'intégration API | AC8, AC10 |
| `frontend/src/components/catalog/ActionCard.test.tsx` | Modifié : 3 tests icône workflow ajoutés | AC9 |
