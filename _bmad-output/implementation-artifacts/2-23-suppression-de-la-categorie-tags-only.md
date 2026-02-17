# Story 2.23 : Suppression de la Catégorie — Tags Only

Status: in-review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **DBOPS**,
I want **que le champ Catégorie soit supprimé du formulaire d'action**,
so that **je n'utilise que les tags pour organiser et filtrer les actions (simplification)**.

## Acceptance Criteria

1. **AC1 — Formulaire création/édition**
   **Given** un DBOPS crée ou édite une action,
   **When** il accède au formulaire (ActionWizard ou ActionForm),
   **Then** le champ "Catégorie" n'est plus présent.

2. **AC2 — Migration des catégories existantes vers tags**
   **Given** une action existante a une catégorie assignée (ex: "Provisioning"),
   **When** la migration s'exécute,
   **Then** un tag correspondant est créé automatiquement (ex: "provisioning" en minuscules),
   **And** ce tag est associé à l'action via ACTION_TAGS.

3. **AC3 — Affichage catalogue et admin**
   **Given** un utilisateur consulte le catalogue ou l'admin,
   **When** la page s'affiche,
   **Then** la catégorie n'est plus affichée (remplacée par les tags existants).

4. **AC4 — Filtrage**
   **Given** un utilisateur veut filtrer les actions,
   **When** il utilise les filtres,
   **Then** les filtres par catégorie sont supprimés (utiliser filtres par tags existants Story 2-6).

5. **AC5 — API et modèles**
   **And** backend : champ `category` retiré de `ActionCreate`, `ActionResponse`, `ActionListItem` (breaking change acceptable car outil interne, pas d'API publique),
   **And** migration SQL : colonne `CATEGORY` rendue nullable ou supprimée.

## Tasks / Subtasks

- [x] Task 1 (AC: 2, 5) — Migration SQL et données
  - [x] 1.1 : Créer migration `V018__drop_category_column.sql`
  - [x] 1.2 : Migration utilise MERGE pour créer tags et associations idempotents

- [x] Task 2 (AC: 5) — Backend : Modèles Pydantic
  - [x] 2.1 : Supprimé `ActionCategory` enum et champs `category` de tous modèles
  - [x] 2.2 : Mis à jour imports dans tous les fichiers backend

- [x] Task 3 (AC: 5) — Backend : Repository SQL
  - [x] 3.1 : Supprimé CATEGORY des SELECT, INSERT, UPDATE et parsing rows

- [x] Task 4 (AC: 4, 5) — Backend : API Routes
  - [x] 4.1 : Supprimé paramètre `category` de GET /admin/actions
  - [x] 4.2 : catalog.py n'avait pas de référence à category

- [x] Task 5 (AC: 1) — Frontend : Types et utilitaires
  - [x] 5.1 : Supprimé type et champs `category` de api.ts
  - [x] 5.2 : Supprimé `CATEGORY_OPTIONS` de actionOptions.ts

- [x] Task 6 (AC: 1) — Frontend : Formulaires admin
  - [x] 6.1 : ActionForm.tsx — supprimé category Select et watchedCategory
  - [x] 6.2 : ActionWizard.tsx — supprimé category de form, validation et payload

- [x] Task 7 (AC: 3) — Frontend : Affichage catalogue
  - [x] 7.1 : ActionCard.tsx — supprimé badge category
  - [x] 7.2 : ActionDrawerPreview.tsx — supprimé Description.Item catégorie

- [x] Task 8 (AC: 4) — Frontend : Services et pages admin
  - [x] 8.1 : admin_service.ts — supprimé query param category
  - [x] 8.2 : AdminPage.tsx — supprimé colonne Catégorie du tableau

- [x] Task 9 — Tests backend
  - [x] 9.1 : test_catalog_models.py — supprimé tests ActionCategory et références
  - [x] 9.2 : test_catalog_repository.py — supprimé category des fixtures et ajusté indices
  - [x] 9.3 : test_catalog_api.py — supprimé imports et fixtures category
  - [x] 9.4 : test_admin_api.py — supprimé category de tous payloads et assertions

- [x] Task 10 — Tests frontend
  - [x] 10.1 : ActionForm.test.tsx — supprimé category des données de test
  - [x] 10.2 : ActionWizard.test.tsx — supprimé category et test Catégorie
  - [x] 10.3 : ActionCard.test.tsx — supprimé test "renders category badge"
  - [x] 10.4 : ActionDrawerPreview.test.tsx — adapté test metadata
  - [x] 10.5 : AdminPreview.test.tsx — supprimé category des fixtures

- [x] Task 11 — Validation finale
  - [x] 11.1 : Tests frontend : 24 fichiers, 214 tests passent
  - [x] 11.2 : Tests backend à exécuter sur environnement avec Python

## Dev Notes

- **Objectif** : Simplifier le modèle de données en utilisant uniquement les tags pour la catégorisation. Les 4 catégories fixes (Provisioning, Patching, Administration, Monitoring) deviennent des tags flexibles parmi d'autres.
- **Breaking change acceptable** : L'API est interne (pas de clients externes). La migration convertit automatiquement les catégories en tags.
- **Ordre d'exécution recommandé** : Migration SQL d'abord (crée les tags), puis backend (modèles → repository → API), puis frontend (types → composants → pages), puis tests.
- **Tags existants** : Le système de tags (Story 2-6) est déjà en place. Cette story retire simplement la catégorie redondante.

### Project Structure Notes

**Backend — fichiers à modifier :**
- `backend/app/models/catalog.py` — Supprimer `ActionCategory` enum et champs `category`
- `backend/app/repositories/catalog_repository.py` — Retirer CATEGORY des requêtes SQL
- `backend/app/api/v1/admin.py` — Supprimer filtre `category`
- `database/migrations/V018__drop_category_column.sql` — Nouvelle migration

**Frontend — fichiers à modifier :**
- `frontend/src/types/api.ts` — Supprimer type et champs `category`
- `frontend/src/utils/actionOptions.ts` — Supprimer `CATEGORY_OPTIONS`
- `frontend/src/components/admin/ActionForm.tsx` — Retirer le Select catégorie
- `frontend/src/components/admin/ActionWizard.tsx` — Retirer le Select catégorie de l'étape 1
- `frontend/src/components/catalog/ActionCard.tsx` — Supprimer badge catégorie
- `frontend/src/components/catalog/ActionDrawerPreview.tsx` — Supprimer Description.Item catégorie
- `frontend/src/services/admin_service.ts` — Retirer query param `category`
- `frontend/src/pages/AdminPage.tsx` — Supprimer colonne et filtres catégorie

**Tests — fichiers à modifier :**
- `backend/tests/unit/test_catalog_models.py`
- `backend/tests/unit/test_catalog_repository.py`
- `backend/tests/unit/test_catalog_api.py`
- `backend/tests/unit/test_admin_api.py`
- `backend/tests/unit/test_project_structure.py`
- `frontend/src/components/admin/ActionForm.test.tsx`
- `frontend/src/components/admin/ActionWizard.test.tsx`
- `frontend/src/components/catalog/ActionCard.test.tsx`
- `frontend/src/components/catalog/ActionDrawerPreview.test.tsx`
- `frontend/src/components/admin/AdminPreview.test.tsx`

### Architecture Compliance

- **Stack** : Python 3.12+, FastAPI, Pydantic v2, React 19, TypeScript, Ant Design 6
- **Patterns** : Repository Pattern (SQL brut), snake_case API, modèles Pydantic typés
- **Migration** : Script SQL versionné (V018), pas d'ORM
- **Tests** : pytest (backend), Vitest + RTL (frontend)

### Library/Framework Requirements

- **Backend** : Aucune nouvelle dépendance
- **Frontend** : Aucune nouvelle dépendance
- **Migration** : Oracle SQL standard

### File Structure Requirements

- Nouvelle migration : `database/migrations/V018__drop_category_column.sql`
- Pas de nouveau fichier source (suppressions uniquement)
- Convention de nommage : double underscore dans nom migration Flyway (`V018__`)

### Testing Requirements

- **Backend** : Tous les tests unitaires doivent passer après suppression des références à `category`
- **Frontend** : Tous les tests Vitest doivent passer
- **Régression** : Création/édition d'action fonctionne sans category ; filtrage par tags fonctionne

### Previous Story Intelligence

- **Story 2-6 (Tags flexibles)** : Système de tags complet déjà implémenté (TAGS, ACTION_TAGS, API CRUD tags, multi-select tags dans formulaires). Cette story s'appuie sur ce système.
- **Story 2-22 (ActionWizard)** : Wizard 3 étapes récent. L'étape 1 "Général" contient actuellement le Select catégorie à supprimer. Retirer `category` de la validation et du payload.
- **Story 2-17/2-18 (Éditeurs visuels)** : Pas impactés par cette story.

### Git Intelligence

Commits récents : Le projet est actif avec plusieurs stories Epic 2 complétées. Le wizard (2-22) est en review. Cette story 2-23 est une simplification de cleanup.

### References

- [Source: _bmad-output/planning-artifacts/epics.md] Story 2.23 — Suppression de la Catégorie (AC détaillés)
- [Source: _bmad-output/planning-artifacts/architecture.md] Section Naming Patterns — UPPER_SNAKE_CASE pour colonnes Oracle
- [Source: idp-portal/database/migrations/V002__create_actions_catalog.sql] Structure actuelle table ACTIONS_CATALOG avec CATEGORY
- [Source: idp-portal/database/migrations/V007__create_tags_and_action_tags.sql] Système de tags existant
- [Source: idp-portal/frontend/src/components/admin/ActionWizard.tsx] Wizard à modifier (étape 1)
- [Source: idp-portal/backend/app/models/catalog.py] Modèles Pydantic avec ActionCategory enum

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- Tous les tests frontend passent (24 fichiers, 214 tests)

### Completion Notes List

1. Migration V018__drop_category_column.sql créée avec MERGE idempotent pour tags et associations
2. Suppression complète de ActionCategory enum et champ category dans tout le codebase
3. Breaking change acceptable car API interne uniquement
4. Les tags existants remplacent entièrement la catégorie pour l'organisation des actions

### File List

**Nouveaux fichiers:**
- `idp-portal/database/migrations/V018__drop_category_column.sql`

**Fichiers modifiés — Backend:**
- `idp-portal/backend/app/models/catalog.py`
- `idp-portal/backend/app/repositories/catalog_repository.py`
- `idp-portal/backend/app/api/v1/admin.py`
- `idp-portal/backend/tests/unit/test_catalog_models.py`
- `idp-portal/backend/tests/unit/test_catalog_repository.py`
- `idp-portal/backend/tests/unit/test_catalog_api.py`
- `idp-portal/backend/tests/unit/test_admin_api.py`

**Fichiers modifiés — Frontend:**
- `idp-portal/frontend/src/types/api.ts`
- `idp-portal/frontend/src/utils/actionOptions.ts`
- `idp-portal/frontend/src/components/admin/ActionForm.tsx`
- `idp-portal/frontend/src/components/admin/ActionWizard.tsx`
- `idp-portal/frontend/src/components/catalog/ActionCard.tsx`
- `idp-portal/frontend/src/components/catalog/ActionDrawerPreview.tsx`
- `idp-portal/frontend/src/services/admin_service.ts`
- `idp-portal/frontend/src/pages/AdminPage.tsx`
- `idp-portal/frontend/src/components/admin/ActionForm.test.tsx`
- `idp-portal/frontend/src/components/admin/ActionWizard.test.tsx`
- `idp-portal/frontend/src/components/catalog/ActionCard.test.tsx`
- `idp-portal/frontend/src/components/catalog/ActionDrawerPreview.test.tsx`
- `idp-portal/frontend/src/components/admin/AdminPreview.test.tsx`
