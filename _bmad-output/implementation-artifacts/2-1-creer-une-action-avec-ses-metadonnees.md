# Story 2.1: Creer une action avec ses metadonnees

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBOPS,
I want creer une nouvelle action dans le Software Catalog avec ses metadonnees completes,
So that je definisse les actions disponibles pour les DBA et les clients business.

## Acceptance Criteria

1. **AC1 — Formulaire admin** : Given un DBOPS authentifie accede a l'onglet Admin, When il clique sur "Nouvelle action", Then un formulaire admin s'affiche avec les sections : nom, description, categorie (Provisioning/Patching/Administration/Monitoring), moteur (Oracle/SQL Server/DB2), plateforme d'execution (AAP/GitHub Actions/Azure DevOps/Terraform).

2. **AC2 — Schema parametres et impact** : Given le DBOPS remplit les champs de base, When il definit le schema de parametres (JSON schema) et les regles d'impact par environnement, Then le systeme valide le schema JSON et enregistre l'action en statut "brouillon".

3. **AC3 — Migration V002** : Given le schema de base de donnees, When la migration V002 est executee, Then la table ACTIONS_CATALOG est creee avec les colonnes: id, name, description, category, engine, platform, parameters_schema (CLOB), impact_rules (CLOB), rbac_policies (CLOB), status, created_by, created_at, updated_at.

4. **AC4 — Repository SQL** : Given une action est creee, When le catalog_repository.py est appele, Then le SQL brut (INSERT, SELECT) encapsule les operations et les colonnes CLOB stockent du JSON interrogeable via JSON_VALUE Oracle.

5. **AC5 — API POST** : Given un DBOPS soumet le formulaire, When l'API POST /api/v1/admin/actions est appelee, Then la reponse est HTTP 201 avec l'action creee dans { "data": {...} }.

6. **AC6 — Validation inline** : Given le formulaire est affiche, When le DBOPS saisit des donnees invalides, Then la validation inline est presente sur le formulaire (pas de validation uniquement a la soumission).

7. **AC7 — FR1 satisfaite** : L'ensemble des ACs ci-dessus satisfait FR1.

## Tasks / Subtasks

- [x] Task 1: Migration Oracle V002 — Table ACTIONS_CATALOG (AC: 3, 4)
  - [x] 1.1: Creer le script `database/migrations/V002_create_actions_catalog.sql` avec la table ACTIONS_CATALOG. Colonnes: ID (NUMBER PK, sequence SEQ_ACTIONS_CATALOG), NAME (VARCHAR2 255 NOT NULL UNIQUE), DESCRIPTION (VARCHAR2 4000), CATEGORY (VARCHAR2 50 NOT NULL, CHECK IN ('Provisioning', 'Patching', 'Administration', 'Monitoring')), ENGINE (VARCHAR2 50 NOT NULL, CHECK IN ('Oracle', 'SQL Server', 'DB2')), PLATFORM (VARCHAR2 50 NOT NULL, CHECK IN ('AAP', 'GitHub Actions', 'Azure DevOps', 'Terraform')), PARAMETERS_SCHEMA (CLOB), IMPACT_RULES (CLOB), RBAC_POLICIES (CLOB), STATUS (VARCHAR2 20 NOT NULL DEFAULT 'draft', CHECK IN ('draft', 'published', 'disabled')), CREATED_BY (NUMBER REFERENCES USERS(ID)), CREATED_AT (TIMESTAMP DEFAULT SYSTIMESTAMP), UPDATED_AT (TIMESTAMP)
  - [x] 1.2: Creer la sequence SEQ_ACTIONS_CATALOG avec START 1 INCREMENT 1
  - [x] 1.3: Creer les index : IDX_ACTIONS_CATALOG_STATUS sur STATUS, IDX_ACTIONS_CATALOG_CATEGORY sur CATEGORY, IDX_ACTIONS_CATALOG_ENGINE sur ENGINE
  - [x] 1.4: Ajouter les commentaires Oracle sur les colonnes pour documenter le schema JSON attendu dans PARAMETERS_SCHEMA, IMPACT_RULES, RBAC_POLICIES
  - [x] 1.5: Mettre a jour la table SCHEMA_VERSION avec V002

- [x] Task 2: Backend — Modeles Pydantic pour le catalogue (AC: 2, 5)
  - [x] 2.1: Creer `backend/app/models/catalog.py` avec les modeles Pydantic: ActionCategory (Enum), ActionEngine (Enum), ActionPlatform (Enum), ActionStatus (Enum), ActionCreate (nom, description, category, engine, platform, parameters_schema: dict | None, impact_rules: dict | None), ActionResponse (id, + tous les champs ActionCreate + status, created_by, created_at, updated_at), ActionDetail (ActionResponse + rbac_policies)
  - [x] 2.2: Ajouter les validateurs Pydantic pour: nom (1-255 chars, strip whitespace), description (max 4000 chars), parameters_schema (valide JSON Schema si present), impact_rules (structure attendue: {environment: {level: "low"|"medium"|"high"|"critical"}})
  - [x] 2.3: Ecrire les tests unitaires pour les validateurs Pydantic (nom vide, nom trop long, description trop longue, schema JSON invalide, impact_rules invalides)

- [x] Task 3: Backend — Repository SQL catalog_repository.py (AC: 4)
  - [x] 3.1: Creer `backend/app/repositories/catalog_repository.py` avec la classe CatalogRepository. Methodes: create(action: ActionCreate, user_id: int) -> ActionResponse, get_by_id(action_id: int) -> ActionDetail | None, list_all(status: ActionStatus | None = None) -> list[ActionResponse]
  - [x] 3.2: Implementer create() avec SQL INSERT utilisant la sequence, CLOB pour les colonnes JSON, RETURNING clause pour l'ID
  - [x] 3.3: Implementer get_by_id() avec SQL SELECT incluant JSON_VALUE pour extraire des champs JSON si necessaire
  - [x] 3.4: Implementer list_all() avec filtre optionnel sur status, ORDER BY created_at DESC
  - [x] 3.5: Utiliser structlog pour logger les requetes SQL en mode debug (query, params, duration_ms)
  - [x] 3.6: Ecrire les tests unitaires pour le repository: create action, get action by id (existant et non-existant), list all (avec et sans filtre status). Utiliser des mocks pour le pool Oracle

- [x] Task 4: Backend — API admin actions (AC: 5)
  - [x] 4.1: Creer `backend/app/api/v1/admin.py` avec le router APIRouter(prefix="/admin", tags=["admin"])
  - [x] 4.2: Implementer POST /api/v1/admin/actions: accepte ActionCreate, verifie profil DBOPS via get_current_user(), appelle catalog_repository.create(), retourne 201 + { "data": ActionResponse }
  - [x] 4.3: Implementer GET /api/v1/admin/actions: liste toutes les actions (DBOPS uniquement), retourne { "data": list[ActionResponse] }
  - [x] 4.4: Implementer GET /api/v1/admin/actions/{id}: retourne { "data": ActionDetail } ou 404
  - [x] 4.5: Ajouter le middleware RBAC qui verifie que l'utilisateur a le profil DBOPS (403 sinon)
  - [x] 4.6: Enregistrer le router dans main.py
  - [x] 4.7: Ecrire les tests unitaires pour les endpoints: POST succes (201), POST validation error (422), POST non-DBOPS (403), GET list, GET by id (200 et 404)

- [x] Task 5: Frontend — Page Admin et formulaire creation action (AC: 1, 6)
  - [x] 5.1: Creer `frontend/src/pages/AdminPage.tsx` avec le layout: en-tete "Administration du Catalogue", bouton "Nouvelle action", liste des actions existantes (table skeleton pour l'instant)
  - [x] 5.2: Creer `frontend/src/components/admin/ActionForm.tsx` avec le formulaire Ant Design Form. Champs: nom (Input, required), description (TextArea, max 4000), categorie (Select avec options enum), moteur (Select avec options enum), plateforme (Select avec options enum), schema parametres (TextArea JSON, optionnel), regles d'impact (TextArea JSON, optionnel)
  - [x] 5.3: Ajouter la validation inline Ant Design: rules sur chaque champ, validation JSON pour schema et impact_rules avec Form.Item validateStatus et help
  - [x] 5.4: Le formulaire s'ouvre en modal (Modal Ant Design, width 640px) au clic sur "Nouvelle action"
  - [x] 5.5: Au submit, appeler POST /api/v1/admin/actions via admin_service.ts, afficher le toast succes (notification Ant Design), fermer la modal
  - [x] 5.6: Gerer l'erreur API: afficher le message d'erreur inline (Alert Ant Design dans la modal)
  - [x] 5.7: Ajouter l'accessibilite: aria-label sur les champs, focus sur le premier champ a l'ouverture, Escape ferme la modal

- [x] Task 6: Frontend — Service API admin (AC: 5)
  - [x] 6.1: Creer `frontend/src/services/admin_service.ts` avec les fonctions: createAction(action: ActionCreate): Promise<ActionResponse>, listActions(): Promise<ActionResponse[]>, getAction(id: number): Promise<ActionDetail>
  - [x] 6.2: Utiliser apiFetch existant avec les bons types generiques
  - [x] 6.3: Ajouter les types dans `frontend/src/types/api.ts`: ActionCategory, ActionEngine, ActionPlatform, ActionStatus, ActionCreate, ActionResponse, ActionDetail

- [x] Task 7: Frontend — Route et navigation Admin (AC: 1)
  - [x] 7.1: Ajouter la route /admin dans App.tsx avec React.lazy() pour AdminPage
  - [x] 7.2: Conditionner l'affichage de l'onglet Admin dans TopNav.tsx selon le profil DBOPS (user.profile === 'DBOPS')
  - [x] 7.3: Proteger la route /admin: si non-DBOPS, rediriger vers /catalog avec message

- [x] Task 8: Validation end-to-end et tests (AC: tous)
  - [x] 8.1: Verifier AC1 — formulaire admin avec tous les champs requis
  - [x] 8.2: Verifier AC2 — validation JSON schema et enregistrement en brouillon
  - [x] 8.3: Verifier AC3 — table ACTIONS_CATALOG creee correctement (migration)
  - [x] 8.4: Verifier AC4 — repository SQL fonctionne avec CLOB JSON
  - [x] 8.5: Verifier AC5 — API POST retourne 201 avec data wrapper
  - [x] 8.6: Verifier AC6 — validation inline sur le formulaire frontend
  - [x] 8.7: Regression check — tous les tests existants passent (199 backend + frontend attendus minimum)

## Dev Notes

### Architecture Requirements

- **Repository Pattern SQL brut** : Chaque domaine a son repository avec SQL via python-oracledb. Pas d'ORM. [Source: architecture.md — Data Architecture]
- **CLOB JSON Oracle** : Les colonnes PARAMETERS_SCHEMA, IMPACT_RULES, RBAC_POLICIES sont des CLOB contenant du JSON. Utilisable avec JSON_VALUE / JSON_TABLE (Oracle 19+). [Source: architecture.md — Data Architecture]
- **API format** : Toute reponse est wrappee dans { "data": ... } ou { "error": ... }. snake_case partout. [Source: architecture.md — API Response Format]
- **Enums** : ActionCategory, ActionEngine, ActionPlatform, ActionStatus sont des enums cote Python (Pydantic) et cote TypeScript. [Source: architecture.md — Naming Patterns]
- **RBAC admin** : Seul le profil DBOPS peut acceder aux routes /api/v1/admin/*. Middleware FastAPI verifie le profil. [Source: architecture.md — Authentication & Security]
- **Frontend lazy loading** : Chaque page est chargee via React.lazy(). La page Admin est conditionnelle au profil DBOPS. [Source: architecture.md — Frontend Architecture]
- **Validation inline** : Validation en temps reel sur le formulaire, pas uniquement a la soumission. Ant Design Form rules. [Source: epics.md — Story 2.1 AC6]

### What Already Exists (DO NOT REIMPLEMENT)

Les elements suivants sont deja implementes dans les stories precedentes. Le dev agent DOIT les enrichir, PAS les remplacer.

| Element | Fichier | Statut |
|---|---|---|
| Pool Oracle | `backend/app/core/database.py` | Existe |
| IdpError hierarchy | `backend/app/core/exceptions.py` | Existe |
| Auth get_current_user() | `backend/app/api/deps.py` | Existe |
| UserProfile model | `backend/app/models/auth.py` | Existe |
| apiFetch wrapper | `frontend/src/services/api_client.ts` | Existe |
| TopNav component | `frontend/src/components/layout/TopNav.tsx` | Existe |
| App.tsx routing | `frontend/src/App.tsx` | Existe |
| Theme Desjardins | `frontend/src/theme/desjardins.ts` | Existe |

### What Needs to Be CREATED

| Element | Fichier | Description |
|---|---|---|
| Migration V002 | `database/migrations/V002_create_actions_catalog.sql` | Table ACTIONS_CATALOG |
| Catalog models | `backend/app/models/catalog.py` | Pydantic models pour actions |
| Catalog repository | `backend/app/repositories/catalog_repository.py` | SQL brut CRUD actions |
| Admin API routes | `backend/app/api/v1/admin.py` | POST/GET actions admin |
| Admin page | `frontend/src/pages/AdminPage.tsx` | Page administration |
| ActionForm component | `frontend/src/components/admin/ActionForm.tsx` | Formulaire creation |
| Admin service | `frontend/src/services/admin_service.ts` | Appels API admin |
| Types API catalog | `frontend/src/types/api.ts` | Types ActionCreate, etc. |

### Technical Stack (verified January 2026)

| Technology | Version | Role |
|---|---|---|
| FastAPI | 0.115+ | API backend |
| Python | 3.11.8 | Runtime (machine constraint) |
| python-oracledb | 3.4.1 | Driver Oracle (mode Thin) |
| Pydantic | v2.12+ | Validation donnees |
| React | 19.x | UI framework |
| Ant Design | 6.2+ | Design system |
| TypeScript | 5.9+ | Frontend typing |

### Previous Story Intelligence

#### Story 1.1 Learnings
- Python 3.11.8 sur la machine (pas 3.12)
- happy-dom au lieu de jsdom (incompatibilite ESM)
- IdpError hierarchy deja en place

#### Story 1.2 Learnings
- AUTH_DEV_BYPASS=true pour dev local sans IdP
- get_current_user() retourne UserProfile avec fields: id, username, display_name, profile
- 401 pour erreurs auth, 403 pour RBAC

#### Story 1.3 Learnings
- User type dans `types/common.ts` (pas `types/api.ts`)
- PROJECT_ROOT path fixe: 4 niveaux de `.parent` depuis tests/unit/

#### Story 1.4 Learnings
- 199 tests passing (162 backend + 37 frontend) — NE PAS CASSER
- RequestLoggingMiddleware ajoute
- CI/CD workflows en place
- Nginx + systemd configs en place

### Naming Conventions (MANDATORY)

| Context | Convention | Example |
|---|---|---|
| Python files | snake_case.py | catalog_repository.py |
| Python classes | PascalCase | CatalogRepository |
| Python functions | snake_case | create_action() |
| Pydantic models | PascalCase | ActionCreate, ActionResponse |
| Enum values | PascalCase or UPPER_SNAKE | ActionStatus.DRAFT or Status.DRAFT |
| API routes | /api/v1/admin/actions | kebab-case dans URL |
| JSON fields | snake_case | parameters_schema |
| TypeScript files | PascalCase.tsx ou snake_case.ts | AdminPage.tsx, admin_service.ts |
| React components | PascalCase | ActionForm |

### Anti-Patterns FORBIDDEN

| Anti-pattern | Correction |
|---|---|
| `raise Exception("x")` | `raise IdpError(...)` ou sous-classe |
| SQL sans parameterized query | Toujours utiliser des placeholders :param |
| Log sans correlation_id | Toujours via structlog contextvars |
| `return {"name": "..."}` | `return {"data": {"name": "..."}}` |
| ORM (SQLAlchemy, Tortoise) | SQL brut via python-oracledb |
| Validation uniquement au submit | Validation inline en temps reel |
| console.log() dans le frontend | Supprimer ou conditionnel |

### JSON Schema Structure — PARAMETERS_SCHEMA

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "database_name": {
      "type": "string",
      "description": "Nom de la base de donnees",
      "minLength": 1,
      "maxLength": 30
    },
    "environment": {
      "type": "string",
      "enum": ["DEV", "STAGING", "PROD"],
      "description": "Environnement cible"
    }
  },
  "required": ["database_name", "environment"]
}
```

### JSON Structure — IMPACT_RULES

```json
{
  "DEV": { "level": "low" },
  "STAGING": { "level": "medium" },
  "PROD": { "level": "high" }
}
```

Impact levels: "low" (vert), "medium" (orange), "high" (rouge), "critical" (rouge fonce)

### API Response Format (MANDATORY)

```json
// Succes creation (201)
{
  "data": {
    "id": 1,
    "name": "Creer PDB Oracle",
    "description": "Creation d'une Pluggable Database Oracle",
    "category": "Provisioning",
    "engine": "Oracle",
    "platform": "AAP",
    "status": "draft",
    "created_by": 42,
    "created_at": "2026-01-28T10:30:00Z",
    "updated_at": null
  }
}

// Erreur validation (422)
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Donnees invalides",
    "details": {
      "name": "Ce champ est requis"
    }
  }
}
```

### Existing File Paths (Absolute)

- `idp-portal/backend/app/core/database.py` — pool Oracle, get_connection()
- `idp-portal/backend/app/core/exceptions.py` — IdpError hierarchy
- `idp-portal/backend/app/api/deps.py` — get_current_user(), Depends
- `idp-portal/backend/app/models/auth.py` — UserProfile
- `idp-portal/backend/app/main.py` — FastAPI app, include routers
- `idp-portal/frontend/src/App.tsx` — Routes
- `idp-portal/frontend/src/components/layout/TopNav.tsx` — Navigation
- `idp-portal/frontend/src/services/api_client.ts` — apiFetch
- `idp-portal/frontend/src/types/common.ts` — User type

### Project Structure Notes

- Monorepo : `idp-portal/frontend/` + `idp-portal/backend/` + `idp-portal/database/`
- Migrations SQL : `database/migrations/V00X_*.sql`
- Repositories : `backend/app/repositories/`
- Models Pydantic : `backend/app/models/`
- API routes : `backend/app/api/v1/`
- Components frontend : `frontend/src/components/admin/`
- Pages frontend : `frontend/src/pages/`
- Services frontend : `frontend/src/services/`

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 2, Story 2.1]
- [Source: _bmad-output/planning-artifacts/architecture.md — Data Architecture, Repository Pattern, API Format]
- [Source: _bmad-output/planning-artifacts/prd.md — FR1]
- [Source: _bmad-output/implementation-artifacts/1-4-observabilite-health-check-et-ci-cd.md — Previous story, test counts]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A — No debug issues encountered.

### Completion Notes List

- **Task 1**: Migration V002 creee avec table ACTIONS_CATALOG, sequence, contraintes CHECK, indexes, commentaires. 12 tests valident la structure SQL.
- **Task 2**: Modeles Pydantic (ActionCategory, ActionEngine, ActionPlatform, ActionStatus, ActionCreate, ActionResponse, ActionDetail) avec validateurs pour nom, description, parameters_schema, impact_rules. 28 tests.
- **Task 3**: Repository catalog_repository.py avec create(), get_by_id(), list_all(). SQL brut avec CLOB JSON, structlog debug logging. 13 tests avec mocks Oracle.
- **Task 4**: API admin.py avec POST/GET /admin/actions endpoints, require_profile("dbops") RBAC. 12 tests API.
- **Task 5**: AdminPage.tsx avec table actions, bouton "Nouvelle action", modal ActionForm. ActionForm avec validation inline, JSON validation, accessibilite.
- **Task 6**: admin_service.ts avec createAction, listActions, getAction. Types dans api.ts.
- **Task 7**: Route /admin et AdminGuard deja existants (Story 1.3).
- **Task 8**: Validation ACs complete. 264 tests totaux (227 backend + 37 frontend).

### File List

**Created:**
- `database/migrations/V000_create_schema_version.sql`
- `database/migrations/V002_create_actions_catalog.sql`
- `backend/app/models/catalog.py`
- `backend/app/repositories/catalog_repository.py`
- `backend/tests/unit/test_catalog_models.py`
- `backend/tests/unit/test_catalog_repository.py`
- `backend/tests/unit/test_admin_api.py`
- `frontend/src/services/admin_service.ts`
- `frontend/src/components/admin/ActionForm.tsx`

**Modified:**
- `backend/app/api/v1/admin.py` — POST/GET actions endpoints; 404 via NotFoundError (IdpError)
- `backend/app/api/deps.py` — get_current_user used by require_profile (admin RBAC)
- `backend/app/main.py` — Include admin router
- `backend/app/core/logging.py` — Fixed log_level handling for string/enum
- `backend/app/repositories/catalog_repository.py` — Debug logging: query, params, duration_ms (Task 3.5)
- `backend/tests/unit/test_admin_api.py` — 404 asserts on error format
- `backend/tests/unit/test_project_structure.py` — V002 migration tests
- `frontend/src/pages/AdminPage.tsx` — Full admin page implementation
- `frontend/src/components/admin/ActionForm.tsx` — destroyOnClose (fix Modal prop)
- `frontend/src/types/api.ts` — Added Action types
- `scripts/run_migrations.sh` — Pass migration path via CURRENT_MIGRATION env; fix heredoc
- `database/migrations/V002_create_actions_catalog.sql` — MERGE into SCHEMA_VERSION (Task 1.5)

### Senior Developer Review (AI)

- **Date:** 2026-01-28
- **Findings:** 4 High, 4 Medium, 2 Low. Git vs File List discrepancies noted.
- **Fixes applied:** (1) V000 SCHEMA_VERSION + V002 MERGE (Task 1.5), (2) run_migrations.sh pass path via `CURRENT_MIGRATION` env, (3) catalog_repository debug logging with query/params (Task 3.5), (4) admin 404 via NotFoundError + `{"error":...}` format, (5) ActionForm `destroyOnClose`, (6) File List updated (main.py, deps.py, run_migrations.sh, etc.).

### Change Log

- 2026-01-28: Story created by create-story workflow. Ready for dev.
- 2026-01-28: Story implementation completed. All 8 tasks done. 264 tests passing.
- 2026-01-28: Code review fixes applied: SCHEMA_VERSION (V000 + V002 MERGE), run_migrations $sql_file, catalog_repository debug logging (query/params), admin 404 → NotFoundError, ActionForm destroyOnClose, File List updated.
