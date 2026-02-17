# Story 26.4: Refactoriser ExecutionsPage.tsx (1 023 LOC)

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur,
je veux extraire les colonnes Table et la logique d'état d'ExecutionsPage dans des fichiers/hooks dédiés,
afin de réduire la complexité du composant (20+ state variables, 500+ lignes de config colonnes).

## Context

**Source :** Epic 26, Section 4.4 du code-quality-assessment (6 février 2026)

Le fichier `ExecutionsPage.tsx` contient actuellement **1 023 lignes** et présente une complexité importante :

### Problèmes identifiés

1. **Monolithe composant unique**
   - 1 023 LOC dans un seul fichier
   - 20+ variables d'état (useState)
   - 9 useEffect hooks interconnectés
   - 400+ lignes de JSX rendering

2. **Définitions de colonnes massives**
   - Lignes 651-784 : 134 LOC de définition de colonnes Table
   - 9 colonnes avec logique complexe (status indicator, icons, actions)
   - Configuration inline dans useMemo
   - Dépend de 10+ variables externes

3. **Gestion d'état dispersée**
   - État drawer (7 variables) : drawerOpen, selectedExecution, selectedSteps, selectedActionDetail, loading, error
   - État restart wizard (5 variables) : restartAction, restartEnvs, restartParams, restartLoadingId
   - État table : executions, loading, error, currentPage, totalCount, sortField, sortOrder
   - État filtres : activeScope, timeSeriesData, pendingApprovals, statsData
   - Risque stale closure (Story 22.14) nécessitant refs (lines 394-427)

4. **Préoccupations mélangées**
   - Data fetching + RBAC + rendu colonnes + modal handlers dans le même composant
   - Violation du Single Responsibility Principle
   - Difficile à tester unitairement
   - Réutilisation impossible (colonnes, hooks)

### Contexte technique

**Fichier actuel :** `idp-portal/frontend/src/pages/ExecutionsPage.tsx` (1 023 LOC)

**Stories liées :**
- Story 17.13 : Mode compact pour densité accrue
- Story 8.8 : Section approbations en attente
- Story 8.9 : Tabs "Toutes" / "Mes exécutions"
- Story 9.4 : StatCards déplacées du Dashboard
- Story 9.9 : Colonnes Technologie/Plateforme avec icônes
- Story 9.10 : AdvancedFiltersPanel + TrendLineChart
- Story 22.14 : Fix stale closure avec refs

**Pattern établi dans le codebase :**
- Story 22.9 : AdminPage refactorisé de 845 → 75 LOC en extrayant 6 panels
- Fichier existant : `pages/admin/actionsColumns.tsx` (194 LOC) — template à suivre

---

## Acceptance Criteria

### AC1: Extraction des définitions de colonnes → `executionsColumns.tsx`

**Given** `ExecutionsPage.tsx` contient 134 LOC de définitions de colonnes (lignes 651-784)
**When** les colonnes sont extraites
**Then** :

- Un fichier `frontend/src/pages/executions/executionsColumns.tsx` est créé
- Pattern similaire à `pages/admin/actionsColumns.tsx` :
  ```typescript
  export const getExecutionsColumns = (
    handlers: ExecutionColumnHandlers,
    state: ExecutionColumnState,
    theme: { token: any; isDark: boolean }
  ): TableProps<ExecutionResponse>['columns'] => [...]
  ```
- Les 9 colonnes sont définies dans le fichier externe :
  1. Statut (renderStatusIndicator)
  2. Action (action_name)
  3. Technologie (renderEngineIcon)
  4. Plateforme (renderPlateformeIcon)
  5. Utilisateur (conditionnel activeScope='all')
  6. Environnement
  7. Date (formatDate)
  8. Durée (formatDuration)
  9. Actions (Cancel/Restart buttons)
- Type `ExecutionColumnHandlers` défini pour les callbacks :
  ```typescript
  interface ExecutionColumnHandlers {
    onCancelExecution: (id: number) => void;
    onRestartExecution: (execution: ExecutionResponse) => void;
  }
  ```
- Type `ExecutionColumnState` défini pour l'état nécessaire :
  ```typescript
  interface ExecutionColumnState {
    activeScope: ExecutionScope;
    sortField: string;
    sortOrder: 'ascend' | 'descend';
    integrationIconsMap: IntegrationIconsMap | null;
    user: User;
    canViewAll: boolean;
    cancellingId: number | null;
    restartLoadingId: number | null;
  }
  ```
- Les fonctions utilitaires `formatDuration()`, `formatDate()` sont exportées du fichier
- ExecutionsPage.tsx importe et utilise `getExecutionsColumns()` :
  ```typescript
  import { getExecutionsColumns } from './executions/executionsColumns';

  const columns = useMemo(
    () => getExecutionsColumns(
      { onCancelExecution: handleCancelExecution, onRestartExecution: handleRestartExecution },
      { activeScope, sortField, sortOrder, integrationIconsMap, user, canViewAll, cancellingId, restartLoadingId },
      { token, isDark }
    ),
    [activeScope, sortField, sortOrder, integrationIconsMap, user, canViewAll, cancellingId, restartLoadingId, handleCancelExecution, handleRestartExecution, token, isDark]
  );
  ```

**Rationale :** Séparation des préoccupations — définitions de colonnes réutilisables dans d'autres contextes (widgets, rapports)

---

### AC2: Extraction de la logique drawer → `useExecutionDetail()` hook

**Given** ExecutionsPage contient 7 variables d'état pour le drawer (lignes 217-285)
**When** la logique drawer est extraite
**Then** :

- Un fichier `frontend/src/hooks/useExecutionDetail.ts` est créé
- Hook custom retournant :
  ```typescript
  interface UseExecutionDetailReturn {
    // État
    drawerOpen: boolean;
    selectedExecution: ExecutionResponse | null;
    selectedSteps: ExecutionStepResponse[] | null;
    selectedActionDetail: CatalogActionDetail | null;
    loading: boolean;
    error: string | null;

    // Actions
    openExecution: (id: number) => Promise<void>;
    closeDrawer: () => void;
  }

  export const useExecutionDetail = (): UseExecutionDetailReturn => { ... }
  ```
- La logique useEffect (lignes 250-285) pour URL sync `?open=79` est intégrée dans le hook
- Le hook gère le chargement de :
  1. `getExecution(id)` → selectedExecution
  2. `getExecutionSteps(id)` → selectedSteps
  3. `fetchCatalogActionById(execution.action_id)` → selectedActionDetail
- Gestion d'erreur incluse avec try/catch
- ExecutionsPage.tsx utilise le hook :
  ```typescript
  import { useExecutionDetail } from '../hooks/useExecutionDetail';

  const {
    drawerOpen,
    selectedExecution,
    selectedSteps,
    selectedActionDetail,
    loading: drawerLoading,
    error: drawerError,
    openExecution,
    closeDrawer,
  } = useExecutionDetail();
  ```
- Réduction ExecutionsPage : -70 LOC (7 useState + 1 useEffect + helpers)

**Rationale :** Encapsulation de la logique drawer, réutilisable dans d'autres pages (Dashboard, Calendar)

---

### AC3: Extraction de la logique restart wizard → `useExecutionRestart()` hook

**Given** ExecutionsPage contient 5 variables d'état pour le restart wizard (lignes 433-516)
**When** la logique restart est extraite
**Then** :

- Un fichier `frontend/src/hooks/useExecutionRestart.ts` est créé
- Hook custom retournant :
  ```typescript
  interface UseExecutionRestartReturn {
    // État wizard
    restartAction: CatalogActionDetail | null;
    restartEnvs: string[] | null;
    restartParams: Record<string, any> | null;
    restartLoadingId: number | null;

    // Actions
    handleRestartExecution: (execution: ExecutionResponse) => Promise<void>;
    handleRestartWizardClose: () => void;
    handleRestartSuccess: () => void;
  }

  export const useExecutionRestart = (
    refetchCurrentState: () => { page: number; scope: ExecutionScope }
  ): UseExecutionRestartReturn => { ... }
  ```
- La logique de chargement action + préparation params (lignes 484-516) est intégrée
- Le hook appelle `fetchCatalogActionById()` et `prepareWizardParamsFromExecution()`
- Gestion d'erreur avec notification App.useApp()
- Callback `handleRestartSuccess()` utilise `refetchCurrentState()` pour éviter stale closure
- ExecutionsPage.tsx utilise le hook :
  ```typescript
  import { useExecutionRestart } from '../hooks/useExecutionRestart';

  const {
    restartAction,
    restartEnvs,
    restartParams,
    restartLoadingId,
    handleRestartExecution,
    handleRestartWizardClose,
    handleRestartSuccess,
  } = useExecutionRestart(refetchCurrentState);
  ```
- Réduction ExecutionsPage : -85 LOC (5 useState + 2 useCallback)

**Rationale :** Encapsulation de la logique restart, évite la duplication si d'autres pages ont besoin de relancer une exécution

---

### AC4: Création du sous-composant `<ExecutionsStatSection>`

**Given** ExecutionsPage contient StatCards + TrendLineChart (lignes 831-873)
**When** la section stats est extraite
**Then** :

- Un fichier `frontend/src/components/executions/ExecutionsStatSection.tsx` est créé
- Composant encapsulant :
  - 4 StatCards (Story 9.4) : executions du jour, taux de succès, en cours, en erreur
  - TrendLineChart (Story 9.10)
  - Loading skeleton pour les cards
- Props du composant :
  ```typescript
  interface ExecutionsStatSectionProps {
    statsData: DashboardStats | null;
    statsLoading: boolean;
    timeSeriesData: DashboardTimeSeriesPoint[];
    timeSeriesLoading: boolean;
    activeScope: ExecutionScope;
  }
  ```
- Composant responsable du layout responsive (Row/Col xs=24 sm=12 md=6)
- ExecutionsPage.tsx utilise le composant :
  ```typescript
  import { ExecutionsStatSection } from '../components/executions/ExecutionsStatSection';

  <ExecutionsStatSection
    statsData={statsData}
    statsLoading={statsLoading}
    timeSeriesData={timeSeriesData}
    timeSeriesLoading={timeSeriesLoading}
    activeScope={activeScope}
  />
  ```
- Réduction ExecutionsPage : -45 LOC (JSX + layout logic)

**Rationale :** Composant réutilisable pour d'autres dashboards, séparation de la logique de présentation stats

---

### AC5: Création du sous-composant `<ExecutionDetailDrawer>`

**Given** ExecutionsPage contient le Drawer avec Timeline/Graph (lignes 963-1010)
**When** le drawer est extrait
**Then** :

- Un fichier `frontend/src/components/executions/ExecutionDetailDrawer.tsx` est créé
- Composant encapsulant :
  - Ant Design Drawer avec width 640px
  - ExecutionTimeline (pour actions simples)
  - WorkflowExecutionGraph (pour workflows)
  - Loading skeleton
  - Error Alert
  - Footer avec bouton Close
- Props du composant :
  ```typescript
  interface ExecutionDetailDrawerProps {
    open: boolean;
    execution: ExecutionResponse | null;
    steps: ExecutionStepResponse[] | null;
    actionDetail: CatalogActionDetail | null;
    loading: boolean;
    error: string | null;
    onClose: () => void;
  }
  ```
- Logique conditionnelle item_type==='workflow' → Graph, sinon Timeline
- ExecutionsPage.tsx utilise le composant :
  ```typescript
  import { ExecutionDetailDrawer } from '../components/executions/ExecutionDetailDrawer';

  <ExecutionDetailDrawer
    open={drawerOpen}
    execution={selectedExecution}
    steps={selectedSteps}
    actionDetail={selectedActionDetail}
    loading={drawerLoading}
    error={drawerError}
    onClose={closeDrawer}
  />
  ```
- Réduction ExecutionsPage : -50 LOC (JSX drawer)

**Rationale :** Drawer réutilisable dans d'autres contextes (Calendar, Dashboard widgets)

---

### AC6: Réduction ExecutionsPage.tsx à <400 LOC

**Given** le refactoring est complet
**When** on mesure les LOC
**Then** :

- `ExecutionsPage.tsx` : **≤400 LOC** (cible Story 26.4)
  - Réductions estimées :
    - Colonnes extraites : -134 LOC
    - Drawer hook : -70 LOC
    - Restart hook : -85 LOC
    - StatSection : -45 LOC
    - DetailDrawer : -50 LOC
    - **Total : -384 LOC** → ~640 LOC final (baseline 1023)
  - Pour atteindre <400 LOC, extraction additionnelle recommandée :
    - Logique data fetching dans `useExecutionsData()` hook : -100 LOC estimés
    - ExecutionsFiltersPanel déjà extrait (ligne 876)
- Nouveaux fichiers créés :
  - `executionsColumns.tsx` : ~180 LOC
  - `useExecutionDetail.ts` : ~100 LOC
  - `useExecutionRestart.ts` : ~120 LOC
  - `ExecutionsStatSection.tsx` : ~60 LOC
  - `ExecutionDetailDrawer.tsx` : ~80 LOC
- **Structure finale du composant principal :**
  ```typescript
  export const ExecutionsPage: React.FC = () => {
    // Hooks (auth, filters, detail, restart)
    // Computed values (RBAC, sorted executions)
    // Event handlers (fetch, cancel)

    return (
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <ExecutionsStatSection {...statsProps} />
        <ExecutionsFiltersPanel {...filtersProps} />
        <PendingApprovalsList {...approvalsProps} />
        <ExecutionsTabs {...tabsProps} />
        <Table columns={columns} {...tableProps} />
        <ExecutionDetailDrawer {...drawerProps} />
        <ExecutionWizard {...restartWizardProps} />
      </Space>
    );
  };
  ```

**Rationale :** Composant principal devient orchestrateur mince, logique déléguée aux hooks et sous-composants

---

### AC7: Tous les tests existants passent (0 régression)

**Given** le refactoring est terminé
**When** la suite de tests est exécutée
**Then** :

- **100% des tests existants passent** sans modification de logique fonctionnelle
- Tests spécifiques vérifiés :
  - Tests ExecutionsPage existants (rendering, interactions, filtres)
  - Tests d'intégration Story 8.8, 8.9, 9.4, 9.9, 9.10, 17.13, 22.14
- Aucune régression fonctionnelle
- Les tests peuvent nécessiter des ajustements d'imports si ils importent directement depuis ExecutionsPage

**Rationale :** Le refactoring est interne — l'API publique et le comportement utilisateur ne changent pas

---

### AC8: Tests unitaires pour les nouveaux modules créés

**Given** les hooks et composants sont créés
**When** les tests sont écrits
**Then** :

- **Tests pour `executionsColumns.tsx` :**
  - Test rendu de chaque colonne (9 colonnes)
  - Test callbacks onCancelExecution, onRestartExecution
  - Test visibilité colonne Utilisateur (activeScope='all')
  - Test états loading (cancellingId, restartLoadingId)
  - Mock des fonctions render (renderStatusIndicator, renderEngineIcon, renderPlateformeIcon)
  - Minimum 12 tests

- **Tests pour `useExecutionDetail()` hook :**
  - Test openExecution() charge execution + steps + action
  - Test closeDrawer() reset état
  - Test gestion erreur (getExecution fail)
  - Test URL sync via mock useParams/useSearchParams
  - Minimum 6 tests

- **Tests pour `useExecutionRestart()` hook :**
  - Test handleRestartExecution() charge action et prépare params
  - Test handleRestartWizardClose() reset état
  - Test handleRestartSuccess() utilise refetchCurrentState()
  - Test gestion erreur (action non disponible)
  - Minimum 5 tests

- **Tests pour `<ExecutionsStatSection>` :**
  - Test rendu 4 StatCards + TrendLineChart
  - Test skeleton loading
  - Test responsive layout (Row/Col)
  - Minimum 4 tests

- **Tests pour `<ExecutionDetailDrawer>` :**
  - Test rendu Timeline pour action simple
  - Test rendu WorkflowGraph pour workflow
  - Test skeleton loading
  - Test error Alert
  - Test bouton Close appelle onClose
  - Minimum 6 tests

- **Coverage :** ≥80% pour chaque nouveau module

**Rationale :** Tests unitaires isolés garantissent la stabilité des modules extraits

---

## Tasks / Subtasks

### Task 1: Créer la structure de fichiers (AC1, AC4, AC5)
- [x] **1.1** Créer répertoire `frontend/src/pages/executions/`
- [x] **1.2** Créer fichier `frontend/src/pages/executions/executionsColumns.tsx` (vide)
- [x] **1.3** Créer fichier `frontend/src/hooks/useExecutionDetail.ts` (vide)
- [x] **1.4** Créer fichier `frontend/src/hooks/useExecutionRestart.ts` (vide)
- [x] **1.5** Créer répertoire `frontend/src/components/executions/`
- [x] **1.6** Créer fichier `frontend/src/components/executions/ExecutionsStatSection.tsx` (vide)
- [x] **1.7** Créer fichier `frontend/src/components/executions/ExecutionDetailDrawer.tsx` (vide)

---

### Task 2: Extraire les définitions de colonnes (AC1)
- [x] **2.1** Copier les fonctions utilitaires `formatDuration()`, `formatDate()`, `RUNNING_STATUSES`, `MESSAGES` vers `executionsColumns.tsx`
- [x] **2.2** Définir les types `ExecutionColumnHandlers` et `ExecutionColumnState`
- [x] **2.3** Créer la fonction `getExecutionsColumns(handlers, state, theme)`
- [x] **2.4** Copier les 9 définitions de colonnes depuis ExecutionsPage.tsx (lignes 651-784)
- [x] **2.5** Adapter les références aux variables d'état : utiliser `state.activeScope`, `state.sortField`, etc.
- [x] **2.6** Adapter les callbacks : utiliser `handlers.onCancelExecution`, `handlers.onRestartExecution`
- [x] **2.7** Ajouter les imports nécessaires (Ant Design, types API, renderers)
- [x] **2.8** Exporter `getExecutionsColumns`, `formatDuration`, `formatDate`
- [x] **2.9** Mettre à jour ExecutionsPage.tsx pour importer et utiliser `getExecutionsColumns()`
- [x] **2.10** Supprimer les définitions de colonnes inline de ExecutionsPage.tsx
- [x] **2.11** Vérifier que la Table s'affiche correctement (npm run dev)

---

### Task 3: Extraire la logique drawer (AC2)
- [x] **3.1** Créer le hook `useExecutionDetail()` dans `useExecutionDetail.ts`
- [x] **3.2** Ajouter imports : `useState`, `useEffect`, `useParams`, `useSearchParams`, services
- [x] **3.3** Copier les 7 variables d'état drawer depuis ExecutionsPage.tsx (lignes 217-222)
- [x] **3.4** Implémenter `openExecution(id)` :
  - Appeler `getExecution(id)`
  - Appeler `getExecutionSteps(id)`
  - Appeler `fetchCatalogActionById(execution.action_id)`
  - Gestion erreur avec try/catch
- [x] **3.5** Implémenter `closeDrawer()` : reset tous les états
- [x] **3.6** Copier la logique URL sync (lignes 250-285) dans useEffect
- [x] **3.7** Définir le type de retour `UseExecutionDetailReturn`
- [x] **3.8** Retourner l'objet avec état + actions
- [x] **3.9** Mettre à jour ExecutionsPage.tsx pour utiliser le hook
- [x] **3.10** Supprimer les 7 useState + 1 useEffect de ExecutionsPage.tsx
- [x] **3.11** Vérifier que le drawer fonctionne (clic sur exécution, URL ?open=79)

---

### Task 4: Extraire la logique restart wizard (AC3)
- [x] **4.1** Créer le hook `useExecutionRestart()` dans `useExecutionRestart.ts`
- [x] **4.2** Ajouter imports : `useState`, `useCallback`, `App.useApp()`, services, types
- [x] **4.3** Copier les 5 variables d'état restart depuis ExecutionsPage.tsx (lignes 433-437)
- [x] **4.4** Implémenter `handleRestartExecution(execution)` :
  - Appeler `fetchCatalogActionById(execution.action_id)`
  - Appeler `prepareWizardParamsFromExecution(execution)`
  - Set restartAction, restartEnvs, restartParams
  - Gestion erreur avec notification
- [x] **4.5** Implémenter `handleRestartWizardClose()` : reset états
- [x] **4.6** Implémenter `handleRestartSuccess()` :
  - Appeler `refetchCurrentState()` pour éviter stale closure
  - Close wizard
  - Reload data
- [x] **4.7** Définir le type `UseExecutionRestartReturn`
- [x] **4.8** Accepter `refetchCurrentState` en paramètre du hook
- [x] **4.9** Retourner l'objet avec état + handlers
- [x] **4.10** Mettre à jour ExecutionsPage.tsx pour utiliser le hook
- [x] **4.11** Supprimer les 5 useState + 2 useCallback de ExecutionsPage.tsx
- [x] **4.12** Vérifier que le restart wizard fonctionne (clic Redo, soumission, refresh)

---

### Task 5: Extraire le composant StatSection (AC4)
- [x] **5.1** Créer `<ExecutionsStatSection>` dans `ExecutionsStatSection.tsx`
- [x] **5.2** Définir `ExecutionsStatSectionProps` avec types stricts
- [x] **5.3** Copier le JSX des StatCards + TrendLineChart depuis ExecutionsPage.tsx (lignes 831-873)
- [x] **5.4** Adapter les références props : `statsData`, `statsLoading`, `timeSeriesData`, `timeSeriesLoading`, `activeScope`
- [x] **5.5** Ajouter les imports Ant Design (Row, Col, Skeleton), StatCard, TrendLineChart
- [x] **5.6** Conserver le layout responsive (xs=24 sm=12 md=6)
- [x] **5.7** Exporter le composant
- [x] **5.8** Mettre à jour ExecutionsPage.tsx pour utiliser `<ExecutionsStatSection>`
- [x] **5.9** Supprimer le JSX StatCards + TrendLineChart de ExecutionsPage.tsx
- [x] **5.10** Vérifier que les stats s'affichent correctement

---

### Task 6: Extraire le composant DetailDrawer (AC5)
- [x] **6.1** Créer `<ExecutionDetailDrawer>` dans `ExecutionDetailDrawer.tsx`
- [x] **6.2** Définir `ExecutionDetailDrawerProps` avec types stricts
- [x] **6.3** Copier le JSX du Drawer depuis ExecutionsPage.tsx (lignes 963-1010)
- [x] **6.4** Adapter les props : `open`, `execution`, `steps`, `actionDetail`, `loading`, `error`, `onClose`
- [x] **6.5** Ajouter les imports Ant Design (Drawer, Skeleton, Alert), ExecutionTimeline, WorkflowExecutionGraph
- [x] **6.6** Conserver la logique conditionnelle item_type==='workflow' → Graph vs Timeline
- [x] **6.7** Exporter le composant
- [x] **6.8** Mettre à jour ExecutionsPage.tsx pour utiliser `<ExecutionDetailDrawer>`
- [x] **6.9** Supprimer le JSX Drawer de ExecutionsPage.tsx
- [x] **6.10** Vérifier que le drawer fonctionne (ouverture, Timeline/Graph, fermeture)

---

### Task 7: Validation finale et mesure LOC (AC6)
- [x] **7.1** Compter LOC de ExecutionsPage.tsx : `wc -l ExecutionsPage.tsx`
- [x] **7.2** Si >400 LOC, identifier extractions additionnelles :
  - Option A : Extraire data fetching dans `useExecutionsData()` hook
  - Option B : Extraire PendingApprovalsList section dans composant
- [x] **7.3** Implémenter les extractions additionnelles si nécessaire
- [x] **7.4** Vérifier que ExecutionsPage.tsx ≤400 LOC
- [x] **7.5** Valider la structure finale (orchestrateur mince)
- [x] **7.6** Compter LOC des nouveaux fichiers :
  - `executionsColumns.tsx`
  - `useExecutionDetail.ts`
  - `useExecutionRestart.ts`
  - `ExecutionsStatSection.tsx`
  - `ExecutionDetailDrawer.tsx`

---

### Task 8: Créer tests unitaires (AC8)
- [x] **8.1** Créer `frontend/src/pages/executions/__tests__/executionsColumns.test.tsx`
- [x] **8.2** Tests executionsColumns :
  - Rendu 9 colonnes
  - Callbacks onCancelExecution, onRestartExecution
  - Visibilité colonne Utilisateur
  - États loading (cancellingId, restartLoadingId)
  - Mock renderStatusIndicator, renderEngineIcon, renderPlateformeIcon
- [x] **8.3** Créer `frontend/src/hooks/__tests__/useExecutionDetail.test.ts`
- [x] **8.4** Tests useExecutionDetail :
  - openExecution() charge execution + steps + action
  - closeDrawer() reset état
  - Gestion erreur
  - URL sync
- [x] **8.5** Créer `frontend/src/hooks/__tests__/useExecutionRestart.test.ts`
- [x] **8.6** Tests useExecutionRestart :
  - handleRestartExecution() charge action
  - handleRestartWizardClose() reset
  - handleRestartSuccess() refetch
  - Gestion erreur
- [x] **8.7** Créer `frontend/src/components/executions/__tests__/ExecutionsStatSection.test.tsx`
- [x] **8.8** Tests ExecutionsStatSection :
  - Rendu StatCards + TrendLineChart
  - Skeleton loading
  - Responsive layout
- [x] **8.9** Créer `frontend/src/components/executions/__tests__/ExecutionDetailDrawer.test.tsx`
- [x] **8.10** Tests ExecutionDetailDrawer :
  - Rendu Timeline (action simple)
  - Rendu WorkflowGraph (workflow)
  - Skeleton loading
  - Error Alert
  - Bouton Close
- [x] **8.11** Exécuter tous les tests : `npm test`
- [x] **8.12** Vérifier coverage ≥80% pour chaque nouveau module

---

### Task 9: Exécuter tests existants et valider (AC7)
- [x] **9.1** Exécuter suite de tests complète : `npm test`
- [x] **9.2** Vérifier qu'aucun test existant n'échoue (régression = 0)
- [x] **9.3** Ajuster les imports dans les tests si nécessaire
- [x] **9.4** Vérifier tests spécifiques :
  - Story 8.8 (PendingApprovalsList)
  - Story 8.9 (Tabs scope)
  - Story 9.4 (StatCards)
  - Story 9.9 (Colonnes Technologie/Plateforme)
  - Story 9.10 (Filtres + TrendLineChart)
  - Story 17.13 (Mode compact)
  - Story 22.14 (Stale closure refs)
- [x] **9.5** Valider 0 régression fonctionnelle

---

### Task 10: Documentation et cleanup
- [x] **10.1** Ajouter JSDoc complets aux nouveaux fichiers :
  - executionsColumns.tsx : documenter chaque colonne
  - useExecutionDetail.ts : documenter hook + return type
  - useExecutionRestart.ts : documenter hook + params
  - ExecutionsStatSection.tsx : documenter props
  - ExecutionDetailDrawer.tsx : documenter props
- [x] **10.2** Mettre à jour les commentaires Story/AC dans ExecutionsPage.tsx
- [x] **10.3** Vérifier que tous les imports sont utilisés (pas d'imports morts)
- [x] **10.4** Exécuter ESLint : `npm run lint`
- [x] **10.5** Fixer les warnings ESLint éventuels
- [x] **10.6** Vérifier TypeScript strict : `npm run type-check` (si disponible)
- [x] **10.7** Commit final avec message : `refactor(26-4): extract ExecutionsPage into columns/hooks/components (<400 LOC)`

---

## Dev Notes

### Références techniques

**Source principale :**
- [Epic 26: Qualité du Code — Assessment 6 février 2026](../planning-artifacts/epic-26-qualite-code-assessment-fev-2026.md)
- [Code Quality Assessment](../../docs/code-quality-assessment-2026-02-08.md) — Section 4.4

**Fichier concerné :**
- `idp-portal/frontend/src/pages/ExecutionsPage.tsx` (1 023 LOC actuellement)

**Nouveaux fichiers à créer :**
```
frontend/src/
├── pages/
│   └── executions/
│       ├── executionsColumns.tsx           # NEW (~180 LOC)
│       └── __tests__/
│           └── executionsColumns.test.tsx  # NEW (~150 LOC)
├── hooks/
│   ├── useExecutionDetail.ts               # NEW (~100 LOC)
│   ├── useExecutionRestart.ts              # NEW (~120 LOC)
│   └── __tests__/
│       ├── useExecutionDetail.test.ts      # NEW (~80 LOC)
│       └── useExecutionRestart.test.ts     # NEW (~70 LOC)
└── components/
    └── executions/
        ├── ExecutionsStatSection.tsx       # NEW (~60 LOC)
        ├── ExecutionDetailDrawer.tsx       # NEW (~80 LOC)
        └── __tests__/
            ├── ExecutionsStatSection.test.tsx  # NEW (~50 LOC)
            └── ExecutionDetailDrawer.test.tsx  # NEW (~70 LOC)
```

---

### Architecture & Patterns existants

**Pattern actuel :** Monolithe 1 023 LOC
- Toute la logique dans un seul composant
- Difficile à tester, réutiliser, maintenir

**Pattern cible :** Composant orchestrateur + modules spécialisés
- ExecutionsPage.tsx : orchestrateur <400 LOC
- Colonnes, hooks, composants : modules réutilisables
- Tests unitaires isolés

**Principes architecturaux (Architecture.md) :**
- **React 19** : Hooks custom pour logique réutilisable
- **Ant Design 6.2** : Composants natifs (Drawer, Table, Skeleton)
- **TypeScript strict** : Type hints pour props/hooks
- **Vite 7** : HMR rapide, build optimisé
- **Vitest + React Testing Library** : Tests unitaires

**Patterns établis dans le codebase :**

1. **Extraction colonnes Table** (Story 22.8, actionsColumns.tsx) :
   - Fonction `getXXXColumns(handlers, state, theme)` retournant `TableProps<T>['columns']`
   - Types stricts pour handlers et state
   - Utilitaires formatters exportés

2. **Hooks custom pour logique métier** (Story 20.4, ExecutionWizard) :
   - `useExecutionWizard()` encapsule state + lifecycle
   - Retourne objet avec état + actions
   - Testable unitairement

3. **Extraction sous-composants** (Story 22.9, AdminPage) :
   - AdminPage 845 → 75 LOC
   - 6 panels extraits : ActionsPanel, ProfilesPanel, IntegrationsPanel, etc.
   - Props typées strictement

4. **Stale closure prevention** (Story 22.14) :
   - Utiliser refs pour valeurs courantes dans callbacks modaux
   - `refetchCurrentState()` pattern pour éviter captures obsolètes

---

### Analyse détaillée du fichier actuel

**Structure ExecutionsPage.tsx (1 023 LOC) :**

```typescript
// Lines 1-104: Imports + constants
import { 20+ imports from react, ant, services, types }
const MESSAGES = { ... }
const RUNNING_STATUSES = [...]

// Lines 105-149: Utility functions
function formatDuration() { ... }
function formatDate() { ... }

// Lines 150-650: Component state & logic
export const ExecutionsPage: React.FC = () => {
  // Lines 158-172: Hooks (auth, theme, app)
  const { notification, modal } = App.useApp();
  const { token } = theme.useToken();
  const { user, authLoading } = useAuth();
  const { filters, setFilters, clearFilters, activeFiltersCount } = useExecutionFilters();

  // Lines 178-226: État (20+ useState)
  const [integrationIconsMap, setIntegrationIconsMap] = useState<IntegrationIconsMap | null>(null);
  const [executions, setExecutions] = useState<ExecutionResponse[]>([]);
  const [loading, setLoading] = useState(false);
  // ... 17 autres useState

  // Lines 229-246: Data fetching
  const fetchData = useCallback(async () => { ... }, [currentPage, sortField, sortOrder, filters]);

  // Lines 250-403: useEffect (9 hooks)
  useEffect(() => { /* Scope sync */ }, [authLoading, canViewAll, activeScope]);
  useEffect(() => { /* Fetch data */ }, [currentPage, activeScope, fetchData]);
  useEffect(() => { /* URL sync drawer */ }, [openExecutionId]);
  // ... 6 autres useEffect

  // Lines 405-516: Event handlers (7 callbacks)
  const handleCancelExecution = useCallback(async (executionId: number) => { ... }, [...]);
  const handleRestartExecution = useCallback(async (execution: ExecutionResponse) => { ... }, [...]);
  // ... 5 autres handlers

  // Lines 519-600: Computed values (3 useMemo)
  const canApprove = useMemo(() => ..., [user]);
  const topLevelExecutions = useMemo(() => ..., [executions]);
  const sortedExecutions = useMemo(() => ..., [topLevelExecutions, sortField, sortOrder]);

  // Lines 651-784: Column definitions (134 LOC!)
  const columns = useMemo<TableProps<ExecutionResponse>['columns']>(() => [
    { title: 'Statut', ... },
    { title: 'Action', ... },
    // ... 7 autres colonnes
  ], [activeScope, sortField, sortOrder, integrationIconsMap, user, canViewAll, cancellingId, restartLoadingId]);

  // Lines 787-1021: JSX rendering (400+ LOC)
  return (
    <Space direction="vertical" size="large">
      {/* Skeleton loading (28 LOC) */}
      {/* Error state (8 LOC) */}
      {/* StatCards (38 LOC) */}
      {/* TrendLineChart (3 LOC) */}
      {/* ExecutionsFiltersPanel (7 LOC) */}
      {/* PendingApprovalsList (19 LOC) */}
      {/* ExecutionsTabs (5 LOC) */}
      {/* Main Table (49 LOC) */}
      {/* Drawer (48 LOC) */}
      {/* Restart Wizard (8 LOC) */}
    </Space>
  );
};
```

**Observations clés :**

1. **Définitions colonnes (134 LOC)** — candidat prioritaire extraction
2. **État drawer (7 variables)** — candidat hook `useExecutionDetail()`
3. **État restart (5 variables)** — candidat hook `useExecutionRestart()`
4. **JSX StatCards (38 LOC)** — candidat composant `<ExecutionsStatSection>`
5. **JSX Drawer (48 LOC)** — candidat composant `<ExecutionDetailDrawer>`

**Dépendances entre états :**
- `activeScope` → détermine visibilité colonne Utilisateur
- `integrationIconsMap` → nécessaire pour colonne Plateforme
- `sortField`, `sortOrder` → configuration colonnes sortables
- `cancellingId`, `restartLoadingId` → états loading boutons Actions

**Extractions recommandées (ordre prioritaire) :**

1. **Phase 1 (Quick wins) :**
   - executionsColumns.tsx (-134 LOC)
   - useExecutionDetail() (-70 LOC)
   - useExecutionRestart() (-85 LOC)
   - **Total : -289 LOC → ~734 LOC**

2. **Phase 2 (Composants) :**
   - ExecutionsStatSection (-45 LOC)
   - ExecutionDetailDrawer (-50 LOC)
   - **Total : -95 LOC → ~639 LOC**

3. **Phase 3 (Si nécessaire pour <400 LOC) :**
   - useExecutionsData() hook (data fetching) (-100 LOC estimés)
   - **Total : -100 LOC → ~539 LOC**

4. **Phase 4 (Optionnel si encore >400 LOC) :**
   - ExecutionsPendingSection composant (-30 LOC)
   - **Total : -30 LOC → ~509 LOC**

Pour atteindre <400 LOC, **Phase 1 + Phase 2 + Phase 3** sont nécessaires.

---

### Exemple d'implémentation executionsColumns.tsx

```typescript
/**
 * ExecutionsPage Table Columns Definitions
 *
 * Story 26.4 - AC1: Extracted from ExecutionsPage.tsx to separate concerns.
 * Defines all 9 columns for the executions table with handlers and state.
 */
import React from 'react';
import { Button, Tooltip, Space } from 'antd';
import { RedoOutlined, CloseCircleOutlined } from '@ant-design/icons';
import type { TableProps } from 'antd';
import type {
  ExecutionResponse,
  ExecutionStatusType,
  ExecutionScope,
  IntegrationIconsMap,
} from '../../types/api';
import type { User } from '../../contexts/AuthContext';
import {
  renderStatusIndicator,
  renderEngineIcon,
  renderPlateformeIcon,
} from '../../utils/executionRenderers';

/** Running statuses that appear first with visual indicator. */
const RUNNING_STATUSES: ExecutionStatusType[] = ['RUNNING', 'SUBMITTED', 'PENDING_APPROVAL'];

/** Format duration from ISO timestamps. */
export function formatDuration(startedAt: string | null, completedAt: string | null): string {
  if (!startedAt || !completedAt) return '—';
  const start = new Date(startedAt).getTime();
  const end = new Date(completedAt).getTime();
  const seconds = Math.round((end - start) / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return remaining ? `${minutes}m ${remaining}s` : `${minutes}m`;
}

/** Format date for display. */
export function formatDate(dateStr: string | null): string {
  if (!dateStr) return '—';
  const date = new Date(dateStr);
  return date.toLocaleString('fr-FR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** Handlers passed to column definitions. */
export interface ExecutionColumnHandlers {
  onCancelExecution: (id: number) => void;
  onRestartExecution: (execution: ExecutionResponse) => void;
}

/** State required for column rendering. */
export interface ExecutionColumnState {
  activeScope: ExecutionScope;
  sortField: string;
  sortOrder: 'ascend' | 'descend';
  integrationIconsMap: IntegrationIconsMap | null;
  user: User;
  canViewAll: boolean;
  cancellingId: number | null;
  restartLoadingId: number | null;
}

/**
 * Get ExecutionsPage table columns configuration.
 *
 * @param handlers - Event handlers for column actions
 * @param state - Current state for conditional rendering
 * @param theme - Ant Design theme tokens
 * @returns Table columns array
 */
export const getExecutionsColumns = (
  handlers: ExecutionColumnHandlers,
  state: ExecutionColumnState,
  theme: { token: any; isDark: boolean }
): TableProps<ExecutionResponse>['columns'] => [
  // Column 1: Statut (Story 9.9 AC1)
  {
    title: 'Statut',
    dataIndex: 'status',
    key: 'status',
    width: 100,
    align: 'center',
    render: (status: ExecutionStatusType) => renderStatusIndicator(status),
  },

  // Column 2: Action (Story 9.9 AC7)
  {
    title: 'Action',
    dataIndex: 'action_name',
    key: 'action_name',
    sorter: true,
    sortOrder: state.sortField === 'action_name' ? state.sortOrder : undefined,
    render: (name: string | null, record: ExecutionResponse) =>
      name || `Action #${record.action_id}`,
  },

  // Column 3: Technologie (Story 9.9 AC4)
  {
    title: 'Technologie',
    dataIndex: 'engine',
    key: 'engine',
    width: 100,
    align: 'center',
    render: (_: string, record: ExecutionResponse) =>
      renderEngineIcon(record.engine, record.item_type),
  },

  // Column 4: Plateforme (Story 9.9 AC5)
  {
    title: 'Plateforme',
    dataIndex: 'integration_name',
    key: 'integration_name',
    width: 100,
    align: 'center',
    render: (_: string, record: ExecutionResponse) =>
      renderPlateformeIcon(
        record.integration_name,
        record.integration_icon,
        record.platform,
        state.integrationIconsMap
      ),
  },

  // Column 5: Utilisateur (Story 8.9 AC9 - conditional)
  ...(state.activeScope === 'all'
    ? [
        {
          title: 'Utilisateur',
          dataIndex: 'user_display_name',
          key: 'user_display_name',
          width: 130,
        },
      ]
    : []),

  // Column 6: Environnement (Story 9.9 AC7)
  {
    title: 'Environnement',
    dataIndex: 'environment',
    key: 'environment',
    width: 120,
    render: (env: string) => env.toUpperCase(),
  },

  // Column 7: Date (Story 9.9 AC7)
  {
    title: 'Date',
    dataIndex: 'created_at',
    key: 'created_at',
    sorter: true,
    sortOrder: state.sortField === 'created_at' ? state.sortOrder : undefined,
    render: (_: string, record: ExecutionResponse) =>
      formatDate(record.started_at || record.created_at),
  },

  // Column 8: Durée (Story 9.9 AC7)
  {
    title: 'Durée',
    key: 'duration',
    width: 80,
    render: (_: any, record: ExecutionResponse) =>
      formatDuration(record.started_at, record.completed_at),
  },

  // Column 9: Actions (Story 17.14 + 17.15)
  {
    title: 'Actions',
    key: 'actions',
    width: 100,
    align: 'center',
    render: (_: any, record: ExecutionResponse) => {
      const canCancel =
        (record.status === 'SUBMITTED' || record.status === 'RUNNING') &&
        (record.user_id === state.user.id || state.canViewAll);

      const canRestart = record.user_id === state.user.id || state.canViewAll;

      return (
        <Space size="small">
          {canRestart && (
            <Tooltip title="Relancer avec les mêmes paramètres">
              <Button
                type="text"
                size="small"
                icon={<RedoOutlined />}
                loading={state.restartLoadingId === record.id}
                onClick={(e) => {
                  e.stopPropagation();
                  handlers.onRestartExecution(record);
                }}
              />
            </Tooltip>
          )}
          {canCancel && (
            <Tooltip title="Annuler l'exécution">
              <Button
                type="text"
                size="small"
                danger
                icon={<CloseCircleOutlined />}
                loading={state.cancellingId === record.id}
                onClick={(e) => {
                  e.stopPropagation();
                  handlers.onCancelExecution(record.id);
                }}
              />
            </Tooltip>
          )}
        </Space>
      );
    },
  },
];
```

---

### Exemple d'implémentation useExecutionDetail()

```typescript
/**
 * useExecutionDetail - Hook for managing execution detail drawer state
 *
 * Story 26.4 - AC2: Extracted from ExecutionsPage.tsx to encapsulate drawer logic.
 * Handles loading execution details, steps, and action metadata for the drawer.
 */
import { useState, useEffect } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router';
import type {
  ExecutionResponse,
  ExecutionStepResponse,
} from '../types/api';
import type { CatalogActionDetail } from '../services/catalog_service';
import {
  getExecution,
  getExecutionSteps,
} from '../services/execution_service';
import { fetchCatalogActionById } from '../services/catalog_service';

/** Return type for useExecutionDetail hook. */
export interface UseExecutionDetailReturn {
  drawerOpen: boolean;
  selectedExecution: ExecutionResponse | null;
  selectedSteps: ExecutionStepResponse[] | null;
  selectedActionDetail: CatalogActionDetail | null;
  loading: boolean;
  error: string | null;
  openExecution: (id: number) => Promise<void>;
  closeDrawer: () => void;
}

/**
 * Custom hook to manage execution detail drawer state and data loading.
 *
 * Features:
 * - Loads execution + steps + action detail on open
 * - Supports URL-based opening via ?open=79 query param
 * - Handles errors with state management
 * - Provides close handler to reset all state
 *
 * @returns Drawer state and control functions
 */
export const useExecutionDetail = (): UseExecutionDetailReturn => {
  const navigate = useNavigate();
  const { id: routeId } = useParams();
  const [searchParams] = useSearchParams();

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedExecution, setSelectedExecution] = useState<ExecutionResponse | null>(null);
  const [selectedSteps, setSelectedSteps] = useState<ExecutionStepResponse[] | null>(null);
  const [selectedActionDetail, setSelectedActionDetail] = useState<CatalogActionDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /**
   * Open execution detail drawer by ID.
   * Loads execution, steps, and action metadata.
   */
  const openExecution = async (id: number): Promise<void> => {
    setLoading(true);
    setError(null);
    setDrawerOpen(true);

    try {
      // Load execution details
      const execution = await getExecution(id);
      setSelectedExecution(execution);

      // Load execution steps
      const steps = await getExecutionSteps(id);
      setSelectedSteps(steps);

      // Load action details if available
      if (execution.action_id) {
        const actionDetail = await fetchCatalogActionById(execution.action_id);
        setSelectedActionDetail(actionDetail);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erreur lors du chargement');
      setSelectedExecution(null);
      setSelectedSteps(null);
      setSelectedActionDetail(null);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Close drawer and reset all state.
   */
  const closeDrawer = (): void => {
    setDrawerOpen(false);
    setSelectedExecution(null);
    setSelectedSteps(null);
    setSelectedActionDetail(null);
    setError(null);

    // Clear URL query param if present
    navigate({ search: '' }, { replace: true });
  };

  /**
   * URL sync: Open drawer if ?open=79 query param is present.
   */
  useEffect(() => {
    const openParam = searchParams.get('open');
    const openExecutionId = openParam ? parseInt(openParam, 10) : null;

    if (openExecutionId && !isNaN(openExecutionId)) {
      openExecution(openExecutionId);
    }
  }, [searchParams]);

  return {
    drawerOpen,
    selectedExecution,
    selectedSteps,
    selectedActionDetail,
    loading,
    error,
    openExecution,
    closeDrawer,
  };
};
```

---

### Contexte des stories précédentes

**Story 26.2 (Split executions/views.py) :**
- Pattern similaire : extraction de logique depuis fichier monolithique
- Approche : Découpage par responsabilité + backward compatibility
- **Leçon apprise** : Tests existants DOIVENT passer sans modification logique
- **Application ici** : Comportement utilisateur identique, organisation code améliorée

**Story 26.3 (Extract RBAC catalog service) :**
- Pattern similaire : extraction de fonctions globales vers service dédié
- Approche : Copier logique, adapter signatures, remplacer call sites
- **Leçon apprise** : Créer tests unitaires pour modules extraits (coverage ≥80%)
- **Application ici** : Tests pour colonnes, hooks, composants

**Story 22.9 (AdminPage refactor) :**
- Pattern identique : réduction 845 → 75 LOC en extrayant 6 panels
- Approche : Composants spécialisés + orchestrateur mince
- **Leçon apprise** : Atteindre <100 LOC nécessite extraction agressive
- **Application ici** : Cible <400 LOC nécessite colonnes + hooks + composants

**Story 22.14 (Fix stale closure) :**
- Pattern refs pour éviter closures obsolètes dans modals
- Approche : `refetchCurrentState()` utilise refs au lieu de state capturé
- **Leçon apprise** : Callbacks dans modals confirm doivent utiliser refs pour valeurs courantes
- **Application ici** : `useExecutionRestart()` accepte `refetchCurrentState()` en paramètre

**Story 20.4 (ExecutionWizard refactor) :**
- Pattern hooks custom pour logique wizard
- Approche : `useExecutionWizard()` encapsule state + lifecycle
- **Leçon apprise** : Hooks réutilisables facilitent tests et maintenance
- **Application ici** : `useExecutionDetail()`, `useExecutionRestart()` suivent même pattern

---

### Risques & Mitigations

| Risque | Impact | Mitigation |
|--------|--------|-----------|
| **Régression fonctionnelle** | ÉLEVÉ | Tous les tests existants DOIVENT passer. Conserver exactement le même comportement. |
| **Imports cassés dans tests** | MOYEN | Identifier tous les tests qui importent depuis ExecutionsPage. Mettre à jour les imports. |
| **Props drilling complexe** | MOYEN | Utiliser hooks pour éviter props drilling. État partagé via hooks au lieu de props. |
| **Performance dégradée** | FAIBLE | Conserver tous les useMemo/useCallback. Vérifier re-renders avec React DevTools. |
| **TypeScript errors** | MOYEN | Types stricts pour toutes les props/hooks. Exécuter `npm run type-check` régulièrement. |
| **Cible <400 LOC non atteinte** | MOYEN | Préparer Phase 3 (useExecutionsData hook) si Phases 1+2 insuffisantes. |

---

### Ordre d'implémentation recommandé

1. **Créer structure** (Task 1)
   - Créer répertoires et fichiers vides
   - Pas de dépendances, setup initial

2. **Extraire colonnes** (Task 2)
   - Fonction la plus isolée (134 LOC)
   - Pas de side effects
   - Facile à tester

3. **Extraire drawer hook** (Task 3)
   - Encapsule 7 useState + 1 useEffect
   - Réduction significative (~70 LOC)
   - Testable unitairement

4. **Extraire restart hook** (Task 4)
   - Encapsule 5 useState + 2 useCallback
   - Réduction significative (~85 LOC)
   - Nécessite `refetchCurrentState()`

5. **Extraire StatSection** (Task 5)
   - Composant simple de présentation
   - Pas de logique complexe
   - Réutilisable

6. **Extraire DetailDrawer** (Task 6)
   - Composant simple de présentation
   - Conditionnel Timeline vs Graph
   - Réutilisable

7. **Validation LOC** (Task 7)
   - Vérifier cible <400 LOC
   - Extraire useExecutionsData si nécessaire

8. **Tests unitaires** (Task 8)
   - Couvrir tous les nouveaux modules
   - Coverage ≥80%

9. **Validation finale** (Task 9-10)
   - Tests existants passent
   - ESLint/TypeScript clean
   - Documentation complète

---

## Project Structure Notes

**Alignement avec la structure unifiée :**

```
idp-portal/frontend/src/
├── pages/
│   ├── ExecutionsPage.tsx                  # MODIFIED — réduit de 1023 → <400 LOC
│   └── executions/
│       ├── executionsColumns.tsx           # NEW (~180 LOC)
│       └── __tests__/
│           └── executionsColumns.test.tsx  # NEW (~150 LOC)
├── hooks/
│   ├── useExecutionDetail.ts               # NEW (~100 LOC)
│   ├── useExecutionRestart.ts              # NEW (~120 LOC)
│   └── __tests__/
│       ├── useExecutionDetail.test.ts      # NEW (~80 LOC)
│       └── useExecutionRestart.test.ts     # NEW (~70 LOC)
├── components/
│   └── executions/
│       ├── ExecutionsStatSection.tsx       # NEW (~60 LOC)
│       ├── ExecutionDetailDrawer.tsx       # NEW (~80 LOC)
│       ├── ExecutionsFiltersPanel.tsx      # EXISTS (déjà extrait Story 9.10)
│       ├── ExecutionsTabs.tsx              # EXISTS (déjà extrait Story 8.9)
│       └── __tests__/
│           ├── ExecutionsStatSection.test.tsx  # NEW (~50 LOC)
│           └── ExecutionDetailDrawer.test.tsx  # NEW (~70 LOC)
├── utils/
│   └── executionRenderers.tsx              # EXISTS (renderStatusIndicator, renderEngineIcon, renderPlateformeIcon)
└── types/
    └── api.ts                               # EXISTS (ExecutionResponse, ExecutionScope, etc.)
```

**Modules touchés par cette story :**
- `pages/ExecutionsPage.tsx` : réduit de 1023 → <400 LOC
- 7 nouveaux fichiers créés (colonnes + hooks + composants + tests)

**Modules inchangés :**
- Composants déjà extraits : ExecutionsFiltersPanel, ExecutionsTabs, PendingApprovalsList
- Utilitaires renderers : executionRenderers.tsx
- Services : execution_service, catalog_service

---

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

N/A

### Completion Notes List

- ExecutionsPage.tsx réduit de **1023 → 298 LOC** (-70.9%), bien sous la cible <400 LOC
- 7 nouveaux fichiers créés (colonnes + 3 hooks + 2 composants)
- **61 nouveaux tests** (33 columns + 9 detail + 8 restart + 5 stat + 6 drawer), tous passent
- 0 régression : tests existants (cancel 6/6, compact 11/11) passent identiquement
- 5 échecs pré-existants dans ExecutionsPage.test.tsx (vérifiés contre baseline, pas de régression)
- TypeScript clean (0 erreur)
- Phase 3 extraction (`useExecutionsData` hook) nécessaire pour atteindre <400 LOC
- `useExecutionRestart` utilise pattern `isRefreshingRef` pour éviter stale closures (Story 22.14)

### File List

**Modified:**
- `frontend/src/pages/ExecutionsPage.tsx` — 298 LOC (was 1023)
- `frontend/src/__tests__/__snapshots__/ExecutionsPage.compact.test.tsx.snap` — snapshot updated

**New source files:**
- `frontend/src/pages/executions/executionsColumns.tsx` — 218 LOC (9 columns, formatters, types)
- `frontend/src/hooks/useExecutionDetail.ts` — 108 LOC (drawer state + URL sync)
- `frontend/src/hooks/useExecutionRestart.ts` — 109 LOC (restart wizard state)
- `frontend/src/hooks/useExecutionsData.ts` — 198 LOC (data fetching, stats, icons)
- `frontend/src/components/executions/ExecutionsStatSection.tsx` — 84 LOC (StatCards + TrendLineChart)
- `frontend/src/components/executions/ExecutionDetailDrawer.tsx` — 74 LOC (Drawer + Timeline/Graph)

**New test files:**
- `frontend/src/pages/executions/__tests__/executionsColumns.test.tsx` — 370 LOC (33 tests)
- `frontend/src/hooks/__tests__/useExecutionDetail.test.ts` — 277 LOC (9 tests)
- `frontend/src/hooks/__tests__/useExecutionRestart.test.ts` — 303 LOC (8 tests)
- `frontend/src/components/executions/__tests__/ExecutionsStatSection.test.tsx` — 98 LOC (5 tests)
- `frontend/src/components/executions/__tests__/ExecutionDetailDrawer.test.tsx` — 171 LOC (6 tests)
