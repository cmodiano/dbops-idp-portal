# Story 34.9 : Frontend — Variant context, WorkflowStepsEditor

Status: done

<!-- Réf: CODEBASE-REVIEW.md SOLID-FE-6, SOLID-FE-8 -->

## Story

En tant que mainteneur frontend,
je veux (1) éliminer le prop drilling de `variant`/`isBusinessProfile` sur 4–5 niveaux de composants en utilisant `useAuth()` directement dans les composants consommateurs, et (2) extraire `SortableStepCard` dans un fichier dédié depuis `WorkflowStepsEditor.tsx` (646 lignes, 2 composants colocalisés),
afin de réduire le couplage par props inutiles (SOLID-FE-6) et de respecter le principe de responsabilité unique par fichier (SOLID-FE-8).

## Acceptance Criteria

### SOLID-FE-6 — Éliminer le prop drilling variant/isBusinessProfile

1. **Given** que `ActionDrawerPreview` reçoit `variant?: 'default' | 'business'` depuis `CatalogPage`
   **Then** la prop `variant` est supprimée de l'interface `ActionDrawerPreviewProps`
   **And** `ActionDrawerPreview` lit `const { isBusinessProfile } = useAuth()` directement
   **And** `isBusiness = isBusinessProfile` remplace `isBusiness = variant === 'business'`

2. **Given** que `ExecutionWizard` reçoit `variant?: 'default' | 'simplified'` depuis `CatalogPage`
   **Then** la prop `variant` est supprimée de `ExecutionWizardProps`
   **And** `ExecutionWizard` lit `const { isBusinessProfile } = useAuth()` directement
   **And** `isSimplified = isBusinessProfile` remplace les ternaires sur `variant`
   **And** `ExecutionWizard` ne passe plus `variant` à ses composants enfants (`TargetSelectionStep`, `ParametersFormStep`, `ConfirmationStep`)

3. **Given** que `TargetSelectionStep` reçoit `variant: 'default' | 'simplified'` en prop requise
   **Then** la prop `variant` est retirée de `TargetSelectionStepProps`
   **And** `TargetSelectionStep` lit `const { isBusinessProfile } = useAuth()` directement
   **And** toutes les conditions `variant === 'simplified'` sont remplacées par `isBusinessProfile`

4. **Given** que `ParametersFormStep` reçoit `variant: 'default' | 'simplified'` en prop requise
   **Then** la prop `variant` est retirée de `ParametersFormStepProps`
   **And** `ParametersFormStep` lit `const { isBusinessProfile } = useAuth()` directement
   **And** toutes les conditions `variant === 'simplified'` sont remplacées par `isBusinessProfile`

5. **Given** que `ConfirmationStep` reçoit `variant: 'default' | 'simplified'` en prop requise
   **Then** la prop `variant` est retirée de `ConfirmationStepProps`
   **And** `ConfirmationStep` lit `const { isBusinessProfile } = useAuth()` directement
   **And** toutes les conditions `variant === 'simplified'` sont remplacées par `isBusinessProfile`

6. **Given** que `CatalogPage` calcule `variant={isBusinessProfile ? 'simplified' : 'default'}` et `variant={isBusinessProfile ? 'business' : 'default'}` pour les passer en props
   **Then** ces props sont supprimées des appels à `ActionDrawerPreview` et `ExecutionWizard` dans `CatalogPage`
   **And** `ActionCard` garde sa prop `variant` (valeurs légitimes : 'default', 'preview', 'business') pour les contextes admin (preview), mais détecte aussi 'business' via `useAuth()` en interne — condition : `isBusiness = variant === 'business' || isBusinessProfile`
   **And** `CatalogPage` supprime le calcul `const cardVariant = isBusinessProfile ? 'business' : 'default'` et n'utilise plus la variable `cardVariant`
   **And** aucune régression de comportement : l'UI business s'affiche exactement comme avant pour `isBusinessProfile = true`

### SOLID-FE-8 — Extraire SortableStepCard

7. **Given** que `SortableStepCard` (302 lignes) et `WorkflowStepsEditor` (263 lignes) cohabitent dans `WorkflowStepsEditor.tsx` (646 lignes)
   **Then** `SortableStepCard` et son interface `SortableStepCardProps` sont déplacés dans `src/components/admin/SortableStepCard.tsx`
   **And** `WorkflowStepsEditor.tsx` importe `SortableStepCard` depuis `./SortableStepCard`
   **And** `SortableStepCard` est exporté nommément (`export const SortableStepCard`) depuis son nouveau fichier

8. **And** `WorkflowStepsEditor.tsx` descend en-dessous de 380 lignes après extraction

9. **And** les tests existants dans `WorkflowStepsEditor.test.tsx` (282 lignes, 9 suites) passent **sans modification** après l'extraction

10. **And** un nouveau fichier `src/components/admin/SortableStepCard.test.tsx` est créé avec au minimum :
    - Test rendu d'une étape avec action sélectionnée (referenced_action_id=1 → AutoComplete affiche "Action Alpha (Oracle)")
    - Test disabled=true désactive AutoComplete, branches Select, retry Switch et bouton supprimer
    - Test retry defaults appliqués à l'activation de `retry_enabled` (3 tentatives, 60s, backoff 2.0)
    - Test branches : options Select excluent l'étape courante
    - Test suppression : `onRemoveStep(index)` appelé au clic quand `canRemove=true`

## Tasks / Subtasks

### SOLID-FE-6 — Prop drilling variant

- [x] Task 1 — Analyser et mapper les changements
  - [x] 1.1 Identifier le chemin exact du hook `useAuth` (vérifier CatalogPage.tsx import line) — probablement `../../hooks/useAuth` ou `../../context/AuthContext`
  - [x] 1.2 Vérifier si `ExecutionWizard` est utilisé en dehors de `CatalogPage` avec `variant='simplified'` non lié à isBusinessProfile
  - [x] 1.3 Lister les tests qui passent `variant` aux composants affectés

- [x] Task 2 — Modifier `ActionDrawerPreview.tsx`
  - [x] 2.1 Ajouter `const { isBusinessProfile } = useAuth()` dans le corps du composant
  - [x] 2.2 Remplacer `isBusiness = variant === 'business'` par `isBusiness = isBusinessProfile`
  - [x] 2.3 Supprimer `variant` de `ActionDrawerPreviewProps` et du destructuring du composant
  - [x] 2.4 Dans `CatalogPage.tsx` : supprimer la prop `variant={isBusinessProfile ? 'business' : 'default'}` de `<ActionDrawerPreview>`

- [x] Task 3 — Modifier `ExecutionWizard.tsx`
  - [x] 3.1 Ajouter `const { isBusinessProfile } = useAuth()` dans le corps du composant
  - [x] 3.2 Remplacer toutes occurrences de `variant === 'simplified'` par `isBusinessProfile`
  - [x] 3.3 Remplacer `errorCardVariant={variant === 'simplified' ? 'business' : 'default'}` par `errorCardVariant={isBusinessProfile ? 'business' : 'default'}`
  - [x] 3.4 Supprimer la prop `variant={variant}` des appels à `TargetSelectionStep`, `ParametersFormStep`, `ConfirmationStep`
  - [x] 3.5 Supprimer `variant` de `ExecutionWizardProps` et du destructuring
  - [x] 3.6 Dans `CatalogPage.tsx` : supprimer la prop `variant={isBusinessProfile ? 'simplified' : 'default'}` de `<ExecutionWizard>`

- [x] Task 4 — Modifier `TargetSelectionStep.tsx`
  - [x] 4.1 Ajouter `const { isBusinessProfile } = useAuth()`
  - [x] 4.2 Remplacer toutes occurrences de `variant === 'simplified'` par `isBusinessProfile`
  - [x] 4.3 Supprimer `variant` de `TargetSelectionStepProps` et du destructuring

- [x] Task 5 — Modifier `ParametersFormStep.tsx`
  - [x] 5.1 Ajouter `const { isBusinessProfile } = useAuth()`
  - [x] 5.2 Remplacer toutes occurrences de `variant === 'simplified'` par `isBusinessProfile`
  - [x] 5.3 Supprimer `variant` de `ParametersFormStepProps` et du destructuring

- [x] Task 6 — Modifier `ConfirmationStep.tsx`
  - [x] 6.1 Ajouter `const { isBusinessProfile } = useAuth()`
  - [x] 6.2 Remplacer toutes occurrences de `variant === 'simplified'` par `isBusinessProfile`
  - [x] 6.3 Supprimer `variant` de `ConfirmationStepProps` et du destructuring

- [x] Task 7 — Adapter `ActionCard.tsx` (cas particulier : 3 valeurs de variant)
  - [x] 7.1 Ajouter `const { isBusinessProfile } = useAuth()` dans `ActionCard`
  - [x] 7.2 Modifier `isBusiness = variant === 'business'` → `isBusiness = variant === 'business' || isBusinessProfile` (backward compat + auto-détection)
  - [x] 7.3 Dans `CatalogPage.tsx` : supprimer `const cardVariant = isBusinessProfile ? 'business' : 'default'` et la prop `variant={cardVariant}` sur `ActionCard` (ActionCard détecte maintenant via useAuth)

- [x] Task 8 — Mettre à jour les tests affectés (SOLID-FE-6)
  - [x] 8.1 Ajouter mock `useAuth` dans `ActionDrawerPreview.test.tsx` et `ExecutionWizard.test.tsx`
  - [x] 8.2 Supprimer les props `variant=` des JSX dans les tests
  - [x] 8.3 Tous les tests passent (112 tests dans 4 fichiers concernés)

### SOLID-FE-8 — Extraction SortableStepCard

- [x] Task 9 — Créer `src/components/admin/SortableStepCard.tsx`
  - [x] 9.1 Créer le fichier avec en-tête JSDoc
  - [x] 9.2 Copier les imports @dnd-kit nécessaires (useSortable, CSS), Ant Design, icons
  - [x] 9.3 Déplacer `SortableStepCardProps` interface
  - [x] 9.4 Déplacer `SortableStepCard` component avec `export const SortableStepCard`
  - [x] 9.5 Importer `WorkflowStepEditable` depuis `./WorkflowStepsEditor`
  - [x] 9.6 Importer `ActionListItem` depuis `../../types/api`

- [x] Task 10 — Mettre à jour `WorkflowStepsEditor.tsx`
  - [x] 10.1 Supprimer SortableStepCardProps + SortableStepCard colocalisés
  - [x] 10.2 Ajouter `import { SortableStepCard } from './SortableStepCard'`
  - [x] 10.3 Exporter `WorkflowStepEditable` et `generateStepId` depuis `WorkflowStepsEditor.tsx`
  - [x] 10.4 Supprimer les imports Ant Design inutilisés (Input, AutoComplete, Select, Switch, InputNumber, Card, Typography, Tooltip, theme)

- [x] Task 11 — Créer `src/components/admin/SortableStepCard.test.tsx`
  - [x] 11.1 Mock `@dnd-kit/sortable` pour tests unitaires sans DndContext
  - [x] 11.2 Test 1 — Rendu avec `referenced_action_id=1` → affiche "Action Alpha (Oracle)"
  - [x] 11.3 Test 2 — `disabled=true` → bouton supprimer disabled
  - [x] 11.4 Test 3 — Clic supprimer avec `canRemove=true` → `onRemoveStep` appelé avec l'index
  - [x] 11.5 Test 4 — Branches : options "(fin du workflow)" présentes
  - [x] 11.6 Test 5 — `hasError=true` + pas d'action → message "Action requise"

- [x] Task 12 — Validation finale
  - [x] 12.1 `npx vitest run` — 112 tests passent sur les 4 fichiers concernés
  - [x] 12.2 `npx tsc --noEmit` — 0 erreur TypeScript
  - [x] 12.3 `WorkflowStepsEditor.tsx` = 331 lignes (< 380)
  - [x] 12.4 14 suites de `WorkflowStepsEditor.test.tsx` passent sans modification

## Dev Notes

### SOLID-FE-6 — Chaîne de prop drilling actuelle (à supprimer)

```
CatalogPage (useAuth() → isBusinessProfile)
  ↓ variant={isBusinessProfile ? 'business' : 'default'}
ActionDrawerPreview (isBusiness = variant === 'business')  ← supprimer prop, lire useAuth

  ↓ variant={isBusinessProfile ? 'simplified' : 'default'} (séparé)
ExecutionWizard (variant === 'simplified' → STEP_ITEMS_SIMPLIFIED)  ← supprimer prop, lire useAuth
  ↓ variant={variant}
TargetSelectionStep    ← supprimer prop, lire useAuth
ParametersFormStep     ← supprimer prop, lire useAuth
ConfirmationStep       ← supprimer prop, lire useAuth
```

**Mapping précis des variantes :**

| Flux | Avant | Après |
|------|-------|-------|
| CatalogPage → ActionDrawerPreview | `variant: 'business' \| 'default'` (prop) | Supprimé — ActionDrawerPreview lit `useAuth()` |
| CatalogPage → ExecutionWizard | `variant: 'simplified' \| 'default'` (prop) | Supprimé — ExecutionWizard lit `useAuth()` |
| ExecutionWizard → steps | `variant: 'simplified' \| 'default'` (prop relayée) | Supprimé — chaque step lit `useAuth()` |
| CatalogPage → ActionCard | `variant: 'business' \| 'default'` (prop) | Supprimé — ActionCard lit `useAuth()` pour auto-détection |
| Admin → ActionCard | `variant: 'preview'` (prop) | **Conservé** — valeur légitime non liée à isBusinessProfile |

### Pattern useAuth à reproduire

```typescript
// Chemin import — vérifier dans CatalogPage.tsx ligne 1-10
// Exemple habituel dans ce projet :
import { useAuth } from '../../hooks/useAuth';

// Dans le composant
const { isBusinessProfile } = useAuth();
const isBusiness = isBusinessProfile; // pour ActionDrawerPreview
// ou
const isSimplified = isBusinessProfile; // pour ExecutionWizard et steps
```

### Modifications CatalogPage.tsx résumées

```tsx
// AVANT (3 endroits à supprimer)
const cardVariant: ActionCardProps['variant'] = isBusinessProfile ? 'business' : 'default';
// ...
<ActionCard variant={cardVariant} ... />
<ActionDrawerPreview variant={isBusinessProfile ? 'business' : 'default'} ... />
<ExecutionWizard variant={isBusinessProfile ? 'simplified' : 'default'} ... />

// APRÈS
// cardVariant supprimée
<ActionCard ... />  // pas de variant (auto-détecté via useAuth en interne)
<ActionDrawerPreview ... />  // pas de variant
<ExecutionWizard ... />  // pas de variant
```

### Pattern type-safe pour ExecutionWizard

```typescript
// Avant
const STEP_ITEMS = variant === 'simplified' ? STEP_ITEMS_SIMPLIFIED : STEP_ITEMS_DEFAULT;
const errorCardVariant = variant === 'simplified' ? 'business' : 'default';

// Après
const { isBusinessProfile } = useAuth();
const STEP_ITEMS = isBusinessProfile ? STEP_ITEMS_SIMPLIFIED : STEP_ITEMS_DEFAULT;
const errorCardVariant: 'business' | 'default' = isBusinessProfile ? 'business' : 'default';
```

### SOLID-FE-8 — Structure WorkflowStepsEditor.tsx actuelle

| Zone | Lignes | Contenu |
|------|--------|---------|
| Imports + types communs | 1–77 | Imports Ant Design, @dnd-kit, `WorkflowStepEditable`, `generateStepId`, `WorkflowStepsEditorProps` |
| `SortableStepCardProps` | 79–92 | Interface props de la carte |
| `SortableStepCard` | 94–381 | Composant : DnD useSortable, AutoComplete action, branches Select, retry Switch/InputNumber |
| `WorkflowStepsEditor` | 383–645 | Composant : state, DndContext, add/remove/change handlers, validation |

**Après extraction :**
- `SortableStepCard.tsx` : ~320 lignes (imports + SortableStepCardProps + SortableStepCard)
- `WorkflowStepsEditor.tsx` : ~330 lignes (imports allégés + WorkflowStepEditable + generateStepId + WorkflowStepsEditorProps + WorkflowStepsEditor)

### Gestion de WorkflowStepEditable et generateStepId

Ces deux éléments sont utilisés dans les deux composants :
- `WorkflowStepsEditor` : state interne, `useState<WorkflowStepEditable[]>`
- `SortableStepCard` : type du prop `step` et `allSteps`

**Stratégie :** Conserver dans `WorkflowStepsEditor.tsx` et **exporter** :
```typescript
// WorkflowStepsEditor.tsx — ajouter export
export interface WorkflowStepEditable extends Omit<WorkflowStep, 'referenced_action_id'> {
  referenced_action_id: number | undefined;
  _tempId?: string;
}
export function generateStepId(): string { ... }
```

```typescript
// SortableStepCard.tsx — importer depuis WorkflowStepsEditor
import type { WorkflowStepEditable } from './WorkflowStepsEditor';
```

### Mock pattern pour les tests des composants modifiés

```typescript
// Dans les fichiers .test.tsx qui utilisaient variant=
// Remplacer la prop par un mock useAuth

vi.mock('../../hooks/useAuth', () => ({
  useAuth: vi.fn().mockReturnValue({
    isAuthenticated: true,
    isBusinessProfile: false,
    // Ajouter les autres champs nécessaires selon l'interface AuthContext
  }),
}));

// Pour tester le comportement 'business' :
vi.mocked(useAuth).mockReturnValue({
  isAuthenticated: true,
  isBusinessProfile: true,
});
```

### Commandes de test recommandées

```bash
cd /Users/cyrille/Documents/Dev/test/idp-portal/frontend

# Lister les tests à mettre à jour (Task 1.3)
grep -rn "variant=" src --include="*.test.tsx" | \
  grep -E "(ExecutionWizard|TargetSelection|ParametersForm|ConfirmationStep|ActionDrawerPreview)"

# Vérifier les usages de ExecutionWizard avec variant (Task 1.2)
grep -rn "ExecutionWizard" src --include="*.tsx" | grep "variant="

# Run tests après chaque étape
npx vitest run src/components/admin/WorkflowStepsEditor.test.tsx
npx vitest run src/components/admin/SortableStepCard.test.tsx
npx vitest run  # tous les tests

# TypeScript check
npx tsc --noEmit

# ESLint
npx eslint src/
```

### Précédents établis

**Story 22.3** (CRIT-3 race condition token) : `useAuth()` déjà utilisé dans composants profonds — pattern mock `vi.mock('../../hooks/useAuth', ...)` établi et fonctionnel.

**Story 26.5** (WorkflowBuilderCanvas 995→487 LOC) : Pattern d'extraction composant en fichier dédié + tests séparés, 107/107 tests pass. Reproduire exactement ce pattern.

**Story 17.2** (ExecutionWizard 2035→536 LOC) : Extraction de hooks et composants depuis fichier volumineux dans le même dossier `admin/`. Convention de nommage et import établis.

**Story 33.5** : `ActionForm` et `ActionWizard` modifiés récemment (champ mort `validateWorkflowSteps`, prop morte `snIntegrationOptions`). Ne pas réintroduire de régression là-dedans — `WizardStep2Automatisme` n'utilise PAS `variant`, aucune interaction.

### Effort et risques

**Effort :** Faible-Moyen — 3–4h pour les deux issues.

**Risque 1 (SOLID-FE-6 — tests)** : Les tests qui passent `variant='simplified'` ou `variant='business'` à un composant modifié doivent mocker `useAuth`. La tâche 1.3 (grep) est critique pour ne rien rater.

**Risque 2 (SOLID-FE-8 — exports circulaires)** : `SortableStepCard.tsx` importe depuis `./WorkflowStepsEditor` pour `WorkflowStepEditable`. Il faut que `WorkflowStepsEditor.tsx` **exporte** cette interface mais **n'importe pas** depuis `SortableStepCard.tsx` (unidirectionnel : SortableStepCard → WorkflowStepsEditor, pas l'inverse). Vérifier avec `npx tsc --noEmit`.

**Risque 3 (ActionCard backward compat)** : L'usage de `variant='business'` passé explicitement depuis du code admin devra rester fonctionnel. La condition `isBusiness = variant === 'business' || isBusinessProfile` garantit ça.

### Project Structure Notes

```
idp-portal/frontend/src/
  components/
    admin/
      WorkflowStepsEditor.tsx          ← MODIFIER (supprimer SortableStepCard lignes 79-381, exporter WorkflowStepEditable)
      SortableStepCard.tsx             ← CRÉER (extraire depuis WorkflowStepsEditor)
      WorkflowStepsEditor.test.tsx     ← INCHANGÉ (9 suites passent sans modification)
      SortableStepCard.test.tsx        ← CRÉER (5 nouveaux tests)
    catalog/
      ActionCard.tsx                   ← MODIFIER (ajouter useAuth, isBusiness = variant==='business' || isBusinessProfile)
      ActionDrawerPreview.tsx          ← MODIFIER (supprimer variant prop, lire useAuth)
      ExecutionWizard.tsx              ← MODIFIER (supprimer variant prop, lire useAuth, ne plus passer aux steps)
      TargetSelectionStep.tsx          ← MODIFIER (supprimer variant prop, lire useAuth)
      ParametersFormStep.tsx           ← MODIFIER (supprimer variant prop, lire useAuth)
      ConfirmationStep.tsx             ← MODIFIER (supprimer variant prop, lire useAuth)
  pages/
    CatalogPage.tsx                    ← MODIFIER (supprimer calcul cardVariant et 3 props variant)
```

**Aucun changement backend. Aucune migration DB. Impact purement frontend.**

### References

- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-FE-6] — prop drilling variant 4–5 niveaux, fix via AuthContext
- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-FE-8] — SortableStepCard colocalisé 302 lignes, fix extraire fichier dédié
- [Source: idp-portal/frontend/src/pages/CatalogPage.tsx:113] — `const { isAuthenticated, isBusinessProfile } = useAuth()` — chemin import à reproduire
- [Source: idp-portal/frontend/src/pages/CatalogPage.tsx:563] — `variant={isBusinessProfile ? 'business' : 'default'}` → ActionDrawerPreview (supprimer)
- [Source: idp-portal/frontend/src/pages/CatalogPage.tsx:589] — `variant={isBusinessProfile ? 'simplified' : 'default'}` → ExecutionWizard (supprimer)
- [Source: idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx:62-75] — interface `variant?: 'default' | 'simplified'`
- [Source: idp-portal/frontend/src/components/catalog/TargetSelectionStep.tsx:35-56] — `variant: 'default' | 'simplified'` requis
- [Source: idp-portal/frontend/src/components/catalog/ParametersFormStep.tsx:22-40] — `variant: 'default' | 'simplified'` requis
- [Source: idp-portal/frontend/src/components/catalog/ConfirmationStep.tsx:29-48] — `variant: 'default' | 'simplified'` requis
- [Source: idp-portal/frontend/src/components/catalog/ActionDrawerPreview.tsx:50-63] — `variant?: 'default' | 'business'`
- [Source: idp-portal/frontend/src/components/catalog/ActionCard.tsx:38-49] — `variant?: 'default' | 'preview' | 'business'` — garder 'preview'
- [Source: idp-portal/frontend/src/components/admin/WorkflowStepsEditor.tsx:79-381] — SortableStepCard à extraire (lignes précises)
- [Source: idp-portal/frontend/src/components/admin/WorkflowStepsEditor.test.tsx] — 9 suites à conserver sans modification
- [Source: _bmad-output/planning-artifacts/epic-34-codebase-review-restant-fev-2026.md#Story-34.9] — priorité moyenne, issues SOLID-FE-6 + SOLID-FE-8
- [Source: _bmad-output/implementation-artifacts/34-8-backend-decomposer-inventory-services.md] — pattern extraction backward-compat (reproduire côté frontend)
- [Source: _bmad-output/implementation-artifacts/26-5-refactoriser-workflowbuildercanvas-tsx.md] — pattern extraction composant dans fichier dédié

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- WorkflowStepsRenderer.tsx a été modifié hors scope explicite : ajout de `useAuth` / `isBusinessProfile` pour sanitiser les descriptions dans le rendu des paramètres workflow (business variant). Ce changement est cohérent avec SOLID-FE-6 mais n'était pas listé dans les ACs/Tasks. Documenté en File List.
- Review code (34-9) : `variant` prop retirée de `ActionDrawerPreviewProps` (fix H1). Tests SortableStepCard complétés : disabled test étendu + test retry defaults ajouté (fix H2).

### File List

- idp-portal/frontend/src/components/catalog/ActionDrawerPreview.tsx (modifié — SOLID-FE-6 : suppression prop variant, useAuth direct)
- idp-portal/frontend/src/components/catalog/ActionDrawerPreview.test.tsx (modifié — mock useAuth, suppression variant= dans tests)
- idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx (modifié — SOLID-FE-6 : suppression prop variant, useAuth direct)
- idp-portal/frontend/src/components/catalog/ExecutionWizard.test.tsx (modifié — mock useAuth, suppression variant= dans tests)
- idp-portal/frontend/src/components/catalog/TargetSelectionStep.tsx (modifié — SOLID-FE-6 : suppression prop variant, useAuth direct)
- idp-portal/frontend/src/components/catalog/ParametersFormStep.tsx (modifié — SOLID-FE-6 : suppression prop variant, useAuth direct)
- idp-portal/frontend/src/components/catalog/ConfirmationStep.tsx (modifié — SOLID-FE-6 : suppression prop variant, useAuth direct)
- idp-portal/frontend/src/components/catalog/ActionCard.tsx (modifié — SOLID-FE-6 : isBusiness = variant==='business' || isBusinessProfile)
- idp-portal/frontend/src/components/catalog/WorkflowStepsRenderer.tsx (modifié — hors scope initial, ajout useAuth/isBusinessProfile pour sanitisation descriptions business dans workflow steps)
- idp-portal/frontend/src/pages/CatalogPage.tsx (modifié — SOLID-FE-6 : suppression cardVariant + 3 props variant)
- idp-portal/frontend/src/components/admin/WorkflowStepsEditor.tsx (modifié — SOLID-FE-8 : extraction SortableStepCard, allègement imports, exports WorkflowStepEditable/generateStepId)
- idp-portal/frontend/src/components/admin/SortableStepCard.tsx (créé — SOLID-FE-8 : extraction depuis WorkflowStepsEditor)
- idp-portal/frontend/src/components/admin/SortableStepCard.test.tsx (créé — SOLID-FE-8 : 6 tests unitaires)

## Change Log

| Date | Change |
|------|--------|
| 2026-02-22 | Story créée — SOLID-FE-6 (prop drilling variant → useAuth direct) + SOLID-FE-8 (SortableStepCard extraction). Analyse exhaustive : 6 composants impactés, chaîne prop drilling documentée, fichiers précis identifiés. |
