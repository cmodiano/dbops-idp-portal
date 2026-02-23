# Story 35.3 : Migration DIP services — Phase 1 (composants prioritaires)

Status: done

<!-- Réf: CODEBASE-REVIEW.md 15 (SOLID-FE-4) — Priorité HIGH -->

## Story

En tant que développeur,
je veux migrer un premier lot de composants admin vers des hooks encapsulant les appels de services,
afin qu'aucun composant ne dépende directement de `admin_service`, `profiles_service` ou `catalog_service` et que l'inversion de dépendances (DIP) soit systématique dans le frontend.

## Contexte

**SOLID-FE-4 [HIGH]** du CODEBASE-REVIEW (2026-02-23) : ~25 composants importent directement les services. Epic 34 (story 34-13) a établi le pattern DIP pour `ExecutionWizard` — la présente story applique ce pattern aux composants admin prioritaires.

**État actuel (analyse du 2026-02-23) :**

| Composant | Lignes | Imports directs de services | Priorité |
|-----------|--------|-----------------------------|----------|
| `ActionWizard.tsx` | 584 | 6 fonctions `admin_service` | **P1** |
| `ProfileForm.tsx` | 511 | 4 `profiles_service` + 2 `admin_service` | **P2** |
| `ProfileWizard.tsx` | 457 | 5 `profiles_service` + 2 `admin_service` | **P2** |
| `WorkflowStepsEditor.tsx` | 332 | 1 `admin_service` | **P3** |
| `IntegrationForm.tsx` | 547 | 0 (déjà conforme) | ✅ |
| `ExecutionWizard.tsx` | 189 | 0 (migré en 34-13) | ✅ |

## Acceptance Criteria

1. **Given** le composant `ActionWizard.tsx`
   **Then** plus aucun import direct de `admin_service` dans le fichier — toutes les fonctions (`getTags`, `updateActionTags`, `updateActionSteps`, `updateWorkflowSteps`, `updateBusinessRulePolicies`, `patchAction`) sont appelées via un hook `useActionWizardState`

2. **Given** les composants `ProfileForm.tsx` et `ProfileWizard.tsx`
   **Then** plus aucun import direct de `profiles_service` ni `admin_service` — un hook partagé `useProfileFormState` encapsule le chargement des permissions (actions, targets) et des options (actions catalog, tags)

3. **Given** le composant `WorkflowStepsEditor.tsx`
   **Then** plus aucun import direct de `admin_service` — `getEligibleActionsForWorkflow` est appelé via un hook `useEligibleActions`

4. **Given** les hooks créés
   **Then** chaque hook respecte le pattern 34-13 :
   - Fichier dans `idp-portal/frontend/src/hooks/`
   - Accepte les props nécessaires (open, editXxx, onSubmit…)
   - Retourne l'état complet + handlers
   - Utilise les hooks existants si disponibles (ex. `useActionFormState` pour les tags)

5. **Given** les tests existants
   **Then** `npx vitest run` passe au moins autant de tests qu'avant (baseline : 2305 pass, 113 échecs pré-existants) — **0 régression**

6. **Given** la liste des composants Phase 1
   **Then** un commentaire dans chaque composant migré indique `// DIP: services encapsulés dans use{X}State — SOLID-FE-4` pour traceabilité

## Tasks / Subtasks

- [x] Task 1 — Créer `useActionWizardState` (AC: #1, #4)
  - [x] 1.1 Lire le contenu complet de `ActionWizard.tsx` pour identifier tous les appels de services et l'état local géré
  - [x] 1.2 Créer `hooks/useActionWizardState.ts` : encapsuler chargement tags (init), et toutes les opérations `handleSave` (updateActionTags, updateActionSteps, updateWorkflowSteps, updateBusinessRulePolicies, patchAction)
  - [x] 1.3 Vérifier que `useActionFormState` (déjà existant) peut être réutilisé pour les tags — useActionFormState est couplé à ActionForm (prend form, editAction, getIntegrationById) — non réutilisable directement ; getTags encapsulé dans useActionWizardState
  - [x] 1.4 Refactoriser `ActionWizard.tsx` pour utiliser le hook — supprimer tous les imports `admin_service`
  - [x] 1.5 Ajouter commentaire DIP traceabilité dans le composant

- [x] Task 2 — Créer `useProfileFormState` (AC: #2, #4)
  - [x] 2.1 Lire `ProfileForm.tsx` et `ProfileWizard.tsx` en entier — identifier l'état partagé (actionsOptions, tagsOptions, permissionState)
  - [x] 2.2 Créer `hooks/useProfileFormState.ts` : chargement `getProfileActions`, `getProfileTargets`, `getAdminActions`, `getTags` dans `useEffect` ; opérations `putProfileActions`, `putProfileTargets` dans handlers ; pattern queueMicrotask conservé
  - [x] 2.3 Refactoriser `ProfileForm.tsx` pour utiliser `useProfileFormState` — supprimer imports `profiles_service` et `admin_service`
  - [x] 2.4 Refactoriser `ProfileWizard.tsx` pour utiliser `useProfileFormState` — handleCreateProfile/handleUpdateProfile exposés par le hook pour le wizard
  - [x] 2.5 Ajouter commentaires DIP dans les deux composants

- [x] Task 3 — Créer `useEligibleActions` (AC: #3, #4)
  - [x] 3.1 Créer `hooks/useEligibleActions.ts` : wraps `getEligibleActionsForWorkflow` de `admin_service`
  - [x] 3.2 Refactoriser `WorkflowStepsEditor.tsx` — supprimer import `admin_service`
  - [x] 3.3 useActionFormState non applicable ici (getEligibleActionsForWorkflow est distinct des tags) — hook dédié créé

- [x] Task 4 — Tests et validation (AC: #5)
  - [x] 4.1 `npx vitest run` : **2325 tests passent** (baseline 2305 ✅), 113 échecs pré-existants
  - [x] 4.2 Tests existants ActionWizard (28/32), ProfileForm/ProfileWizard/WorkflowStepsEditor (75/75) — 0 régression ; mocks service toujours valides car hooks délèguent aux services
  - [x] 4.3 20 tests unitaires créés : 8 (useActionWizardState) + 7 (useProfileFormState) + 5 (useEligibleActions)

### Review Follow-ups (AI)
- [ ] [AI-Review][MEDIUM] Migrer les mocks des tests composants du niveau service vers le niveau hook — `ActionWizard.test.tsx:14` (mock `admin_service` → mock `useActionWizardState`), `ProfileForm.test.tsx:22-39` + `ProfileWizard.test.tsx:21-22` (mock `profiles_service`/`admin_service` → mock `useProfileFormState`), `WorkflowStepsEditor.test.tsx:16` (mock `admin_service` → mock `useEligibleActions`) — améliore isolation des tests composants vs couche service

## Dev Notes

### Pattern DIP — Référence obligatoire (Story 34-13)

**Ne JAMAIS réinventer — utiliser exactement ce pattern :**

```typescript
// ✅ PATTERN CIBLE : hook encapsulant les services
// hooks/useExecutionWizardState.ts (RÉFÉRENCE)

export function useExecutionWizardState(options: UseExecutionWizardStateOptions) {
  // État local du hook
  const [currentStep, setCurrentStep] = useState(0);

  // Réutilisation de hooks existants (DIP en cascade)
  const { inventoryData, loadingInventory } = useTargetInventory({...});
  const { workflowStepActions } = useWorkflowStepActions({...});

  // Handler qui appelle le service submit via useExecutionSubmit
  const { handleSubmit, isSubmitting } = useExecutionSubmit({...});

  return {
    currentStep, setCurrentStep,
    inventoryData, loadingInventory,
    workflowStepActions,
    handleSubmit, isSubmitting,
  };
}
```

```typescript
// ✅ PATTERN CIBLE : composant sans import de service
// components/catalog/ExecutionWizard.tsx (RÉFÉRENCE)

import { useExecutionWizardState } from '../../hooks/useExecutionWizardState';
// AUCUN import de service ici

export function ExecutionWizard({ open, action, ... }) {
  const { currentStep, handleSubmit, ... } = useExecutionWizardState({ open, action, ... });
  // Composant = rendu pur
}
```

### Hooks existants à réutiliser (NE PAS recréer)

| Hook | Service wrappé | À utiliser dans |
|------|---------------|-----------------|
| `useActionFormState` | `getTags` (admin_service) | `useActionWizardState` (pour le chargement des tags) |
| `useEnvironments` | Environments | ProfileForm/Wizard (déjà utilisé) |
| `useIntegrationTypes` | Catalogue intégrations | — |
| `useCatalogState` | Catalogue catalog_service | — |

**Commande pour vérifier les hooks existants :**
```bash
ls /Users/cyrille/Documents/Dev/test/idp-portal/frontend/src/hooks/
```

### Détail des services à encapsuler par composant

**ActionWizard.tsx — imports actuels (ligne ~34) :**
```typescript
import {
  getTags,                    // → déjà dans useActionFormState — RÉUTILISER
  updateActionTags,           // → handler save dans useActionWizardState
  updateActionSteps,          // → handler save
  updateWorkflowSteps,        // → handler save (cas workflow)
  updateBusinessRulePolicies, // → handler save
  patchAction,                // → handler save
} from '../../services/admin_service';
```

**ProfileForm.tsx — imports actuels (ligne ~10-15) :**
```typescript
import {
  getProfileActions,  // → useEffect dans useProfileFormState
  putProfileActions,  // → handleSubmit
  getProfileTargets,  // → useEffect
  putProfileTargets,  // → handleSubmit
} from '../../services/profiles_service';
import { getAdminActions, getTags } from '../../services/admin_service';
// getAdminActions → useEffect ; getTags → déjà dans useActionFormState si applicable
```

**ProfileWizard.tsx — imports actuels :**
```typescript
import {
  createProfile, updateProfile,  // → handleSubmit wizard
  getProfileActions, getProfileTargets,
  putProfileActions, putProfileTargets,
} from '../../services/profiles_service';
import { getAdminActions, getTags } from '../../services/admin_service';
```

**WorkflowStepsEditor.tsx — import actuel (ligne ~38) :**
```typescript
import { getEligibleActionsForWorkflow } from '../../services/admin_service';
// useEffect ligne ~112 : await getEligibleActionsForWorkflow()
```

### Localisation des fichiers

```
idp-portal/frontend/src/
├── hooks/                          ← Créer les nouveaux hooks ici
│   ├── useActionWizardState.ts     ← NOUVEAU
│   ├── useProfileFormState.ts      ← NOUVEAU
│   ├── useEligibleActions.ts       ← NOUVEAU
│   ├── useActionFormState.ts       ← Existant (réutiliser pour tags)
│   ├── useExecutionWizardState.ts  ← Existant (modèle de référence)
│   └── ...
├── components/
│   ├── admin/
│   │   ├── ActionWizard.tsx        ← Refactoriser (P1)
│   │   ├── ProfileForm.tsx         ← Refactoriser (P2)
│   │   ├── ProfileWizard.tsx       ← Refactoriser (P2)
│   │   └── WorkflowStepsEditor.tsx ← Refactoriser (P3)
│   └── ...
└── services/                       ← NE PAS modifier (couche service inchangée)
    ├── admin_service.ts
    ├── profiles_service.ts
    └── ...
```

### Tests — adapter les mocks

Si des tests existants font `vi.mock('../../services/admin_service')` dans les tests de `ActionWizard`, il faut les adapter pour mocker le hook `useActionWizardState` à la place :

```typescript
// ❌ AVANT
vi.mock('../../services/admin_service', () => ({
  getTags: vi.fn().mockResolvedValue([]),
  updateActionTags: vi.fn().mockResolvedValue({}),
}));

// ✅ APRÈS
vi.mock('../../hooks/useActionWizardState', () => ({
  useActionWizardState: vi.fn().mockReturnValue({
    tagsOptions: [],
    selectedTags: [],
    handleSave: vi.fn(),
    isSaving: false,
  }),
}));
```

### Stack technique

- **Framework :** React 18, TypeScript strict
- **UI :** Ant Design 6.2 — utiliser les API non-dépréciées
- **Tests :** Vitest + React Testing Library
- **Lint :** ESLint (0 violation autorisée) — vérifier avec `npx eslint src/hooks/useXxx.ts`
- **Pattern de retour des hooks :** objet nommé (pas de tuple), destructuring côté composant

### Vérifications CI à passer

```bash
# Depuis idp-portal/frontend/
npx vitest run --reporter=verbose 2>&1 | tail -30
npx eslint src/hooks/useActionWizardState.ts src/hooks/useProfileFormState.ts src/hooks/useEligibleActions.ts
npx tsc --noEmit
```

### Points d'attention — éviter les erreurs classiques

1. **Ne pas recréer `getTags` dans `useActionWizardState`** — réutiliser `useActionFormState` qui l'encapsule déjà
2. **ProfileForm vs ProfileWizard** — les deux partagent le chargement mais PAS le submit (Form.useForm() vs steps wizard) — le hook partagé peut exposer les deux handlers séparément
3. **Cancellation pattern** — utiliser `let cancelled = false` dans les `useEffect` (pattern existant dans `ProfileForm.tsx` ligne ~163) — le conserver dans le hook
4. **`queueMicrotask(() => setLoadingActions(true))`** — pattern Oracle/React batch update présent dans ProfileForm — le conserver dans le hook pour éviter la régression
5. **Tests du hook** : mocker la couche service, pas la couche hook — vérifier que le hook appelle correctement le service

### Référence story 34-13 (patterns établis)

Commit de référence : `4068394 feat(34-13): DIP services, props steps, useExecutionWizardState (SOLID-FE-4, SOLID-FE-7, SOLID-FE-9)`

Learnings du code review 34-13 (à appliquer ici) :
- H1 variant prop : ne pas supprimer les props du composant sans vérifier les consommateurs
- H2 tests incomplets : les nouveaux hooks doivent avoir des tests sur les cas retry + disabled
- M1 File List : compléter la section File List avec tous les fichiers modifiés
- La story 34-13 a réduit les imports directs de services dans ExecutionWizard : de 3 imports directs → 0 ✅

### Commits récents (contexte)

```
942ec1b refactor(35-2): auditer except Exception backend et .catch() frontend résiduels
7f8bf6a refactor(35-1): consolider STATUS_CONFIG dupliqués → execution-status.ts (SOLID-FE-10)
4068394 feat(34-13): DIP services, props steps, useExecutionWizardState (SOLID-FE-4, SOLID-FE-7, SOLID-FE-9)
```

### Project Structure Notes

- Tous les hooks vont dans `idp-portal/frontend/src/hooks/` — **jamais dans `components/`**
- Convention de nommage : `use{ComponentName}State` pour les hooks d'état de composant complexe, `use{Feature}` pour les hooks fonctionnels simples
- Aucune migration DB, aucun changement backend requis
- IntegrationForm.tsx est déjà conforme — NE PAS modifier

### References

- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-FE-4] — finding DIP violations frontend
- [Source: _bmad-output/planning-artifacts/epic-35-codebase-review-points-restants-post-refactoring.md#35.3] — détail story
- [Source: idp-portal/frontend/src/hooks/useExecutionWizardState.ts] — hook de référence DIP
- [Source: idp-portal/frontend/src/hooks/useActionFormState.ts] — hook tags (à réutiliser)
- [Source: idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx] — composant refactorisé de référence
- [Source: _bmad-output/implementation-artifacts/35-2-audit-except-exception-et-catch-residuels.md] — learnings story précédente
- [Source: _bmad-output/implementation-artifacts/34-13-frontend-dip-services-props-execution-wizard.md] — story 34-13 (pattern DIP établi)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- **Task 1 ✅** : `useActionWizardState` créé — wraps getTags (chargement à l'ouverture), updateActionTags, updateActionSteps, updateWorkflowSteps, updateBusinessRulePolicies, patchAction. ActionWizard.tsx : import admin_service supprimé, hook utilisé, commentaire DIP ajouté. 8 tests unitaires (mock service). 28/32 tests ActionWizard passent (4 pré-existants).
- **Task 2 ✅** : `useProfileFormState` créé — wraps getProfileActions, getProfileTargets, getAdminActions, getTags (chargement en useEffect), putProfileActions, putProfileTargets, createProfile, updateProfile. Pattern queueMicrotask conservé (Oracle/React batch). ProfileForm.tsx et ProfileWizard.tsx refactorisés, imports profiles_service et admin_service supprimés, commentaires DIP ajoutés. 7 tests unitaires. 75/75 tests ProfileForm/ProfileWizard passent.
- **Task 3 ✅** : `useEligibleActions` créé — wraps getEligibleActionsForWorkflow avec gestion erreur identique. WorkflowStepsEditor.tsx : import admin_service et useEffect de chargement supprimés, hook utilisé, commentaire DIP ajouté. 5 tests unitaires.
- **Task 4 ✅** : 2325 tests passent (≥ 2305 baseline ✅), 113 échecs pré-existants inchangés. 0 régression. TypeScript 0 erreur. ESLint 0 violation.

### File List

- `idp-portal/frontend/src/hooks/useActionWizardState.ts` ← NOUVEAU
- `idp-portal/frontend/src/hooks/useActionWizardState.test.ts` ← NOUVEAU
- `idp-portal/frontend/src/hooks/useProfileFormState.ts` ← NOUVEAU
- `idp-portal/frontend/src/hooks/useProfileFormState.test.ts` ← NOUVEAU
- `idp-portal/frontend/src/hooks/useEligibleActions.ts` ← NOUVEAU
- `idp-portal/frontend/src/hooks/useEligibleActions.test.ts` ← NOUVEAU
- `idp-portal/frontend/src/components/admin/ActionWizard.tsx`
- `idp-portal/frontend/src/components/admin/ProfileForm.tsx`
- `idp-portal/frontend/src/components/admin/ProfileWizard.tsx`
- `idp-portal/frontend/src/components/admin/WorkflowStepsEditor.tsx`
- `_bmad-output/implementation-artifacts/35-3-migration-dip-services-phase-1.md`
- `_bmad-output/implementation-artifacts/sprint-status.yaml`

## Senior Developer Review (AI)

**Date :** 2026-02-23 | **Reviewer :** claude-sonnet-4-6

**Résultat :** ✅ APPROUVÉ avec fixes auto-appliqués

**ACs validés :** 6/6 (AC4 partiel avant fix M1, maintenant complet)

**Findings et corrections appliquées :**

| Sévérité | ID | Fichier | Description | Statut |
|---|---|---|---|---|
| 🔴 HIGH | H1 | `useProfileFormState.ts:106-119` | `loadingData` jamais activé en mode création → Selects sans spinner | ✅ FIXÉ |
| 🟡 MEDIUM | M1 | `useActionWizardState.ts:60-81` | Handlers non mémoïsés (`useCallback` manquant) — pattern 34-13 non respecté | ✅ FIXÉ |
| 🟡 MEDIUM | M2 | `useProfileFormState.test.ts` | Test d'erreur absent en mode édition (`.catch()` branch non couvert) | ✅ FIXÉ |
| 🟡 MEDIUM | M3 | `*.test.tsx` composants | 4 fichiers tests mockent encore `admin_service`/`profiles_service` au lieu des hooks | ⏭ ACTION ITEM |
| 🟢 LOW | L1 | `useEligibleActions.test.ts:11-16` | Mock initial `vi.mock` redondant (écrasé par `beforeEach`) | ✅ FIXÉ |
| 🟢 LOW | L2 | `ProfileWizard.tsx:183` | `setSaving(false)` dupliqué (inner catch + outer `finally`) | ✅ FIXÉ |

**Issues fixées automatiquement :** 5 (H1 + M1 + M2 + L1 + L2)
**Action items créés :** 1 (M3 — voir Review Follow-ups ci-dessus)

## Change Log

- **2026-02-23** : Code review (AI) — 1H+3M+2L findings, 5 auto-fixés (loadingData création mode, useCallback handlers, test erreur édition, mock redondant, setSaving dupliqué), 1 action item M3 (migration mocks composants vers hooks). Story marquée **done**.
- **2026-02-23** : Implémentation complète story 35.3 (SOLID-FE-4 HIGH) — 3 nouveaux hooks DIP créés (useActionWizardState, useProfileFormState, useEligibleActions), 4 composants refactorisés (ActionWizard, ProfileForm, ProfileWizard, WorkflowStepsEditor), 20 tests unitaires ajoutés, 2325 tests passent (baseline 2305 ✅), 0 régression, TypeScript 0 erreur, ESLint 0 violation.
