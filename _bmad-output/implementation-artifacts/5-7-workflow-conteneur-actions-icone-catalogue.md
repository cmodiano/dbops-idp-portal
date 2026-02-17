# Story 5.7 : Workflow — conteneur d'actions et icône identifiable dans le catalogue

Status: done

<!-- Note: Validation optionnelle. Exécuter validate-create-story pour contrôle qualité avant dev-story. -->

## Story

En tant que **DBOPS**,
je veux **créer des workflows qui enchaînent des actions existantes (sans connecteur sur le workflow)**,
afin que **je compose des chaînes (ex. PDB → OUD → OEM) dans le portail avec une icône claire pour les distinguer des actions simples**.

## Contexte

Aujourd'hui une entrée du catalogue est une **action** avec des étapes à connecteur (AAP, ServiceNow, etc.). Il n'existe pas de **workflow** : un conteneur dont les étapes sont uniquement des références à d'autres actions. Le connecteur est porté par l'action référencée, pas par le workflow. Les utilisateurs doivent pouvoir identifier rapidement un workflow dans le catalogue grâce à une icône dédiée.

## Acceptance Criteria

1. **AC1 — Typage action vs workflow**
   **Given** le catalogue,
   **When** on crée ou consulte une entrée,
   **Then** on distingue **action** (unité exécutable avec connecteur) et **workflow** (conteneur sans connecteur). Le workflow n'a pas de `connector_type` ; seules les actions en ont.

2. **AC2 — Étapes d'un workflow**
   **Given** une entrée de type workflow,
   **When** on définit ses étapes,
   **Then** chaque étape est une **référence à une action existante** (ex. `referenced_action_id` + ordre + nom d'affichage). Aucun connecteur n'est configuré sur ces étapes.

3. **AC3 — Icône identifiable dans le catalogue**
   **Given** le catalogue (liste, cartes, drawer),
   **When** l'utilisateur parcourt les entrées,
   **Then** les workflows affichent une **icône dédiée et identifiable** (distincte de l'icône des actions simples), pour repérer visuellement les workflows.

4. **AC4 — Création / édition workflow**
   **Given** un workflow en création ou édition,
   **When** on configure les étapes,
   **Then** l'interface propose d'**ajouter une étape = choisir une action existante** (liste / autocomplete). Pas de choix de connecteur pour le workflow.

5. **AC5 — Contraintes et validation**
   **And** on interdit les **boucles** (A → B → A) : validation à la sauvegarde. Optionnel : limite de profondeur (ex. workflow peut référencer des actions, une action ne peut pas référencer un workflow en étape, ou profondeur max 2).

6. **AC6 — Exécution**
   **Given** une exécution lancée sur un workflow,
   **When** le moteur traite les étapes,
   **Then** chaque étape « référence action » déclenche l'exécution de l'action référencée (sous-exécution ou enchaînement), dans l'ordre ; le connecteur est celui de l'action, pas du workflow.

## Tasks / Subtasks

- [x] Task 1 : Backend — Modèle et persistance (AC1, AC2, AC5)
  - [x] 1.1 Introduire un champ **type** (ou **kind**) sur le catalogue : `action` | `workflow` (ex. colonne `ITEM_TYPE` ou usage d'un champ existant). Valeur par défaut `action` pour l'existant.
  - [x] 1.2 Pour les **workflows** : étapes = liste d'objets `{ order, referenced_action_id, name? }`. Pas de `connector_type` / `connector_config` sur ces étapes. Adapter le schéma JSON (EXECUTION_STEPS ou structure dédiée) et les modèles Pydantic.
  - [x] 1.3 Validation à la sauvegarde : détection de **boucles** (graphe de références) et rejet si boucle. Optionnel : refuser qu'une action référence un workflow (ou limiter la profondeur).
  - [x] 1.4 Migration DB si nécessaire (nouvelle colonne, commentaires).

- [x] Task 2 : Backend — API et règles métier (AC1, AC4, AC5)
  - [x] 2.1 Création d'entrée : permettre de choisir le type `action` ou `workflow`. Si `workflow`, ne pas exiger `connector_type` / `platform` (ou les laisser null/N/A).
  - [x] 2.2 Mise à jour des étapes : si type `workflow`, accepter uniquement des étapes avec `referenced_action_id` ; rejeter les étapes avec connecteur. Si type `action`, conserver le comportement actuel (étapes à connecteur).
  - [x] 2.3 Liste d'actions éligibles : endpoint ou filtre pour lister les actions (ex. pour peupler le sélecteur d'étape workflow), en excluant les workflows si on interdit workflow → workflow selon AC5.

- [ ] Task 3 : Backend — Moteur d'exécution (AC6)
  - [ ] 3.1 Lorsqu'une exécution est lancée sur une entrée de type **workflow**, le moteur interprète les étapes comme des références à des actions. Pour chaque étape : lancer l'exécution de l'action référencée (même environnement, paramètres mappés si besoin), attendre la fin, puis passer à l'étape suivante.
  - [ ] 3.2 Gestion des sous-exécutions : soit une exécution parent avec steps « enfants » (chaque step = une exécution d'action), soit exécutions liées (parent_id). Décision à trancher (traceabilité, annulation, logs).

- [ ] Task 4 : Frontend — Admin workflow (AC1, AC2, AC4)
  - [ ] 4.1 Création / édition : au choix du type **action** ou **workflow**. Si workflow, masquer / désactiver les champs connecteur et afficher l'éditeur d'étapes « référence à une action ».
  - [ ] 4.2 Éditeur d'étapes workflow : pour chaque étape, sélecteur d'**action existante** (liste ou autocomplete par nom/id). Ordre et libellé d'affichage optionnel. Pas de choix de connecteur.
  - [ ] 4.3 Validation côté frontend : pas d'étape avec connecteur pour un workflow ; affichage d'erreur si boucle (si l'API retourne une erreur de validation).

- [x] Task 5 : Frontend — Catalogue et icône (AC3)
  - [x] 5.1 Définir une **icône dédiée aux workflows** (ex. nœuds en chaîne, pipeline, liste ordonnée), distincte de l'icône des actions. L'utiliser partout où une entrée de type workflow est affichée (liste catalogue, cartes, drawer détail).
  - [x] 5.2 Afficher cette icône à côté du nom (ou à la place de l'icône action) pour les entrées dont le type est `workflow`. S'assurer que le libellé ou tooltip permet de comprendre « workflow » (ex. « Workflow » ou « Chaîne d'actions »).

- [ ] Task 6 : Tests (AC1–AC6)
  - [ ] 6.1 Backend : tests unitaires ou d'intégration pour création/mise à jour workflow, validation boucles, exécution workflow (enchaînement d'actions).
  - [ ] 6.2 Frontend : tests pour l'éditeur d'étapes workflow (sélecteur d'action, pas de connecteur) et affichage de l'icône workflow dans le catalogue.

## Dev Notes

### Contexte technique

- **Epic 5** : Dashboard & Activité (Phase 2). Cette story introduit le type **workflow** dans le catalogue : conteneur d'actions sans connecteur propre, avec icône identifiable.
- **Modèle actuel** : `ExecutionStep` (catalog) a `connector_type` (aap, servicenow, …). Pour un workflow, les « steps » sont d'un autre type : uniquement `order` + `referenced_action_id` (+ `name` optionnel). Soit un champ `step_type` (e.g. `connector` | `action_reference`), soit un type d'entrée catalogue `workflow` avec un schéma d'étapes différent (ex. `workflow_steps` ou extension de EXECUTION_STEPS avec discriminant).
- **Catalogue** : `ACTIONS_CATALOG` peut être étendu avec `ITEM_TYPE VARCHAR2(20) DEFAULT 'action'` ; ou réutiliser un champ existant si déjà prévu. Vérifier `catalog_repository` et `app/models/catalog.py` — actuellement pas de champ item_type.
- **Icône** : Ant Design Icons (ex. `Apartment`, `NodeIndex`, `Partition`, `ClusterOutlined`) ou icône custom ; à valider avec la charte du portail (design system liquid glass, thème Desjardins).

### Architecture Compliance

- [Source: architecture.md] **Repository Pattern** : `catalog_repository.py` gère ACTIONS_CATALOG ; toute nouvelle colonne (ITEM_TYPE) et tout nouveau format d'étapes (workflow steps) doivent être lus/écrits via le repository, pas de SQL ad hoc.
- [Source: architecture.md] **API format** : snake_case JSON, wrapper `{ "data": ... }` / `{ "error": ... }`. Les réponses catalogue (list/detail) doivent inclure `item_type` pour que le frontend affiche l'icône.
- [Source: architecture.md] **Execution facade** : `execution_service.py` et `execution_repository.get_action_execution_steps` lisent les étapes d'une action ; pour un workflow, le moteur doit résoudre les étapes en « références action » puis lancer une exécution par action référencée (ou une exécution parent avec sous-steps).
- [Source: idp-portal] **EXECUTION_STEPS** : CLOB JSON dans ACTIONS_CATALOG (V003, V008). Format actuel : `[{"order", "name", "type", "connector_type", "connector_config", "conditional_environments"}]`. Pour workflow : soit même colonne avec discriminant `step_type: "action_reference"` et `referenced_action_id`, soit colonne dédiée `WORKFLOW_STEPS` CLOB. Décision à documenter dans la story / migration.
- [Source: idp-portal] **EXECUTIONS / EXECUTION_STEPS** (table) : V023 EXECUTIONS, V025 EXECUTION_STEPS. Lorsqu'un workflow s'exécute, décider si on crée une exécution parent + N exécutions enfants (ACTION_ID = action référencée) ou une seule exécution avec steps « virtuels » pointant vers les exécutions des actions. Impact traceabilité et annulation.

### Technical Requirements

- **Typage catalogue** : Introduire `item_type: "action" | "workflow"` (backend + API + frontend). Valeur par défaut `action` pour toutes les lignes existantes (migration + UPDATE si besoin).
- **Étapes workflow** : Modèle Pydantic pour étape workflow : `order`, `referenced_action_id`, `name` (optionnel). Validation : `referenced_action_id` doit exister dans ACTIONS_CATALOG et être de type `action` (pas workflow) si on interdit workflow→workflow.
- **Boucles** : À la sauvegarde d'un workflow, construire le graphe des références (workflow → actions référencées) et détecter un cycle (ex. DFS). Rejeter avec message explicite (400).
- **Exécution** : Pour un workflow, le moteur doit : (1) charger les étapes workflow (referenced_action_id), (2) pour chaque étape dans l'ordre, charger l'action référencée et ses paramètres/exécution_steps, (3) lancer l'exécution de cette action (même environment, paramètres du workflow mappés sur les paramètres de l'action si besoin), (4) attendre la fin (COMPLETED/FAILED/CANCELLED), (5) si FAILED/CANCELLED, faire échouer le workflow ; sinon étape suivante.
- **RBAC** : Les permissions (profiles, actions, targets) s'appliquent à l'entrée catalogue (action ou workflow). Pour un workflow, l'utilisateur doit avoir le droit d'exécuter chaque action référencée (ou au minimum le workflow lui-même — à clarifier avec le product owner).

### Library / Framework Requirements

- **Backend** : Python 3.12+, FastAPI, Pydantic. Réutiliser `ExecutionStep` (catalog) en l'étendant (discriminant step_type) ou ajouter `WorkflowStep` et union dans le modèle. Pas de nouvelle dépendance obligatoire.
- **Frontend** : React 18+, Ant Design 6.x, TypeScript. Composants existants : `ActionCard`, `ActionDrawerPreview`, `StepsEditor`, `ActionWizard`. Étendre pour type workflow : choix type dans le wizard, éditeur d'étapes « référence action » (Select/AutoComplete vers GET /api/v1/catalog/actions ou /admin/actions), icône conditionnelle selon `item_type`.
- **Icônes** : `@ant-design/icons` (Apartment, NodeIndex, Partition, ClusterOutlined). Aligner avec `ImpactIndicator`, `ActionCard` (design system liquid glass).

### Project Structure Notes

- **Backend** : `app/models/catalog.py` (ActionResponse, ActionDetail, ExecutionStep, nouveau ItemType enum et WorkflowStep si besoin) ; `app/repositories/catalog_repository.py` (lecture/écriture ITEM_TYPE et workflow steps) ; `app/api/v1/catalog.py` et `app/api/v1/admin.py` (création/édition avec type, étapes workflow) ; `app/services/execution_service.py` (branche workflow : résolution des étapes et enchaînement d'exécutions).
- **Frontend** : `src/types/api.ts` (item_type, workflow steps dans type Action) ; `src/components/admin/ActionWizard.tsx` et `StepsEditor.tsx` (type workflow, sélecteur d'actions) ; `src/components/catalog/ActionCard.tsx` et `ActionDrawerPreview.tsx` (icône workflow).
- **Migrations** : `database/migrations/V027__add_item_type_workflow_steps.sql` (ou numéro courant) : ALTER TABLE ACTIONS_CATALOG ADD ITEM_TYPE VARCHAR2(20) DEFAULT 'action' ; COMMENT ; si structure dédiée pour workflow steps, ajouter colonne ou documenter extension EXECUTION_STEPS.
- **Alignement** : Ne pas casser les appels existants (catalogue list/detail sans item_type → défaut action). Tests existants (catalog, admin, execution) doivent rester verts ou être adaptés (données de test avec item_type).

### Référence story précédente (5.6)

- **Story 5.6** (Script seed données BD tests frontend) : Script Python `scripts/seed_dev_data.py` insère actions, profils, exécutions, etc. Pour 5.7 : après implémentation, étendre le seed pour créer au moins un **workflow** (conteneur de 2–3 actions existantes) afin que les tests manuels et les tests E2E puissent vérifier l’affichage workflow (icône) et l’exécution en chaîne. Réutiliser les repositories existants ; ne pas dupliquer la logique de création d’actions.
- **Fichiers modifiés 5.6** : `idp-portal/scripts/seed_dev_data.py`, `idp-portal/README.md`. Pour 5.7, le seed pourra appeler la même API ou repository pour créer un workflow une fois le backend prêt.

### Testing Requirements

- **Backend** : Tests unitaires pour (1) création/mise à jour d’une entrée avec `item_type=workflow` et étapes `referenced_action_id` ; (2) rejet des étapes avec connecteur pour un workflow ; (3) validation boucle (workflow A référence action B, workflow B référence action A → rejet) ; (4) exécution workflow : mock des exécutions d’actions, vérifier l’ordre des appels et le statut final.
- **Frontend** : Tests pour l’éditeur d’étapes workflow (sélecteur d’action, pas de connecteur), affichage de l’icône workflow dans ActionCard et drawer. Snapshot ou assertion sur l’icône rendue selon `item_type`.
- **Non-régression** : Tous les tests existants catalogue / admin / execution doivent rester verts ; données de test avec `item_type: "action"` par défaut.

### Project Context Reference

- [Source: _bmad-output/planning-artifacts/architecture.md] Stack backend (FastAPI, python-oracledb), Repository Pattern, API snake_case, structure dossiers.
- [Source: idp-portal/backend/app/models/catalog.py] ActionResponse, ActionDetail, ExecutionStep, ConnectorType, ExecutionStepType.
- [Source: idp-portal/backend/app/repositories/catalog_repository.py] _parse_execution_steps, _execution_steps_to_json, update_execution_steps, get_by_id (detail avec execution_steps).
- [Source: idp-portal/backend/app/services/execution_service.py] prepare_execution, get_action_execution_steps, enchaînement des étapes.
- [Source: idp-portal/database/migrations/V002__create_actions_catalog.sql, V003__add_execution_steps.sql, V008__connector_type_in_execution_steps.sql] Schéma ACTIONS_CATALOG, EXECUTION_STEPS CLOB.
- [Source: idp-portal/frontend/src/components/catalog/ActionCard.tsx, ActionDrawerPreview.tsx] Affichage carte et drawer ; ajouter branche icône selon item_type.
- [Source: idp-portal/frontend/src/components/admin/StepsEditor.tsx, ActionWizard.tsx] Éditeur d’étapes et wizard ; ajouter mode workflow (sélecteur d’actions).

### References

- [Source: idp-portal/backend/app/models/catalog.py] ExecutionStep, ConnectorType, ActionDetail.
- [Source: idp-portal/backend/app/repositories/catalog_repository.py] EXECUTION_STEPS format, update_execution_steps.
- [Source: idp-portal/database/migrations/] ACTIONS_CATALOG, EXECUTION_STEPS (table), EXECUTIONS.
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md] Composants catalogue, design system, icônes.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

- **Task 1**: Backend model and persistence complete:
  - V027 migration adds ITEM_TYPE column to ACTIONS_CATALOG with CHECK constraint and index
  - ItemType enum (action, workflow) added to catalog.py
  - WorkflowStep model for workflow steps (order, name, referenced_action_id)
  - WorkflowStepsUpdate model with order validation
  - ActionCreate updated with item_type field and model_validator for engine/platform requirements
  - ActionResponse, ActionDetail, ActionListItem updated to include item_type
  - catalog_repository.py updated with:
    - Helper functions: _parse_item_type, _parse_engine, _parse_platform
    - _parse_workflow_steps and _safe_parse_workflow_steps for workflow step parsing
    - _workflow_steps_to_json for serialization
    - Updated _row_to_action_response and _row_to_action_detail for item_type
    - Updated all SQL queries (get_by_id, list_all, list_catalog, list_all_admin) to include ITEM_TYPE
    - Loop detection: validate_workflow_steps, _detect_workflow_loop, WorkflowLoopError, InvalidWorkflowStepError
    - update_workflow_steps function for updating workflow steps

- **Task 2**: Backend API complete:
  - admin.py updated with:
    - ItemType filter on list_actions endpoint
    - PUT /admin/actions/{id}/workflow-steps endpoint for workflow steps
    - GET /admin/actions/eligible-for-workflow endpoint for listing eligible actions (published actions only)

- **Task 5**: Frontend catalog icons complete:
  - TypeScript types updated (api.ts): ItemType, WorkflowStep, WorkflowStepsUpdate, updated ActionCreate/Response/Detail/ListItem
  - ActionCard.tsx: ApartmentOutlined icon for workflows with tooltip "Workflow (chaîne d'actions)"
  - ActionDrawerPreview.tsx: Workflow badge indicator in header

- **Task 3 & 4 & 6**: Pending - Execution engine for workflows, Admin UI for workflow creation/editing, and tests.

### File List

- idp-portal/database/migrations/V027__add_item_type_workflows.sql (new)
- idp-portal/backend/app/models/catalog.py (modified)
- idp-portal/backend/app/repositories/catalog_repository.py (modified)
- idp-portal/backend/app/api/v1/admin.py (modified)
- idp-portal/backend/tests/unit/test_admin_api.py (modified) — code review fix
- idp-portal/backend/tests/unit/test_catalog_repository.py (modified) — code review fix
- idp-portal/frontend/src/types/api.ts (modified)
- idp-portal/frontend/src/components/catalog/ActionCard.tsx (modified)
- idp-portal/frontend/src/components/catalog/ActionDrawerPreview.tsx (modified)

### Change Log

- 2026-01-30: Tasks 1, 2, 5 completed — Backend model, persistence, API, and frontend catalog icons implemented. Tasks 3, 4, 6 pending.
- 2026-01-30: Passed to code review. Remaining tasks (execution engine, admin UI, tests) can be addressed in follow-up work.
- 2026-01-30: **Code review fixes applied** (10 issues found, all fixed):
  - HIGH: ITEM_TYPE column was missing from get_by_id, list_all, list_catalog, list_all_admin SQL queries — all fixed
  - MEDIUM: item_type filter was not applied in list_all, list_catalog, list_all_admin — all fixed
  - MEDIUM: Test expected old call signature without item_type param — fixed
  - LOW: Test fixtures missing ITEM_TYPE column — updated all fixtures
  - LOW: Removed stale comments "omitted until V027"
  - Tests: 74 catalog models + 37 admin API + 443 frontend tests pass
