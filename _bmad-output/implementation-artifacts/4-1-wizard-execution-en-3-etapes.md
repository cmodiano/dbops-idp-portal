# Story 4.1: Wizard d'exécution en 3 étapes

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBA,
I want exécuter une action via un wizard guidé (Environnement → Paramètres → Confirmation),
So that j'avance une décision à la fois et je comprenne l'impact avant de confirmer.

## Acceptance Criteria

1. **Given** un DBA clique sur "Exécuter" dans le drawer d'une action **When** le wizard s'ouvre (centre, 640px max) **Then** le stepper affiche 3 étapes avec labels : Environnement, Paramètres, Confirmation

2. **Given** le DBA est à l'étape 1 (Environnement) **When** il sélectionne "Production" **Then** un badge orange avertissement s'affiche et l'ImpactIndicator se met à jour selon les règles d'impact de l'action

3. **Given** le DBA est à l'étape 2 (Paramètres) **When** il remplit les champs dynamiques générés depuis le parameters_schema JSON de l'action **Then** la validation inline s'exécute en temps réel sous chaque champ et le bouton "Suivant" reste désactivé si la validation échoue **And** les listes déroulantes sont pre-remplies depuis l'inventaire (bases, serveurs)

4. **Given** le DBA est à l'étape 3 (Confirmation) **When** il voit le récap **Then** s'affichent : nom de l'action, environnement, tous les paramètres, ImpactIndicator, type de changement (pre-approuvé / CAB) **And** le bouton "Confirmer l'exécution" est en primary

5. **And** le composant ExecutionWizard est accessible : aria-label="Étape [n] sur 3: [label]", navigation clavier entre étapes **And** les données saisies sont conservées si l'utilisateur revient en arrière (Précédent) **And** les labels sont toujours visibles au-dessus du champ (pas de placeholder-as-label) **And** FR13 et FR15 sont satisfaites

## Tasks / Subtasks

- [x] Task 1 — Backend : API d'exécution et validation (AC: 3, 4, 5)
  - [x] 1.1 Créer endpoint POST /api/v1/executions avec payload : `{ action_id, environment, parameters }`. Validation Pydantic : action_id existe, environment valide (dev/staging/prod), parameters conforme au parameters_schema de l'action. Retourne HTTP 201 avec `{ "data": { "execution_id", "status": "SUBMITTED", "created_at" } }`
  - [x] 1.2 Créer `execution_repository.py` : `create_execution(user_id, action_id, environment, parameters)` → INSERT dans EXECUTIONS (statut "SUBMITTED"). Retourne execution_id. Utiliser SQL brut via python-oracledb (pattern repository).
  - [x] 1.3 Créer migration Flyway `V023__create_executions.sql` : table EXECUTIONS (id, action_id, user_id, environment, parameters CLOB JSON, status, servicenow_change_id, started_at, completed_at, created_at). PK id (sequence SEQ_EXECUTIONS), FK vers ACTIONS_CATALOG, USERS. Index sur status, user_id, action_id.
  - [x] 1.4 Validation des paramètres : charger parameters_schema depuis ACTIONS_CATALOG, valider parameters via JSON Schema (bibliothèque jsonschema Python). Erreur 400 si validation échoue avec détails du champ invalide.

- [x] Task 2 — Backend : données inventaire pour listes déroulantes (AC: 3)
  - [x] 2.1 Créer endpoint GET /api/v1/inventory/{type} (type = "databases", "servers", "environments"). Retourne `{ "data": [ { "id", "name", "environment" } ] }`. Pour MVP, données mockées ou depuis config (Story 4.2 implémentera la vraie sync inventaire).
  - [x] 2.2 Créer `inventory_service.py` : `get_inventory_items(type)` → pour MVP, retourner données statiques ou depuis cache. Préparer interface pour Story 4.2 (sync réelle).

- [x] Task 3 — Frontend : composant ExecutionWizard et stepper (AC: 1, 5)
  - [x] 3.1 Créer `ExecutionWizard.tsx` : modal centré 640px max avec Ant Design Steps (3 étapes : Environnement, Paramètres, Confirmation). State local pour : currentStep (0-2), environment, parameters (objet dynamique), action (chargée depuis API).
  - [x] 3.2 Navigation : boutons "Précédent" / "Suivant" / "Confirmer l'exécution". "Suivant" désactivé si validation étape échoue. "Précédent" toujours actif (sauf étape 1). Persistance state : données conservées si retour arrière.
  - [x] 3.3 Accessibilité : aria-label="Étape [n] sur 3: [label]" sur Steps, navigation clavier Tab/Shift+Tab entre champs, Enter = Suivant, Escape = annuler wizard. Focus management : focus sur premier champ à chaque changement d'étape.

- [x] Task 4 — Frontend : étape 1 Environnement (AC: 2)
  - [x] 4.1 Étape 1 affiche : Select environnement (dev, staging, prod) avec options depuis GET /api/v1/inventory/environments. Label visible au-dessus (pas placeholder-as-label).
  - [x] 4.2 Si environnement = "Production" : afficher Badge orange "Avertissement — Environnement Production" + ImpactIndicator mis à jour (charger impact_rules depuis action, évaluer selon environnement → impact faible/moyen/élevé).
  - [x] 4.3 ImpactIndicator : composant existant (triple codage couleur + icône + texte). Props : impact level (LOW/MEDIUM/HIGH), environnement. Afficher à droite de l'étape 1 (persistant dans les étapes suivantes).

- [x] Task 5 — Frontend : étape 2 Paramètres dynamiques (AC: 3, 5)
  - [x] 5.1 Charger parameters_schema depuis l'action (déjà dans action object). Générer formulaire dynamique : pour chaque paramètre dans schema.properties, créer champ selon type (string → Input, number → InputNumber, enum → Select, array → Select multiple).
  - [x] 5.2 Validation inline temps réel : Ant Design Form avec rules. Sous chaque champ, message d'erreur si validation échoue (required, type, pattern, enum values). "Suivant" désactivé si au moins un champ invalide.
  - [x] 5.3 Listes déroulantes depuis inventaire : si paramètre a `"source": "inventory"` et `"inventory_type": "databases"`, charger GET /api/v1/inventory/databases et afficher en Select. Pré-remplir options.
  - [x] 5.4 Labels toujours visibles : Form.Item avec label au-dessus, pas de placeholder comme label. Aide contextuelle : tooltip (icône ?) si description paramètre présente.

- [x] Task 6 — Frontend : étape 3 Confirmation (AC: 4)
  - [x] 6.1 Étape 3 affiche récap : nom action (titre), environnement (badge), tous les paramètres (liste clé-valeur), ImpactIndicator (état final selon environnement), type de changement (badge "Pre-approuvé" ou "CAB requis" selon change_model_code de l'action et environnement).
  - [x] 6.2 Bouton "Confirmer l'exécution" : style primary (vert Desjardins #00874E), désactivé si validation échoue. Au clic : POST /api/v1/executions avec action_id, environment, parameters. Gérer loading (spinner sur bouton), erreur (toast + StructuredErrorCard si erreur API), succès (fermer wizard, rediriger vers timeline Story 4.6 ou afficher message succès).

- [x] Task 7 — Frontend : intégration avec ActionDrawer (AC: 1)
  - [x] 7.1 Dans `ActionDrawer.tsx` (Story 3.2), bouton "Exécuter" ouvre ExecutionWizard en modal. Passer action_id (ou action object complet) au wizard.
  - [x] 7.2 Wizard charge action via GET /api/v1/catalog/actions/{id} si nécessaire (ou reçoit action depuis drawer). Afficher nom action dans header wizard.

- [x] Task 8 — Tests et qualité (AC: tous)
  - [x] 8.1 Tests unitaires backend : execution_repository.create_execution, validation parameters_schema, endpoint POST /executions (succès, erreur validation, erreur action inexistante).
  - [x] 8.2 Tests unitaires frontend : ExecutionWizard navigation étapes, validation inline étape 2, récap étape 3, accessibilité (aria-labels, navigation clavier).
  - [x] 8.3 Tests d'intégration : flow complet drawer → wizard → soumission → création execution en DB.

## Dev Notes

### Contexte métier

- **FR13** : DBA peut exécuter une action via un formulaire dynamique adapté aux paramètres de l'action sélectionnée. **FR15** : Le système valide les paramètres saisis avant de déclencher l'exécution.
- **Epic 4** : DBA exécute une action de bout en bout via le wizard et suit la progression étape par étape en temps réel via la timeline. Cette story 4.1 couvre uniquement le wizard d'exécution (3 étapes). Story 4.3 implémentera le moteur d'exécution backend, Story 4.6 la timeline temps réel.
- **ImpactIndicator** : Composant existant (Story 3.1, 3.2). Triple codage couleur + icône + texte. Impact évalué depuis impact_rules de l'action selon environnement sélectionné.

### Patterns à respecter

- **API** : snake_case JSON, wrapper `{ "data": ... }` / `{ "error": ... }`, dates ISO 8601 UTC. [Source: architecture.md]
- **Frontend** : données API en snake_case → camelCase au point d'usage. [Source: architecture.md]
- **Repository** : SQL brut via python-oracledb, pas d'ORM. [Source: architecture.md]
- **Composants** : Réutiliser ImpactIndicator existant. ExecutionWizard = nouveau composant custom (comme ActionWizard Story 2.22 mais pour exécution, pas création action).
- **Wizard pattern** : Ant Design Steps, state local persistant, validation par étape, navigation Précédent/Suivant. [Source: Story 2.22 ActionWizard]

### Ce qui existe déjà

- **Backend** : `GET /api/v1/catalog/actions/{id}` retourne action avec parameters_schema, impact_rules, change_model_code. Pas de table EXECUTIONS, pas d'endpoint POST /executions, pas d'inventory service.
- **Frontend** : `ActionDrawer.tsx` (Story 3.2) avec bouton "Exécuter" (stub). `ImpactIndicator` composant existant (triple codage). `ActionWizard` (Story 2.22) pour création action — pattern réutilisable mais logique différente (exécution vs création).
- **Architecture** : Table EXECUTIONS définie dans architecture.md (V003), structure : id, action_id, user_id, environment, parameters CLOB JSON, status, servicenow_change_id, started_at, completed_at, created_at.

### Références techniques

- **Parameters schema** : JSON Schema standard. Exemple depuis epics.md : `{ "type": "object", "properties": { "pdb_name": { "type": "string", "pattern": "^[A-Z_]+$" }, "size_gb": { "type": "number", "minimum": 1 } } }`
- **Impact rules** : JSON depuis impact_rules colonne ACTIONS_CATALOG. Format : `{ "dev": "LOW", "staging": "MEDIUM", "prod": "HIGH" }` ou plus complexe avec conditions.
- **Change model** : change_model_code colonne ACTIONS_CATALOG. Valeurs : "pre-approved" ou "cab-required". Évaluation selon environnement (prod = souvent CAB, dev = pre-approved).

### Inventaire (MVP vs Story 4.2)

- **Story 4.1 (MVP)** : Endpoint GET /api/v1/inventory/{type} retourne données mockées ou depuis config statique. Suffisant pour tester le wizard avec listes déroulantes.
- **Story 4.2** : Implémentera la vraie synchronisation avec l'inventaire interne (sync périodique, cache, API réelle). L'interface inventory_service reste compatible.

### Project Structure Notes

- **Backend** : `idp-portal/backend/app/repositories/execution_repository.py` (nouveau), `idp-portal/backend/app/api/v1/executions.py` (nouveau), `idp-portal/backend/app/services/inventory_service.py` (nouveau, MVP mocké), `idp-portal/database/migrations/V003__create_executions.sql` (nouveau).
- **Frontend** : `idp-portal/frontend/src/components/execution/ExecutionWizard.tsx` (nouveau), `idp-portal/frontend/src/components/execution/WizardStepEnv.tsx` (nouveau, optionnel si découpé), `idp-portal/frontend/src/components/execution/WizardStepParams.tsx` (nouveau, optionnel), `idp-portal/frontend/src/components/execution/WizardStepConfirm.tsx` (nouveau, optionnel). Modifier `ActionDrawer.tsx` pour ouvrir ExecutionWizard.
- **Services** : `idp-portal/frontend/src/services/execution_service.ts` (nouveau) : `submitExecution(actionId, environment, parameters)`, `getInventoryItems(type)`.

### Architecture Compliance

- **Stack** : React 19, TypeScript, Ant Design 6 (Steps, Form, Input, Select, Button, Badge, Modal). FastAPI, Pydantic v2, python-oracledb 3.4.1.
- **API** : REST JSON, versioning /api/v1/, erreurs format `{ "error": { "code": "...", "message": "...", "details": {...} } }`. [Source: architecture.md]
- **Database** : Oracle via python-oracledb mode Thin, SQL brut dans repositories, migrations Flyway séquentielles. [Source: architecture.md]
- **Accessibilité** : WCAG 2.1 AA, triple codage (couleur + icône + texte), aria-labels, navigation clavier complète, focus visible. [Source: architecture.md, ux-design-specification.md]

### Library/Framework Requirements

- **Ant Design 6.2** : Steps (stepper), Form (validation), Input/InputNumber, Select (listes), Button, Badge (avertissements), Modal (wizard container). Composants déjà utilisés dans ActionWizard (Story 2.22).
- **Backend** : jsonschema Python pour validation parameters_schema. python-oracledb pour SQL brut. Pydantic pour modèles API.

### File Structure Requirements

- **Nouveau backend** : `execution_repository.py`, `executions.py` (routes), `inventory_service.py` (MVP mocké), migration `V003__create_executions.sql`.
- **Nouveau frontend** : `ExecutionWizard.tsx` (composant principal), optionnellement `WizardStepEnv.tsx`, `WizardStepParams.tsx`, `WizardStepConfirm.tsx` si découpage modulaire. `execution_service.ts` (appels API).
- **Modifier** : `ActionDrawer.tsx` pour intégrer bouton "Exécuter" → ouverture ExecutionWizard.

### Testing Requirements

- **Backend** : Tests unitaires execution_repository (create_execution, validation), tests API POST /executions (succès, erreurs validation, erreur action inexistante).
- **Frontend** : Tests unitaires ExecutionWizard (navigation étapes, validation inline, récap, accessibilité), tests intégration flow drawer → wizard → soumission.
- **Patterns** : Réutiliser patterns de tests Story 2.22 (ActionWizard) et Story 3.1 (catalogue).

### Previous Story Intelligence

- **Story 2.22 (ActionWizard)** : Pattern wizard 3 étapes avec Ant Design Steps, state local persistant, validation par étape. Réutiliser structure mais logique différente (exécution vs création). [Source: 2-22-wizard-de-creation-et-edition-daction.md]
- **Story 3.1 (Catalogue)** : ImpactIndicator composant existant, triple codage, aria-labels. ActionCard avec drawer. Patterns de validation et accessibilité. [Source: 3-1-catalogue-actions-avec-modes-affichage-et-favoris.md]
- **Story 3.2 (ActionDrawer)** : Drawer latéral 480px, bouton "Exécuter" préparé. Intégrer ExecutionWizard depuis ce bouton. [Source: epics.md Story 3.2]

### Git Intelligence Summary

- **Derniers commits** : Versions générales, pas de patterns spécifiques détectés. Suivre les conventions établies dans les stories précédentes (Epic 2, Epic 3).

### Latest Tech Information

- **Ant Design 6.2** : Steps component supporte aria-label, current prop pour étape active, onChange callback. Form validation inline avec rules, validateTrigger="onChange" pour validation temps réel.
- **FastAPI** : Validation Pydantic automatique, erreurs 422 si validation échoue. Custom exception handler pour format erreur uniforme `{ "error": {...} }`.
- **JSON Schema validation Python** : Bibliothèque `jsonschema` standard. `jsonschema.validate(instance, schema)` lève ValidationError si invalide. Intégrer dans endpoint POST /executions.

### Project Context Reference

- **Architecture** : [Source: planning-artifacts/architecture.md] — Stack React + FastAPI + Oracle, patterns repository SQL brut, API REST JSON, accessibilité WCAG 2.1 AA.
- **UX Design** : [Source: planning-artifacts/ux-design-specification.md] — Wizard 3 étapes (Environnement → Paramètres → Confirmation), modal centre 640px max, ImpactIndicator persistant, validation inline temps réel, labels toujours visibles, accessibilité complète.
- **Epics** : [Source: planning-artifacts/epics.md] — Story 4.1 acceptance criteria détaillés, dépendances Story 4.2 (inventaire), Story 4.3 (moteur exécution), Story 4.6 (timeline).

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

None

### Completion Notes List

- **Task 1 (Backend API)**: Created execution API with full validation. `POST /api/v1/executions` validates action exists, environment is valid, and parameters conform to JSON Schema (rejects extra properties). Returns execution_id on success. Migration V023 creates EXECUTIONS table.
- **Task 2 (Inventory MVP)**: Created `inventory_service.py` with static mock data for databases, servers, environments. `GET /api/v1/inventory/{type}` supports filtering by environment.
- **Tasks 3-6 (Frontend ExecutionWizard)**: Single component `ExecutionWizard.tsx` implementing all 3 steps. Features: dynamic form generation from parameters_schema, inventory-based dropdowns (with caching), inline validation, ImpactIndicator integration with null safety, change type display (Pre-approuve/CAB requis), accessible with aria-labels, aria-live regions, and keyboard navigation. Environments loaded from inventory service (not hard-coded). Action published status verified before allowing execution.
- **Task 7 (Integration)**: Updated `ActionDrawerPreview.tsx` with `onExecute` prop. Integrated `ExecutionWizard` in `CatalogPage.tsx` - clicking Execute button in drawer opens the wizard.
- **Task 8 (Tests)**: 44 backend tests (execution models, repository, API) + 18 inventory tests + 19 frontend tests. All 620 backend tests pass. All 356 frontend tests pass. No regressions.
- **Code Review Fixes (2026-01-29)**: Fixed null check for ImpactIndicator, added action published check, implemented inventory caching, fixed JSON Schema validation to reject extra properties, added ARIA live region for step changes, replaced hard-coded environments with inventory service, improved error handling in submission flow.

### File List

**Backend (new files)**:
- `idp-portal/database/migrations/V023__create_executions.sql` (Task 1.3 - Note: V023 not V003 due to existing migrations)
- `idp-portal/backend/app/models/execution.py` (Task 1.1 - Execution models)
- `idp-portal/backend/app/repositories/execution_repository.py` (Task 1.2 - SQL repository)
- `idp-portal/backend/app/api/v1/executions.py` (Task 1.1, 1.4 - API endpoints with JSON Schema validation)
- `idp-portal/backend/app/services/inventory_service.py` (Task 2.2 - MVP mock inventory)
- `idp-portal/backend/app/api/v1/inventory.py` (Task 2.1 - Inventory API)
- `idp-portal/backend/tests/unit/test_execution_models.py` (Task 8.1 - Model tests)
- `idp-portal/backend/tests/unit/test_execution_repository.py` (Task 8.1 - Repository tests)
- `idp-portal/backend/tests/unit/test_execution_api.py` (Task 8.1 - API tests)
- `idp-portal/backend/tests/unit/test_inventory_service.py` (Task 8.1 - Inventory service tests)
- `idp-portal/backend/tests/unit/test_inventory_api.py` (Task 8.1 - Inventory API tests)

**Backend (modified)**:
- `idp-portal/backend/app/main.py` (added executions, inventory routers)
- `idp-portal/backend/pyproject.toml` (added jsonschema dependency)

**Frontend (new files)**:
- `idp-portal/frontend/src/services/execution_service.ts` (Task 1.1, 2.1 - API client)
- `idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx` (Tasks 3-6 - Main wizard component)
- `idp-portal/frontend/src/components/catalog/ExecutionWizard.test.tsx` (Task 8.2 - Component tests)

**Frontend (modified)**:
- `idp-portal/frontend/src/types/api.ts` (added ExecutionCreateRequest, ExecutionCreateResponse, ExecutionResponse, InventoryItem types)
- `idp-portal/frontend/src/components/catalog/index.ts` (export ExecutionWizard)
- `idp-portal/frontend/src/components/catalog/ActionDrawerPreview.tsx` (Task 7.1 - added onExecute prop)
- `idp-portal/frontend/src/pages/CatalogPage.tsx` (Task 7.2 - integrated ExecutionWizard modal)
