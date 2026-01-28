# Story 2.2: Definir les etapes d'execution et le changement ServiceNow

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBOPS,
I want configurer les etapes d'execution d'une action et le type de changement ServiceNow associe,
So that chaque action suit le bon processus d'execution selon l'environnement cible.

## Acceptance Criteria

1. **AC1 — Section etapes d'execution** : Given un DBOPS edite une action en brouillon, When il accede a la section "Etapes d'execution", Then il peut definir une liste ordonnee d'etapes avec nom et type (pre-requis, execution, verification).

2. **AC2 — Etapes conditionnelles** : Given le DBOPS configure une etape conditionnelle, When il specifie "ouverture changement ServiceNow" pour l'environnement Production, Then l'etape est marquee comme conditionnelle a l'environnement cible.

3. **AC3 — Type de changement** : Given le DBOPS definit le type de changement, When il choisit "pre-approuve" ou "CAB", Then le systeme enregistre ce type dans la definition de l'action, par environnement si necessaire.

4. **AC4 — Colonne execution_steps** : Given le schema de base de donnees, When la migration V003 est verifiee, Then la colonne execution_steps (CLOB JSON) existe dans ACTIONS_CATALOG.

5. **AC5 — API PUT steps** : Given un DBOPS soumet les etapes, When l'API PUT /api/v1/admin/actions/{id}/steps est appelee, Then les etapes sont enregistrees et la reponse est HTTP 200 avec l'action mise a jour dans { "data": {...} }.

6. **AC6 — FR2 et FR4 satisfaites** : L'ensemble des ACs ci-dessus satisfait FR2 (definir les etapes d'execution) et FR4 (type de changement pre-approuve/CAB).

## Tasks / Subtasks

- [x] Task 1: Migration Oracle — Ajouter execution_steps et change_type a ACTIONS_CATALOG (AC: 4)
  - [x] 1.1: Creer le script `database/migrations/V003_add_execution_steps.sql` pour ajouter EXECUTION_STEPS (CLOB) et CHANGE_TYPE_CONFIG (CLOB) a ACTIONS_CATALOG
  - [x] 1.2: Ajouter les commentaires Oracle documentant la structure JSON attendue pour execution_steps et change_type_config
  - [x] 1.3: Mettre a jour la table SCHEMA_VERSION avec V003

- [x] Task 2: Backend — Modeles Pydantic pour les etapes (AC: 1, 2, 3)
  - [x] 2.1: Ajouter dans `backend/app/models/catalog.py` les modeles: ExecutionStepType (Enum: prerequisite, execution, verification), ExecutionStep (order, name, type, is_servicenow_change, conditional_environments: list[str] | None), ChangeType (Enum: pre_approved, cab), ChangeTypeConfig ({environment: ChangeType}), ExecutionStepsUpdate (steps: list[ExecutionStep], change_type_config: ChangeTypeConfig | None)
  - [x] 2.2: Ajouter les validateurs Pydantic: order doit etre unique et sequentiel (1, 2, 3...), name non vide (1-255 chars), conditional_environments si is_servicenow_change=true
  - [x] 2.3: Mettre a jour ActionDetail pour inclure execution_steps et change_type_config
  - [x] 2.4: Ecrire les tests unitaires pour les validateurs: order non sequentiel, name vide, conditional_environments manquant si servicenow_change, ChangeType valide

- [x] Task 3: Backend — Repository SQL update execution_steps (AC: 5)
  - [x] 3.1: Ajouter la methode `update_execution_steps(action_id: int, steps: list[ExecutionStep], change_type_config: ChangeTypeConfig | None) -> ActionDetail | None` dans catalog_repository.py
  - [x] 3.2: Implementer avec SQL UPDATE utilisant CLOB JSON, verifier action existe et est en draft, RETURNING pour validation
  - [x] 3.3: Logger la requete SQL en mode debug (query, params, duration_ms) via structlog
  - [x] 3.4: Ecrire les tests unitaires: update succes, action non trouvee, action non-draft (erreur)

- [x] Task 4: Backend — API PUT /admin/actions/{id}/steps (AC: 5)
  - [x] 4.1: Ajouter l'endpoint PUT /api/v1/admin/actions/{id}/steps dans admin.py: accepte ExecutionStepsUpdate, verifie profil DBOPS, appelle catalog_repository.update_execution_steps()
  - [x] 4.2: Retourner 200 + { "data": ActionDetail } en succes, 404 si action non trouvee, 400 si action non-draft, 422 si validation echouee
  - [x] 4.3: Ecrire les tests unitaires: PUT succes (200), PUT non trouvee (404), PUT non-draft (400), PUT validation error (422), PUT non-DBOPS (403)

- [x] Task 5: Frontend — Composant StepsEditor pour les etapes (AC: 1, 2)
  - [x] 5.1: Creer `frontend/src/components/admin/StepsEditor.tsx` avec interface: liste ordonnee d'etapes (drag-and-drop Ant Design), bouton "Ajouter une etape"
  - [x] 5.2: Chaque etape: Input nom, Select type (Pre-requis/Execution/Verification), Switch "Changement ServiceNow", Select multi "Environnements conditionnes" (visible si switch actif)
  - [x] 5.3: Validation inline: nom requis, au moins une etape, environnements requis si ServiceNow coche
  - [x] 5.4: Accessibilite: aria-label sur les champs, ordre de focus logique, boutons supprimer accessibles

- [x] Task 6: Frontend — Composant ChangeTypeConfig (AC: 3)
  - [x] 6.1: Creer `frontend/src/components/admin/ChangeTypeConfig.tsx` avec interface: tableau des environnements (DEV, STAGING, PROD) avec Select type de changement (Pre-approuve/CAB) pour chacun
  - [x] 6.2: Afficher un badge "Pre-approuve" vert ou "CAB" orange selon le type selectionne
  - [x] 6.3: Accessibilite: aria-label sur chaque select, tableau avec role="table"

- [x] Task 7: Frontend — Integration dans ActionForm (AC: 1, 2, 3)
  - [x] 7.1: Ajouter les composants StepsEditor et ChangeTypeConfig dans ActionForm.tsx (nouvelle section sous les champs de base)
  - [x] 7.2: Integrer dans le state du formulaire: execution_steps et change_type_config
  - [x] 7.3: Au submit, si etapes modifiees, appeler PUT /api/v1/admin/actions/{id}/steps apres la creation/update de l'action
  - [x] 7.4: Afficher les erreurs de validation inline pour les etapes

- [x] Task 8: Frontend — Service API et types (AC: 5)
  - [x] 8.1: Ajouter dans `frontend/src/services/admin_service.ts`: updateActionSteps(actionId: number, steps: ExecutionStepsUpdate): Promise<ActionDetail>
  - [x] 8.2: Ajouter les types dans `frontend/src/types/api.ts`: ExecutionStepType, ExecutionStep, ChangeType, ChangeTypeConfig, ExecutionStepsUpdate

- [x] Task 9: Validation end-to-end et tests (AC: tous)
  - [x] 9.1: Verifier AC1 — section etapes avec liste ordonnee et types
  - [x] 9.2: Verifier AC2 — etapes conditionnelles ServiceNow par environnement
  - [x] 9.3: Verifier AC3 — type de changement par environnement
  - [x] 9.4: Verifier AC4 — colonnes EXECUTION_STEPS et CHANGE_TYPE_CONFIG presentes
  - [x] 9.5: Verifier AC5 — API PUT retourne 200 avec data wrapper
  - [x] 9.6: Regression check — tous les tests existants passent (264+ backend + frontend attendus minimum)

- [x] Review Follow-ups (AI)
  - [x] [AI-Review][MEDIUM] StepsEditor: implémenter drag-and-drop Ant Design (Task 5.1) — actuellement boutons Monter/Descendre [StepsEditor.tsx]

## Dev Notes

### Architecture Requirements

- **Repository Pattern SQL brut** : Chaque domaine a son repository avec SQL via python-oracledb. Pas d'ORM. [Source: architecture.md — Data Architecture]
- **CLOB JSON Oracle** : Les colonnes EXECUTION_STEPS et CHANGE_TYPE_CONFIG sont des CLOB contenant du JSON. [Source: architecture.md — Data Architecture]
- **API format** : Toute reponse est wrappee dans { "data": ... } ou { "error": ... }. snake_case partout. [Source: architecture.md — API Response Format]
- **RBAC admin** : Seul le profil DBOPS peut acceder aux routes /api/v1/admin/*. [Source: architecture.md — Authentication & Security]
- **Validation inline** : Validation en temps reel sur le formulaire, pas uniquement a la soumission. [Source: epics.md — Story 2.1 AC6]
- **Actions en draft uniquement** : Les etapes ne peuvent etre modifiees que sur une action en statut "draft". [Source: epics.md — Story 2.4]

### What Already Exists (DO NOT REIMPLEMENT)

| Element | Fichier | Statut |
|---|---|---|
| Table ACTIONS_CATALOG | `database/migrations/V002_create_actions_catalog.sql` | Existe |
| Catalog models | `backend/app/models/catalog.py` | Existe — ENRICHIR |
| Catalog repository | `backend/app/repositories/catalog_repository.py` | Existe — ENRICHIR |
| Admin API routes | `backend/app/api/v1/admin.py` | Existe — ENRICHIR |
| Admin page | `frontend/src/pages/AdminPage.tsx` | Existe |
| ActionForm component | `frontend/src/components/admin/ActionForm.tsx` | Existe — ENRICHIR |
| Admin service | `frontend/src/services/admin_service.ts` | Existe — ENRICHIR |
| Types API catalog | `frontend/src/types/api.ts` | Existe — ENRICHIR |

### What Needs to Be CREATED

| Element | Fichier | Description |
|---|---|---|
| Migration V003 | `database/migrations/V003_add_execution_steps.sql` | Ajouter colonnes EXECUTION_STEPS et CHANGE_TYPE_CONFIG |
| StepsEditor component | `frontend/src/components/admin/StepsEditor.tsx` | Editeur liste ordonnee d'etapes |
| ChangeTypeConfig component | `frontend/src/components/admin/ChangeTypeConfig.tsx` | Config type changement par environnement |

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

#### Story 2.1 Learnings

- **Migration pattern**: V00X_*.sql avec MERGE into SCHEMA_VERSION pour idempotence
- **Catalog models**: ActionCategory, ActionEngine, ActionPlatform, ActionStatus enums en place
- **ActionDetail** inclut deja parameters_schema, impact_rules, rbac_policies (CLOB JSON)
- **catalog_repository**: create(), get_by_id(), list_all() implementes avec SQL brut + structlog debug
- **admin.py**: POST/GET endpoints avec require_profile("dbops") RBAC decorator
- **ActionForm**: Modal Ant Design avec validation inline, JSON validation, destroyOnClose
- **Tests**: 264 tests totaux (227 backend + 37 frontend) — NE PAS CASSER
- **404 handling**: via NotFoundError (IdpError) → `{"error":...}` format
- **Debug logging**: catalog_repository log query/params/duration_ms

#### Patterns a Reproduire

```python
# Repository method pattern (from catalog_repository.py)
async def update_execution_steps(
    self, action_id: int, steps: list[ExecutionStep], change_type_config: ChangeTypeConfig | None
) -> ActionDetail | None:
    log = structlog.get_logger()
    query = """
        UPDATE ACTIONS_CATALOG
        SET EXECUTION_STEPS = :execution_steps,
            CHANGE_TYPE_CONFIG = :change_type_config,
            UPDATED_AT = SYSTIMESTAMP
        WHERE ID = :action_id AND STATUS = 'draft'
    """
    # ... implementation
```

```typescript
// Frontend service pattern (from admin_service.ts)
export async function updateActionSteps(
  actionId: number,
  data: ExecutionStepsUpdate
): Promise<ActionDetail> {
  return apiFetch<ActionDetail>(`/api/v1/admin/actions/${actionId}/steps`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}
```

### JSON Schema Structure — EXECUTION_STEPS

```json
[
  {
    "order": 1,
    "name": "Verification pre-requis",
    "type": "prerequisite",
    "is_servicenow_change": false,
    "conditional_environments": null
  },
  {
    "order": 2,
    "name": "Ouverture changement ServiceNow",
    "type": "execution",
    "is_servicenow_change": true,
    "conditional_environments": ["STAGING", "PROD"]
  },
  {
    "order": 3,
    "name": "Execution action AAP",
    "type": "execution",
    "is_servicenow_change": false,
    "conditional_environments": null
  },
  {
    "order": 4,
    "name": "Verification post-execution",
    "type": "verification",
    "is_servicenow_change": false,
    "conditional_environments": null
  }
]
```

### JSON Structure — CHANGE_TYPE_CONFIG

```json
{
  "DEV": "pre_approved",
  "STAGING": "pre_approved",
  "PROD": "cab"
}
```

Change types: "pre_approved" (pre-approuve, vert), "cab" (CAB, orange)

### API Endpoint Specification

**PUT /api/v1/admin/actions/{id}/steps**

Request body:
```json
{
  "steps": [
    {
      "order": 1,
      "name": "Verification pre-requis",
      "type": "prerequisite",
      "is_servicenow_change": false,
      "conditional_environments": null
    }
  ],
  "change_type_config": {
    "DEV": "pre_approved",
    "STAGING": "pre_approved",
    "PROD": "cab"
  }
}
```

Response 200:
```json
{
  "data": {
    "id": 1,
    "name": "Creer PDB Oracle",
    "execution_steps": [...],
    "change_type_config": {...},
    ...
  }
}
```

Error 400 (action not in draft):
```json
{
  "error": {
    "code": "INVALID_STATE",
    "message": "Les etapes ne peuvent etre modifiees que pour une action en brouillon",
    "details": { "status": "published" }
  }
}
```

### Naming Conventions (MANDATORY)

| Context | Convention | Example |
|---|---|---|
| Python files | snake_case.py | catalog_repository.py |
| Python classes | PascalCase | ExecutionStep |
| Enum values | snake_case | ExecutionStepType.prerequisite |
| API routes | /api/v1/admin/actions/{id}/steps | kebab-case URL |
| JSON fields | snake_case | execution_steps, change_type_config |
| TypeScript files | PascalCase.tsx | StepsEditor.tsx |
| React components | PascalCase | StepsEditor, ChangeTypeConfig |

### Anti-Patterns FORBIDDEN

| Anti-pattern | Correction |
|---|---|
| `raise Exception("x")` | `raise IdpError(...)` ou sous-classe |
| Update action sans verifier status | Verifier status='draft' dans WHERE clause |
| Validation uniquement au submit | Validation inline en temps reel |
| ORM (SQLAlchemy) | SQL brut via python-oracledb |
| `return {"name": "..."}` | `return {"data": {"name": "..."}}` |

### Existing File Paths (Absolute)

- `idp-portal/database/migrations/V002_create_actions_catalog.sql` — Table existante
- `idp-portal/backend/app/models/catalog.py` — Modeles Pydantic existants
- `idp-portal/backend/app/repositories/catalog_repository.py` — Repository existant
- `idp-portal/backend/app/api/v1/admin.py` — Routes admin existantes
- `idp-portal/frontend/src/components/admin/ActionForm.tsx` — Formulaire existant
- `idp-portal/frontend/src/services/admin_service.ts` — Service existant
- `idp-portal/frontend/src/types/api.ts` — Types existants

### Project Structure Notes

- Monorepo : `idp-portal/frontend/` + `idp-portal/backend/` + `idp-portal/database/`
- Migrations SQL : `database/migrations/V00X_*.sql`
- Components frontend : `frontend/src/components/admin/`

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 2, Story 2.2]
- [Source: _bmad-output/planning-artifacts/architecture.md — Data Architecture, Repository Pattern, API Format]
- [Source: _bmad-output/planning-artifacts/prd.md — FR2, FR4]
- [Source: _bmad-output/implementation-artifacts/2-1-creer-une-action-avec-ses-metadonnees.md — Previous story patterns]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- catalog_repository_update_execution_steps: logs query, params, duration_ms, action_id, steps_count
- catalog_repository_get_by_id: updated to include EXECUTION_STEPS, CHANGE_TYPE_CONFIG columns

### Completion Notes List

- **Task 1**: V003 migration created with ALTER TABLE for EXECUTION_STEPS and CHANGE_TYPE_CONFIG CLOB columns. Comments document JSON structure. MERGE ensures idempotent SCHEMA_VERSION update. 5 migration tests added. Code review: migration made idempotent via PL/SQL (add columns only if missing).
- **Task 2**: Pydantic models ExecutionStepType, ExecutionStep, ChangeType, ExecutionStepsUpdate added with comprehensive validators. 19 unit tests cover order sequentiality, name validation, conditional_environments requirement when is_servicenow_change=True.
- **Task 3**: catalog_repository.update_execution_steps() implemented with InvalidStateError for non-draft actions. JSON conversion helpers added. 13 repository tests cover success, not found, and invalid state scenarios. Code review: rowcount check (0 rows → InvalidStateError), robust JSON parse with ValueError; +1 test for zero-rows race.
- **Task 4**: PUT /admin/actions/{id}/steps endpoint added with DBOPS RBAC, InvalidStateError → 400 conversion. 5 API tests cover all response codes (200, 400, 403, 404, 422).
- **Task 5-6**: StepsEditor and ChangeTypeConfig components created with Ant Design, inline validation, accessibility (aria-labels, role attributes). Drag-and-drop deferred to follow-up (currently buttons).
- **Task 7**: ActionForm updated to support edit mode with StepsEditor/ChangeTypeConfig in collapsible section. Steps saved via updateActionSteps after action creation. Code review: create+steps flow fixed (handleCreate returns created action, onSuccess closes/refreshes); edit mode wired in AdminPage (Modifier, getAction); steps validation blocks submit when invalid; saving state for confirmLoading.
- **Task 8**: TypeScript types and admin_service.updateActionSteps(), getAction added.
- **Task 9**: Full regression passed: 273 backend + 37 frontend = 310 tests (up from 264 baseline).
- **Review Follow-up [MEDIUM]**: StepsEditor drag-and-drop implemented via @dnd-kit/core + @dnd-kit/sortable. Replaced ↑↓ buttons with HolderOutlined drag handle. SortableStepCard component extracts sortable logic. All tests pass.

### File List

#### New Files
- `idp-portal/database/migrations/V003_add_execution_steps.sql`
- `idp-portal/frontend/src/components/admin/StepsEditor.tsx`
- `idp-portal/frontend/src/components/admin/ChangeTypeConfig.tsx`

#### Modified (code review fixes)
- `idp-portal/frontend/src/components/admin/StepsEditor.tsx` — canRemove prop to require at least one step
- `idp-portal/frontend/src/components/admin/ChangeTypeConfig.tsx` — ARIA table header row (role="row")

#### Modified Files
- `idp-portal/backend/app/models/catalog.py` — Added ExecutionStepType, ExecutionStep, ChangeType, ExecutionStepsUpdate models; updated ActionDetail
- `idp-portal/backend/app/repositories/catalog_repository.py` — Added update_execution_steps(), InvalidStateError, JSON conversion helpers; updated get_by_id query; rowcount check, JSON parse error handling; _safe_parse_* to avoid 500 on invalid CLOB (code review)
- `idp-portal/backend/app/api/v1/admin.py` — Added PUT /admin/actions/{id}/steps endpoint
- `idp-portal/backend/app/core/exceptions.py` — Added InvalidStateError (HTTP 400)
- `idp-portal/backend/tests/unit/test_project_structure.py` — Added V003 migration tests
- `idp-portal/backend/tests/unit/test_catalog_models.py` — Added execution step validation tests
- `idp-portal/backend/tests/unit/test_catalog_repository.py` — Added update_execution_steps tests + zero-rows race test
- `idp-portal/backend/tests/unit/test_admin_api.py` — Added PUT steps API tests
- `idp-portal/frontend/src/types/api.ts` — Added ExecutionStep types
- `idp-portal/frontend/src/services/admin_service.ts` — Added updateActionSteps(), getAction used by edit flow
- `idp-portal/frontend/src/components/admin/ActionForm.tsx` — Integrated StepsEditor/ChangeTypeConfig; create+steps flow, onSuccess, steps validation, edit support; require at least one step in edit mode (code review)
- `idp-portal/frontend/src/pages/AdminPage.tsx` — Edit mode: Modifier button, getAction, handleEditSubmit, onSuccess, create returns created action (code review)
- `idp-portal/frontend/package.json` — Added @dnd-kit/core, @dnd-kit/sortable, @dnd-kit/utilities dependencies (review follow-up)
- `idp-portal/database/migrations/V003_add_execution_steps.sql` — Idempotent PL/SQL add-column (code review)

## Change Log

- 2026-01-28: Story 2.2 implementation complete. All 9 tasks and 32 subtasks done. 309 tests passing (272 backend + 37 frontend). Ready for code review.
- 2026-01-28: Code review (AI): fixes applied. Create+steps persistence, edit mode (Modifier + getAction), UPDATE rowcount race, steps validation, V003 idempotent, JSON parse robustness. 273 backend + 37 frontend tests. Follow-up: drag-and-drop StepsEditor.
- 2026-01-28: Review follow-up resolved. StepsEditor drag-and-drop via @dnd-kit (AC #1 Task 5.1). 310 tests passing.
- 2026-01-28: Adversarial code review fixes. ActionForm: require at least one step in edit mode (validation + block submit). StepsEditor: disable remove when only one step (canRemove). ChangeTypeConfig: ARIA table header row fixed (role="row"). catalog_repository: _safe_parse_execution_steps / _safe_parse_change_type_config to avoid 500 on invalid CLOB JSON. Story AC4: V002 → V003.

