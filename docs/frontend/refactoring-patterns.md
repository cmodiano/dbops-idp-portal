# Frontend Refactoring Patterns

Guide de refactoring des composants frontend volumineux, basé sur le refactoring d'ExecutionWizard.tsx (Story 17.2).

## Critères d'identification

Un composant est candidat au refactoring si :

- **>500 lignes** de code dans un seul fichier
- **Responsabilités multiples** : state management + API calls + validation + rendering
- **Tests difficiles** : mocking complexe, tests fragiles, couverture faible
- **Modifications risquées** : toucher une partie casse une autre

### Candidats identifiés (post-Epic 17.2)

| Composant | Lignes | Priorité | Axes d'extraction |
|---|---|---|---|
| WorkflowBuilderCanvas.tsx | 927 | #2 | React Flow state, node/edge editors, validation |
| CalendarPage.tsx | 895 | #3 | Calendar state, event rendering, filtres |
| ActionWizard.tsx | 683 | #4 | Wizard state, step components (metadata, steps, RBAC) |
| ActionForm.tsx | 614 | #5 | Form validation, sections en sous-composants |
| ExecutionTimeline.tsx | 664 | #6 | WebSocket hooks, rendering de cards par type |

## Pattern de refactoring

### Phase 1 : Extraire hooks (state + API)

Identifier les blocs de logique indépendants et les extraire en custom hooks :

- **State management** : `useState` groupés par domaine -> hook dédié (ex: `useWizardState`)
- **API calls** : `useEffect` + fetch -> hook dédié (ex: `useTargetInventory`)
- **Validation** : logique de validation complexe -> hook dédié (ex: `useSchedulingValidation`)
- **Transformation de données** : parsing/mapping -> fonction pure exportée (ex: `extractParameterFields`)

**Convention de retour hook :**
```ts
{ data, loading, error, refetch }  // pour hooks d'API
{ state, updateState, reset }       // pour hooks de state
```

### Phase 2 : Extraire panneaux/sections

Identifier les sections UI autonomes et les extraire en composants :

- Sections conditionnellement rendues (ex: SchedulingPanel affiché seulement en mode planification)
- Sections répétées dans plusieurs contextes

### Phase 3 : Extraire steps/pages

Pour les wizards et pages multi-sections :

- Chaque step/section -> composant dédié (ex: `TargetSelectionStep`, `ParametersFormStep`)
- Le composant parent devient un **orchestrateur** : navigation, state, events
- Les sous-composants sont des **composants contrôlés** : reçoivent state via props

### Phase 4 : Optimisations

- `React.memo()` sur les sous-composants (éviter re-render si props inchangées)
- `React.lazy()` + `Suspense` pour les composants chargés conditionnellement
- Vérifier `useMemo`/`useCallback` pour dépendances optimales

## Testing strategy

### Tests hooks (isolés)

```ts
import { renderHook, act } from '@testing-library/react';
import { useWizardState } from './useWizardState';

it('navigates forward', () => {
  const { result } = renderHook(() => useWizardState());
  act(() => result.current.next());
  expect(result.current.currentStep).toBe(1);
});
```

### Tests composants (avec mocks)

Les tests existants du composant principal restent la référence. Les sous-composants sont testés via le composant parent.

### Couverture cible

- Hooks : 90%+ (logique critique)
- Composants : 85%+
- Intégration : tests existants doivent passer sans régression

## Exemple : ExecutionWizard (Story 17.2)

### Avant

- `ExecutionWizard.tsx` : 2035 lignes, tout en un seul fichier

### Après

| Fichier | Lignes | Rôle |
|---|---|---|
| ExecutionWizard.tsx | ~595 | Orchestrateur (state, navigation, submission) |
| TargetSelectionStep.tsx | ~285 | Step 1 - sélection cibles/environnement |
| ParametersFormStep.tsx | ~302 | Step 2 - formulaire dynamique |
| ConfirmationStep.tsx | ~156 | Step 3 - récapitulatif |
| SchedulingPanel.tsx | ~328 | Panel de planification |
| useWizardState.ts | ~65 | State management wizard |
| useExecutionSubmit.ts | ~120 | Logique de soumission |
| useTargetInventory.ts | ~85 | Fetch inventory/targets |
| useDynamicForm.ts | ~90 | Parsing schema -> champs formulaire |
| useSchedulingValidation.ts | ~60 | Validation planning/cron |

### Tests

- 37 tests ExecutionWizard existants : 0 régression
- 48 tests hooks ajoutés (useWizardState, useExecutionSubmit, useDynamicForm, useSchedulingValidation, useTargetInventory)
- Total : 85 tests

## Checklist de refactoring

Template pour futurs refactorings :

- [ ] Analyse de structure et dépendances (identifier responsabilités multiples)
- [ ] Définir architecture cible (hooks + composants)
- [ ] Stratégie de migration progressive (phases)
- [ ] Extraction hooks (state, API, validation) + tests
- [ ] Extraction sous-composants (UI sections) + tests
- [ ] Tests existants passent après chaque phase
- [ ] Optimisations (React.memo, React.lazy, Suspense)
- [ ] Performance validée (render time, bundle size)
- [ ] Documentation mise à jour
