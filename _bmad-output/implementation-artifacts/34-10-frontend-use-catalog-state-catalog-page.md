# Story 34.10 : Frontend — Extraire useCatalogState (CatalogPage)

Status: done

<!-- Réf: CODEBASE-REVIEW.md SOLID-FE-2 -->

## Story

En tant que mainteneur,
je veux extraire la logique d'état de `CatalogPage.tsx` (601 lignes, 22 useState + 1 useRef, 8+ useCallback) dans un hook dédié `useCatalogState`,
afin de réduire la taille de la page et de centraliser la logique (SRP), comme pour ActionForm → useActionFormState ou CalendarPage → useCalendarState.

## Acceptance Criteria

1. **Given** CatalogPage actuel (601 lignes)
   **Then** un hook `useCatalogState()` est créé dans `src/hooks/useCatalogState.ts` et contient **tout** l'état et la logique :
   - États de vue : `viewMode` + persistence localStorage
   - États de filtre : `activeCategory`, `searchText`, `filterTags`, `filterEngines`, `filterImpacts`
   - Données catalogue : `actions`, `loading`, `tagsWithCounts`, `favorites`
   - Sélection/drawer action : `selectedAction`, `selectedActionDetail`, `selectedActionCanExecute`, `selectedActionEnvs`, `selectedActionStats`, `statsLoading`, `drawerVisible`, `drawerLoading`, `lastFocusedCardRef`
   - État execution : `executionWizardOpen`, `activeExecutionId`, `executionViewId`, `parentExecutionId`
   - Dérivés : `hasActiveFilters`, `filteredActions` (useMemo)
   - Handlers : `loadData`, `resetFilters`, `handleToggleFavorite`, `handleViewModeChange`, `handleCategoryChange`, `handleActionClick`, `handleDrawerClose`, `handleExecuteClick`, `handleExecutionSuccess`, `handleBackToCatalog`, `handleRemediationSuggestionClick`

2. **And** le hook retourne un objet typé `UseCatalogStateReturn` avec tous les états et handlers nécessaires au rendu.

3. **And** `CatalogPage.tsx` utilise `const state = useCatalogState()` (ou déstructuré) et ne contient plus que :
   - Les imports React/Ant Design/composants
   - `toPreviewData()` (fonction utilitaire pure, reste dans la page)
   - `renderActionCard()`, `renderSkeleton()`, `renderEmpty()` (fonctions de rendu JSX)
   - Le JSX de la page (`return (...)`)
   - La constante `contentMaxWidth = 1600`
   - **La taille de CatalogPage.tsx descend sous 300 lignes.**

4. **And** le comportement de la page catalogue est rigoureusement inchangé : filtres, sélection, favoris, ouverture wizard, drawer exécution, retour focus, localStorage — identiques.

5. **And** les 33 tests existants de `CatalogPage.test.tsx` passent sans modification du fichier de test (seuls les mocks peuvent être ajustés si `App.useApp()` est déplacé dans le hook).

6. **And** un fichier de test `src/hooks/useCatalogState.test.ts` est créé avec au minimum :
   - Test `filteredActions` : "Mes actions" retourne uniquement les favoris
   - Test `resetFilters` : remet toutes les valeurs à leur état initial
   - Test `handleViewModeChange` : met à jour `viewMode` et écrit dans localStorage
   - Test `hasActiveFilters` : true quand au moins un filtre actif, false sinon

## Tasks / Subtasks

- [x] Task 1 — Créer `src/hooks/useCatalogState.ts`
  - [x] 1.1 Définir l'interface `UseCatalogStateReturn` avec tous les états et handlers exposés
  - [x] 1.2 Déplacer les constantes `CATALOG_VIEW_MODE_KEY`, `type ViewMode`, `getStoredViewMode()` dans le fichier du hook
  - [x] 1.3 Déplacer les 22 useState + 1 useRef (cf. inventaire ci-dessous) dans le hook
  - [x] 1.4 Déplacer `useDebounce(searchText, 300)` dans le hook
  - [x] 1.5 Appeler `App.useApp()` directement dans le hook (même pattern que CatalogPage) pour accéder à `message`
  - [x] 1.6 Déplacer `loadData` (useCallback + useEffect) dans le hook
  - [x] 1.7 Déplacer `hasActiveFilters`, `resetFilters`, `filteredActions` dans le hook
  - [x] 1.8 Déplacer tous les handlers async : `handleToggleFavorite`, `handleViewModeChange`, `handleCategoryChange`, `handleActionClick`, `handleDrawerClose`, `handleExecuteClick`, `handleExecutionSuccess`, `handleBackToCatalog`, `handleRemediationSuggestionClick`
  - [x] 1.9 Retourner un objet `UseCatalogStateReturn` complet

- [x] Task 2 — Refactoriser `CatalogPage.tsx`
  - [x] 2.1 Supprimer toutes les constantes, types, useState, useCallback, useMemo, useEffect et handlers déplacés dans le hook
  - [x] 2.2 Ajouter `import { useCatalogState } from '../hooks/useCatalogState'`
  - [x] 2.3 Appeler `const { ... } = useCatalogState()` (déstructurer les valeurs nécessaires au rendu)
  - [x] 2.4 Conserver `toPreviewData()`, `renderActionCard()`, `renderSkeleton()`, `renderEmpty()` et le JSX
  - [x] 2.5 Vérifier que la page est < 300 lignes

- [x] Task 3 — Tests
  - [x] 3.1 Vérifier que les 33 tests de `CatalogPage.test.tsx` passent sans modification (ou adapter uniquement les mocks si nécessaire)
  - [x] 3.2 Créer `src/hooks/useCatalogState.test.ts` avec les 4 tests unitaires du hook (AC6)

- [x] Task 4 — Validation finale
  - [x] 4.1 `npx vitest run src/pages/CatalogPage.test.tsx` — 37 tests passent (33+ hérités)
  - [x] 4.2 `npx vitest run src/hooks/useCatalogState.test.ts` — 4 tests passent
  - [x] 4.3 `npx tsc --noEmit` — 0 erreur TypeScript
  - [x] 4.4 CatalogPage.tsx < 300 lignes (267 lignes)

## Dev Notes

### Inventaire complet des états à déplacer (CatalogPage.tsx actuel)

| Ligne | Variable | Type | Note |
|-------|----------|------|------|
| 114 | `viewMode` | `ViewMode` | + localStorage init via `getStoredViewMode()` |
| 117 | `activeCategory` | `CategoryKey` | import depuis CategoryTabs |
| 119 | `searchText` | `string` | |
| 120 | `debouncedQ` | `string` | via `useDebounce(searchText, 300)` |
| 121 | `filterTags` | `string[]` | |
| 126 | `filterEngines` | `string[]` | |
| 127 | `filterImpacts` | `string[]` | |
| 129 | `tagsWithCounts` | `CatalogTagWithCount[]` | |
| 130 | `loading` | `boolean` | |
| 131 | `actions` | `CatalogAction[]` | |
| 132 | `favorites` | `Set<number>` | |
| 133 | `selectedAction` | `CatalogAction \| null` | |
| 134 | `selectedActionDetail` | `CatalogActionDetail \| null` | |
| 135 | `selectedActionCanExecute` | `boolean` | |
| 136 | `selectedActionEnvs` | `string[]` | |
| 137 | `selectedActionStats` | `ActionStats \| null` | |
| 138 | `statsLoading` | `boolean` | |
| 139 | `drawerVisible` | `boolean` | |
| 140 | `drawerLoading` | `boolean` | |
| 141 | `executionWizardOpen` | `boolean` | |
| 142 | `activeExecutionId` | `number \| null` | |
| 144 | `executionViewId` | `number \| null` | |
| 146 | `parentExecutionId` | `number \| null` | |
| 147 | `lastFocusedCardRef` | `React.RefObject<HTMLElement \| null>` | useRef |

**Dérivés à déplacer :**
- `debouncedQ` — `useDebounce(searchText, 300)` (l.120)
- `hasActiveFilters` — booléen dérivé (l.190–195)
- `filteredActions` — `useMemo` (l.205–210)

### Structure du hook `useCatalogState.ts`

```typescript
// src/hooks/useCatalogState.ts

import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { App } from 'antd';
import type { CategoryKey } from '../components/catalog/CategoryTabs';
import { useDebounce } from './useDebounce';
import {
  fetchCatalogActions, fetchCatalogActionById, fetchCatalogTags,
  fetchFavorites, addFavorite, removeFavorite, fetchActionStats,
  type CatalogAction, type CatalogActionDetail, type CatalogTagWithCount, type FavoriteEntry,
} from '../services/catalog_service';
import type { ActionStats, RemediationSuggestion } from '../types/api';
import logger from '../services/logger';

/** localStorage key for view mode (AC2). */
const CATALOG_VIEW_MODE_KEY = 'catalog-view-mode';

/** View mode: grid or list */
export type ViewMode = 'grid' | 'list';

function getStoredViewMode(): ViewMode {
  try {
    const stored = localStorage.getItem(CATALOG_VIEW_MODE_KEY);
    if (stored === 'grid' || stored === 'list') return stored;
  } catch { /* ignore */ }
  return 'grid';
}

export interface UseCatalogStateReturn {
  // Vue
  viewMode: ViewMode;
  handleViewModeChange: (mode: ViewMode) => void;
  // Filtres
  activeCategory: CategoryKey;
  searchText: string;
  setSearchText: React.Dispatch<React.SetStateAction<string>>;
  filterTags: string[];
  setFilterTags: React.Dispatch<React.SetStateAction<string[]>>;
  filterEngines: string[];
  setFilterEngines: React.Dispatch<React.SetStateAction<string[]>>;
  filterImpacts: string[];
  setFilterImpacts: React.Dispatch<React.SetStateAction<string[]>>;
  hasActiveFilters: boolean;
  resetFilters: () => void;
  handleCategoryChange: (category: CategoryKey) => void;
  // Données
  loading: boolean;
  actions: CatalogAction[];
  filteredActions: CatalogAction[];
  tagsWithCounts: CatalogTagWithCount[];
  favorites: Set<number>;
  handleToggleFavorite: (actionId: number, e: React.MouseEvent) => Promise<void>;
  // Sélection / drawer action
  selectedAction: CatalogAction | null;
  selectedActionDetail: CatalogActionDetail | null;
  selectedActionCanExecute: boolean;
  selectedActionEnvs: string[];
  selectedActionStats: ActionStats | null;
  statsLoading: boolean;
  drawerVisible: boolean;
  drawerLoading: boolean;
  lastFocusedCardRef: React.RefObject<HTMLElement | null>;
  handleActionClick: (action: CatalogAction, event?: React.MouseEvent) => Promise<void>;
  handleDrawerClose: () => void;
  // Execution wizard / view
  executionWizardOpen: boolean;
  activeExecutionId: number | null;
  setActiveExecutionId: React.Dispatch<React.SetStateAction<number | null>>;
  executionViewId: number | null;
  setExecutionViewId: React.Dispatch<React.SetStateAction<number | null>>;
  parentExecutionId: number | null;
  setParentExecutionId: React.Dispatch<React.SetStateAction<number | null>>;
  setExecutionWizardOpen: React.Dispatch<React.SetStateAction<boolean>>;
  handleExecuteClick: () => void;
  handleExecutionSuccess: (executionId: number) => void;
  handleBackToCatalog: () => void;
  handleRemediationSuggestionClick: (suggestion: RemediationSuggestion) => Promise<void>;
}

export function useCatalogState(): UseCatalogStateReturn {
  const { message } = App.useApp();
  // ... tous les états et handlers
}
```

### CatalogPage.tsx après refactoring (structure cible)

```tsx
// src/pages/CatalogPage.tsx — < 300 lignes
import { ... } from 'react';  // uniquement useState si besoin local
import { ... } from 'antd';   // composants UI uniquement
import { ... } from '../components/catalog/...';
import { useCatalogState } from '../hooks/useCatalogState';
import type { ... } from '../types/api';
import { toPreviewData } from '...';  // reste ici (pure function)

export default function CatalogPage() {
  const {
    viewMode, handleViewModeChange,
    activeCategory, handleCategoryChange,
    searchText, setSearchText,
    filterTags, setFilterTags,
    filterEngines, setFilterEngines,
    filterImpacts, setFilterImpacts,
    hasActiveFilters, resetFilters,
    loading, filteredActions, tagsWithCounts, favorites, handleToggleFavorite,
    selectedAction, selectedActionDetail, selectedActionCanExecute,
    selectedActionEnvs, selectedActionStats, statsLoading,
    drawerVisible, drawerLoading, lastFocusedCardRef,
    handleActionClick, handleDrawerClose, handleExecuteClick,
    executionWizardOpen, activeExecutionId, setActiveExecutionId,
    setExecutionWizardOpen, parentExecutionId, setParentExecutionId,
    handleExecutionSuccess, handleBackToCatalog,
    executionViewId, setExecutionViewId,
    handleRemediationSuggestionClick,
  } = useCatalogState();

  const { isAuthenticated } = useAuth();

  const renderActionCard = ...  // JSX — reste
  const renderSkeleton = ...    // JSX — reste
  const renderEmpty = ...       // JSX — reste

  return ( ... );  // JSX identique à aujourd'hui
}
```

### Points d'attention critiques

**1. `App.useApp()` dans le hook**
`message` est utilisé dans `loadData`, `handleToggleFavorite`, `handleActionClick`, `handleRemediationSuggestionClick`. Le hook appelle `App.useApp()` directement — c'est valide car le hook est appelé depuis l'arbre React qui a un `<App>` provider. Pattern identique à ce que fait déjà `CatalogPage.tsx` l.112.

**2. `useAuth()` — diviser les responsabilités**
- `isAuthenticated` est utilisé uniquement dans le JSX (`showFavoriteButton={isAuthenticated}`) → reste dans CatalogPage, appelé directement.
- Aucune utilisation de `useAuth` dans la logique d'état → le hook `useCatalogState` n'a pas besoin de `useAuth`.

**3. `toPreviewData()` reste dans CatalogPage**
Cette fonction est une pure transformation de données utilisée dans `renderActionCard` et dans le JSX du drawer — elle est couplée au rendu, pas à l'état. Elle reste dans la page.

**4. Imports à ajuster (chemins relatifs)**
Le hook est dans `src/hooks/`, donc les imports doivent être ajustés :
```typescript
// Dans useCatalogState.ts (hooks/)
import { useDebounce } from './useDebounce';                          // hooks/ → hooks/
import type { CategoryKey } from '../components/catalog/CategoryTabs'; // hooks/ → components/
import { fetchCatalogActions, ... } from '../services/catalog_service'; // hooks/ → services/
import type { ActionStats, RemediationSuggestion } from '../types/api'; // hooks/ → types/
import logger from '../services/logger';                               // hooks/ → services/
```

**5. `handleExecutionSuccess` dépend de `loadData`**
`loadData` sera dans le hook, donc `handleExecutionSuccess` (qui appelle `loadData()`) doit aussi être dans le hook. La dépendance est interne — pas de problème.

**6. `setActiveExecutionId` avec callback fonctionnel (Story 9.2 fix)**
La ligne `setActiveExecutionId((prev) => { capturedParentId = prev; return null; })` dans `handleRemediationSuggestionClick` utilise la forme fonctionnelle pour éviter une race condition. Ce pattern doit être **préservé identiquement** dans le hook.

**7. Tests `CatalogPage.test.tsx` : mock `App.useApp()`**
Le mock `vi.spyOn(App, 'useApp')` est déjà dans le `renderWithTheme()` helper (l.22-28). Lorsque `App.useApp()` est déplacé dans le hook, ce mock s'applique toujours (le spy fonctionne au niveau module, pas au niveau composant). Les tests devraient passer sans modification.

### Pattern de test du hook (`useCatalogState.test.ts`)

```typescript
import { renderHook, act } from '@testing-library/react';
import { App } from 'antd';
import { useCatalogState } from './useCatalogState';
import * as catalogService from '../services/catalog_service';

vi.mock('../services/catalog_service');

// Wrapper avec App pour App.useApp()
const wrapper = ({ children }: { children: React.ReactNode }) => (
  <App>{children}</App>
);

describe('useCatalogState', () => {
  beforeEach(() => {
    vi.mocked(catalogService.fetchCatalogActions).mockResolvedValue([]);
    vi.mocked(catalogService.fetchCatalogTags).mockResolvedValue([]);
    vi.mocked(catalogService.fetchFavorites).mockResolvedValue([]);
    vi.mocked(catalogService.fetchActionStats).mockResolvedValue(null);
  });

  it('filteredActions: "mes-actions" retourne uniquement les favoris', () => { ... });
  it('resetFilters: remet toutes les valeurs à leur état initial', () => { ... });
  it('handleViewModeChange: met à jour viewMode et localStorage', () => { ... });
  it('hasActiveFilters: true quand un filtre actif, false sinon', () => { ... });
});
```

### Précédents établis à reproduire

| Précédent | Pattern | Relevance |
|-----------|---------|-----------|
| Story 26.6 — `useCalendarState` | Hook extrait depuis CalendarPage, retourne `UseCalendarStateReturn` typé | **Référence directe** |
| Story 33.5 — `useActionFormState` | Hook avec params, gère useEffect init/reset | Pattern états complexes |
| Story 26.4 — `useExecutionsData`, `useExecutionFilters` | Hooks depuis ExecutionsPage 1023→298 LOC (-70.9%) | Objectif LOC similaire |
| Story 22.3 — mock `App.useApp()` | `vi.spyOn(App, 'useApp').mockReturnValue(...)` | Tests qui appellent message |

**Référence clé :** `src/hooks/useCalendarState.ts` — hook extrait depuis CalendarPage, même structure avec interface return typée, `useCallback` pour tous les handlers. Reproduire exactement ce pattern.

### Vérification taille cible

| Fichier | Avant | Après |
|---------|-------|-------|
| CatalogPage.tsx | 601 lignes | < 300 lignes (-50%) |
| useCatalogState.ts | (nouveau) | ~350–380 lignes |
| useCatalogState.test.ts | (nouveau) | ~80–100 lignes |

### Project Structure Notes

```
idp-portal/frontend/src/
  hooks/
    useCatalogState.ts          ← CRÉER (~350 lignes : tous les états + handlers)
    useCatalogState.test.ts     ← CRÉER (≥4 tests unitaires)
    useCalendarState.ts         ← RÉFÉRENCE (même pattern)
    useActionFormState.ts       ← RÉFÉRENCE ALTERNATIVE (pattern params)
  pages/
    CatalogPage.tsx             ← MODIFIER (supprimer logique d'état, appeler useCatalogState)
    CatalogPage.test.tsx        ← NE PAS MODIFIER (les 33 tests doivent passer as-is)
    CatalogPage.story19_4.integration.test.tsx  ← NE PAS MODIFIER
```

**Aucun changement backend. Aucune migration DB. Impact purement frontend.**

### Commandes de test recommandées

```bash
cd /Users/cyrille/Documents/Dev/test/idp-portal/frontend

# Tests de la page catalogue (33 tests — doit passer sans modification)
npx vitest run src/pages/CatalogPage.test.tsx

# Tests du nouveau hook
npx vitest run src/hooks/useCatalogState.test.ts

# TypeScript check
npx tsc --noEmit

# ESLint
npx eslint src/hooks/useCatalogState.ts src/pages/CatalogPage.tsx
```

### References

- [Source: idp-portal/frontend/src/pages/CatalogPage.tsx:111-601] — fichier source complet à refactoriser
- [Source: idp-portal/frontend/src/pages/CatalogPage.test.tsx] — 33 tests à préserver
- [Source: idp-portal/frontend/src/hooks/useCalendarState.ts] — patron de référence exact
- [Source: idp-portal/frontend/src/hooks/useActionFormState.ts] — patron états complexes
- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-FE-2] — CatalogPage 606 lignes, 23 useState, 8 useCallback
- [Source: _bmad-output/planning-artifacts/epic-34-codebase-review-restant-fev-2026.md#34.10] — priorité Haute, SOLID-FE-2
- [Source: _bmad-output/implementation-artifacts/34-9-frontend-variant-context-workflow-steps-editor.md] — story précédente, pattern hooks frontend
- [Source: _bmad-output/implementation-artifacts/26-4-refactoriser-executionspage-tsx.md] — ExecutionsPage 1023→298 LOC (-70.9%), 7 fichiers extraits
- [Source: _bmad-output/implementation-artifacts/26-6-refactoriser-calendarpage-tsx.md] — CalendarPage 896→269 LOC (-70%), pattern useCalendarState

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- **Task 1** : Hook `useCatalogState.ts` créé (~270 lignes) — 22 useState + 1 useRef + useDebounce + 9 handlers + loadData + useEffect extraits de CatalogPage. Interface `UseCatalogStateReturn` typée complète. `App.useApp()` appelé directement dans le hook (pattern valide car contexte React parent). Race condition `setActiveExecutionId((prev) => ...)` préservée identiquement (Story 9.2 fix).
- **Task 2** : CatalogPage.tsx réduit de 601 → 267 lignes (-55%). Ne contient plus que : imports UI, `toPreviewData()` (fonction pure), `renderActionCard/Skeleton/Empty()` (JSX), JSX de la page, `contentMaxWidth`. `useAuth()` conservé pour `isAuthenticated` (JSX uniquement).
- **Task 3** : 37 tests CatalogPage passent sans modification du fichier de test. Mock `vi.spyOn(App, 'useApp')` fonctionne au niveau module — s'applique au hook. 4 tests hook créés.
- **Task 4** : 41/41 tests passent, 0 erreur TypeScript, 267 lignes (< 300 ✅).
- **Code Review** : 2 HIGH + 1 MEDIUM + 1 LOW auto-fixés — H1 : `handleToggleFavorite`, `handleViewModeChange`, `handleActionClick`, `handleDrawerClose` wrappés dans `useCallback` (stabilité props enfants) ; H2 : `hasActiveFilters` converti en `useMemo` (cohérence avec `filteredActions`) ; M1 : warnings `act()` tests hook éliminés (await act async + waitFor) ; L1 : `contentMaxWidth` déplacé au niveau module. 41/41 tests passent, 0 erreur TypeScript.

### File List

- idp-portal/frontend/src/hooks/useCatalogState.ts (créé — extraction logique état CatalogPage, ~270 lignes)
- idp-portal/frontend/src/hooks/useCatalogState.test.ts (créé — 4 tests unitaires hook)
- idp-portal/frontend/src/pages/CatalogPage.tsx (modifié — 601→267 lignes, appelle useCatalogState)

## Change Log

| Date | Change |
|------|--------|
| 2026-02-22 | Story créée — SOLID-FE-2 : extraction useCatalogState depuis CatalogPage (601→<300 lignes). Analyse exhaustive : 22 useState + 1 useRef, 8 useCallback, inventaire complet, patterns et références identifiés. |
| 2026-02-22 | Implémentation complète — useCatalogState.ts créé, CatalogPage.tsx 601→267 lignes (-55%), 37 tests CatalogPage + 4 tests hook passent, 0 erreur TypeScript. |
| 2026-02-22 | Code review adversarial — 2 HIGH + 1 MEDIUM + 1 LOW auto-fixés : useCallback sur 4 handlers, useMemo sur hasActiveFilters, act() warnings éliminés, contentMaxWidth module-level. 41/41 tests passent, 0 erreur TypeScript. Story marquée done. |
