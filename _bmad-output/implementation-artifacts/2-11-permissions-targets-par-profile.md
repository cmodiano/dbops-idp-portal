# Story 2.11 : Permissions targets par profil

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBOPS,
I want definir les targets (serveurs/bases) autorises pour un profil (liste explicite ou pattern),
So that chaque equipe ne puisse executer que sur ses propres ressources.

## Acceptance Criteria

1. **AC1 — Section « Targets autorises »** : Given un DBOPS edite un profil, When il accede a la section « Targets autorises », Then il peut choisir entre : liste de targets explicites, pattern (ex: assurance-*), ou « * » (tous).

2. **AC2 — Pattern** : Given le DBOPS choisit « Pattern », When il saisit « assurance-* », Then le profil aura acces aux targets dont le nom commence par « assurance- ».

3. **AC3 — Liste explicite** : Given le DBOPS choisit « Liste explicite », When il selectionne des targets depuis l'inventaire (autocomplete), Then seuls ces targets seront accessibles.

4. **AC4 — Filtrage execution** : Given un utilisateur execute une action, When le wizard charge les targets disponibles, Then seuls les targets autorises par ses profils (cumules) ET presents dans l'inventaire sont affiches.

5. **AC5 — Backend** : La table PROFILE_TARGET_PERMISSIONS est creee via migration SQL. Les targets sont valides contre l'inventaire interne au moment de l'execution. L'API PUT /api/v1/admin/profiles/{id}/targets enregistre les permissions. FR25b est completement satisfaite (actions + targets). FR26a est satisfaite.

## Tasks / Subtasks

- [x] Task 1 : Migration SQL — table PROFILE_TARGET_PERMISSIONS (AC: 1, 5)
  - [x] 1.1 : Creer `database/migrations/V012_create_profile_target_permissions.sql`. Colonnes : profile_id (FK PROFILES), permission_type (LIST / PATTERN / ALL), target_names (JSON array pour liste explicite), target_patterns (JSON array pour patterns comme "assurance-*"). Conventions UPPER_SNAKE, contraintes, index.
  - [x] 1.2 : Mettre a jour SCHEMA_VERSION (MERGE idempotent). Executer apres V011.

- [x] Task 2 : Backend — Modeles et repository (AC: 2, 3, 5)
  - [x] 2.1 : Creer ou etendre `backend/app/models/profile.py` : Pydantic ProfileTargetPermissionsUpdate (targets_type: "list" | "pattern" | "all", target_names?: list[str], target_patterns?: list[str]). Validation selon type.
  - [x] 2.2 : Creer `backend/app/repositories/profile_target_permission_repository.py` (ou etendre profile_repository) : get_target_permissions(profile_id), set_target_permissions(profile_id, payload). SQL brut oracledb.
  - [x] 2.3 : Fonction helper `match_targets(user_profiles, available_targets) -> list[str]` qui cumule les permissions targets et filtre contre l'inventaire. Patterns utilisant fnmatch ou regex simple.

- [x] Task 3 : Backend — API PUT /api/v1/admin/profiles/{id}/targets (AC: 2, 3, 5)
  - [x] 3.1 : Ajouter PUT /api/v1/admin/profiles/{profile_id}/targets dans `profiles.py`. Body : targets_type, target_names (si list), target_patterns (si pattern). Reponse 200 avec donnees mises a jour. Codes 400 (validation), 401, 403, 404.
  - [x] 3.2 : Proteger par require_profile("dbops"). Invalider cache RBAC si present (ou documenter pour 2.12).

- [x] Task 4 : Frontend — Section « Targets autorises » dans l'edition profil (AC: 1, 2, 3)
  - [x] 4.1 : Dans le formulaire/modal d'edition de profil (ou page detail profil), ajouter une section « Targets autorises » : radio ou select (Liste explicite / Pattern / Tous).
  - [x] 4.2 : Si « Liste explicite » : multi-select ou autocomplete des targets (mock pour l'instant : ["assurance-db01", "assurance-db02", "infra-oracle-prod"] ou API inventaire si disponible). Si « Pattern » : champ texte pour patterns (ex: "assurance-*", "infra-*"). Si « Tous » : aucun champ additionnel.
  - [x] 4.3 : Soumission : PUT /api/v1/admin/profiles/{id}/targets avec le payload. Afficher succes/erreur (toast ou message).

- [x] Task 5 : Tests et regression (AC: 5)
  - [x] 5.1 : Tests unitaires backend : repository (get/set target permissions, patterns matching), API (PUT 200, 400 validation, 404 profil, 403 non-DBOPS).
  - [x] 5.2 : Tests frontend : section Targets autorises (rendu selon type, soumission). Co-localiser avec composant.
  - [x] 5.3 : Linter, type-check, pas de regression sur profiles CRUD (2.9), permissions actions (2.10), catalog, auth.

## Dev Notes

- **Contexte metier** : FR25b — DBOPS definit les permissions d'un profil : actions (story 2.10), targets (cette story), environnements (story 2.10). Cette story complete FR25b avec la partie **targets** par profil.
- **Story 2.10** : A livre les permissions actions et environnements (table PROFILE_ACTION_PERMISSIONS, API PUT .../actions, section UI). Il s'agit maintenant d'ajouter les permissions **targets** avec un endpoint dedie et l'UI dans l'edition de profil.
- **Inventaire targets** : Pour cette story, les targets sont des noms de serveurs/bases (strings). L'inventaire reel viendra de l'API Epic 4 (donnees inventaire). Pour l'instant, mock ou liste statique en frontend, et validation backend via pattern matching.
- **Pattern matching** : Utiliser fnmatch (Python stdlib) pour les patterns comme "assurance-*". Simple et efficace.

### Ce qui existe deja (NE PAS REIMPLEMENTER)

| Element | Fichier | Role |
|---------|---------|------|
| PROFILES | V010_create_profiles.sql | Table profils, FK pour PROFILE_TARGET_PERMISSIONS |
| PROFILE_ACTION_PERMISSIONS | V011_create_profile_action_permissions.sql | Table permissions actions (story 2.10) |
| ProfileForm, ProfilesTable | frontend/src/components/admin/ | Edition profil ; ajouter section permissions targets |
| profiles_service, API profiles | frontend + backend/api/v1/profiles.py | CRUD profils + PUT .../actions ; ajouter PUT .../targets |
| require_profile("dbops") | backend/app/core/security.py | RBAC admin |

### Architecture (extrait)

- **Repository Pattern** : SQL brut, pas d'ORM. Nouvelle table PROFILE_TARGET_PERMISSIONS. Conventions UPPER_SNAKE.
- **API** : REST JSON, snake_case, wrapper `{ "data" }` / `{ "error" }`. PUT pour remplacer toutes les permissions targets d'un profil.
- **Frontend** : Reutiliser ProfileForm ou page detail profil ; section « Targets autorises ».
- **Pattern matching** : fnmatch (Python) ou RegExp (JS) pour "assurance-*" -> match "assurance-db01".

### Project Structure Notes

- Migrations : `idp-portal/database/migrations/` — **V012** (apres V011). Nom explicite `V012_create_profile_target_permissions.sql`.
- Backend : `models/profile.py` (etendre avec ProfileTargetPermissionsUpdate) ou `models/profile_permissions.py`, `repositories/profile_target_permission_repository.py` (ou methodes dans profile_repository.py), `api/v1/profiles.py` (route PUT /{profile_id}/targets).
- Frontend : `components/admin/ProfileForm.tsx` ou `ProfileTargetPermissionsSection.tsx`, `services/profiles_service.ts` (putProfileTargets), `types/api.ts`.

### References

- [Source: epics.md — Story 2.11, FR25b, FR26a]
- [Source: architecture.md — Repository Pattern, API format, RBAC]
- [Source: prd.md — FR25b targets, FR26a validation inventaire]

---

## Developer Context (Guardrails)

### Technical requirements

- **Backend** : Python 3.12+, FastAPI, Pydantic v2. Modeles stricts pour ProfileTargetPermissionsUpdate : selon targets_type, exiger target_names (list) ou target_patterns (list) ou aucun pour "all". Repository : SQL brut oracledb. Pattern matching avec fnmatch. Gestion erreurs IdpError, 404 (profil), 400 (validation).
- **Frontend** : TypeScript strict, React, Ant Design 6. Section conditionnelle selon type (liste / pattern / tous). Mock inventory pour l'instant. Types API snake_case.
- **DB** : Nouvelle table PROFILE_TARGET_PERMISSIONS. Colonnes : profile_id (FK), permission_type (LIST/PATTERN/ALL), target_names (CLOB JSON array), target_patterns (CLOB JSON array). FK profile_id → PROFILES(id).

### Architecture compliance

- Nouvelle table et nouveau endpoint sous /api/v1/admin/profiles. Reponses `{ "data": ... }` / `{ "error": ... }`. Dates ISO 8601 UTC. RBAC : require_profile("dbops") sur PUT .../targets.

### Library / framework requirements

- Aucune nouvelle dependance. FastAPI, Pydantic, React, Ant Design 6, python-oracledb. Pour multi-select targets : reutiliser Select ou AutoComplete Ant Design. Pour pattern matching backend : fnmatch (stdlib).

### File structure requirements

- Migrations : `idp-portal/database/migrations/V012_create_profile_target_permissions.sql`.
- Backend : `models/profile.py` (etendre) ou `models/profile_permissions.py`, `repositories/profile_target_permission_repository.py` (ou methodes dans profile_repository.py), `api/v1/profiles.py` (PUT /{profile_id}/targets).
- Frontend : composants admin (ProfileForm ou ProfileTargetPermissionsSection), service putProfileTargets(profileId, payload), types dans api.ts.

### Testing requirements

- Backend : tests unitaires repository (get/set target permissions, pattern matching fnmatch), API (PUT 200, 400, 404, 403).
- Frontend : tests section Targets autorises (affichage selon type, soumission, erreur). Co-localiser avec le composant.
- Pas de regression sur tests 2.9 (profiles CRUD), 2.10 (permissions actions), catalog, auth.

---

## Previous Story Intelligence (2.10)

- **Permissions actions** : Story 2.10 a livre table PROFILE_ACTION_PERMISSIONS (V011), ProfileActionPermissionsUpdate (actions_type: list/pattern/all, action_ids, tag_patterns, environments), repository profile_action_permission_repository, route PUT /admin/profiles/{id}/actions, section UI « Actions autorisees » dans formulaire profil.
- **Pattern a suivre** : Cette story (2.11) suit le meme pattern que 2.10 : nouvelle table V012, nouveau modele ProfileTargetPermissionsUpdate, nouveau repository/methodes, nouvelle route PUT .../targets, nouvelle section UI « Targets autorises ».
- **Fichiers a toucher** : migration V012, modeles profile (etendre), repository permissions targets, API profiles.py (PUT .../targets), frontend (formulaire profil : section Targets autorises).

---

## Git Intelligence Summary

- Contexte recent : stories 2.9 (profils dynamiques), 2.10 (permissions actions). Structure monorepo idp-portal, backend FastAPI, frontend React/Vite, migrations V000–V011. S'appuyer sur les memes conventions (snake_case API, repository SQL brut, composants admin, pattern matching avec fnmatch).

---

## Project Context Reference

- [Source: _bmad-output/planning-artifacts/architecture.md — Repository Pattern, API, RBAC, structure projet]
- [Source: _bmad-output/planning-artifacts/epics.md — Story 2.11, 2.10, 2.12, FR25b, FR26a]
- [Source: _bmad-output/planning-artifacts/prd.md — FR25b targets, FR26a validation inventaire]
- [Source: idp-portal/database/migrations/V010_create_profiles.sql — PROFILES]
- [Source: idp-portal/database/migrations/V011_create_profile_action_permissions.sql — PROFILE_ACTION_PERMISSIONS (story 2.10)]
- [Source: idp-portal/backend/app/api/v1/profiles.py — Router profiles existant avec PUT .../actions]
- [Source: idp-portal/backend/app/repositories/profile_repository.py — CRUD profils]

---

## Story Completion Status

- **Status** : review
- **Sprint status** : development_status["2-11-permissions-targets-par-profile"] = "review"

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- Migration V012 : table PROFILE_TARGET_PERMISSIONS (profile_id, PERMISSION_TYPE LIST/PATTERN/ALL, TARGET_NAMES_JSON, TARGET_PATTERNS_JSON), MERGE SCHEMA_VERSION.
- Backend : ProfileTargetPermissionsUpdate/Response dans `models/profile.py` ; `repositories/profile_target_permission_repository.py` (get/set_target_permissions, match_targets avec fnmatch).
- API : PUT/GET `/api/v1/admin/profiles/{id}/targets` dans `api/v1/profiles.py`, require_profile("dbops").
- Frontend : section « Targets autorisés » dans ProfileForm (Liste explicite / Pattern / Tous), mock MOCK_TARGET_OPTIONS, getProfileTargets/putProfileTargets dans profiles_service, types dans api.ts.
- Tests : test_profile_target_permission_repository.py (get/set, match_targets) ; test_profiles_api.py (GET/PUT targets 200, 422, 404, 403) ; ProfileForm.test.tsx (section Targets, putProfileTargets on submit, getProfileTargets load). Suite backend 440 passed, frontend ProfileForm 10 passed.

### Senior Developer Review (AI)

**Review Date:** 2026-01-28
**Review Outcome:** Changes Requested → Fixed

**Action Items:**
- [x] [M2] profiles_service.ts docstring manquait Story 2.11 — corrigé
- [!] [M1] Note: fichiers non liés modifiés dans git (admin.py pagination Query, catalog.py validation exclusive) — bug fixes à committer séparément

### Change Log

- 2026-01-28 : Story 2.11 implémentée (migration V012, backend repository + API, frontend section Targets, tests).
- 2026-01-28 : Code review — M2 corrigé (docstring profiles_service.ts), M1 documenté (bug fixes non liés).

### File List

- idp-portal/database/migrations/V012_create_profile_target_permissions.sql
- idp-portal/backend/app/models/profile.py
- idp-portal/backend/app/repositories/profile_target_permission_repository.py
- idp-portal/backend/app/api/v1/profiles.py
- idp-portal/backend/tests/unit/test_profile_target_permission_repository.py
- idp-portal/backend/tests/unit/test_profiles_api.py
- idp-portal/frontend/src/types/api.ts
- idp-portal/frontend/src/services/profiles_service.ts
- idp-portal/frontend/src/components/admin/ProfileForm.tsx
- idp-portal/frontend/src/components/admin/ProfileForm.test.tsx
- _bmad-output/implementation-artifacts/sprint-status.yaml
- _bmad-output/implementation-artifacts/2-11-permissions-targets-par-profile.md
