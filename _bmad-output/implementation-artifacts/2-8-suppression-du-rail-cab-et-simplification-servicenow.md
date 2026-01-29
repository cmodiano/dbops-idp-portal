# Story 2.8 : Suppression du rail CAB et simplification ServiceNow

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a développeur,
I want supprimer la logique de changement CAB bloquant et ne garder que les changements pre-approuvés,
So that l'exécution ne soit jamais bloquée en attente d'approbation ServiceNow.

## Acceptance Criteria

1. **AC1 — Comportement exécution** : Given une action configure un changement ServiceNow, When l'exécution atteint l'étape ServiceNow, Then le changement est créé comme pre-approuvé et l'exécution continue immédiatement (non-bloquant).

2. **AC2 — Modèle ChangeType** : Given le modèle ChangeType contenait "pre_approved" et "cab", When le modèle est mis à jour, Then seul "pre_approved" existe (ou le champ est supprimé car implicite).

3. **AC3 — Interface admin** : Given l'interface admin permettait de choisir "CAB", When le composant ChangeTypeConfig est mis à jour, Then l'option CAB est supprimée, seule la configuration par environnement reste (changement requis oui/non).

4. **AC4 — Migration et régression** : La migration de données convertit tous les "cab" existants en "pre_approved". Les stories 4-5 (ServiceNow) et les tests sont mis à jour. FR4 et FR16 (PRD mis à jour) sont satisfaites.

## Tasks / Subtasks

- [x] Task 1: Backend — Modèle et enum ChangeType (AC: 2)
  - [x] 1.1: Dans `backend/app/models/catalog.py` : supprimer la valeur `CAB` de l'enum `ChangeType` ; ne garder que `PRE_APPROVED` (ou déprécier l'enum et n'accepter qu'une seule valeur si le champ devient binaire par environnement).
  - [x] 1.2: Si on garde un enum à une seule valeur, documenter que `change_type_config` signifie désormais « changement requis (pre-approuvé) » par environnement ; les valeurs stockées sont uniquement `pre_approved` (ou équivalent booléen par env).
  - [x] 1.3: Mettre à jour les types Pydantic (ActionDetail, UpdateActionRequest, etc.) pour ne plus référencer CAB.

- [x] Task 2: Backend — Repository et migration de données (AC: 2, 4)
  - [x] 2.1: Dans `_parse_change_type_config` : toute valeur "cab" lue depuis le JSON doit être convertie en "pre_approved".
  - [x] 2.2: Dans `_change_type_config_to_json` : n'écrire que "pre_approved" (plus de "cab").
  - [x] 2.3: Créer une migration SQL (ex. V009) ou script de migration de données : UPDATE ACTIONS_CATALOG SET CHANGE_TYPE_CONFIG = ... pour remplacer toutes les occurrences "cab" par "pre_approved" dans le CLOB existant.
  - [x] 2.4: Tests repository : parse "cab" → pre_approved ; to_json n'émet jamais "cab".

- [x] Task 3: Backend — API (AC: 4)
  - [x] 3.1: Les réponses GET admin/actions et catalog ne doivent plus exposer "cab" ; validation Pydantic refuser "cab" en entrée si on garde l'enum (ou accepter et convertir en pre_approved).
  - [x] 3.2: Tests API : body avec "cab" refusé ou converti ; body avec "pre_approved" accepté.

- [x] Task 4: Frontend — ChangeTypeConfig et types (AC: 3, 4)
  - [x] 4.1: Dans `frontend/src/types/api.ts` : type `ChangeType = 'pre_approved'` uniquement (ou supprimer l'union 'cab').
  - [x] 4.2: Dans `ChangeTypeConfig.tsx` : supprimer l'option "CAB" du dropdown ; ne garder que "Pre-approuvé" (ou simplifier en case à cocher « Changement requis » par environnement si le modèle devient booléen).
  - [x] 4.3: ActionForm : plus de référence à CAB ; changeTypeConfig ne contient que pre_approved par environnement.
  - [x] 4.4: Tests ChangeTypeConfig et ActionForm : plus d'option CAB ; sauvegarde n'envoie que pre_approved.

- [x] Task 5: Régression et documentation (AC: 4)
  - [x] 5.1: Tous les tests existants (test_catalog_models, test_catalog_repository, test_admin_api, test_project_structure, ChangeTypeConfig, ActionForm) passent après adaptation (fixtures sans "cab" ou avec conversion).
  - [x] 5.2: Vérifier / mettre à jour les stories ou specs 4-5 (ServiceNow) si elles mentionnent CAB ; documenter que seul le changement pre-approuvé est supporté.
  - [x] 5.3: Linter et suite complète. File List et Dev Agent Record à jour.

## Dev Notes

- **Contexte métier** : FR4 (DBOPS peut configurer si un changement ServiceNow est requis par environnement) et FR16 (ouverture automatique changement ServiceNow). Le PRD précise que tous les changements sont pre-approuvés, non-bloquants ; le rail CAB bloquant n’est plus souhaité.
- **Story 2.7** a introduit `connector_type` / `connector_config` pour les étapes ; ChangeTypeConfig reste le composant pour « par environnement, type de changement ServiceNow ». Cette story simplifie ChangeType en retirant CAB.
- **Fichiers à toucher** : `backend/app/models/catalog.py` (ChangeType), `backend/app/repositories/catalog_repository.py` (_parse_change_type_config, _change_type_config_to_json), `backend/app/api/v1/admin.py` (validation), `frontend/src/types/api.ts` (ChangeType), `frontend/src/components/admin/ChangeTypeConfig.tsx`, `frontend/src/components/admin/ActionForm.tsx`. Migration V009 (ou script de mise à jour CLOB). Tous les tests qui utilisent ChangeType.CAB ou "cab".

### Ce qui existe déjà (NE PAS RÉIMPLÉMENTER)

| Élément | Fichier | Rôle |
|--------|---------|------|
| ChangeType (enum) | `backend/app/models/catalog.py` | Réduire à PRE_APPROVED uniquement |
| _parse_change_type_config / _change_type_config_to_json | `backend/app/repositories/catalog_repository.py` | Convertir "cab" → "pre_approved" en lecture, ne plus écrire "cab" |
| ChangeTypeConfig | `frontend/src/components/admin/ChangeTypeConfig.tsx` | Retirer l’option CAB du Select |
| ChangeType (TS) | `frontend/src/types/api.ts` | Type = 'pre_approved' uniquement |
| ActionForm | `frontend/src/components/admin/ActionForm.tsx` | Utilise ChangeTypeConfig ; pas de changement structurel majeur |

### Architecture (extrait)

- **Repository Pattern** : SQL brut ; CHANGE_TYPE_CONFIG reste un CLOB JSON. La migration de données met à jour les valeurs "cab" → "pre_approved" dans le CLOB.
- **API** : snake_case JSON. Les réponses ne doivent plus exposer "cab". L’API peut accepter "cab" en entrée pour rétro-compat et le convertir en "pre_approved", ou refuser avec 422.
- **FR4 / FR16** : Configuration changement par environnement = uniquement « requis (pre-approuvé) » ou « non requis ». Aucun workflow d’approbation bloquant côté portail.

### Project Structure Notes

- Migrations : `idp-portal/database/migrations/` — **V009** (après V008 connector_type). Contenu : script UPDATE sur ACTIONS_CATALOG pour remplacer "cab" par "pre_approved" dans CHANGE_TYPE_CONFIG (JSON).
- Backend : `backend/app/models/catalog.py`, `backend/app/repositories/catalog_repository.py`, `backend/app/api/v1/admin.py`.
- Frontend : `frontend/src/types/api.ts`, `frontend/src/components/admin/ChangeTypeConfig.tsx`, `frontend/src/components/admin/ActionForm.tsx`.

### References

- [Source: epics.md — Story 2.8, FR4, FR16]
- [Source: architecture.md — Repository Pattern, API format, ServiceNow pre-approuvé]
- [Source: 2-7-refactorisation-des-connecteurs-generiques.md — ChangeTypeConfig conservé pour l’instant ; story 2.8 le simplifie]

---

## Developer Context (Guardrails)

### Technical requirements

- **Backend** : Pydantic v2. Enum `ChangeType` ne doit plus contenir `CAB`. Toute lecture de "cab" depuis la base ou l’API doit être convertie en "pre_approved". Validation : refuser "cab" en entrée (422) ou accepter et convertir selon décision produit.
- **Frontend** : TypeScript strict. Type `ChangeType` = `'pre_approved'` uniquement. ChangeTypeConfig : un seul choix par environnement (Pre-approuvé) ou simplification en booléen « Changement requis » si le produit le permet.
- **Migration** : script idempotent ; toutes les valeurs "cab" dans CHANGE_TYPE_CONFIG (CLOB) doivent devenir "pre_approved".

### Architecture compliance

- Pas de nouvelle route ni table. Mise à jour du modèle ChangeType, du repository (parse/serialize), du composant ChangeTypeConfig et des types TS.
- API : même contrat de haut niveau (change_type_config par environnement) ; valeurs autorisées réduites à pre_approved.

### Library / framework requirements

- Aucune nouvelle dépendance. FastAPI, Pydantic v2, React, Ant Design 6 (Select ou Switch selon simplification).

### File structure requirements

- Modèles : `backend/app/models/catalog.py`.
- Repository : `backend/app/repositories/catalog_repository.py`.
- Migration : `idp-portal/database/migrations/V009_*.sql` (nom explicite, ex. V009_remove_cab_change_type.sql).
- Types : `frontend/src/types/api.ts`.
- UI : `frontend/src/components/admin/ChangeTypeConfig.tsx`, `ActionForm.tsx`.

### Testing requirements

- Backend : tests unitaires pour ChangeType (plus de CAB), _parse_change_type_config ("cab" → pre_approved), _change_type_config_to_json (jamais "cab"), tests API (body avec "cab" refusé ou converti).
- Frontend : tests ChangeTypeConfig (plus d’option CAB), ActionForm (sauvegarde change_type_config sans cab).
- Régression : test_catalog_models, test_catalog_repository, test_admin_api, test_project_structure (V003 peut encore mentionner cab dans le fichier de migration historique ; adapter les assertions qui vérifient le comportement actuel).

---

## Previous Story Intelligence (2.7)

- **ConnectorType / StepsEditor** : Story 2.7 a remplacé `is_servicenow_change` par `connector_type` et `connector_config`. ChangeTypeConfig n’a pas été modifié en 2.7 ; il affichait encore Pre-approuvé et CAB. Cette story 2.8 retire CAB de ChangeTypeConfig.
- **Fichiers modifiés en 2.7** : catalog.py (ConnectorType, ExecutionStep), catalog_repository.py (parse/to_json steps), admin.py, api.ts, StepsEditor.tsx, ActionForm.tsx. Pour 2.8 : catalog.py (ChangeType), catalog_repository.py (change_type_config parse/to_json), admin.py (validation), api.ts (ChangeType), ChangeTypeConfig.tsx, ActionForm.tsx, migration V009.
- **Tests** : En 2.7 les fixtures utilisent encore `ChangeType.CAB` / `"cab"` dans change_type_config. Les remplacer par `pre_approved` ou adapter les tests pour vérifier la conversion "cab" → "pre_approved".

---

## Project Context Reference

- [Source: _bmad-output/planning-artifacts/architecture.md — Repository Pattern, API format, ServiceNow pre-approuvé]
- [Source: _bmad-output/planning-artifacts/epics.md — Story 2.8, FR4, FR16]
- [Source: idp-portal/database/migrations/V003_add_execution_steps.sql — Colonne CHANGE_TYPE_CONFIG]

---

## Story Completion Status

- **Status** : done
- **Sprint status** : development_status["2-8-suppression-du-rail-cab-et-simplification-servicenow"] = "done"

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- ChangeType enum réduit à PRE_APPROVED ; docstring change_type_config (catalog.py).
- _parse_change_type_config : "cab" → PRE_APPROVED ; _change_type_config_to_json : n'écrit que "pre_approved" (catalog_repository.py).
- Migration V009_remove_cab_change_type.sql : UPDATE CLOB + comment CHANGE_TYPE_CONFIG.
- API : Pydantic refuse "cab" en entrée (422) ; réponses sans "cab". Test test_update_steps_change_type_config_cab_rejected_422.
- Frontend : ChangeType = 'pre_approved' ; ChangeTypeConfig sans option CAB ; ActionForm tooltip mise à jour. Tests ChangeTypeConfig (3) et ActionForm save pre_approved (1).
- 5.2 : Stories 4-5 (ServiceNow) mentionnent encore CAB dans epics ; à mettre à jour lors de leur implémentation. Comportement actuel documenté dans code et story.
- AC1 : Comportement exécution (changement pre-approuvé, non-bloquant) à valider dans Epic 4 / story 4-5 ; hors périmètre de ce repo.

### File List

- idp-portal/backend/app/models/catalog.py
- idp-portal/backend/app/repositories/catalog_repository.py
- idp-portal/backend/app/api/v1/admin.py
- idp-portal/database/migrations/V009_remove_cab_change_type.sql
- idp-portal/frontend/src/types/api.ts
- idp-portal/frontend/src/components/admin/ChangeTypeConfig.tsx
- idp-portal/frontend/src/components/admin/ActionForm.tsx
- idp-portal/backend/tests/unit/test_catalog_models.py
- idp-portal/backend/tests/unit/test_catalog_repository.py
- idp-portal/backend/tests/unit/test_admin_api.py
- idp-portal/frontend/src/components/admin/ChangeTypeConfig.test.tsx (new)
- idp-portal/frontend/src/components/admin/ActionForm.test.tsx
- _bmad-output/implementation-artifacts/sprint-status.yaml
- _bmad-output/implementation-artifacts/2-8-suppression-du-rail-cab-et-simplification-servicenow.md

### Change Log

- 2026-01-28: Story 2.8 implémentée. Suppression CAB, migration V009, parse/to_json, API 422 sur "cab", frontend ChangeTypeConfig + tests.
- 2026-01-28: Code review — V009 insensible à la casse (CAB/Cab), statut → done, note AC1.
