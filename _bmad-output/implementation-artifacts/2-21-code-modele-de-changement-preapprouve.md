# Story 2.21: Code modèle de changement préapprouvé

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **DBOPS**,
I want **spécifier le code du modèle de changement préapprouvé (ex. "1516B") pour chaque action**,
so that **le service d'intégration ServiceNow crée le changement avec le bon modèle**.

## Acceptance Criteria

1. **AC1 — Champ dans la section changement**
   **Given** un DBOPS édite une action qui nécessite un changement ServiceNow,
   **When** il accède à la section changement,
   **Then** il voit un champ `change_model_code` (texte alphanumérique).

2. **AC2 — Validation inline**
   **Given** le DBOPS saisit un code,
   **When** le format ne respecte pas `^[A-Za-z0-9]+$`,
   **Then** une erreur de validation s'affiche inline.

3. **AC3 — Migration et modèle**
   **And** migration SQL ajoute colonne `change_model_code VARCHAR(50)` nullable à `ACTIONS_CATALOG`.
   **And** modèle Pydantic `Action` mis à jour avec champ optionnel.
   **And** API `PUT /api/v1/admin/actions/{id}` accepte le nouveau champ.

## Tasks / Subtasks

- [x] Task 1 (AC: 3) — Migration et schéma
  - [x] 1.1: Créer migration Flyway `V017__add_change_model_code.sql` : `ALTER TABLE ACTIONS_CATALOG ADD change_model_code VARCHAR2(50) NULL;` + COMMENT ON COLUMN. (V017 car V016 existait déjà)
  - [x] 1.2: Vérifier ordre de version (V017 > V016) — OK. Migration à exécuter manuellement en dev.

- [x] Task 2 (AC: 3) — Backend
  - [x] 2.1: Ajouter `change_model_code: str | None = None` à `ActionCreate`, `ActionResponse`, `ActionDetail` dans `backend/app/models/catalog.py` avec validateur optionnel `^[A-Za-z0-9]*$` et max_length 50.
  - [x] 2.2: Dans `catalog_repository.py` : inclure `change_model_code` dans INSERT (create), SELECT (get_by_id, list_all, etc.), UPDATE (update_action).
  - [x] 2.3: S'assurer que PUT /api/v1/admin/actions/{id} (body ActionCreate ou équivalent) accepte et persiste `change_model_code`.

- [x] Task 3 (AC: 1, 2) — Frontend
  - [x] 3.1: Ajouter `change_model_code?: string | null` aux types `ActionCreate`, `ActionResponse`, `ActionDetail` dans `frontend/src/types/api.ts`.
  - [x] 3.2: Dans le formulaire admin (ActionForm), section « Changement » (même panneau que ChangeTypeConfig ou immédiatement après), ajouter un champ Input pour « Code modèle de changement » avec validation : alphanumerique uniquement, max 50, optionnel.
  - [x] 3.3: Afficher la valeur en mode édition ; envoyer la valeur à l'API à la création et à la mise à jour.

- [x] Task 4 (AC: 2, 3) — Tests
  - [x] 4.1: Test unitaire backend : modèle Pydantic rejette caractères non alphanumériques ; accepte null et chaîne vide ou valide. (9 tests ajoutés)
  - [x] 4.2: Test API : PUT avec `change_model_code` présent et valide retourne 200 et persiste ; valeur invalide retourne 422. (3 tests ajoutés)
  - [x] 4.3: Test frontend (optionnel) : validation inline sur le champ (regex / max length). (implémenté avec feedback inline)

## Dev Notes

- Champ **optionnel** : une action sans changement ServiceNow n'a pas besoin de code modèle.
- **Regex** : `^[A-Za-z0-9]+$` pour une valeur non vide ; si vide/null, pas d'erreur (optionnel).
- **Emplacement UI** : même section « Changement » que la config par environnement (ChangeTypeConfig) ; le code modèle s'applique à l'action (ServiceNow utilisera ce code pour créer le changement).
- **ServiceNow** : l'intégration réelle (création du changement avec ce code) est dans l'Epic 4 (exécution) ; cette story se limite au catalogue (saisie, persistance, API).

### Project Structure Notes

- Migrations : `idp-portal/database/migrations/`. Prochaine version : V016 (après V015__drop_schema_version.sql).
- Modèles : `idp-portal/backend/app/models/catalog.py` (ActionCreate, ActionResponse, ActionDetail).
- Repository : `idp-portal/backend/app/repositories/catalog_repository.py` (INSERT, SELECT, UPDATE sur ACTIONS_CATALOG).
- Admin API : `idp-portal/backend/app/api/v1/admin.py` (PUT action).
- Frontend : `idp-portal/frontend/src/components/admin/ActionForm.tsx`, `ChangeTypeConfig.tsx` (ou champ à côté), `frontend/src/types/api.ts`, `frontend/src/services/admin_service.ts`.

### References

- [Source: _bmad-output/planning-artifacts/epics.md] Story 2.21 — Code modèle de changement préapprouvé (AC, FR4, intégration ServiceNow).
- [Source: idp-portal/database/migrations/V003__add_execution_steps.sql] Colonnes EXECUTION_STEPS, CHANGE_TYPE_CONFIG sur ACTIONS_CATALOG.
- [Source: idp-portal/backend/app/repositories/catalog_repository.py] Colonnes actuelles INSERT/SELECT pour ACTIONS_CATALOG (PARAMETERS_SCHEMA, IMPACT_RULES, DEFAULT_IMPACT_LEVEL, etc.).
- [Source: idp-portal/frontend/src/components/admin/ChangeTypeConfig.tsx] Section changement (environnements + type pre_approved) — ajouter le champ change_model_code dans la même zone ou panneau.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- 474 backend tests pass
- 203 frontend tests pass

### Completion Notes List

- Migration créée en V017 (car V016 existait déjà — drop_sequences)
- Champ `change_model_code` ajouté aux modèles Pydantic avec validation regex `^[A-Za-z0-9]+$`
- Repository mis à jour pour les 14 colonnes (ActionResponse) et 16 colonnes (ActionDetail)
- Frontend: champ ajouté dans la section Collapse « Changement » avec validation inline
- 12 nouveaux tests ajoutés (9 Pydantic, 3 API)

### Code Review Fixes (2026-01-29)

- **Issue #1 Fixed**: File List mis à jour pour inclure `ActionForm.test.tsx`
- **Issue #2 Fixed**: 3 tests frontend ajoutés pour valider `change_model_code` (validation inline, submit, blocage)
- **Issue #3 Fixed**: Regex inline corrigée de `*` vers `+` pour alignement avec AC2
- **Issue #4 Fixed**: Fixtures API (`sample_action_response`, `sample_action_detail`, `sample_action_detail_with_steps`) mises à jour avec `change_model_code` et `default_impact_level`

### File List

**Database:**
- `idp-portal/database/migrations/V017__add_change_model_code.sql` (NEW)

**Backend:**
- `idp-portal/backend/app/models/catalog.py` (MODIFIED)
- `idp-portal/backend/app/repositories/catalog_repository.py` (MODIFIED)
- `idp-portal/backend/tests/unit/test_catalog_models.py` (MODIFIED)
- `idp-portal/backend/tests/unit/test_admin_api.py` (MODIFIED)
- `idp-portal/backend/tests/unit/test_catalog_repository.py` (MODIFIED)

**Frontend:**
- `idp-portal/frontend/src/types/api.ts` (MODIFIED)
- `idp-portal/frontend/src/components/admin/ActionForm.tsx` (MODIFIED)
- `idp-portal/frontend/src/components/admin/ActionForm.test.tsx` (MODIFIED)
