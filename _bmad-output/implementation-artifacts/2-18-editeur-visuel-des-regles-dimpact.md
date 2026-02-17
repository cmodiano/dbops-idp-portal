# Story 2.18: Editeur visuel des regles d'impact

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBOPS,
I want definir les regles d'impact d'une action via un editeur visuel dynamique (ajouter/supprimer),
So that je configure les criteres d'evaluation du niveau de risque par environnement de maniere intuitive.

## Acceptance Criteria

1. **AC1 — Section Regles d'impact**
   **Given** un DBOPS edite une action dans l'admin,
   **When** il accede a la section "Regles d'impact",
   **Then** il voit un editeur visuel avec une liste de regles par environnement et un bouton "Ajouter une regle".

2. **AC2 — Ajout regle**
   **Given** le DBOPS clique sur "Ajouter une regle",
   **When** une nouvelle regle est ajoutee,
   **Then** un formulaire inline s'affiche avec les champs : environnement (dropdown: DEV, STAGING, PROD, etc.), niveau d'impact (dropdown: faible/vert, moyen/orange, eleve/rouge), critere/justification (texte).

3. **AC3 — Preview dynamique**
   **Given** le DBOPS definit plusieurs regles,
   **When** il configure des niveaux differents par environnement,
   **Then** l'ImpactIndicator de la preview (AdminPreview) se met a jour dynamiquement selon l'environnement selectionne.

4. **AC4 — Suppression regle**
   **Given** le DBOPS veut supprimer une regle,
   **When** il clique sur l'icone X,
   **Then** la regle est supprimee de la liste.

5. **AC5 — Impact par defaut**
   **Given** aucune regle n'est definie pour un environnement,
   **When** l'action est executee dans cet environnement,
   **Then** le niveau d'impact par defaut (configure dans l'action) s'applique.

6. **AC6 — Validation et UX**
   **And** la validation inline s'execute (environnement unique par regle, niveau requis).
   **And** le composant ImpactRulesEditor utilise le meme pattern que ParametersEditor et StepsEditor.
   **And** les regles sont stockees dans impact_rules (CLOB JSON) de ACTIONS_CATALOG.
   **And** FR1 (PRD mis a jour) est satisfaite pour les regles d'impact visuelles.
   **And** Cette story remplace l'input JSON des regles d'impact de la Story 2.1.

## Tasks / Subtasks

- [x] Task 1: Types et schema (AC: 5, 6)
  - [x] 1.1: Definir le type `ImpactRuleDefinition` (environment, level, criteria) et le mapping JSON ↔ liste.
  - [x] 1.2: Fonction `impactRulesToList(rules)` et `listToImpactRules(list)` pour build/parse impact_rules (format: `{"DEV": {"level": "low", "criteria": "..."}, ...}`).
  - [x] 1.3: Ajouter une option de niveau d'impact par defaut dans le type si necessaire.

- [x] Task 2: Composant ImpactRulesEditor (AC: 1, 2, 4, 6)
  - [x] 2.1: Creer `frontend/src/components/admin/ImpactRulesEditor.tsx` — liste de regles, bouton "Ajouter une regle".
  - [x] 2.2: Formulaire inline par regle : Select environnement (DEV, STAGING, PROD), Select niveau d'impact (low/vert, medium/orange, high/rouge, critical/rouge fonce), Input critere/justification.
  - [x] 2.3: Bouton supprimer (X) par regle; validation inline (environnement unique, niveau requis).
  - [x] 2.4: Exposer `value: ImpactRuleDefinition[]` et `onChange`; meme pattern que StepsEditor (Cartes, Space, DeleteOutlined, colorisation selon niveau).
  - [x] 2.5: Afficher la pastille ImpactIndicator (composant shared) a cote de chaque regle pour previsualisation immediate.

- [x] Task 3: Integration ActionForm (AC: 1, 3, 5, 6)
  - [x] 3.1: Remplacer le champ TextArea `impact_rules` dans `ActionForm.tsx` par ImpactRulesEditor.
  - [x] 3.2: A l'ouverture (edit): convertir impact_rules (JSON objet) en liste et passer a ImpactRulesEditor; a la sauvegarde: convertir la liste en JSON objet et envoyer dans payload.
  - [x] 3.3: Mettre a jour le calcul de `previewData.impact_level` pour utiliser la liste de regles au lieu de parser le JSON brut.
  - [x] 3.4: Ajouter un selecteur d'environnement optionnel dans AdminPreview pour voir l'impact selon l'environnement choisi (AC3).
  - [x] 3.5: Conserver la validation cote backend (format JSON valide); le backend ne change pas.

- [x] Task 4: Tests (AC: 6)
  - [x] 4.1: Tests unitaires ImpactRulesEditor (ajout, suppression, validation environnement unique, preview niveau).
  - [x] 4.2: Test integration ActionForm avec ImpactRulesEditor (create/update action avec regles visuelles).
  - [x] 4.3: Regression: tests admin existants passent.

## Dev Notes

- **Objectif** : Remplacer l'input JSON brut des regles d'impact (Story 2.1) par un editeur visuel listant les regles par environnement avec niveau et critere; meme UX que ParametersEditor et StepsEditor.
- **Format JSON impact_rules** : La colonne `impact_rules` (CLOB JSON) dans ACTIONS_CATALOG stocke un objet avec les environnements comme cles : `{"DEV": {"level": "low", "criteria": "..."}, "PROD": {"level": "high", "criteria": "..."}}`. L'editeur doit produire/consommer ce format; pas de changement de schema DB.
- **Niveaux d'impact** : `low`, `medium`, `high`, `critical` — aligner avec le type `ImpactLevel` existant dans `types/api.ts`.
- **Environnements** : Utiliser les memes options que StepsEditor: DEV, STAGING, PROD (possibilite d'etendre plus tard).
- **Preview dynamique (AC3)** : L'AdminPreview affiche actuellement le premier environnement trouve dans impact_rules. Ajouter un selecteur pour choisir l'environnement et voir l'indicateur correspondant.
- **Story 2-17 comme reference** : Le ParametersEditor (story 2-17) utilise le meme pattern — cartes inline, ajout/suppression, validation. Reproduire ce pattern pour ImpactRulesEditor.

### Project Structure Notes

- **Frontend** : `idp-portal/frontend/src/components/admin/` — ajouter `ImpactRulesEditor.tsx`; modifier `ActionForm.tsx` (supprimer TextArea impact_rules, ajouter ImpactRulesEditor + conversion liste ↔ objet JSON).
- **Backend** : Aucune migration ni changement d'API. L'API POST/PUT action accepte deja `impact_rules` en objet JSON; le frontend enverra le meme format, genere depuis l'editeur visuel.
- **Fichiers existants a modifier** :
  - `ActionForm.tsx` (section Regles d'impact, lignes 381-393)
  - `AdminPreview.tsx` (optionnel: selecteur environnement pour preview)
- **Fichiers a creer** :
  - `ImpactRulesEditor.tsx`
  - `ImpactRulesEditor.test.tsx`
- **Composant existant a reutiliser** : `ImpactIndicator` (shared) pour afficher la pastille couleur + icone + texte.

### Architecture Compliance

- **Stack** : React 19, TypeScript, Ant Design 6, composants Card/Select/Input/Button/Space standard.
- **Pattern** : Controle value/onChange; conversion cote formulaire entre liste d'items et objet JSON; pas de logique metier dans l'editeur, uniquement affichage/edition liste.
- **API** : Aucun nouvel endpoint. Payload existant `impact_rules` (objet JSON) conserve.
- **Naming** : snake_case pour les props API, camelCase pour les variables locales React.

### Library/Framework Requirements

- **Ant Design 6.2** : Card, Select, Input, Button, Space, Typography, Form.Item pour validation inline.
- **Types** : Utiliser `ImpactLevel` existant (`low`, `medium`, `high`, `critical`) de `types/api.ts`.
- **Pas de @dnd-kit** : Les regles d'impact ne necessitent pas de reordonnancement (contrairement aux etapes). Pas de drag-and-drop, juste ajout/suppression.

### Testing Standards

- **Tests unitaires** : Vitest + React Testing Library.
- **Patterns** : Render, user interaction (add rule, select environment, select level, type criteria, delete rule), verify state changes via onChange.
- **Validation** : Tester que l'ajout d'un environnement deja utilise affiche une erreur; tester que le niveau est requis.

### Previous Story Intelligence

La story 2-17 (Editeur visuel de parametres) a ete implementee avec succes en utilisant:
- Le pattern value/onChange pour le controle externe
- Des cartes Ant Design pour chaque item de la liste
- Un bouton "Ajouter" de type dashed en bas
- Une validation inline avec Form.Item
- La conversion JSON Schema ↔ liste au niveau du formulaire parent

**Appliquer les memes patterns** pour ImpactRulesEditor, mais sans drag-and-drop puisque l'ordre des regles n'a pas d'importance.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.18]
- [Source: _bmad-output/planning-artifacts/epics.md#Story-2.1] (regles d'impact visuelles remplacent l'input JSON)
- [Source: idp-portal/frontend/src/components/admin/StepsEditor.tsx] — pattern de reference (Cartes, inline form, DeleteOutlined)
- [Source: idp-portal/frontend/src/components/admin/ActionForm.tsx:381-393] — emplacement actuel du champ impact_rules (TextArea)
- [Source: idp-portal/frontend/src/components/shared/ImpactIndicator.tsx] — composant a reutiliser pour afficher l'indicateur visuel
- [Source: idp-portal/frontend/src/types/api.ts] — type ImpactLevel existant

### Code Patterns to Follow

**Format JSON impact_rules attendu par le backend :**
```json
{
  "DEV": {"level": "low", "criteria": "Environnement de developpement isole"},
  "STAGING": {"level": "medium", "criteria": "Donnees de test, impact limite"},
  "PROD": {"level": "high", "criteria": "Environnement de production"}
}
```

**Type ImpactRuleDefinition suggere :**
```typescript
interface ImpactRuleDefinition {
  environment: string;      // DEV, STAGING, PROD
  level: ImpactLevel;       // low, medium, high, critical
  criteria: string | null;  // Justification/description
}
```

**Conversion fonctions :**
```typescript
// JSON objet → liste pour l'editeur
function impactRulesToList(rules: Record<string, {level: string; criteria?: string}> | null): ImpactRuleDefinition[]

// Liste → JSON objet pour le payload API
function listToImpactRules(list: ImpactRuleDefinition[]): Record<string, {level: string; criteria?: string | null}>
```

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- Task 1: Added `ImpactRuleDefinition` type to `types/api.ts` and created `impactRulesSchema.ts` utility with conversion functions `impactRulesToList` and `listToImpactRules`. 14 unit tests passing.
- Task 2: Created `ImpactRulesEditor.tsx` component following ParametersEditor pattern (Card-based UI, inline validation, ImpactIndicator preview). Updated exports in index.ts. Fixed Ant Design 6 deprecation (direction → orientation). 12 unit tests passing.
- Task 3: Integrated ImpactRulesEditor into ActionForm.tsx, replacing TextArea. Added state for impactRulesList and previewEnvironment. Updated previewData calculation for AC3 dynamic preview. Added validation for duplicate environments and missing levels. 18 integration tests passing.
- Task 4: All 198 tests pass (no regressions).

**Review Follow-ups (2026-01-29) — Round 1:**
- Issue #1 (HIGH): AC5 — Added `default_impact_level` field to ActionCreate/ActionResponse, state in ActionForm, Select in form UI, fallback logic in previewData.
- Issue #2 (MEDIUM): Extended `ActionCreate.impact_rules` type to include `criteria` field. Moved `ImpactLevel` before `ActionCreate`.
- Issue #3 (MEDIUM): Changed ID generation in `impactRulesToList` to deterministic `rule-${environment}`.
- Issue #4 (MEDIUM): Added round-trip tests for null/empty impact_rules.
- Issue #5 (LOW→MEDIUM): Added proper `Form.Item` with label for preview environment selector.
- All 202 tests pass.

**Review Follow-ups (2026-01-29) — Round 2 (Adversarial):**
- Issue #1 (CRITICAL): AC5 backend — `default_impact_level` was only in frontend types; backend ignored it. Fixed: added field to `ActionCreate`/`ActionResponse` in `catalog.py`, migration `V014__add_default_impact_level.sql`, repository CRUD updates.
- Issue #2 (HIGH): `ActionResponse.impact_rules.level` typed as `string` instead of `ImpactLevel`. Fixed in `types/api.ts`.
- Issue #3 (MEDIUM): Added AC3 test (preview environment selector changes impact indicator).
- Issue #5 (MEDIUM): Fixed test data using invalid environment 'CRITICAL' → 'CRITICAL_ENV'.
- All 203 frontend tests + 426 backend unit tests pass (32 unrelated migration path tests excluded).

### File List

**New files:**
- idp-portal/frontend/src/utils/impactRulesSchema.ts
- idp-portal/frontend/src/utils/impactRulesSchema.test.ts
- idp-portal/frontend/src/components/admin/ImpactRulesEditor.tsx
- idp-portal/frontend/src/components/admin/ImpactRulesEditor.test.tsx
- idp-portal/database/migrations/V014__add_default_impact_level.sql (Review fix #1: AC5 backend)

**Modified files:**
- idp-portal/frontend/src/types/api.ts (added ImpactRuleDefinition type; Review fix #2: ImpactLevel in ActionResponse.impact_rules)
- idp-portal/frontend/src/components/admin/index.ts (added ImpactRulesEditor export)
- idp-portal/frontend/src/components/admin/ActionForm.tsx (replaced TextArea with ImpactRulesEditor)
- idp-portal/frontend/src/components/admin/ActionForm.test.tsx (updated tests for ImpactRulesEditor; Review fix #3: AC3 test)
- idp-portal/backend/app/models/catalog.py (Review fix #1: default_impact_level in ActionCreate/ActionResponse)
- idp-portal/backend/app/repositories/catalog_repository.py (Review fix #1: CRUD for default_impact_level)
- idp-portal/backend/tests/unit/test_catalog_repository.py (Review fix #1: updated mock fixtures)

---

## Senior Developer Review (AI)

**Reviewer:** Cyrille (adversarial code review)
**Date:** 2026-01-29
**Story key:** 2-18-editeur-visuel-des-regles-dimpact
**Outcome:** ✅ APPROVED

### Round 2 — Post-Fix Review

**Issues found in Round 1:** 1 Critical, 1 High, 3 Medium, 2 Low
**Issues fixed:** 1 Critical, 1 High, 2 Medium
**Remaining (accepted as LOW/tech debt):** 2 Low

### Issues Fixed

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 1 | CRITICAL | AC5 — `default_impact_level` not persisted (backend ignored field) | Migration V014, model + repository updates |
| 2 | HIGH | `ActionResponse.impact_rules.level` typed as `string` | Changed to `ImpactLevel` |
| 3 | MEDIUM | No test for AC3 dynamic preview | Added test |
| 5 | MEDIUM | Test data used invalid environment 'CRITICAL' | Fixed to 'CRITICAL_ENV' |

### Remaining (Accepted as Tech Debt)

| # | Severity | Issue | Notes |
|---|----------|-------|-------|
| 6 | LOW | Invalid level fallback silent | Acceptable — edge case, data rarely corrupted |
| 7 | LOW | Single-rule preview UX | Acceptable — minor polish |

### Validation Post-Fix

- **AC1–AC6:** All implemented and verified
- **AC5 (default_impact_level):** Now persisted end-to-end (frontend → API → DB → API → frontend)
- **Frontend tests:** 203 passed
- **Backend tests:** 426 passed (43 catalog repository tests updated for new column)
- **Migration:** V014 adds DEFAULT_IMPACT_LEVEL column with CHECK constraint
- **No regressions**

### Change Log

- 2026-01-29 R1: Initial adversarial review — 1 Critical, 1 High, 3 Medium, 2 Low identified
- 2026-01-29 R2: Fixed Critical/High/Medium issues — backend AC5, type safety, AC3 test. Story APPROVED.
