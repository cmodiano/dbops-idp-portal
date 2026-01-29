# Story 2.9 : Gestion des profils dynamiques

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBOPS,
I want créer et gérer des profils dynamiques avec leur mapping vers un groupe AD,
So that je peux définir des permissions granulaires pour chaque équipe ou rôle.

## Acceptance Criteria

1. **AC1 — Section Profiles** : Given un DBOPS accède à la section "Profiles" dans l'admin, When il clique sur "Nouveau profil", Then un formulaire s'affiche avec : nom, description, groupe AD associé, flags (is_admin, is_auditor).

2. **AC2 — Création** : Given le DBOPS crée un profil "Assurance" avec groupe AD "GRP-IDP-ASSURANCE", When il sauvegarde, Then le profil est créé et le mapping AD est enregistré.

3. **AC3 — Liste** : Given le DBOPS consulte la liste des profils, When la page se charge, Then tous les profils sont affichés avec : nom, groupe AD, nombre de permissions, date de création.

4. **AC4 — Édition et cache** : Given le DBOPS édite un profil existant, When il modifie le groupe AD, Then le nouveau mapping s'applique immédiatement (cache invalidé).

5. **AC5 — Backend** : La table PROFILES est créée via migration SQL. L'API CRUD /api/v1/admin/profiles est implémentée. FR25a est satisfaite.

## Tasks / Subtasks

- [x] Task 1: Migration SQL — table PROFILES (AC: 5)
  - [x] 1.1: Créer `database/migrations/V010_create_profiles.sql`. Colonnes : id, name (unique), description, ad_group (VARCHAR2, groupe AD), is_admin (NUMBER(1)), is_auditor (NUMBER(1)), created_at, updated_at. Suivre conventions UPPER_SNAKE, contraintes, index.
  - [x] 1.2: Mettre à jour SCHEMA_VERSION (MERGE idempotent). Exécuter migrations dans l'ordre (V010 après V009).

- [x] Task 2: Backend — Modèles et repository (AC: 2, 4, 5)
  - [x] 2.1: Créer `backend/app/models/profile.py` : Pydantic ProfileCreate, ProfileUpdate, ProfileResponse, ProfileListItem (snake_case, champs alignés DB). Validation : name et ad_group requis, is_admin/is_auditor booléens.
  - [x] 2.2: Créer `backend/app/repositories/profile_repository.py` : SQL brut via python-oracledb, CRUD (create, get_by_id, get_all, update, delete). Pas d'ORM. Encapsuler requêtes dans des méthodes dédiées.
  - [x] 2.3: Pour la liste, afficher "nombre de permissions" : 0 par défaut (table PROFILE_ACTION_PERMISSIONS créée en 2.10). Soit colonne calculée / sous-requête future, soit champ fixe 0 dans ProfileListItem pour l’instant.

- [x] Task 3: Backend — API CRUD /api/v1/admin/profiles (AC: 2, 3, 4, 5)
  - [x] 3.1: Créer `backend/app/api/v1/profiles.py` (ou étendre admin) : GET /api/v1/admin/profiles (liste), GET /api/v1/admin/profiles/{id}, POST /api/v1/admin/profiles (201), PUT /api/v1/admin/profiles/{id}, DELETE /api/v1/admin/profiles/{id}. Réponses wrappées { "data": ... } ou { "error": ... }. Codes HTTP : 200, 201, 204, 400, 401, 403, 404.
  - [x] 3.2: Protéger les routes par `require_profile("dbops")` (middleware RBAC existant). Injecter pool DB et current_user via deps.
  - [x] 3.3: Monter le router dans `main.py` (prefix /api/v1, tags ["admin"] ou ["profiles"]).
  - [x] 3.4: Invalidation cache : si un cache RBAC ou profil existe (ex. TTL 1 min), invalider à la création / mise à jour / suppression d'un profil. Sinon, documenter que le cache sera invalide lorsque le service RBAC (2.10–2.12) sera en place.

- [x] Task 4: Frontend — Section Profiles et formulaire (AC: 1, 2, 3, 4)
  - [x] 4.1: Ajouter une section "Profiles" dans l'admin. Option A : onglets "Actions" | "Profiles" sur AdminPage. Option B : sous-route /admin/profiles. Choisir selon cohérence avec l'existant (AdminPage actuel = liste actions uniquement).
  - [x] 4.2: Page ou vue Liste : tableau avec colonnes nom, groupe AD, nombre de permissions, date de création. Bouton "Nouveau profil". Actions : modifier, supprimer (avec confirmation).
  - [x] 4.3: Formulaire (modal ou page) : champs nom, description, groupe AD, is_admin (Switch), is_auditor (Switch). Validation inline (nom et groupe AD requis). Soumission → POST ou PUT.
  - [x] 4.4: Service `profiles_service.ts` (ou `admin_service` étendu) : getProfiles(), getProfile(id), createProfile(payload), updateProfile(id, payload), deleteProfile(id). Appels vers /api/v1/admin/profiles.

- [x] Task 5: Tests et régression (AC: 5)
  - [x] 5.1: Tests unitaires backend : `test_profile_repository.py` (CRUD, contraintes), `test_profiles_api.py` (CRUD, 401/403 si non-DBOPS, 404, validation 400).
  - [x] 5.2: Tests frontend : composants liste et formulaire profiles (rendu, soumission, erreurs). Co-localiser avec les composants (ex. `ProfilesTable.test.tsx`, `ProfileForm.test.tsx`).
  - [x] 5.3: Linter, type-check, suite existante. Pas de régression sur admin actions, catalog, auth.

## Dev Notes

- **Contexte métier** : FR25a — DBOPS crée et gère des profils dynamiques avec mapping vers un groupe AD. Les permissions (actions, targets, environnements) par profil sont introduites en 2.10–2.11. Cette story pose uniquement la fondation : entité Profil + mapping AD.
- **Ancien RBAC** : Aujourd’hui, RBAC par action (rbac_policies dans ACTIONS_CATALOG, RbacEditor) et profil utilisateur (UserProfile enum). Les stories 2.9–2.14 mènent au nouveau modèle : profils dynamiques (table PROFILES) + permissions par profil. Ne pas supprimer l’ancien RBAC dans cette story ; le refactoring est prévu en 2.14.
- **Fichiers à toucher** : `database/migrations/V010_create_profiles.sql`, `backend/app/models/profile.py`, `backend/app/repositories/profile_repository.py`, `backend/app/api/v1/profiles.py` (ou admin), `main.py`, `frontend` (AdminPage ou /admin/profiles, formulaire, service, types).

### Ce qui existe déjà (NE PAS RÉIMPLÉMENTER)

| Élément | Fichier | Rôle |
|--------|---------|------|
| require_profile | `backend/app/core/security.py` | Décorateur RBAC pour routes admin |
| Admin router | `backend/app/api/v1/admin.py` | CRUD actions ; modèle pour ajouter routes profiles |
| AdminPage | `frontend/src/pages/AdminPage.tsx` | Liste actions, modal ActionForm ; base pour ajouter onglets ou lien Profiles |
| api client | `frontend/src/services/*` | Wrapper fetch, auth ; réutiliser pour profiles |
| Repository pattern | `backend/app/repositories/*` | SQL brut, pool Oracle ; même pattern pour profile_repository |

### Architecture (extrait)

- **Repository Pattern** : SQL brut, pas d’ORM. PROFILES en table dédiée. Conventions naming (UPPER_SNAKE, FK si nécessaire).
- **API** : REST JSON, snake_case, wrapper `{ "data" }` / `{ "error" }`. Versioning /api/v1.
- **Frontend** : React, Ant Design 6, AdminPage existant. Structure `components/admin/`, `services/`, `types/api.ts`.

### Project Structure Notes

- Migrations : `idp-portal/database/migrations/` — **V010** (après V009). Nom explicite type `V010_create_profiles.sql`.
- Backend : `models/profile.py`, `repositories/profile_repository.py`, `api/v1/profiles.py` (ou sous-router dans admin).
- Frontend : `pages/AdminPage` ou `pages/ProfilesPage`, `components/admin/ProfileForm.tsx`, `ProfilesTable.tsx`, `services/profiles_service.ts` (ou admin_service), `types/api.ts` (types Profile*).

### References

- [Source: epics.md — Story 2.9, FR25a]
- [Source: architecture.md — Repository Pattern, API format, RBAC]
- [Source: prd.md — FR25a, groupes AD, profils dynamiques]

---

## Developer Context (Guardrails)

### Technical requirements

- **Backend** : Python 3.12+, FastAPI, Pydantic v2. Modèles Pydantic stricts (name, ad_group requis). Repository : SQL brut oracledb, pas d’ORM. Gestion explicite des erreurs (IdpError, 404, 400).
- **Frontend** : TypeScript strict, React, Ant Design 6. Formulaire contrôlé, validation avant submit. Types API alignés sur le backend (snake_case dans les appels).
- **DB** : Oracle, migrations séquentielles. Pas de modification des tables USERS ou ACTIONS_CATALOG dans cette story.

### Architecture compliance

- Nouvelle table PROFILES et nouveau module API profiles. Pas de changement aux routes catalog ou auth. RBAC admin : `require_profile("dbops")` sur toutes les routes profiles.
- Réponses API : `{ "data": { ... } }` ou `{ "error": { "code", "message", "details" } }`. Dates ISO 8601 UTC.

### Library / framework requirements

- Aucune nouvelle dépendance côté backend ou frontend. FastAPI, Pydantic, React, Ant Design 6, python-oracledb.

### File structure requirements

- Migrations : `idp-portal/database/migrations/V010_create_profiles.sql`.
- Backend : `backend/app/models/profile.py`, `backend/app/repositories/profile_repository.py`, `backend/app/api/v1/profiles.py` (ou équivalent), enregistrement dans `main.py`.
- Frontend : composants admin profiles, service API, types dans `api.ts`. Structure par feature (admin/) conservée.

### Testing requirements

- Backend : tests unitaires repository (CRUD, unicité name) et API (CRUD, auth, validation).
- Frontend : tests composants liste + formulaire (rendu, submit, erreurs). Co-localiser les tests avec les composants.
- Pas de régression sur tests existants (catalog, admin actions, auth).

---

## Previous Story Intelligence (2.8)

- **ChangeType / Admin** : Story 2.8 a simplifié ChangeType (CAB retiré), migrations V009, catalog_repository (parse/serialize), ChangeTypeConfig, ActionForm. Patterns utiles : mise à jour ciblée de modèles et repository, migration de données, tests API et composants.
- **Fichiers modifiés en 2.8** : `catalog.py`, `catalog_repository.py`, `admin.py`, `api.ts`, `ChangeTypeConfig.tsx`, `ActionForm.tsx`, V009. Pour 2.9 : nouveaux fichiers profiles (models, repository, API, UI) + V010 ; pas de modification du catalog.
- **Tests** : Conserver le style des tests 2.8 (fixtures, client FastAPI, mocks DB si utilisé). Vérifier que la suite admin et catalog reste verte après ajout des tests profiles.

---

## Git Intelligence Summary

- Derniers commits : "New version", "nouvelle version", "First commit". Peu de contexte technique dans les messages. S’appuyer sur la structure actuelle (monorepo idp-portal, backend FastAPI, frontend React/Vite, migrations V000–V009) et les patterns des stories 2.7–2.8.

---

## Project Context Reference

- [Source: _bmad-output/planning-artifacts/architecture.md — Repository Pattern, API, RBAC, structure projet]
- [Source: _bmad-output/planning-artifacts/epics.md — Story 2.9, 2.10–2.14, FR25a–FR25d]
- [Source: _bmad-output/planning-artifacts/prd.md — FR25a, groupes AD, profils dynamiques]
- [Source: idp-portal/database/migrations/V001_create_users.sql — USERS ; pas de modification]
- [Source: idp-portal/backend/app/api/v1/admin.py — Router admin existant]

---

## Story Completion Status

- **Status** : review
- **Sprint status** : development_status["2-9-gestion-des-profiles-dynamiques"] = "review"

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- **Task 1** : V010_create_profiles.sql créée (PROFILES, SEQ_PROFILES, UK_PROFILES_NAME, CK IS_ADMIN/IS_AUDITOR, IDX). MERGE SCHEMA_VERSION.
- **Task 2** : profile.py (ProfileCreate, ProfileUpdate, ProfileResponse, ProfileListItem). profile_repository.py : CRUD, get_connection, IntegrityError → InvalidStateError (DUPLICATE_NAME). permission_count = 0 dans ProfileListItem (2.10).
- **Task 3** : profiles.py router (GET/POST/PUT/DELETE /admin/profiles), require_profile("dbops"). Inclus dans admin router. Cache : documenté (invalidation lorsque RBAC 2.10–2.12).
- **Task 4** : Onglets AdminPage "Actions" | "Profiles". ProfilesTable (liste), ProfileForm (modal), profiles_service. api_client : 204 → skip JSON (DELETE).
- **Task 5** : test_profile_repository.py (row conversions, CRUD, duplicate name), test_profiles_api.py (CRUD, 401/403, 404, 400 validation/duplicate). ProfileForm.test, ProfilesTable.test. Backend 400 tests, frontend 142 tests ; aucune régression.

### Change Log

- 2026-01-28: Story 2.9 implémentée (migration V010, backend profiles CRUD, frontend section Profiles, tests backend + frontend).

### File List

- idp-portal/database/migrations/V010_create_profiles.sql
- idp-portal/backend/app/models/profile.py
- idp-portal/backend/app/repositories/profile_repository.py
- idp-portal/backend/app/api/v1/profiles.py
- idp-portal/backend/app/api/v1/admin.py
- idp-portal/backend/tests/unit/test_profile_repository.py
- idp-portal/backend/tests/unit/test_profiles_api.py
- idp-portal/frontend/src/types/api.ts
- idp-portal/frontend/src/services/api_client.ts
- idp-portal/frontend/src/services/profiles_service.ts
- idp-portal/frontend/src/components/admin/ProfileForm.tsx
- idp-portal/frontend/src/components/admin/ProfileForm.test.tsx
- idp-portal/frontend/src/components/admin/ProfilesTable.tsx
- idp-portal/frontend/src/components/admin/ProfilesTable.test.tsx
- idp-portal/frontend/src/components/admin/index.ts
- idp-portal/frontend/src/pages/AdminPage.tsx
- _bmad-output/implementation-artifacts/sprint-status.yaml
- _bmad-output/implementation-artifacts/2-9-gestion-des-profiles-dynamiques.md
