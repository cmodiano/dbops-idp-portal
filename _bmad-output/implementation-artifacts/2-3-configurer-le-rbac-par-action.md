# Story 2.3: Configurer le RBAC par action

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBOPS,
I want definir les regles d'acces par action (qui peut executer, qui doit approuver, par profil et par environnement),
So that chaque action respecte les politiques de securite de l'entreprise.

## Acceptance Criteria

1. **AC1 — Section controle d'acces** : Given un DBOPS edite une action en brouillon, When il accede a la section "Controle d'acces", Then il peut selectionner les profils autorises (DBA Applicatif, DBA Infrastructure, Client Business) par environnement.

2. **AC2 — Configuration approbation** : Given le DBOPS configure l'approbation, When il definit "approbation DBA requise pour Production", Then la regle est enregistree dans rbac_policies (CLOB JSON) de l'action.

3. **AC3 — Filtrage RBAC invisible** : Given un profil n'est pas autorise pour un environnement, When un utilisateur de ce profil consulte le catalogue, Then l'action n'apparait pas pour cet environnement (filtrage RBAC invisible).

4. **AC4 — API PUT rbac** : Given un DBOPS soumet les politiques RBAC, When l'API PUT /api/v1/admin/actions/{id}/rbac est appelee, Then les politiques sont enregistrees et la reponse est HTTP 200 avec l'action mise a jour dans { "data": {...} }.

5. **AC5 — FR3 satisfaite** : L'ensemble des ACs ci-dessus satisfait FR3 (configurer les regles RBAC par action).

## Tasks / Subtasks

- [x] Task 1: Backend — Modeles Pydantic pour RBAC policies (AC: 1, 2)
  - [x] 1.1: Ajouter dans `backend/app/models/catalog.py` les modeles: UserProfile (Enum: dba_applicatif, dba_infrastructure, client_business, dbops), EnvironmentPermission (profiles: list[UserProfile], requires_approval: bool, approver_profiles: list[UserProfile] | None), RbacPolicies (environments: dict[str, EnvironmentPermission] pour DEV/STAGING/PROD), RbacPoliciesUpdate (policies: RbacPolicies)
  - [x] 1.2: Ajouter les validateurs Pydantic: au moins un profil autorise par environnement, requires_approval=true implique approver_profiles non vide
  - [x] 1.3: Mettre a jour ActionDetail pour inclure rbac_policies parse (actuellement CLOB brut)
  - [x] 1.4: Ecrire les tests unitaires pour les validateurs: profil vide, approver_profiles manquant si requires_approval

- [x] Task 2: Backend — Repository SQL update rbac_policies (AC: 4)
  - [x] 2.1: Ajouter la methode `update_rbac_policies(action_id: int, policies: RbacPolicies) -> ActionDetail | None` dans catalog_repository.py
  - [x] 2.2: Implementer avec SQL UPDATE sur RBAC_POLICIES (CLOB JSON), verifier action existe et est en draft, RETURNING pour validation
  - [x] 2.3: Logger la requete SQL en mode debug (query, params, duration_ms) via structlog
  - [x] 2.4: Ecrire les tests unitaires: update succes, action non trouvee, action non-draft (erreur)

- [x] Task 3: Backend — API PUT /admin/actions/{id}/rbac (AC: 4)
  - [x] 3.1: Ajouter l'endpoint PUT /api/v1/admin/actions/{id}/rbac dans admin.py: accepte RbacPoliciesUpdate, verifie profil DBOPS, appelle catalog_repository.update_rbac_policies()
  - [x] 3.2: Retourner 200 + { "data": ActionDetail } en succes, 404 si action non trouvee, 400 si action non-draft, 422 si validation echouee
  - [x] 3.3: Ecrire les tests unitaires: PUT succes (200), PUT non trouvee (404), PUT non-draft (400), PUT validation error (422), PUT non-DBOPS (403)

- [x] Task 4: Backend — Filtrage RBAC sur GET catalogue (AC: 3)
  - [x] 4.1: Modifier `catalog_repository.list_all()` pour accepter un parametre user_profile et filter les actions dont rbac_policies n'autorise pas ce profil
  - [x] 4.2: Modifier l'endpoint GET /api/v1/catalog/actions pour passer le profil utilisateur courant au repository (filtrage invisible)
  - [x] 4.3: Ecrire les tests unitaires: liste filtree par profil, action visible pour profil autorise, action invisible pour profil non autorise

- [x] Task 5: Frontend — Composant RbacEditor pour le controle d'acces (AC: 1, 2)
  - [x] 5.1: Creer `frontend/src/components/admin/RbacEditor.tsx` avec interface: tableau des environnements (DEV, STAGING, PROD)
  - [x] 5.2: Pour chaque environnement: Select multi "Profils autorises" (DBA Applicatif, DBA Infrastructure, Client Business), Switch "Approbation requise", Select multi "Profils approbateurs" (visible si switch actif)
  - [x] 5.3: Validation inline: au moins un profil par environnement, profils approbateurs requis si approbation cochee
  - [x] 5.4: Accessibilite: aria-label sur les champs, role="table" sur le tableau, focus logique

- [x] Task 6: Frontend — Integration dans ActionForm (AC: 1, 2)
  - [x] 6.1: Ajouter le composant RbacEditor dans ActionForm.tsx (nouvelle section Collapse "Controle d'acces" apres "Type de changement")
  - [x] 6.2: Integrer dans le state du formulaire: rbac_policies
  - [x] 6.3: Au submit, si politiques modifiees, appeler PUT /api/v1/admin/actions/{id}/rbac apres les autres updates
  - [x] 6.4: Afficher les erreurs de validation inline pour les politiques RBAC

- [x] Task 7: Frontend — Service API et types (AC: 4)
  - [x] 7.1: Ajouter dans `frontend/src/services/admin_service.ts`: updateActionRbac(actionId: number, policies: RbacPoliciesUpdate): Promise<ActionDetail>
  - [x] 7.2: Ajouter les types dans `frontend/src/types/api.ts`: UserProfile, EnvironmentPermission, RbacPolicies, RbacPoliciesUpdate

- [x] Task 8: Validation end-to-end et tests (AC: tous)
  - [x] 8.1: Verifier AC1 — section controle d'acces avec profils par environnement
  - [x] 8.2: Verifier AC2 — approbation configuree et enregistree
  - [x] 8.3: Verifier AC3 — filtrage RBAC invisible sur le catalogue (avec utilisateur de profil different)
  - [x] 8.4: Verifier AC4 — API PUT retourne 200 avec data wrapper
  - [x] 8.5: Regression check — tous les tests existants passent (310+ backend + frontend attendus minimum)

## Dev Notes

### Architecture Requirements

- **Repository Pattern SQL brut** : Chaque domaine a son repository avec SQL via python-oracledb. Pas d'ORM. [Source: architecture.md — Data Architecture]
- **CLOB JSON Oracle** : La colonne RBAC_POLICIES est un CLOB contenant du JSON. [Source: architecture.md — Data Architecture]
- **API format** : Toute reponse est wrappee dans { "data": ... } ou { "error": ... }. snake_case partout. [Source: architecture.md — API Response Format]
- **RBAC admin** : Seul le profil DBOPS peut acceder aux routes /api/v1/admin/*. [Source: architecture.md — Authentication & Security]
- **Filtrage RBAC invisible** : L'API filtre en amont — le frontend ne recoit que les donnees autorisees. [Source: architecture.md — UX Architectural Implications]
- **Validation inline** : Validation en temps reel sur le formulaire, pas uniquement a la soumission. [Source: epics.md — Story 2.1 AC6]
- **Actions en draft uniquement** : Les politiques RBAC ne peuvent etre modifiees que sur une action en statut "draft". [Source: epics.md — Story 2.4]

### What Already Exists (DO NOT REIMPLEMENT)

| Element | Fichier | Statut |
|---|---|---|
| Table ACTIONS_CATALOG avec RBAC_POLICIES | `database/migrations/V002_create_actions_catalog.sql` | Existe — colonne RBAC_POLICIES CLOB deja presente |
| Catalog models | `backend/app/models/catalog.py` | Existe — ENRICHIR avec RbacPolicies |
| Catalog repository | `backend/app/repositories/catalog_repository.py` | Existe — ENRICHIR avec update_rbac_policies() et filtrage |
| Admin API routes | `backend/app/api/v1/admin.py` | Existe — ENRICHIR avec PUT rbac |
| Catalog API routes | `backend/app/api/v1/catalog.py` | Existe — ENRICHIR avec filtrage RBAC |
| ActionForm component | `frontend/src/components/admin/ActionForm.tsx` | Existe — ENRICHIR avec RbacEditor |
| Admin service | `frontend/src/services/admin_service.ts` | Existe — ENRICHIR avec updateActionRbac() |
| Types API catalog | `frontend/src/types/api.ts` | Existe — ENRICHIR avec RbacPolicies |
| InvalidStateError | `backend/app/core/exceptions.py` | Existe (story 2.2) |

### What Needs to Be CREATED

| Element | Fichier | Description |
|---|---|---|
| RbacEditor component | `frontend/src/components/admin/RbacEditor.tsx` | Editeur politiques RBAC par environnement |

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

#### Story 2.2 Learnings

- **Repository method pattern**: update_execution_steps() avec InvalidStateError pour non-draft, rowcount check
- **PUT endpoint pattern**: DBOPS RBAC decorator, 200/400/403/404/422 responses
- **Frontend component pattern**: Collapsible sections dans ActionForm, validation inline
- **Tests baseline**: 310 tests (273 backend + 37 frontend) — NE PAS CASSER
- **JSON parse robustness**: _safe_parse_* helpers to avoid 500 on invalid CLOB JSON
- **Edit mode**: ActionForm supporte create et edit avec onSuccess callback

#### Patterns a Reproduire

```python
# Repository method pattern (from catalog_repository.py)
async def update_rbac_policies(
    self, action_id: int, policies: RbacPolicies
) -> ActionDetail | None:
    log = structlog.get_logger()
    query = """
        UPDATE ACTIONS_CATALOG
        SET RBAC_POLICIES = :rbac_policies,
            UPDATED_AT = SYSTIMESTAMP
        WHERE ID = :action_id AND STATUS = 'draft'
    """
    # ... implementation with rowcount check
```

```typescript
// Frontend service pattern (from admin_service.ts)
export async function updateActionRbac(
  actionId: number,
  data: RbacPoliciesUpdate
): Promise<ActionDetail> {
  return apiFetch<ActionDetail>(`/api/v1/admin/actions/${actionId}/rbac`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}
```

### JSON Schema Structure — RBAC_POLICIES

```json
{
  "environments": {
    "DEV": {
      "profiles": ["dba_applicatif", "dba_infrastructure", "client_business"],
      "requires_approval": false,
      "approver_profiles": null
    },
    "STAGING": {
      "profiles": ["dba_applicatif", "dba_infrastructure"],
      "requires_approval": false,
      "approver_profiles": null
    },
    "PROD": {
      "profiles": ["dba_applicatif", "dba_infrastructure"],
      "requires_approval": true,
      "approver_profiles": ["dba_infrastructure"]
    }
  }
}
```

### User Profiles Definition

| Profile | Code | Description |
|---|---|---|
| DBA Applicatif | dba_applicatif | DBA responsable des applications |
| DBA Infrastructure | dba_infrastructure | DBA responsable de l'infrastructure |
| Client Business | client_business | Utilisateur metier (self-service) |
| DBOPS | dbops | Administrateur du catalogue |

### API Endpoint Specification

**PUT /api/v1/admin/actions/{id}/rbac**

Request body:
```json
{
  "policies": {
    "environments": {
      "DEV": {
        "profiles": ["dba_applicatif", "client_business"],
        "requires_approval": false,
        "approver_profiles": null
      },
      "STAGING": {
        "profiles": ["dba_applicatif"],
        "requires_approval": false,
        "approver_profiles": null
      },
      "PROD": {
        "profiles": ["dba_applicatif"],
        "requires_approval": true,
        "approver_profiles": ["dba_infrastructure"]
      }
    }
  }
}
```

Response 200:
```json
{
  "data": {
    "id": 1,
    "name": "Creer PDB Oracle",
    "rbac_policies": {...},
    ...
  }
}
```

Error 400 (action not in draft):
```json
{
  "error": {
    "code": "INVALID_STATE",
    "message": "Les politiques RBAC ne peuvent etre modifiees que pour une action en brouillon",
    "details": { "status": "published" }
  }
}
```

### Filtrage RBAC — Logique

```python
# Dans catalog_repository.list_all()
# Si user_profile != "dbops":
#   Filtrer les actions ou rbac_policies.environments[env].profiles ne contient pas user_profile
#   L'action n'apparait que si au moins un environnement autorise le profil

# Exemple: user_profile = "client_business"
# Action A: DEV autorise [client_business], PROD autorise [dba_applicatif]
# → Action A visible car DEV l'autorise
# Action B: DEV autorise [dba_applicatif], PROD autorise [dba_applicatif]
# → Action B invisible car aucun environnement n'autorise client_business
```

### Naming Conventions (MANDATORY)

| Context | Convention | Example |
|---|---|---|
| Python files | snake_case.py | catalog_repository.py |
| Python classes | PascalCase | RbacPolicies, EnvironmentPermission |
| Enum values | snake_case | UserProfile.dba_applicatif |
| API routes | /api/v1/admin/actions/{id}/rbac | kebab-case URL |
| JSON fields | snake_case | rbac_policies, requires_approval |
| TypeScript files | PascalCase.tsx | RbacEditor.tsx |
| React components | PascalCase | RbacEditor |

### Anti-Patterns FORBIDDEN

| Anti-pattern | Correction |
|---|---|
| `raise Exception("x")` | `raise IdpError(...)` ou sous-classe |
| Update action sans verifier status | Verifier status='draft' dans WHERE clause |
| Validation uniquement au submit | Validation inline en temps reel |
| ORM (SQLAlchemy) | SQL brut via python-oracledb |
| `return {"name": "..."}` | `return {"data": {"name": "..."}}` |
| Filtrage RBAC cote frontend | Filtrage cote API (invisible) |

### Existing File Paths (Absolute)

- `idp-portal/database/migrations/V002_create_actions_catalog.sql` — Table avec RBAC_POLICIES existante
- `idp-portal/backend/app/models/catalog.py` — Modeles Pydantic existants
- `idp-portal/backend/app/repositories/catalog_repository.py` — Repository existant
- `idp-portal/backend/app/api/v1/admin.py` — Routes admin existantes
- `idp-portal/backend/app/api/v1/catalog.py` — Routes catalogue existantes (si existe, sinon admin.py)
- `idp-portal/frontend/src/components/admin/ActionForm.tsx` — Formulaire existant
- `idp-portal/frontend/src/services/admin_service.ts` — Service existant
- `idp-portal/frontend/src/types/api.ts` — Types existants

### Project Structure Notes

- Monorepo : `idp-portal/frontend/` + `idp-portal/backend/` + `idp-portal/database/`
- Components frontend : `frontend/src/components/admin/`
- Le filtrage RBAC s'applique sur GET catalogue, pas sur GET admin (DBOPS voit tout)

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 2, Story 2.3]
- [Source: _bmad-output/planning-artifacts/architecture.md — Data Architecture, RBAC, API Format]
- [Source: _bmad-output/planning-artifacts/prd.md — FR3, FR26]
- [Source: _bmad-output/implementation-artifacts/2-2-definir-les-etapes-execution-et-changement-servicenow.md — Previous story patterns]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

- **Task 1**: Backend Pydantic models added: UserProfile enum, EnvironmentPermission, RbacPolicies, RbacPoliciesUpdate. Validators: empty profiles, approver_profiles required when requires_approval. 11 tests.
- **Task 2**: Repository update_rbac_policies() with InvalidStateError for non-draft, rowcount race check, structlog debug. 10 tests.
- **Task 3**: API PUT /admin/actions/{id}/rbac endpoint with 200/400/403/404/422 responses. 5 tests.
- **Task 4**: RBAC filtering in list_all(user_profile=...) with _action_visible_for_profile helper. New GET /catalog/actions endpoint with invisible filtering. 3 tests.
- **Task 5**: RbacEditor component with Table layout, profile multi-select, approval switch, approver profiles. Inline validation. Accessibility.
- **Task 6**: ActionForm integration: rbacPolicies state, Collapse section, validation on submit, updateActionRbac call.
- **Task 7**: Types (UserProfileType, EnvironmentPermission, RbacPolicies, RbacPoliciesUpdate) + updateActionRbac() service.
- **Task 8**: Full regression passed: 301 backend + 37 frontend = 338 tests (up from 310 baseline).
- **Code review fixes (AI)**: (1) catalog_repository: _row_to_action_detail uses _safe_parse_rbac_policies for rbac_policies (no 500 on invalid CLOB, normalized shape). (2) test_catalog_api.py: GET /catalog/actions RBAC API tests (no auth, DBOPS, client_business, dba_applicatif). (3) catalog.py: docstring on unknown-profile behavior. (4) ActionForm: separate rbacError state and Alert "Erreur contrôle d'accès (RBAC)" for RBAC validation (Story 6.4). (5) test_admin_api + test_catalog_repository: fixtures use valid RbacPolicies shape; test_row_to_action_detail_invalid_rbac_json_returns_none added.

### File List

#### New Files
- `idp-portal/backend/app/api/v1/catalog.py` — Catalog router with GET /catalog/actions and RBAC filtering
- `idp-portal/frontend/src/components/admin/RbacEditor.tsx` — RBAC policies editor component
- `idp-portal/backend/tests/unit/test_catalog_api.py` — GET /catalog/actions RBAC API tests (Story 2.3 AC #3)

#### Modified Files
- `idp-portal/backend/app/models/catalog.py` — Added UserProfile, EnvironmentPermission, RbacPolicies, RbacPoliciesUpdate
- `idp-portal/backend/app/repositories/catalog_repository.py` — Added update_rbac_policies(), list_all(user_profile=...), _safe_parse_rbac_policies in _row_to_action_detail, _rbac_policies_to_json, _parse_rbac_policies, _safe_parse_rbac_policies, _action_visible_for_profile
- `idp-portal/backend/app/api/v1/catalog.py` — Docstring on unknown-profile behavior
- `idp-portal/backend/app/api/v1/admin.py` — Added PUT /admin/actions/{id}/rbac endpoint
- `idp-portal/backend/app/main.py` — Registered catalog router
- `idp-portal/backend/tests/unit/test_catalog_models.py` — Added RBAC model validation tests (11 tests)
- `idp-portal/backend/tests/unit/test_catalog_repository.py` — RBAC repository tests, valid RBAC fixtures, test_row_to_action_detail_invalid_rbac_json_returns_none
- `idp-portal/backend/tests/unit/test_admin_api.py` — RBAC API tests (5 tests), fixtures with valid RbacPolicies shape
- `idp-portal/frontend/src/types/api.ts` — Added UserProfileType, EnvironmentPermission, RbacPolicies, RbacPoliciesUpdate
- `idp-portal/frontend/src/services/admin_service.ts` — Added updateActionRbac()
- `idp-portal/frontend/src/components/admin/ActionForm.tsx` — Integrated RbacEditor, rbacPolicies state, rbacError state and Alert for RBAC validation (Story 6.4)

## Change Log

- 2026-01-28: Story 2.3 implementation complete. All 8 tasks and 28 subtasks done. 338 tests passing (301 backend + 37 frontend). Ready for code review.
- 2026-01-28: Code review fixes applied: safe parse for rbac_policies in get_by_id, catalog API tests, RBAC error Alert, valid fixtures. Recommandation: commiter les fichiers nouveaux (catalog.py, RbacEditor.tsx, test_catalog_api.py) si pas déjà fait.

