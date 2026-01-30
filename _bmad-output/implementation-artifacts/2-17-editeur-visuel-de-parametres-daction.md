# Story 2.17: Editeur visuel de parametres d'action

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBOPS,
I want definir les parametres d'une action via un editeur visuel dynamique (ajouter/supprimer) au lieu d'un input JSON,
So that je configure les parametres de maniere intuitive sans risque d'erreur de syntaxe JSON.

## Acceptance Criteria

1. **AC1 — Section Parametres**  
   **Given** un DBOPS edite une action dans l'admin,  
   **When** il accede a la section "Parametres",  
   **Then** il voit un editeur visuel avec une liste de parametres et un bouton "Ajouter un parametre".

2. **AC2 — Ajout parametre**  
   **Given** le DBOPS clique sur "Ajouter un parametre",  
   **When** un nouveau parametre est ajoute,  
   **Then** un formulaire inline s'affiche avec les champs : nom (texte), type (dropdown: string, number, boolean, date, select, etc.), requis (toggle oui/non), valeur par defaut (texte), description (texte).

3. **AC3 — Reordonner / supprimer**  
   **Given** le DBOPS a plusieurs parametres,  
   **When** il veut reordonner ou supprimer un parametre,  
   **Then** il peut drag-and-drop pour reordonner et cliquer sur l'icone X pour supprimer un parametre.

4. **AC4 — Sauvegarde et schema**  
   **Given** le DBOPS sauvegarde l'action,  
   **When** les parametres sont valides,  
   **Then** le systeme genere automatiquement le JSON schema en backend et le stocke dans parameters_schema.

5. **AC5 — Migration affichage**  
   **Given** une action existante a des parametres en JSON schema,  
   **When** le DBOPS ouvre le formulaire d'edition,  
   **Then** les parametres existants sont affiches dans l'editeur visuel (migration de l'affichage).

6. **AC6 — Validation et UX**  
   **And** la validation inline s'execute sur chaque champ (nom requis, nom unique, type requis).  
   **And** le composant ParametersEditor utilise le meme pattern que StepsEditor (UX coherente).  
   **And** FR1 (PRD mis a jour) est satisfaite pour les parametres visuels.  
   **And** Cette story remplace l'input JSON schema de la Story 2.1.

## Tasks / Subtasks

- [x] Task 1: Types et schema (AC: 4, 5)
  - [x] 1.1: Definir le type `ParameterDefinition` (name, type, required, default, description) et la conversion JSON Schema ↔ liste (frontend + alignement backend si besoin).
  - [x] 1.2: Fonction `schemaToParameterList(schema)` et `parameterListToSchema(list)` pour build/parse parameters_schema.

- [x] Task 2: Composant ParametersEditor (AC: 1, 2, 3, 6)
  - [x] 2.1: Creer `frontend/src/components/admin/ParametersEditor.tsx` — liste de parametres, bouton "Ajouter un parametre".
  - [x] 2.2: Formulaire inline par parametre : Input nom, Select type (string, number, boolean, date, select, etc.), Switch requis, Input valeur par defaut, Input description.
  - [x] 2.3: Drag-and-drop pour reordonner (meme stack que StepsEditor : @dnd-kit/core + @dnd-kit/sortable).
  - [x] 2.4: Bouton supprimer (X) par parametre; validation inline (nom requis, nom unique, type requis).
  - [x] 2.5: Exposer `value: ParameterDefinition[]` et `onChange`; meme pattern que StepsEditor (Cartes, Space, HolderOutlined, DeleteOutlined).

- [x] Task 3: Integration ActionForm (AC: 1, 4, 5, 6)
  - [x] 3.1: Remplacer le champ TextArea `parameters_schema` dans `ActionForm.tsx` par ParametersEditor.
  - [x] 3.2: A l'ouverture (edit): convertir parameters_schema (JSON) en liste et passer a ParametersEditor; a la sauvegarde: convertir la liste en JSON schema et envoyer dans payload.
  - [x] 3.3: Conserver la validation cote backend (schema valide); le backend ne change pas (il recoit deja parameters_schema en JSON).

- [x] Task 4: Tests (AC: 6)
  - [x] 4.1: Tests unitaires ParametersEditor (ajout, suppression, reordre, validation).
  - [x] 4.2: Test integration ActionForm avec ParametersEditor (create/update action avec parametres visuels).
  - [x] 4.3: Regression: tests admin existants (POST/GET actions, steps, tags) passent.

## Dev Notes

- **Objectif** : Remplacer l’input JSON brut des parametres (Story 2.1) par un editeur visuel listant les parametres avec nom, type, requis, defaut, description; meme UX que StepsEditor (drag-and-drop, cartes, inline form).
- **Source donnees** : La colonne `parameters_schema` (CLOB JSON) dans ACTIONS_CATALOG stocke deja un JSON Schema (type "object", properties, required). Le frontend doit produire/consommer ce format; pas de changement de schema DB.
- **Types JSON Schema utiles** : string, number, integer, boolean, date, date-time; pour "select" on peut utiliser enum dans le schema. Aligner les options du dropdown avec ce que le backend/catalog accepte (voir `catalog.py` validate_parameters_schema).

### Project Structure Notes

- **Frontend** : `idp-portal/frontend/src/components/admin/` — ajouter `ParametersEditor.tsx`; modifier `ActionForm.tsx` (supprimer TextArea parameters_schema, ajouter ParametersEditor + conversion liste ↔ schema).
- **Backend** : Aucune migration ni changement d’API. L’API POST/PUT action accepte deja `parameters_schema` en objet JSON; le frontend enverra le meme format, genere depuis l’editeur visuel.
- **Fichiers existants a modifier** : `ActionForm.tsx` (section Parametres). Fichiers a creer : `ParametersEditor.tsx`, eventuellement `ParametersEditor.test.tsx`.

### Architecture Compliance

- **Stack** : React 19, TypeScript, Ant Design 6, @dnd-kit pour le drag-and-drop (deja utilise dans StepsEditor).
- **Pattern** : Controle value/onChange; conversion cote formulaire entre liste d’items et JSON schema; pas de logique metier dans l’editeur, uniquement affichage/édition liste.
- **API** : Aucun nouvel endpoint. Payload existant `parameters_schema` (objet) conserve.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.17]
- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.1] (parametres visuels remplacent l’input JSON)
- [Source: idp-portal/frontend/src/components/admin/StepsEditor.tsx] — pattern a reproduire (DndContext, SortableContext, Cartes, HolderOutlined, DeleteOutlined)
- [Source: idp-portal/frontend/src/components/admin/ActionForm.tsx] — emplacement actuel du champ parameters_schema (TextArea)
- [Source: idp-portal/backend/app/models/catalog.py] — validation parameters_schema (JSON Schema reconnu)

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- Task 1: Types `ParameterDefinition` et `ParameterSchemaType` ajoutes dans `api.ts`; utilitaire `parametersSchema.ts` avec `schemaToParameterList` et `parameterListToSchema`; tests unitaires dans `parametersSchema.test.ts` (10 tests).
- Task 2: Composant `ParametersEditor.tsx` cree (liste, formulaire inline, DnD @dnd-kit, validation nom requis/unique, types string/number/integer/boolean/date/date-time/select avec enum).
- Task 3: `ActionForm.tsx` — champ TextArea parameters_schema remplace par ParametersEditor; state `parameterList`; conversion schema ↔ liste a l’ouverture et a la sauvegarde; preview utilise `parameterListToSchema(parameterList)`.
- Task 4: Tests ParametersEditor (9 tests), tests ActionForm (AC5 migration, edit submit parameters_schema); test JSON invalide adapte pour impact_rules; regression frontend 168 tests, backend 458 tests OK.
- Code-review 2026-01-29: Validation paramètres avant sauvegarde (AC4) dans ActionForm (nom requis, noms uniques); clés stables ParametersEditor (id optionnel); tests reorder (ordre affiché + poignée DnD); note File List 2-14 vs 2-17.

### File List

_Note: Les changements backend (admin, catalog, profiles, auth, catalog_repository, models), la migration V013 et la suppression de RbacEditor dans le même diff git appartiennent à la story 2-14, pas à la 2-17._

- idp-portal/frontend/src/types/api.ts (ParameterDefinition, ParameterSchemaType, id optionnel)
- idp-portal/frontend/src/utils/parametersSchema.ts (nouveau)
- idp-portal/frontend/src/utils/parametersSchema.test.ts (nouveau)
- idp-portal/frontend/src/components/admin/ParametersEditor.tsx (nouveau)
- idp-portal/frontend/src/components/admin/ParametersEditor.test.tsx (nouveau)
- idp-portal/frontend/src/components/admin/index.ts (export ParametersEditor)
- idp-portal/frontend/src/components/admin/ActionForm.tsx (ParametersEditor, parameterList, conversion)
- idp-portal/frontend/src/components/admin/ActionForm.test.tsx (tests 2.17, validation impact_rules)
- _bmad-output/implementation-artifacts/sprint-status.yaml (2-17 in-progress puis review)
- _bmad-output/implementation-artifacts/2-17-editeur-visuel-de-parametres-daction.md (tasks, Dev Agent Record, File List, Status)

## Change Log

- 2026-01-29: Implementation complete — ParametersEditor, conversion schema/liste, integration ActionForm, tests unitaires et integration, regression frontend/backend OK. Status → review.
- 2026-01-29: Code-review — correctifs AC4 (validation paramètres avant save), clés stables DnD, tests reorder, note File List 2-14.
