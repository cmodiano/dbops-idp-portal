# Story 2.27 : Backend — Intégrations (plateformes distantes)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **DBOPS**,
I want **stocker la configuration des plateformes distantes (AAP, Terraform, ServiceNow, etc.) : type, nom, URL, référence aux credentials, icône**,
so that **le portail peut déclarer quelles instances appeler pour déclencher les exécutions et les afficher dans l'admin**.

## Acceptance Criteria

1. **AC1 — Table INTEGRATIONS**
   **Given** une migration SQL est exécutée,
   **When** la table INTEGRATIONS est créée,
   **Then** elle contient au minimum : ID (identity), TYPE (aap | servicenow | terraform | azuredevops | jira | github_actions), NAME (unique), BASE_URL, CREDENTIAL_REF (référence Vault ou nom logique — aucun secret stocké, NFR7), ICON (varchar — identifiant preset ou URL d'icône), CREATED_AT, UPDATED_AT.

2. **AC2 — GET /api/v1/admin/integrations**
   **Given** un DBOPS appelle les API admin des intégrations,
   **When** il fait GET /api/v1/admin/integrations,
   **Then** la liste des intégrations est retournée (sans exposer de secret).

3. **AC3 — POST / PUT intégrations**
   **Given** un DBOPS crée ou modifie une intégration,
   **When** il fait POST /api/v1/admin/integrations ou PUT /api/v1/admin/integrations/{id},
   **Then** le backend valide type, name, base_url, credential_ref (optionnel), icon (optionnel) et persiste en base.

4. **AC4 — Sécurité et NFR**
   **And** les routes sont protégées par le profil DBOPS (require_profile dbops).
   **And** aucun credential brut n'est stocké — uniquement credential_ref (NFR7, FR29).

## Tasks / Subtasks

- [x] Task 1 (AC: 1) — Migration SQL table INTEGRATIONS
  - [x] 1.1 : Créer fichier de migration Flyway `V0XX__create_integrations.sql` (convention double underscore).
  - [x] 1.2 : Définir table INTEGRATIONS avec colonnes : ID GENERATED ALWAYS AS IDENTITY, TYPE VARCHAR avec contrainte check (enum), NAME VARCHAR unique not null, BASE_URL VARCHAR not null, CREDENTIAL_REF VARCHAR nullable, ICON VARCHAR nullable, CREATED_AT TIMESTAMP, UPDATED_AT TIMESTAMP.
  - [x] 1.3 : Pas de séquence (identity columns uniquement, cohérent avec V016+).

- [x] Task 2 (AC: 2, 3) — Modèle Pydantic et repository
  - [x] 2.1 : Créer modèle `Integration` dans `backend/app/models/` (ou module dédié integrations) : id, type, name, base_url, credential_ref (optional), icon (optional), created_at, updated_at. Type = Literal des valeurs autorisées.
  - [x] 2.2 : Créer `IntegrationCreate` / `IntegrationUpdate` (sans id, sans exposition de secret). Ne jamais exposer credential_ref en lecture si politique exige (ou exposer uniquement la clé logique, jamais la valeur).
  - [x] 2.3 : Créer `IntegrationRepository` dans `backend/app/repositories/` : get_all(), get_by_id(), create(), update(), delete() — SQL brut via python-oracledb, pattern identique à catalog_repository.

- [x] Task 3 (AC: 2, 3, 4) — API FastAPI admin
  - [x] 3.1 : Créer router ou étendre `backend/app/api/v1/admin.py` : GET /integrations (liste), GET /integrations/{id}, POST /integrations, PUT /integrations/{id}, DELETE /integrations/{id}.
  - [x] 3.2 : Protéger toutes les routes avec dépendance type `require_profile("dbops")` (ou équivalent existant dans le projet).
  - [x] 3.3 : Réponses au format wrapper { "data": ... } / { "error": ... }, snake_case JSON, codes HTTP 200/201/400/404.

- [x] Task 4 (AC: 4) — Validation et NFR7
  - [x] 4.1 : Validation Pydantic : type dans enum, name non vide, base_url format URL valide, credential_ref et icon optionnels.
  - [x] 4.2 : S'assurer qu'aucun champ ne stocke de secret — uniquement credential_ref (référence logique ou chemin Vault).

- [x] Task 5 — Tests unitaires
  - [x] 5.1 : Tests repository : create, get_by_id, get_all, update, delete (avec base de test ou mocks).
  - [x] 5.2 : Tests API : GET liste (vide puis avec données), POST création (201), PUT mise à jour, GET par id, DELETE ; vérifier 403 si non-DBOPS.

## Dev Notes

- **Contexte** : Cette story pose la fondation backend pour la configuration des plateformes d'exécution (AAP, Terraform, ServiceNow, etc.). La story 2.28 ajoutera le frontend Admin (onglet Intégrations, liste, formulaire, icône). Ne pas implémenter l'appel réel aux plateformes ici — uniquement le CRUD de configuration.
- **Réutilisation** : Suivre le même pattern que `admin/actions` et `admin/profiles` : repository SQL brut, modèles Pydantic, router sous `/api/v1/admin/`, protection DBOPS.
- **TYPE** : Valeurs possibles alignées sur les connecteurs existants (ExecutionStep connector_type) : aap, servicenow, terraform, azuredevops, jira, github_actions. Utiliser un Enum Python et une contrainte CHECK en base.
- **CREDENTIAL_REF** : Stocker uniquement une référence (ex. chemin Vault `secret/idp/aap-prod` ou nom logique). Le portail ne stocke jamais le secret ; récupération à l'exécution via le connecteur Vault (Story 4.2bis, FR29, NFR7).
- **Secret 0 (connexion à Vault)** : Le token ou les identifiants AppRole permettant de se connecter à Vault ne sont jamais stockés en base ni configurés dans l'admin. Ils sont fournis par l'environnement (variables d'env : `VAULT_ADDR`, `VAULT_TOKEN` ou `VAULT_ROLE_ID` + `VAULT_SECRET_ID`, secrets K8s, etc.) et lus au démarrage. Le connecteur Vault (Story 4.2bis) utilise cette config pour se connecter et récupérer dynamiquement les secrets pointés par `credential_ref`.

### Project Structure Notes

- **Backend** : `idp-portal/backend/app/` — models (nouveau modèle ou fichier integrations.py), repositories/integration_repository.py, api/v1/admin.py (router intégrations ou sous-fichier).
- **Migrations** : `idp-portal/database/migrations/` — prochain numéro V0XX (vérifier dernier numéro existant, ex. V020 ou V021) avec nom `V0XX__create_integrations.sql`.
- **Tests** : `idp-portal/backend/tests/unit/` — test_integration_repository.py, test_integration_api.py (ou tests intégrés dans test_admin_api.py selon convention projet).

### Architecture Compliance

- **Stack** : FastAPI, Pydantic v2, python-oracledb (mode Thin), pas de stockage de secrets (NFR7).
- **Pattern** : Repository SQL brut comme catalog_repository ; pas d'ORM. Réponses API : wrapper { "data" } / { "error" }, snake_case, ISO 8601 UTC pour dates.
- **Sécurité** : Routes admin protégées par RBAC (profil DBOPS). Aucun credential en base — uniquement credential_ref.
- **Convention migrations** : Flyway, format `V0XX__description_snake_case.sql`, identity columns (pas de séquences), cohérent avec V016+.

### Library/Framework Requirements

- **FastAPI** : Router, Depends pour require_profile, status codes explicites.
- **Pydantic** : Modèles avec validation (type enum, HttpUrl pour base_url si souhaité).
- **python-oracledb** : Connexion via pool existant (core/database.py), pas de nouveau driver.

### File Structure Requirements

- Nouveau ou modifié : `backend/app/models/integration.py` (ou intégré dans models existant avec préfixe clair).
- Nouveau : `backend/app/repositories/integration_repository.py`.
- Modifié : `backend/app/api/v1/admin.py` (ajout routes intégrations) — ou nouveau fichier `admin_integrations.py` et inclusion dans le router principal si structure multi-fichiers.
- Nouveau : `database/migrations/V0XX__create_integrations.sql`.
- Tests : `backend/tests/unit/test_integration_repository.py`, `backend/tests/unit/test_integration_api.py` (ou équivalent).

### Testing Requirements

- **pytest** : Tests unitaires repository (CRUD avec DB de test ou mocks).
- **httpx** : Tests API (TestClient FastAPI) — GET/POST/PUT/DELETE, vérification 403 si utilisateur non-DBOPS.
- Pas de tests d'intégration plateforme réelle (AAP, etc.) dans cette story — uniquement persistance et API.

### Previous Story Intelligence (Story 2.26 — Visualisation YAML import profils)

- **Contexte** : Story 2.26 était frontend (ProfileImportModal, template YAML). La 2.27 est backend-only ; le frontend Admin (onglet Intégrations) viendra en 2.28.
- **À réutiliser** : Même patterns que les autres entités admin : repository dans `repositories/`, modèles Pydantic dans `models/`, routes sous `api/v1/admin.py`, protection DBOPS identique aux routes actions/profiles.
- **Cohérence** : Nommage français dans les messages utilisateur si applicable ; libellés d'erreur clairs (validation type, name unique, etc.).

### Project Context Reference

- [Source: _bmad-output/planning-artifacts/epics.md] Story 2.27 — Backend Intégrations (lignes 616–638).
- [Source: _bmad-output/planning-artifacts/epics.md] FR29, NFR7 — Zero credential stocké, credential_ref uniquement.
- [Source: idp-portal/backend/app/repositories/catalog_repository.py] Pattern repository SQL brut.
- [Source: idp-portal/backend/app/api/v1/admin.py] Pattern routes admin et protection DBOPS.
- [Source: idp-portal/database/migrations/] Convention Flyway V0XX__description.sql et identity columns (V016+).

### References

- [Source: _bmad-output/planning-artifacts/architecture.md] Repository Pattern, API format snake_case, wrapper data/error.
- [Source: idp-portal/backend/app/models/catalog.py] Exemple modèles Pydantic avec champs optionnels et contraintes.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- 39 tests intégrations (repository + API) passent (après code review 2026-01-29)
- Tests totaux : idem + aucune régression

### Completion Notes List

- **Task 1**: Migration `V020__create_integrations.sql` créée avec table INTEGRATIONS, identity column, contrainte CHECK sur TYPE, index sur TYPE
- **Task 2**: Modèle `IntegrationResponse`, `IntegrationCreate`, `IntegrationUpdate` dans `models/integration.py`. Repository `integration_repository.py` avec CRUD complet (get_all, get_by_id, get_by_name, create, update, delete)
- **Task 3**: Router `integrations.py` avec routes GET/POST/PUT/DELETE sous `/admin/integrations`, inclus dans `admin.py`. Protection `require_profile("dbops")` sur toutes les routes
- **Task 4**: Validations Pydantic intégrées (type enum, name non vide, base_url URL valide). Aucun secret stocké — uniquement credential_ref (référence Vault)
- **Task 5**: 16 tests repository + 23 tests API = 39 tests passent

### Senior Developer Review (AI)

- **Date**: 2026-01-29
- **Findings**: 1 HIGH, 2 MEDIUM, 3 LOW. Tous corrigés automatiquement.
- **Correctifs appliqués**:
  - **HIGH** — Gestion `IntegrityError` : mapping systématique vers `DuplicateNameError` sur create ; sur update, mapping vers `DuplicateNameError` si `name` fourni, sinon `InvalidStateError` (évite 500 selon format Oracle).
  - **MEDIUM** — Import mort `HttpUrl` retiré de `models/integration.py`.
  - **MEDIUM** — correlation_id : déjà propagé via `structlog.contextvars.merge_contextvars` (aucun changement).
  - **LOW** — `integration_id` avec `Path(..., ge=1)` sur GET/PUT/DELETE ; `RuntimeError` après create remplacé par `IdpError(500, CREATION_FAILED)` ; test 401 (sans token) et test 422 pour `integration_id=0` ajoutés.
- **Statut après review** : done.

### Change Log

- 2026-01-29 : Code review (AI) — correctifs HIGH/MEDIUM/LOW appliqués ; statut → done.

### File List

**New files:**
- `idp-portal/database/migrations/V020__create_integrations.sql`
- `idp-portal/backend/app/models/integration.py`
- `idp-portal/backend/app/repositories/integration_repository.py`
- `idp-portal/backend/app/api/v1/integrations.py`
- `idp-portal/backend/tests/unit/test_integration_repository.py`
- `idp-portal/backend/tests/unit/test_integration_api.py`

**Modified files:**
- `idp-portal/backend/app/api/v1/admin.py` (ajout import + include_router integrations)
