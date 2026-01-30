# Story 2.24 : Changement ServiceNow conditionnel par environnement

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **DBOPS**,
I want **définir si un changement ServiceNow est requis pour chaque environnement et spécifier le code modèle par environnement**,
so that **je configure précisément quels environnements nécessitent une ouverture de changement (souvent uniquement PROD)**.

## Acceptance Criteria

1. **AC1 — Toggle « Changement requis » par environnement**
   **Given** un DBOPS configure la section Changement d'une action (ActionWizard étape 3 ou ActionForm),
   **When** il voit la liste des environnements (DEV, STAGING, PROD, etc.),
   **Then** pour chaque environnement il peut activer/désactiver « Changement requis » (toggle, défaut : non).

2. **AC2 — Code modèle obligatoire quand changement requis**
   **Given** un DBOPS active « Changement requis » pour un environnement,
   **When** le toggle est actif,
   **Then** un champ « Code modèle » apparaît pour cet environnement,
   **And** le code modèle est obligatoire et doit être alphanumérique (max 50 caractères).

3. **AC3 — Code modèle masqué quand changement non requis**
   **Given** un DBOPS désactive « Changement requis » pour un environnement,
   **When** le toggle est désactivé,
   **Then** le champ « Code modèle » disparaît pour cet environnement.

4. **AC4 — Structure change_type_config**
   **And** structure `change_type_config` évolue vers : `{"PROD": {"required": true, "change_model_code": "1516B"}, "DEV": {"required": false}}`,
   **And** migration données : si `change_model_code` existait au niveau action (Story 2.21), le reporter sur les environnements qui avaient `pre_approved` dans l’ancien `change_type_config`,
   **And** le champ `change_model_code` au niveau action est supprimé (déplacé dans `change_type_config`),
   **And** validation backend : si `required: true`, alors `change_model_code` obligatoire et alphanumérique,
   **And** API accepte la nouvelle structure et rejette l’ancienne avec message d’erreur clair (422 + message explicite).

5. **AC5 — Exemple de configuration**
   Exemple : DEV = Changement requis Non ; STAGING = Non ; PROD = Oui, Code modèle = "1516B".

## Tasks / Subtasks

- [x] Task 1 (AC: 4) — Migration SQL et données
  - [x] 1.1 : Créer migration `V019__change_type_config_per_env.sql` (V018 pris par 2.23) : PL/SQL avec JSON_OBJECT_T pour construire nouveau JSON par ligne, puis DROP COLUMN CHANGE_MODEL_CODE
  - [x] 1.2 : Tests unitaires migration (fichier existe, DROP COLUMN, nouveau format, COMMENT)

- [x] Task 2 (AC: 4) — Backend : Modèles Pydantic
  - [x] 2.1 : `ChangeTypeConfigEntry` (required, change_model_code), validateur required⇒code obligatoire et alphanumérique max 50 ; suppression change_model_code de ActionCreate/ActionResponse/ActionDetail ; change_type_config dict[str, ChangeTypeConfigEntry] dans ActionDetail et ExecutionStepsUpdate
  - [x] 2.2 : ExecutionStepsUpdate.change_type_config typé dict[str, ChangeTypeConfigEntry] ; validateur mode="before" rejette legacy (env→string) avec message clair

- [x] Task 3 (AC: 4) — Backend : Repository
  - [x] 3.1 : _parse_change_type_config retourne dict[str, ChangeTypeConfigEntry], lève LegacyChangeTypeConfigError si valeur string ; _change_type_config_to_json sérialise {env: {required, change_model_code}} ; suppression CHANGE_MODEL_CODE de toutes les requêtes et row mappers (12/14 colonnes)

- [x] Task 4 (AC: 1, 2, 3, 5) — Frontend : Types
  - [x] 4.1 : ChangeTypeConfigEntry, change_type_config Record<string, ChangeTypeConfigEntry> dans ActionDetail et ExecutionStepsUpdate ; suppression change_model_code de ActionCreate et ActionResponse

- [x] Task 5 (AC: 1, 2, 3, 5) — Frontend : Formulaire Changement (Wizard étape 3 / ActionForm)
  - [x] 5.1 : ChangeTypeConfig réécrit : Switch « Changement requis » + Input « Code modèle » par env (DEV, STAGING, PROD)
  - [x] 5.2 : Payload change_type_config au format { "PROD": { required: true, change_model_code: "1516B" }, "DEV": { required: false } } dans updateActionSteps
  - [x] 5.3 : ActionCreate sans change_model_code ; Wizard appelle updateActionSteps avec étape placeholder si changeTypeConfig non vide

- [x] Task 6 — Backend : API et validation
  - [x] 6.1 : ExecutionStepsUpdate field_validator(mode="before") rejette env→string avec ValueError message explicite (422)
  - [x] 6.2 : ChangeTypeConfigEntry model_validator : required=true ⇒ change_model_code obligatoire et alphanumérique

- [x] Task 7 — Tests
  - [x] 7.1 : Backend : test_catalog_models (ChangeTypeConfigEntry, legacy rejet), test_catalog_repository (parse/serialize, LegacyChangeTypeConfigError), test_admin_api (nouveau format 200, legacy 422), test_migration (V019)
  - [x] 7.2 : Frontend : ChangeTypeConfig.test (table, Switch, code input), ActionForm.test (change_type_config nouveau format, validation required+code), ActionWizard.test (sans change_model_code)

## Dev Notes

- **Contexte** : Story 2.21 a introduit `change_model_code` au niveau action (un seul code pour toute l’action). Story 2.24 déplace ce concept dans `change_type_config` par environnement : chaque env peut avoir « changement requis » oui/non et, si oui, un code modèle dédié.
- **Rétrocompatibilité** : La migration doit convertir l’ancien état (colonnes `change_type_config` + `change_model_code`) vers le nouveau format. L’API ne doit plus accepter l’ancien format après déploiement (breaking change interne, outil DBOPS).
- **Fichiers impactés** : `backend/app/models/catalog.py`, `backend/app/repositories/catalog_repository.py`, `backend/app/api/v1/admin.py`, `frontend/src/types/api.ts`, `frontend/src/components/admin/ActionWizard.tsx`, `frontend/src/components/admin/ActionForm.tsx`, migrations SQL.

### Project Structure Notes

- **Backend** : `models/catalog.py` (nouveau modèle `ChangeTypeConfigEntry`, suppression `change_model_code`), `repositories/catalog_repository.py` (parsing/sérialisation nouveau format), `api/v1/admin.py` (validation entrée).
- **Frontend** : `types/api.ts`, `ActionWizard.tsx` (étape 3), `ActionForm.tsx` (section Changement).
- **Migrations** : Nouveau script SQL (V018 ou suivant) : transformation données + suppression colonne `change_model_code`.

### Architecture Compliance

- **Stack** : Python 3.12+, FastAPI, Pydantic v2, React 19, TypeScript, Ant Design 6.
- **Patterns** : Repository (SQL brut), snake_case API, CLOB JSON pour `change_type_config`.
- **Migration** : Flyway naming `Vnnn__description.sql`.

### Library/Framework Requirements

- Aucune nouvelle dépendance. Validation Pydantic et Ant Design Form/Switch/Input existants.

### File Structure Requirements

- Nouvelle migration : `database/migrations/V018__change_type_config_per_env.sql` (ou numéro cohérent avec l’existant).
- Pas de nouveau module ; modifications ciblées sur catalog et admin.

### Testing Requirements

- **Backend** : pytest — modèles (valid/invalid `ChangeTypeConfigEntry`), repository (round-trip nouveau format), API (200 nouveau format, 422 ancien format ou `required: true` sans `change_model_code`).
- **Frontend** : Vitest + RTL — formulaire étape 3 / section Changement : toggles par env, champ code modèle conditionnel, validation alphanumérique.
- **Régression** : Création/édition d’action avec section Changement ; exécution (Story 4.x) continue de consommer `change_type_config` pour savoir si un changement ServiceNow est requis par env.

### Previous Story Intelligence

- **Story 2.21 (code modèle pré-approuvé)** : A ajouté `change_model_code` au niveau action. Cette story le déplace dans `change_type_config` par environnement et supprime la colonne/le champ.
- **Story 2.22 (ActionWizard)** : L’étape 3 « Impact & Change » contient déjà la section Changement ; y intégrer les toggles par env + code modèle par env.
- **Story 2.23 (Suppression catégorie)** : Même périmètre admin (ActionWizard, ActionForm, types, repository). Ordre d’exécution : vérifier si V018 est déjà pris par 2.23 ; si oui, utiliser V019 pour cette migration.

### Git Intelligence

- Le projet utilise déjà `change_type_config` (Record<string, ChangeType>) et `change_model_code` (action-level). Les tests et l’admin font référence à ces champs ; tous devront être alignés sur le nouveau format.

### References

- [Source: _bmad-output/planning-artifacts/epics.md] Story 2.24 — Changement ServiceNow conditionnel par environnement (AC détaillés)
- [Source: idp-portal/backend/app/models/catalog.py] ChangeType, change_model_code (Story 2.21)
- [Source: idp-portal/database/migrations/V017__add_change_model_code.sql] Colonne CHANGE_MODEL_CODE
- [Source: idp-portal/frontend/src/components/admin/ActionWizard.tsx] Étape 3 Impact & Change
- [Source: idp-portal/backend/app/repositories/catalog_repository.py] _parse_change_type_config, _change_type_config_to_json

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- Migration V019 : PL/SQL avec JSON_OBJECT_T pour migrer change_type_config (env→"pre_approved") + change_model_code action → nouveau format par env ; DROP COLUMN CHANGE_MODEL_CODE. V019 préserve NULL et ne réécrit pas les lignes déjà au nouveau format (détection get_Object).
- Backend : ChangeTypeConfigEntry (required + change_model_code), LegacyChangeTypeConfigError dans repository ; ExecutionStepsUpdate rejette legacy format (422).
- Frontend : ChangeTypeConfig composant Switch + Input par env ; ActionForm/ActionWizard envoient change_type_config via updateActionSteps (ActionForm envoie aussi avec étape placeholder si uniquement change_type_config rempli).
- Code-review 2026-01-29 : correctifs appliqués (ActionForm placeholder step, V019 idempotence + préservation NULL, tests API 422 required sans code + message legacy, test Wizard payload change_type_config).
- Fichiers modifiés dans git hors File List : autres stories (catalog API, profiles, auth, migrations renommées, etc.) ; la File List ci-dessous couvre uniquement la story 2.24.
- Tous les tests unitaires backend et frontend passent.

### File List

- idp-portal/database/migrations/V019__change_type_config_per_env.sql
- idp-portal/backend/app/models/catalog.py
- idp-portal/backend/app/repositories/catalog_repository.py
- idp-portal/backend/app/api/v1/admin.py (aucune modification directe ; validation via ExecutionStepsUpdate)
- idp-portal/backend/tests/unit/test_migration.py
- idp-portal/backend/tests/unit/test_catalog_models.py
- idp-portal/backend/tests/unit/test_catalog_repository.py
- idp-portal/backend/tests/unit/test_admin_api.py
- idp-portal/frontend/src/types/api.ts
- idp-portal/frontend/src/components/admin/ChangeTypeConfig.tsx
- idp-portal/frontend/src/components/admin/ChangeTypeConfig.test.tsx
- idp-portal/frontend/src/components/admin/ActionForm.tsx
- idp-portal/frontend/src/components/admin/ActionForm.test.tsx
- idp-portal/frontend/src/components/admin/ActionWizard.tsx
- idp-portal/frontend/src/components/admin/ActionWizard.test.tsx
- _bmad-output/implementation-artifacts/sprint-status.yaml
- _bmad-output/implementation-artifacts/2-24-changement-servicenow-conditionnel-par-environnement.md
