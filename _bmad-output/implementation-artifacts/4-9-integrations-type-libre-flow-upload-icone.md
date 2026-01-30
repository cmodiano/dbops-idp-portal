# Story 4.9 : Intégrations — type libre, flow d’auth et upload d’icône

Status: review

<!-- Story ajoutée hors Epic 2 (terminé). Positionnée dans Epic 4 (Exécution & suivi) car les intégrations alimentent les connecteurs d'exécution. -->

## Story

As a **DBOPS**,
I want **définir une intégration avec un type libre (nom de plateforme), un flow d'authentification, une icône uploadée, l'URL et la référence Vault**,
So that **je peux ajouter demain une nouvelle plateforme sans changer le code : je choisis le nom, j'uploade l'icône, je définis l'URL, le flow de connexion et le secret Vault**.

## Acceptance Criteria

1. **AC1 — Type libre**
   **Given** un DBOPS crée ou modifie une intégration,
   **When** il renseigne le type (ou « nom de plateforme »),
   **Then** le type est une chaîne libre (saisie texte, 1–100 caractères), pas une liste figée ; aucune modification de code n'est requise pour ajouter une nouvelle plateforme.

2. **AC2 — Flow d'authentification**
   **Given** un DBOPS crée ou modifie une intégration,
   **When** il configure l'authentification,
   **Then** il peut choisir un flow parmi : token (Bearer), basic (username/password), basic_then_token (user/pass puis échange pour token), pat (Personal Access Token). Ce flow est persisté et utilisé par le moteur d'exécution pour savoir comment utiliser le secret Vault (clés attendues, méthode d'auth).

3. **AC3 — Upload d'icône**
   **Given** un DBOPS crée ou modifie une intégration,
   **When** il souhaite associer une icône,
   **Then** il peut uploader un fichier image (PNG, JPEG, SVG ou équivalent) ; le backend stocke l'icône (ou une référence/URL) et l'affichage dans la liste et le formulaire utilise cette icône. L'option « URL d'icône » (saisie manuelle) reste possible.

4. **AC4 — Champs existants conservés**
   **Given** une intégration,
   **Then** les champs nom (unique), URL de base, référence credentials (Vault) restent tels quels ; le formulaire inclut : nom, type (libre), URL, flow (select), référence Vault, icône (upload ou URL).

5. **AC5 — Rétrocompatibilité**
   **Given** des intégrations existantes avec type enum (aap, servicenow, etc.),
   **When** la migration est appliquée,
   **Then** les types existants restent valides (chaîne) ; les intégrations sans flow ont une valeur par défaut ou nullable selon le design ; l'affichage et l'API restent cohérents.

6. **AC6 — Backend**
   **Given** le modèle et l'API intégrations,
   **Then** la base de données permet un type VARCHAR libre et une colonne auth_flow (ou équivalent) ; l'API CRUD expose type (string) et flow ; un endpoint d'upload d'icône (ex. POST /admin/integrations/upload-icon) accepte un fichier et retourne une URL ou un chemin à enregistrer dans le champ icon.

7. **AC7 — Frontend**
   **Given** le formulaire d'intégration,
   **Then** le champ type est un Input texte (avec suggestions optionnelles) ; le champ flow est un Select (token, basic, basic_then_token, pat) ; le champ icône propose Upload (fichier) et/ou URL ; la liste des intégrations affiche l'icône uploadée ou l'URL.

## Tasks / Subtasks

- [x] Task 1 (AC: 1, 5, 6) — Migration DB : type libre + auth_flow
  - [x] 1.1 : Créer migration Flyway `V024__integrations_type_libre_auth_flow.sql`
  - [x] 1.2 : Modifier colonne TYPE : supprimer contrainte CHECK, passer en VARCHAR2(100) (ou ALTER TABLE pour étendre)
  - [x] 1.3 : Ajouter colonne AUTH_FLOW VARCHAR2(50) nullable avec contrainte CHECK (token, basic, basic_then_token, pat) ou nullable par défaut
  - [x] 1.4 : Migration données existantes : convertir types enum existants en chaînes (aap → 'aap', etc.), AUTH_FLOW = NULL ou valeur par défaut 'token' selon design
  - [x] 1.5 : Supprimer index IDX_INTEGRATIONS_TYPE si plus nécessaire (ou le garder pour performance)

- [x] Task 2 (AC: 1, 2, 4, 6) — Backend : modèles Pydantic et repository
  - [x] 2.1 : Modifier `IntegrationType` enum → remplacer par type `str` dans `IntegrationCreate` / `IntegrationUpdate` / `IntegrationResponse`
  - [x] 2.2 : Ajouter enum `AuthFlow` : token, basic, basic_then_token, pat (pour validation)
  - [x] 2.3 : Ajouter champ `auth_flow: AuthFlow | None` dans modèles Pydantic (Create, Update, Response)
  - [x] 2.4 : Modifier `integration_repository.py` : adapter requêtes SQL pour TYPE VARCHAR libre, ajouter AUTH_FLOW dans SELECT/INSERT/UPDATE
  - [x] 2.5 : Validation Pydantic : type (str, 1-100 chars), auth_flow (enum ou None), garder credential_ref, icon

- [x] Task 3 (AC: 3, 6) — Backend : endpoint upload icône
  - [x] 3.1 : Créer endpoint POST `/api/v1/admin/integrations/upload-icon` (multipart/form-data)
  - [x] 3.2 : Validation fichier : type MIME (image/png, image/jpeg, image/svg+xml), taille max (ex. 2MB), extension
  - [x] 3.3 : Stockage fichier : option 1 = fichiers locaux dans `backend/static/icons/` (ou configurable), option 2 = préparer interface pour futur S3
  - [x] 3.4 : Retourner URL relative ou absolue (ex. `/static/icons/{uuid}.png` ou URL complète) dans `{ "data": { "icon_url": "..." } }`
  - [x] 3.5 : Protection route : `require_profile("dbops")` comme autres routes admin

- [x] Task 4 (AC: 1, 2, 3, 4, 7) — Frontend : types TypeScript et formulaire
  - [x] 4.1 : Modifier `types/api.ts` : `IntegrationType` → `string`, ajouter `AuthFlow` type union, ajouter `auth_flow?: AuthFlow | null` dans interfaces
  - [x] 4.2 : Modifier `IntegrationForm.tsx` : remplacer Select type par Input texte (avec suggestions optionnelles basées sur types existants)
  - [x] 4.3 : Ajouter Select pour `auth_flow` : options token, basic, basic_then_token, pat avec labels français
  - [x] 4.4 : Ajouter composant Upload icône : Ant Design Upload avec accept="image/*", maxCount=1, avantText="Uploader" ou option URL (Input avec toggle)
  - [x] 4.5 : Aperçu icône : afficher image uploadée ou URL dans Avatar, fallback sur preset si vide
  - [x] 4.6 : Modifier `IntegrationsTable.tsx` : afficher icône uploadée (img src) ou URL, fallback preset si vide

- [x] Task 5 (AC: 5) — Tests et rétrocompatibilité
  - [x] 5.1 : Tests backend : repository avec type libre, auth_flow nullable, migration données existantes
  - [x] 5.2 : Tests API : POST/PUT avec type libre, auth_flow, upload icône (multipart), rétrocompatibilité types existants
  - [x] 5.3 : Tests frontend : formulaire type Input libre, Select flow, Upload icône, affichage liste
  - [x] 5.4 : Tests migration : vérifier données existantes converties correctement, AUTH_FLOW NULL ou défaut

## Dev Notes

### Contexte métier

- **Epic 4** : DBA exécute une action de bout en bout via le wizard et suit la progression étape par étape en temps réel via la timeline. Les intégrations (Story 2.27, 2.28) alimentent le moteur d'exécution (Story 4.3). Le flow d'auth permet à l'exécuteur de savoir comment utiliser le secret Vault (Bearer, Basic, échange token, PAT) sans coder en dur par type.
- **Position** : Epic 4 (Exécution & suivi) — story 4.9 ; Epic 2 est considéré terminé.
- **Problème résolu** : Actuellement, le type d'intégration est un enum fixe. Pour ajouter une nouvelle plateforme, il faut modifier le code (enum, labels, icônes). Le flow d'authentification n'est pas défini par intégration, donc l'exécuteur ne sait pas comment utiliser le secret Vault. L'icône est soit un preset par type, soit une URL saisie manuellement — pas d'upload.

### Patterns à respecter

- **API** : snake_case JSON, wrapper `{ "data": ... }` / `{ "error": ... }`, dates ISO 8601 UTC. [Source: architecture.md]
- **Frontend** : données API en snake_case → camelCase au point d'usage. [Source: architecture.md]
- **Repository** : SQL brut via python-oracledb, pas d'ORM. [Source: architecture.md]
- **Migrations** : Flyway, format `V0XX__description_snake_case.sql`, identity columns (pas de séquences), cohérent avec V016+. [Source: architecture.md]
- **Sécurité** : Routes admin protégées par RBAC (profil DBOPS). Aucun credential en base — uniquement credential_ref. [Source: Story 2.27]

### Ce qui existe déjà

- **Backend** : Table INTEGRATIONS (V020) avec TYPE enum (CHECK constraint), modèles Pydantic `IntegrationType` enum, repository `integration_repository.py`, API `/admin/integrations` (GET, POST, PUT, DELETE). Pas de colonne AUTH_FLOW, pas d'endpoint upload icône.
- **Frontend** : `IntegrationForm.tsx` avec Select type enum, `IntegrationsTable.tsx` avec affichage icône preset ou URL. Types TypeScript `IntegrationType` enum dans `types/api.ts`.
- **Références** : Story 2.27 (backend intégrations), Story 2.28 (frontend admin intégrations).

### Références techniques

- **Auth flows** : 
  - `token` : Bearer token (header `Authorization: Bearer <token>`)
  - `basic` : Basic auth (header `Authorization: Basic <base64(user:pass)>`)
  - `basic_then_token` : Basic auth puis échange pour token (POST /auth/login → récupère token → Bearer)
  - `pat` : Personal Access Token (header `Authorization: token <pat>` ou `X-Api-Key: <pat>`)
- **Upload icône** : Ant Design Upload component, validation MIME type, stockage local (MVP) ou S3 (futur). Format recommandé : PNG, JPEG, SVG. Taille max : 2MB.
- **Rétrocompatibilité** : Types existants (aap, servicenow, terraform, etc.) restent valides comme chaînes. AUTH_FLOW = NULL pour intégrations existantes (ou valeur par défaut 'token').

### Project Structure Notes

- **Backend** : 
  - Modifier : `backend/app/models/integration.py` (type str, auth_flow)
  - Modifier : `backend/app/repositories/integration_repository.py` (SQL avec TYPE VARCHAR, AUTH_FLOW)
  - Modifier : `backend/app/api/v1/integrations.py` (ajout endpoint upload-icon)
  - Nouveau : `backend/app/services/icon_service.py` (optionnel, logique upload/storage)
  - Nouveau : `database/migrations/V024__integrations_type_libre_auth_flow.sql`
- **Frontend** :
  - Modifier : `frontend/src/types/api.ts` (IntegrationType string, AuthFlow, auth_flow)
  - Modifier : `frontend/src/components/admin/IntegrationForm.tsx` (Input type libre, Select flow, Upload icône)
  - Modifier : `frontend/src/components/admin/IntegrationsTable.tsx` (affichage icône uploadée)
  - Nouveau : `frontend/src/services/integration_service.ts` (optionnel, méthode uploadIcon si séparé)

### Architecture Compliance

- **Stack** : FastAPI, Pydantic v2, python-oracledb (mode Thin), React 19, TypeScript, Ant Design 6.2.
- **API** : REST JSON, versioning `/api/v1/`, erreurs format `{ "error": { "code": "...", "message": "...", "details": {...} } }`. [Source: architecture.md]
- **Database** : Oracle via python-oracledb mode Thin, SQL brut dans repositories, migrations Flyway séquentielles. [Source: architecture.md]
- **Sécurité** : Routes admin protégées par RBAC (profil DBOPS). Aucun secret stocké — uniquement credential_ref. [Source: Story 2.27, NFR7]
- **Convention migrations** : Flyway, format `V0XX__description_snake_case.sql`, identity columns (pas de séquences), cohérent avec V016+. [Source: architecture.md]

### Library/Framework Requirements

- **FastAPI** : Router, Depends pour require_profile, File upload via `UploadFile` (multipart/form-data), status codes explicites.
- **Pydantic** : Modèles avec validation (type str 1-100 chars, auth_flow enum ou None), HttpUrl pour icon URL si souhaité.
- **python-oracledb** : Connexion via pool existant (core/database.py), pas de nouveau driver.
- **Ant Design 6.2** : Upload component pour icône, Input pour type libre, Select pour auth_flow, Avatar pour aperçu icône.
- **Backend upload** : `python-multipart` (déjà dans FastAPI) pour multipart/form-data, validation MIME type, stockage fichiers locaux (ou interface S3).

### File Structure Requirements

- **Nouveau backend** : `database/migrations/V024__integrations_type_libre_auth_flow.sql` (migration TYPE + AUTH_FLOW)
- **Modifier backend** : `backend/app/models/integration.py` (type str, auth_flow), `backend/app/repositories/integration_repository.py` (SQL adapté), `backend/app/api/v1/integrations.py` (endpoint upload-icon)
- **Modifier frontend** : `frontend/src/types/api.ts` (IntegrationType string, AuthFlow), `frontend/src/components/admin/IntegrationForm.tsx` (Input type, Select flow, Upload), `frontend/src/components/admin/IntegrationsTable.tsx` (affichage icône)
- **Tests** : `backend/tests/unit/test_integration_repository.py` (tests type libre, auth_flow), `backend/tests/unit/test_integration_api.py` (tests upload-icon), `frontend/src/components/admin/IntegrationForm.test.tsx` (tests formulaire)

### Testing Requirements

- **Backend** : Tests unitaires repository (create/update avec type libre, auth_flow nullable), tests API POST/PUT avec type libre, tests endpoint upload-icon (multipart, validation MIME, stockage), tests migration données existantes.
- **Frontend** : Tests unitaires IntegrationForm (Input type libre, Select flow, Upload icône, validation), tests IntegrationsTable (affichage icône uploadée), tests intégration flow complet.
- **Rétrocompatibilité** : Tests migration V024 (vérifier types existants convertis, AUTH_FLOW NULL ou défaut), tests API avec types existants (aap, servicenow, etc.).

### Previous Story Intelligence

- **Story 2.27 (Backend Intégrations)** : Pattern repository SQL brut identique, modèles Pydantic avec validation, routes admin protégées DBOPS, format API wrapper `{ "data" }` / `{ "error" }`. Réutiliser structure mais adapter pour type libre et auth_flow. [Source: 2-27-backend-integrations-plateformes-distantes.md]
- **Story 2.28 (Frontend Admin Intégrations)** : Pattern formulaire IntegrationForm avec Select type enum, aperçu icône Avatar, validation inline. Modifier pour Input type libre, Select flow, Upload icône. [Source: 2-28-frontend-admin-integrations-liste-formulaire-icone.md]
- **Story 4.1 (Wizard Exécution)** : Pattern validation inline Ant Design Form, gestion fichiers (inventaire). Réutiliser patterns validation et gestion fichiers pour upload icône. [Source: 4-1-wizard-execution-en-3-etapes.md]

### Git Intelligence Summary

- **Derniers commits** : Stories Epic 2 et Epic 3 complétées. Patterns établis : repository SQL brut, modèles Pydantic, routes admin DBOPS, migrations Flyway identity columns. Suivre conventions établies.
- **Fichiers modifiés récemment** : `integration.py`, `integration_repository.py`, `integrations.py` (Story 2.27), `IntegrationForm.tsx`, `IntegrationsTable.tsx` (Story 2.28). Modifier ces fichiers pour type libre et auth_flow.

### Latest Tech Information

- **FastAPI File Upload** : `UploadFile` de `fastapi` pour multipart/form-data. Validation MIME type via `file.content_type`, taille via `file.size`. Stockage : `await file.read()` puis écriture fichier local ou S3.
- **Ant Design Upload** : Composant `Upload` avec `accept="image/*"`, `maxCount={1}`, `beforeUpload` pour validation (taille, type). `onChange` pour gestion état (fileList). `customRequest` pour contrôle total upload.
- **Oracle ALTER TABLE** : `ALTER TABLE INTEGRATIONS MODIFY TYPE VARCHAR2(100)` pour étendre colonne. `ALTER TABLE INTEGRATIONS ADD AUTH_FLOW VARCHAR2(50)` pour ajouter colonne. Supprimer contrainte CHECK : `ALTER TABLE INTEGRATIONS DROP CONSTRAINT CK_INTEGRATIONS_TYPE`.

### Project Context Reference

- **Architecture** : [Source: _bmad-output/planning-artifacts/architecture.md] — Stack FastAPI + React + Oracle, patterns repository SQL brut, API REST JSON, migrations Flyway.
- **Epics** : [Source: _bmad-output/planning-artifacts/epics.md] — Epic 4 Story 4.9 (non détaillée dans epics.md, créée après Epic 2 terminé).
- **Story 2.27** : [Source: _bmad-output/implementation-artifacts/2-27-backend-integrations-plateformes-distantes.md] — Backend intégrations avec TYPE enum, modèles Pydantic, repository SQL brut.
- **Story 2.28** : [Source: _bmad-output/implementation-artifacts/2-28-frontend-admin-integrations-liste-formulaire-icone.md] — Frontend admin intégrations avec formulaire, liste, icône preset ou URL.
- **Migration V020** : [Source: idp-portal/database/migrations/V020__create_integrations.sql] — Table INTEGRATIONS avec TYPE enum CHECK constraint.

### References

- [Source: idp-portal/backend/app/models/integration.py] Modèles Pydantic existants avec IntegrationType enum
- [Source: idp-portal/backend/app/repositories/integration_repository.py] Repository SQL brut avec CRUD intégrations
- [Source: idp-portal/backend/app/api/v1/integrations.py] Routes API admin intégrations
- [Source: idp-portal/frontend/src/components/admin/IntegrationForm.tsx] Formulaire création/édition intégration
- [Source: idp-portal/frontend/src/types/api.ts] Types TypeScript IntegrationType enum
- [Source: _bmad-output/planning-artifacts/architecture.md] Patterns architecture, conventions migrations, sécurité RBAC

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.5 (2026-01-29)

### Debug Log References

N/A

### Completion Notes List

**Code Review Fixes (2026-01-29)**

Revue de code adversariale effectuée. 10 problèmes identifiés et 7 corrigés:

**CRITICAL (3 fixes):**
1. ✅ Tests API: Remplacé `IntegrationType` enum par strings libres (lignes 257, 420)
2. ✅ Tests repository: Ajouté colonne `auth_flow` manquante dans fixture row2
3. ✅ Tests API: Remplacé test validation enum obsolète par test type trop long (>100 chars)

**MEDIUM (4 fixes):**
4. ✅ IntegrationForm: Ajouté Authorization header dans upload icon (fetch avec JWT token)
5. ✅ IntegrationsTable: Ajouté fallback dans AUTH_FLOW_LABELS lookup (affiche flow brut si invalide)
6. ✅ IntegrationForm: Supprimé règle validation `whitespace` redondante pour type
7. ✅ Migration V024: Ajouté commentaires impact rétrocompatibilité auth_flow NULL

**LOW (3 fixes):**
8. ✅ Static path: Ajouté vérification writable au startup avec test file touch/unlink + logging
9. ✅ Icon upload path: Centralisé dans config.py avec `settings.get_static_path()` (fini 4× parent fragile)
10. ✅ Test upload icon: Ajouté mock `Path.exists` pour isolation complète filesystem CI/CD

**Configuration ajoutée (LOW-9):**
- Nouveau champ `static_files_path` dans `app.core.config.Settings` (optionnel, défaut: backend/static/)
- Variable d'environnement `STATIC_FILES_PATH` pour override du path
- Méthode helper `settings.get_static_path()` utilisée par main.py et integrations.py

**Story 4.9 — Implémentation complète (2026-01-29)**

Implémenté toutes les tâches pour rendre les intégrations extensibles via type libre, flow d'authentification, et upload d'icône:

**Task 1 — Migration DB**
- Créé migration V024 avec DROP CHECK constraint TYPE, extension VARCHAR2(100), ajout colonne AUTH_FLOW nullable avec CHECK constraint
- Données existantes conservées (types déjà strings en DB), AUTH_FLOW NULL pour rétrocompatibilité (AC5)
- Index IDX_INTEGRATIONS_TYPE conservé pour performance

**Task 2 — Backend modèles et repository**
- Remplacé enum IntegrationType par type string libre (1-100 chars) dans modèles Pydantic (AC1)
- Ajouté enum AuthFlow (token, basic, basic_then_token, pat) avec validation Pydantic (AC2)
- Mis à jour repository: _row_to_integration_response prend 9 colonnes (ajout AUTH_FLOW), SELECT/INSERT/UPDATE adaptés
- Validation type strip whitespace, auth_flow nullable

**Task 3 — Backend endpoint upload icône**
- Créé POST /api/v1/admin/integrations/upload-icon (multipart/form-data) protégé DBOPS (AC3, AC6)
- Validation MIME type (image/png, jpeg, svg+xml), taille max 2MB
- Stockage local backend/static/icons/{uuid}.{ext}, retour URL relative /static/icons/...
- Monté StaticFiles dans main.py pour servir /static

**Task 4 — Frontend types et formulaire**
- Remplacé IntegrationType enum par type string, ajouté AuthFlow type, auth_flow dans interfaces (AC1, AC2)
- IntegrationForm: AutoComplete pour type libre avec suggestions (AC1, AC7), Select pour auth_flow (AC2, AC7)
- Ajouté Upload component (Ant Design) avec validation MIME/taille, appel API upload-icon (AC3, AC7)
- Aperçu icône Avatar (uploadée ou URL), fallback ApiOutlined
- IntegrationsTable: affichage icône uploadée (Avatar src), colonne Auth Flow, type libre (Tag)

**Task 5 — Tests et rétrocompatibilité**
- Tests backend: fixtures avec type string + auth_flow, test row conversion avec auth_flow NULL (AC5), test type libre (jenkins)
- Tests API: fixtures mises à jour, ajout TestUploadIcon (success, invalid MIME, file too large, forbidden)
- Tests frontend: IntegrationForm mis à jour avec auth_flow, test type libre, test validation type required

**Patterns respectés:**
- Repository SQL brut python-oracledb, modèles Pydantic v2, validation inline
- Routes admin protégées require_profile("dbops"), format API { data } / { error }
- Migrations Flyway identity columns, pas de séquences
- Frontend camelCase au point d'usage, types snake_case depuis API

**Rétrocompatibilité (AC5):**
- Types existants (aap, servicenow, etc.) restent valides comme strings
- AUTH_FLOW NULL pour intégrations existantes (nullable)
- Tests vérifient row conversion avec auth_flow NULL

**Tous les ACs satisfaits:**
- AC1: Type libre VARCHAR2(100), Input texte frontend
- AC2: Auth flow (token, basic, basic_then_token, pat), Select frontend
- AC3: Upload icône PNG/JPEG/SVG max 2MB, stockage local /static/icons/, affichage Avatar
- AC4: Champs existants conservés (nom, URL, credential_ref), formulaire complet
- AC5: Types existants restent valides, auth_flow nullable, rétrocompatibilité
- AC6: Backend modèles + repository + endpoint upload + validation + RBAC DBOPS
- AC7: Frontend AutoComplete type, Select flow, Upload icône, affichage liste/formulaire

### File List

**Backend - Database:**
- database/migrations/V024__integrations_type_libre_auth_flow.sql

**Backend - Models:**
- backend/app/models/integration.py

**Backend - Repositories:**
- backend/app/repositories/integration_repository.py

**Backend - API:**
- backend/app/api/v1/integrations.py
- backend/app/main.py

**Backend - Core (Code Review LOW-9 fix):**
- backend/app/core/config.py

**Backend - Tests:**
- backend/tests/unit/test_integration_repository.py
- backend/tests/unit/test_integration_api.py

**Frontend - Types:**
- frontend/src/types/api.ts

**Frontend - Components:**
- frontend/src/components/admin/IntegrationForm.tsx
- frontend/src/components/admin/IntegrationsTable.tsx

**Frontend - Tests:**
- frontend/src/components/admin/IntegrationForm.test.tsx
