# Story 2.10 : Permissions actions par profil

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBOPS,
I want définir les actions autorisées pour un profil (liste explicite ou pattern/tags),
So that chaque profil a accès uniquement aux actions nécessaires.

## Acceptance Criteria

1. **AC1 — Section « Actions autorisées »** : Given un DBOPS édite un profil, When il accède à la section « Actions autorisées », Then il peut choisir entre : liste d’actions spécifiques, pattern par tags, ou « * » (toutes).

2. **AC2 — Pattern par tags** : Given le DBOPS choisit « Pattern par tags », When il saisit « tag:oracle, tag:provisioning », Then le profil aura accès à toutes les actions ayant ces tags.

3. **AC3 — Liste d’actions** : Given le DBOPS choisit « Liste d’actions », When il sélectionne des actions spécifiques dans un multi-select, Then seules ces actions seront accessibles.

4. **AC4 — Environnements autorisés** : Given le DBOPS définit les environnements autorisés, When il sélectionne [DEV, STAGING], Then le profil ne pourra exécuter que sur ces environnements.

5. **AC5 — Backend** : La table PROFILE_ACTION_PERMISSIONS est créée via migration SQL. L’API PUT /api/v1/admin/profiles/{id}/actions enregistre les permissions. FR25b est partiellement satisfaite (actions).

## Tasks / Subtasks

- [x] Task 1 : Migration SQL — table PROFILE_ACTION_PERMISSIONS et environnements (AC: 4, 5)
  - [x] 1.1 : Créer `database/migrations/V011_create_profile_action_permissions.sql`. Colonnes selon modèle : profile_id (FK PROFILES), type d’autorisation (list / pattern / all), données (actions list ou patterns tags), environnements (liste ou JSON). Conventions UPPER_SNAKE, contraintes, index. Une ligne par profil (ou schéma normalisé : PROFILE_ACTIONS + PROFILE_ENVIRONMENTS si séparés).
  - [x] 1.2 : Mettre à jour SCHEMA_VERSION (MERGE idempotent). Exécuter après V010.

- [x] Task 2 : Backend — Modèles et repository (AC: 2, 3, 4, 5)
  - [x] 2.1 : Créer ou étendre `backend/app/models/profile.py` : Pydantic ProfileActionPermissionsUpdate (actions_type: "list" | "pattern" | "all", action_ids?: list[int], tag_patterns?: list[str], environments?: list[str]). Validation selon type.
  - [x] 2.2 : Créer `backend/app/repositories/profile_action_permission_repository.py` (ou étendre profile_repository) : get_actions_permissions(profile_id), set_actions_permissions(profile_id, payload). SQL brut oracledb.

- [x] Task 3 : Backend — API PUT /api/v1/admin/profiles/{id}/actions (AC: 2, 3, 4, 5)
  - [x] 3.1 : Ajouter PUT /api/v1/admin/profiles/{profile_id}/actions dans `profiles.py`. Body : actions_type, action_ids (si list), tag_patterns (si pattern), environments. Réponse 200 avec données mises à jour. Codes 400 (validation), 401, 403, 404.
  - [x] 3.2 : Protéger par require_profile("dbops"). Invalider cache RBAC si présent (ou documenter pour 2.12).

- [x] Task 4 : Frontend — Section « Actions autorisées » dans l’édition profil (AC: 1, 2, 3, 4)
  - [x] 4.1 : Dans le formulaire/modal d’édition de profil (ou page détail profil), ajouter une section « Actions autorisées » : radio ou select (Liste d’actions / Pattern par tags / Toutes).
  - [x] 4.2 : Si « Liste d’actions » : multi-select des actions (chargées depuis GET /api/v1/catalog/actions ou admin/actions). Si « Pattern par tags » : champ tags (multi-select ou saisie tag:oracle, tag:provisioning). Si « Toutes » : aucun champ additionnel.
  - [x] 4.3 : Champ « Environnements autorisés » : multi-select (DEV, STAGING, PROD, etc.) aligné sur les valeurs du catalogue/architecture.
  - [x] 4.4 : Soumission : PUT /api/v1/admin/profiles/{id}/actions avec le payload. Afficher succès/erreur (toast ou message).

- [x] Task 5 : Tests et régression (AC: 5)
  - [x] 5.1 : Tests unitaires backend : repository (get/set permissions), API (PUT 200, 400 validation, 404 profil, 403 non-DBOPS).
  - [x] 5.2 : Tests frontend : section Actions autorisées (rendu selon type, soumission). Co-localiser avec composant.
  - [x] 5.3 : Linter, type-check, pas de régression sur profiles CRUD (2.9), catalog, auth.

## Dev Notes

- **Contexte métier** : FR25b — DBOPS définit les permissions d’un profil : actions (liste ou pattern/tags), targets (story 2.11), environnements. Cette story couvre uniquement la partie **actions** et **environnements** par profil.
- **Story 2.9** : Les profils existent (table PROFILES, CRUD, ProfileForm, ProfilesTable). Il s’agit d’ajouter la gestion des permissions « actions » et « environnements » par profil, avec un endpoint dédié et l’UI dans l’édition de profil.
- **Fichiers à toucher** : migration V011, modèles profile (ou nouveau profile_permissions), repository profile_action_permission (ou étendre profile_repository), API profiles.py (PUT …/actions), frontend (formulaire profil : section Actions autorisées + Environnements).

### Ce qui existe déjà (NE PAS RÉIMPLÉMENTER)

| Élément | Fichier | Rôle |
|--------|---------|------|
| PROFILES | V010_create_profiles.sql | Table profils, FK pour PROFILE_ACTION_PERMISSIONS |
| ProfileForm, ProfilesTable | frontend/src/components/admin/ | Édition profil ; ajouter section permissions actions/envs |
| profiles_service, GET/POST/PUT/DELETE profiles | frontend + backend/api/v1/profiles.py | CRUD profils ; ajouter appel PUT …/actions |
| require_profile("dbops") | backend/app/core/security.py | RBAC admin |
| Catalogue actions | GET /api/v1/admin/actions ou catalog | Liste des actions pour le multi-select |
| TAGS | V007, GET /api/v1/tags | Tags existants pour pattern par tags |

### Architecture (extrait)

- **Repository Pattern** : SQL brut, pas d’ORM. Nouvelle table PROFILE_ACTION_PERMISSIONS (ou schéma normalisé). Conventions UPPER_SNAKE.
- **API** : REST JSON, snake_case, wrapper `{ "data" }` / `{ "error" }`. PUT pour remplacer toutes les permissions actions/envs d’un profil.
- **Frontend** : Réutiliser ProfileForm ou page détail profil ; section « Actions autorisées » + « Environnements autorisés ».

### Project Structure Notes

- Migrations : `idp-portal/database/migrations/` — **V011** (après V010). Nom explicite `V011_create_profile_action_permissions.sql`.
- Backend : `models/profile.py` (étendre) ou `models/profile_permissions.py`, `repositories/profile_action_permission_repository.py` (ou méthode dans profile_repository), `api/v1/profiles.py` (route PUT /{id}/actions).
- Frontend : `components/admin/ProfileForm.tsx` ou `ProfilePermissionsSection.tsx`, `services/profiles_service.ts` (putProfileActions), `types/api.ts`.

### References

- [Source: epics.md — Story 2.10, FR25b]
- [Source: architecture.md — Repository Pattern, API format, RBAC]
- [Source: prd.md — FR25b, permissions par profil]

---

## Developer Context (Guardrails)

### Technical requirements

- **Backend** : Python 3.12+, FastAPI, Pydantic v2. Modèles stricts pour ProfileActionPermissionsUpdate : selon actions_type, exiger action_ids (list) ou tag_patterns (list) ou aucun pour "all". Environnements : liste de chaînes (DEV, STAGING, PROD). Repository : SQL brut oracledb. Gestion erreurs IdpError, 404 (profil), 400 (validation).
- **Frontend** : TypeScript strict, React, Ant Design 6. Section conditionnelle selon type (liste / pattern / toutes). Multi-select actions depuis API catalogue/admin. Types API snake_case.
- **DB** : Nouvelle table PROFILE_ACTION_PERMISSIONS. Peut stocker : profile_id, permission_type (LIST/PATTERN/ALL), action_ids (JSON array ou table de liaison), tag_patterns (JSON array), environments (JSON array). Ou tables normalisées (PROFILE_ACTIONS, PROFILE_ENVIRONMENTS) selon choix de schéma. FK profile_id → PROFILES(id).

### Architecture compliance

- Nouvelle table et nouveau endpoint sous /api/v1/admin/profiles. Réponses `{ "data": ... }` / `{ "error": ... }`. Dates ISO 8601 UTC. RBAC : require_profile("dbops") sur PUT …/actions.

### Library / framework requirements

- Aucune nouvelle dépendance. FastAPI, Pydantic, React, Ant Design 6, python-oracledb. Pour multi-select actions : réutiliser Select ou TreeSelect Ant Design ; données depuis API existante.

### File structure requirements

- Migrations : `idp-portal/database/migrations/V011_create_profile_action_permissions.sql`.
- Backend : `models/profile.py` ou `models/profile_permissions.py`, `repositories/profile_action_permission_repository.py` (ou méthodes dans profile_repository.py), `api/v1/profiles.py` (PUT /{profile_id}/actions).
- Frontend : composants admin (ProfileForm ou ProfilePermissionsSection), service putProfileActions(profileId, payload), types dans api.ts.

### Testing requirements

- Backend : tests unitaires repository (get/set permissions, contraintes), API (PUT 200, 400, 404, 403).
- Frontend : tests section Actions autorisées (affichage selon type, soumission, erreur). Co-localiser avec le composant.
- Pas de régression sur tests 2.9 (profiles CRUD), catalog, auth.

---

## Previous Story Intelligence (2.9)

- **Profiles CRUD** : Story 2.9 a livré table PROFILES (V010), ProfileCreate/ProfileUpdate/ProfileResponse/ProfileListItem, profile_repository.py (CRUD), router GET/POST/PUT/DELETE /admin/profiles, AdminPage onglets « Actions » | « Profiles », ProfileForm (modal), ProfilesTable, profiles_service. Permission_count = 0 dans ProfileListItem en attendant 2.10.
- **Fichiers modifiés en 2.9** : V010, profile.py, profile_repository.py, profiles.py, AdminPage.tsx, ProfileForm.tsx, ProfilesTable.tsx, profiles_service.ts, api_client (204 no body). Pour 2.10 : ajouter V011, modèle permissions actions/envs, repository permissions, route PUT …/actions, section UI dans formulaire ou détail profil.
- **Patterns** : Même style API (wrapper data/error), require_profile("dbops"), validation Pydantic. Formulaire Ant Design (Form, Select, Switch). Co-localiser tests composants.

---

## Git Intelligence Summary

- Contexte récent : stories 2.7–2.9 (connecteurs, CAB supprimé, profils dynamiques). Structure monorepo idp-portal, backend FastAPI, frontend React/Vite, migrations V000–V010. S’appuyer sur les mêmes conventions (snake_case API, repository SQL brut, composants admin).

---

## Project Context Reference

- [Source: _bmad-output/planning-artifacts/architecture.md — Repository Pattern, API, RBAC, structure projet]
- [Source: _bmad-output/planning-artifacts/epics.md — Story 2.10, 2.11–2.14, FR25b]
- [Source: _bmad-output/planning-artifacts/prd.md — FR25b, permissions par profil]
- [Source: idp-portal/database/migrations/V010_create_profiles.sql — PROFILES]
- [Source: idp-portal/backend/app/api/v1/profiles.py — Router profiles existant]
- [Source: idp-portal/backend/app/repositories/profile_repository.py — CRUD profils]

---

## Story Completion Status

- **Status** : review
- **Sprint status** : development_status["2-10-permissions-actions-par-profile"] = "in-progress" → "review" (après complétion)

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- Task 1 : Migration V011 créée (PROFILE_ACTION_PERMISSIONS, une ligne par profil, colonnes JSON CLOB), SCHEMA_VERSION MERGE.
- Task 2 : ProfileActionPermissionsUpdate / ProfileActionPermissionsResponse dans profile.py ; profile_action_permission_repository.py (get_actions_permissions, set_actions_permissions avec MERGE SQL).
- Task 3 : PUT /admin/profiles/{id}/actions et GET /admin/profiles/{id}/actions dans profiles.py ; require_profile("dbops") ; 404 si profil absent.
- Task 4 : Section « Actions autorisées » dans ProfileForm (édition uniquement) : radio list/pattern/all, multi-select actions ou tags, environnements ; chargement getProfileActions + listActions + getTags ; soumission putProfileActions après update profile.
- Task 5 : Tests unitaires backend (test_profiles_api.py : GET/PUT actions 200, 404, 403, validation ; test_profile_action_permission_repository.py get/set). Tests frontend ProfileForm (section visible en edit, putProfileActions appelé au submit). 414 tests backend + 8 tests ProfileForm passent.

### Senior Developer Review (AI)

**Review Date:** 2026-01-28
**Review Outcome:** Changes Requested → Fixed

**Action Items:**
- [x] [M1] ProfileForm: Gestion erreur partielle si putProfileActions échoue après update profil — ajouté try/catch + warning alert
- [x] [M2] V011: Index redondant sur PROFILE_ID (déjà PK) — supprimé CREATE INDEX
- [x] [M3] Repository: Validation CLOB incomplète pour tag_patterns/environments — ajouté all(isinstance(x, str))
- [x] [M4] Tests: Couverture lacunaire — ajouté test GET pattern, test malformed JSON, test frontend putProfileActions failure

### Change Log

- 2026-01-28: Story implémentée (Tasks 1–5).
- 2026-01-28: Code review — 4 issues M corrigées (erreur partielle frontend, index redondant, validation CLOB, tests).

### File List

- idp-portal/database/migrations/V011_create_profile_action_permissions.sql
- idp-portal/backend/app/models/profile.py
- idp-portal/backend/app/repositories/profile_action_permission_repository.py
- idp-portal/backend/app/api/v1/profiles.py
- idp-portal/frontend/src/types/api.ts
- idp-portal/frontend/src/services/profiles_service.ts
- idp-portal/frontend/src/components/admin/ProfileForm.tsx
- idp-portal/backend/tests/unit/test_profiles_api.py
- idp-portal/backend/tests/unit/test_profile_action_permission_repository.py
- idp-portal/frontend/src/components/admin/ProfileForm.test.tsx
- _bmad-output/implementation-artifacts/sprint-status.yaml
- _bmad-output/implementation-artifacts/2-10-permissions-actions-par-profile.md
