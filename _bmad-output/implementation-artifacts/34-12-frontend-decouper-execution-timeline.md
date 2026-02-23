# Story 34.12 : Frontend — Découper ExecutionTimeline (god component)

Status: done

<!-- Réf: CODEBASE-REVIEW.md SOLID-FE-1 [CRITICAL] -->

## Story

En tant que mainteneur,
je veux découper `ExecutionTimeline.tsx` (729 lignes, 12+ responsabilités) en hooks et composants dédiés,
afin de rendre le code maintenable, testable et conforme au SRP (Priorité CRITICAL du code review).

## Acceptance Criteria

1. **Given** `ExecutionTimeline.tsx` (729 lignes actuelles)
   **Then** la logique est extraite en trois hooks dédiés :
   - `useExecutionData` — fusion données WebSocket + fallback polling, dérivation `steps`/`execution`/`loading`/`error`/`isPolling`/`lastMessage`
   - `useAutoRemediationState` — machine à états auto-remédiation pilotée par `lastMessage` + reset au changement d'`executionId`
   - `useStepUIState` — état expand/collapse, drawer logs (`logsDrawerStepId`), focus trap sur ouverture

2. **And** cinq sous-composants sont créés dans un dossier `ExecutionTimeline/` :
   - `ExecutionStatusBanners` — les 7 variantes d'Alert (polling, parent corrective, PENDING_APPROVAL, REJECTED, COMPLETED succès, auto-remédiation failed, auto-remédiation en cours)
   - `RemediationPanel` — StructuredErrorCard + skeleton chargement contexte + carte contexte remédiation
   - `TimelineList` — `<div role="list">` + région aria-live + liste des steps
   - `TimelineStepItem` — rendu d'un step (icône statut, bouton expand, détail expand, badge ServiceNow)
   - `StepLogsDrawer` — Drawer Ant Design avec contenu logs (timestamps, erreur, output JSON)

3. **And** `ExecutionTimeline.tsx` devient un orchestrateur pur (< 250 lignes) : utilise les 3 hooks, compose les 5 sous-composants et propage les props/callbacks sans logique propre.

4. **And** tous les tests existants (`ExecutionTimeline.test.tsx`, 1 137 lignes, ~35 tests) passent sans modification — les mocks `useWebSocket`, `useExecutionPolling`, `useRemediationSuggestions` restent au niveau module et couvrent les hooks extraits.

5. **And** `npx tsc --noEmit` retourne 0 erreur TypeScript.

6. **And** les `data-testid` existants sont préservés à l'identique : `polling-mode-alert`, `auto-remediation-failed-alert`, `auto-remediation-progress-card`, `parent-execution-alert`, `remediation-context-card`.

## Tasks / Subtasks

- [x] Task 1 — Extraire `useExecutionData`
  - [x] 1.1 Créer `src/hooks/useExecutionData.ts` : déplacer `FORCE_POLLING`, logique `useWs`/`usePolling`, appels `useWebSocket` + `useExecutionPolling`, dérivation `steps`/`execution`
  - [x] 1.2 Définir l'interface `UseExecutionDataReturn` (voir Dev Notes)
  - [x] 1.3 Supprimer ces variables de `ExecutionTimeline.tsx` et les remplacer par `const { ... } = useExecutionData(...)`

- [x] Task 2 — Extraire `useAutoRemediationState`
  - [x] 2.1 Créer `src/hooks/useAutoRemediationState.ts` : déplacer `autoRemediationState`, `setAutoRemediationState`, les deux `useEffect` (lastMessage + reset executionId), le type inline
  - [x] 2.2 Définir l'interface `AutoRemediationState` et `UseAutoRemediationStateReturn`

- [x] Task 3 — Extraire `useStepUIState`
  - [x] 3.1 Créer `src/hooks/useStepUIState.ts` : déplacer `expandedId`, `logsDrawerStepId`, `logsDrawerContentRef`, `logsDrawerStep` (useMemo), `useEffect` focus trap
  - [x] 3.2 Définir l'interface `UseStepUIStateReturn`

- [x] Task 4 — Créer les sous-composants
  - [x] 4.1 Créer `src/components/execution/ExecutionTimeline/ExecutionStatusBanners.tsx` : les 7 blocs Alert/Card (voir inventaire des bannières)
  - [x] 4.2 Créer `src/components/execution/ExecutionTimeline/RemediationPanel.tsx` : StructuredErrorCard + Skeleton + carte contexte remédiation
  - [x] 4.3 Créer `src/components/execution/ExecutionTimeline/TimelineList.tsx` : `<div role="list">` + région aria-live + `{steps.map(step => <TimelineStepItem .../>)}`
  - [x] 4.4 Créer `src/components/execution/ExecutionTimeline/TimelineStepItem.tsx` : rendu d'un step (icône + expand + badge ServiceNow + "Voir logs détaillés")
  - [x] 4.5 Créer `src/components/execution/ExecutionTimeline/StepLogsDrawer.tsx` : Drawer Ant Design + contenu logs (préserver le `ref` focus trap)
  - [x] 4.6 Créer `src/components/execution/ExecutionTimeline/index.ts` : barrel export de tous les composants

- [x] Task 5 — Refactoriser `ExecutionTimeline.tsx`
  - [x] 5.1 Supprimer tous les useState/useMemo/useEffect/imports remplacés par les hooks et sous-composants
  - [x] 5.2 Composer l'orchestrateur (< 250 lignes) : `useExecutionData`, `useAutoRemediationState`, `useStepUIState`, puis JSX composé uniquement des 5 sous-composants
  - [x] 5.3 Conserver `formatDuration` dans le fichier racine ou le déplacer dans `ExecutionTimeline/utils.ts`

- [x] Task 6 — Tests et régression
  - [x] 6.1 Exécuter `npx vitest run src/components/execution/ExecutionTimeline.test.tsx` — tous les tests doivent passer
  - [x] 6.2 Exécuter `npx tsc --noEmit` — 0 erreur TypeScript
  - [x] 6.3 Vérifier manuellement (ou via test) le flux : démarrage exécution, mise à jour temps réel, bannières, remédiation, ouverture logs

## Dev Notes

### Analyse exhaustive du composant actuel (729 lignes)

**Responsabilités identifiées dans `ExecutionTimeline.tsx` :**

| # | Responsabilité | Lignes | Hook/Composant cible |
|---|---------------|--------|----------------------|
| 1 | WebSocket connection + données | 68–81 | `useExecutionData` |
| 2 | Fallback polling WebSocket | 72–77 | `useExecutionData` |
| 3 | Fusion steps/execution (WS vs polling vs props) | 109–117 | `useExecutionData` |
| 4 | Machine à états auto-remédiation | 84–107, 136–170 | `useAutoRemediationState` |
| 5 | État expand/collapse + drawer | 131–133, 151–155 | `useStepUIState` |
| 6 | Focus trap drawer | 151–155 | `useStepUIState` |
| 7 | Bannière polling mode | 209–219 | `ExecutionStatusBanners` |
| 8 | Bannière parent corrective | 221–239 | `ExecutionStatusBanners` |
| 9 | Bannière PENDING_APPROVAL | 242–257 | `ExecutionStatusBanners` |
| 10 | Bannière REJECTED | 260–287 | `ExecutionStatusBanners` |
| 11 | Bannière COMPLETED succès | 289–319 | `ExecutionStatusBanners` |
| 12 | Bannière auto-remédiation failed | 322–351 | `ExecutionStatusBanners` |
| 13 | Card auto-remédiation en cours | 354–386 | `ExecutionStatusBanners` |
| 14 | StructuredErrorCard (FAILED) | 389–405 | `RemediationPanel` |
| 15 | Skeleton + carte contexte remédiation | 407–480 | `RemediationPanel` |
| 16 | `<div role="list">` + aria-live | 482–494 | `TimelineList` |
| 17 | État vide (workflow child card) | 495–523 | `TimelineList` |
| 18 | Rendu d'un step (boucle + JSX) | 524–661 | `TimelineStepItem` |
| 19 | `<style>` @keyframes pulse | 663–668 | `TimelineStepItem` |
| 20 | Drawer logs détaillés | 672–725 | `StepLogsDrawer` |

---

### Interface `useExecutionData`

```typescript
// src/hooks/useExecutionData.ts
import { useMemo } from 'react';
import { useWebSocket } from './useWebSocket';
import { useExecutionPolling } from './useExecutionPolling';
import type { ExecutionResponse, ExecutionStepResponse } from '../types/api';

const FORCE_POLLING = import.meta.env.VITE_SIMULATE_EXECUTION === 'true';

export interface UseExecutionDataProps {
  executionId?: number | null;
  executionProp?: ExecutionResponse | null;
  stepsProp?: ExecutionStepResponse[];
  mode?: 'realtime' | 'historical';
}

export interface UseExecutionDataReturn {
  steps: ExecutionStepResponse[];
  execution: ExecutionResponse | null;
  loading: boolean;
  error: string | null;
  isPolling: boolean;
  lastMessage: ReturnType<typeof useWebSocket>['lastMessage'];
}

export function useExecutionData({
  executionId, executionProp, stepsProp, mode,
}: UseExecutionDataProps): UseExecutionDataReturn {
  const useRealtime = mode === 'realtime' && executionId != null;
  const useWs = useRealtime && !FORCE_POLLING;
  const { steps: wsSteps, execution: wsExecution, loading: wsLoading, error: wsError, lastMessage } = useWebSocket(useWs ? executionId : null);
  const wsHasError = useWs && wsError != null;
  const usePolling = useRealtime && (FORCE_POLLING || wsHasError);
  const { execution: pollExecution, steps: pollSteps, isPolling, error: pollError } = useExecutionPolling({
    executionId: executionId ?? null,
    enabled: usePolling,
    interval: 2500,
  });
  const loading = useWs ? wsLoading : false;
  const error = useWs && !wsHasError ? wsError : (pollError?.message ?? null);
  const steps = useMemo(() => {
    if (usePolling) return pollSteps;
    if (useWs) return wsSteps;
    return stepsProp ?? [];
  }, [usePolling, useWs, pollSteps, wsSteps, stepsProp]);
  const execution = usePolling ? pollExecution : (useWs ? wsExecution : executionProp ?? null);
  return { steps, execution, loading, error, isPolling, lastMessage };
}
```

---

### Interface `useAutoRemediationState`

```typescript
// src/hooks/useAutoRemediationState.ts
import { useState, useEffect, useRef } from 'react';

export interface AutoRemediationState {
  inProgress: boolean;
  failed: boolean;
  childExecutionId: number | null;
  correctiveActionName: string | null;
  failureMessage: string | null;
}

const INITIAL_STATE: AutoRemediationState = {
  inProgress: false, failed: false,
  childExecutionId: null, correctiveActionName: null, failureMessage: null,
};

export function useAutoRemediationState(
  lastMessage: { type: string; data?: unknown } | null | undefined,
  executionId?: number | null,
): AutoRemediationState {
  const [state, setState] = useState<AutoRemediationState>(INITIAL_STATE);
  const prevExecutionIdRef = useRef(executionId);

  useEffect(() => {
    if (!lastMessage) return;
    if (lastMessage.type === 'auto_remediation_started') {
      const data = lastMessage.data as { child_execution_id?: number; corrective_action_name?: string } | undefined;
      setState(() => ({
        inProgress: true, failed: false,
        childExecutionId: data?.child_execution_id ?? null,
        correctiveActionName: data?.corrective_action_name ?? null,
        failureMessage: null,
      }));
    } else if (lastMessage.type === 'auto_remediation_failed') {
      const data = lastMessage.data as { child_execution_id?: number; message?: string } | undefined;
      setState((prev) => ({
        ...prev, inProgress: false, failed: true,
        childExecutionId: data?.child_execution_id ?? prev.childExecutionId,
        failureMessage: data?.message ?? 'Tentative de correction automatique échouée',
      }));
    }
  }, [lastMessage]);

  useEffect(() => {
    if (prevExecutionIdRef.current !== executionId) {
      setState(INITIAL_STATE);
      prevExecutionIdRef.current = executionId;
    }
  }, [executionId]);

  return state;
}
```

---

### Interface `useStepUIState`

```typescript
// src/hooks/useStepUIState.ts
import { useState, useRef, useEffect, useMemo } from 'react';
import type { ExecutionStepResponse } from '../types/api';

export interface UseStepUIStateReturn {
  expandedId: number | null;
  setExpandedId: (id: number | null) => void;
  logsDrawerStepId: number | null;
  setLogsDrawerStepId: (id: number | null) => void;
  logsDrawerStep: ExecutionStepResponse | null;
  logsDrawerContentRef: React.RefObject<HTMLDivElement>;
}

export function useStepUIState(steps: ExecutionStepResponse[]): UseStepUIStateReturn {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [logsDrawerStepId, setLogsDrawerStepId] = useState<number | null>(null);
  const logsDrawerContentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (logsDrawerStepId != null && logsDrawerContentRef.current) {
      logsDrawerContentRef.current.focus();
    }
  }, [logsDrawerStepId]);

  const logsDrawerStep = useMemo(
    () => (logsDrawerStepId != null ? steps.find((s) => s.id === logsDrawerStepId) : null) ?? null,
    [steps, logsDrawerStepId],
  );

  return { expandedId, setExpandedId, logsDrawerStepId, setLogsDrawerStepId, logsDrawerStep, logsDrawerContentRef };
}
```

---

### Props des sous-composants

#### `ExecutionStatusBanners`
```typescript
interface ExecutionStatusBannersProps {
  execution: ExecutionResponse | null;
  isPolling: boolean;
  autoRemediationState: AutoRemediationState;
}
```

#### `RemediationPanel`
```typescript
interface RemediationPanelProps {
  execution: ExecutionResponse | null;
  failedStep: ExecutionStepResponse | undefined;
  executionId?: number | null;
  onRetry?: () => void;
  onContact?: () => void;
  onViewLogs: (stepId: number) => void;
  errorCardVariant?: 'default' | 'business';
  remediationSuggestions?: RemediationSuggestion[] | null;
  suggestionsLoading: boolean;
  onSuggestionClick?: (s: RemediationSuggestion) => void;
  remediationContext: RemediationContextType | null;  // type depuis useRemediationContext
  remediationLoading: boolean;
}
```

#### `TimelineList`
```typescript
interface TimelineListProps {
  steps: ExecutionStepResponse[];
  execution: ExecutionResponse | null;
  embedInWorkflowStepDrawer: boolean;
  statusAnnouncement: string;
  expandedId: number | null;
  onToggleExpand: (id: number) => void;
  onOpenLogs: (id: number) => void;
}
```

#### `TimelineStepItem`
```typescript
interface TimelineStepItemProps {
  step: ExecutionStepResponse;
  isExpanded: boolean;
  isLast: boolean;
  onToggleExpand: () => void;
  onOpenLogs: () => void;
}
```

#### `StepLogsDrawer`
```typescript
interface StepLogsDrawerProps {
  step: ExecutionStepResponse | null;
  open: boolean;
  onClose: () => void;
  contentRef: React.RefObject<HTMLDivElement>;
}
```

---

### `ExecutionTimeline.tsx` cible (orchestrateur pur)

```typescript
export function ExecutionTimeline({ executionId, execution: executionProp, steps: stepsProp, mode = 'realtime', onRetry, onContact, errorCardVariant = 'default', onSuggestionClick, embedInWorkflowStepDrawer = false }: ExecutionTimelineProps) {
  const { steps, execution, loading, error, isPolling, lastMessage } = useExecutionData({ executionId, executionProp, stepsProp, mode });
  const autoRemediationState = useAutoRemediationState(lastMessage, executionId);
  const { expandedId, setExpandedId, logsDrawerStepId, setLogsDrawerStepId, logsDrawerStep, logsDrawerContentRef } = useStepUIState(steps);

  const { suggestions: remediationSuggestions, loading: suggestionsLoading } = useRemediationSuggestions(executionId ?? null, execution?.status ?? null);
  const { context: remediationContext, loading: remediationLoading } = useRemediationContext(executionId ?? null, execution?.status ?? null);

  const failedStep = useMemo(() => steps.find((s) => s.status === 'FAILED'), [steps]);
  const statusAnnouncement = useMemo(() => { /* logique actuelle */ }, [steps]);

  if (useRealtime && loading && steps.length === 0) return <LoadingSpinner />;
  if (error) return <ErrorDisplay error={error} />;

  return (
    <>
      <ExecutionStatusBanners execution={execution} isPolling={isPolling} autoRemediationState={autoRemediationState} />
      <RemediationPanel execution={execution} failedStep={failedStep} executionId={executionId} onRetry={onRetry} onContact={onContact} onViewLogs={setLogsDrawerStepId} errorCardVariant={errorCardVariant} remediationSuggestions={remediationSuggestions} suggestionsLoading={suggestionsLoading} onSuggestionClick={onSuggestionClick} remediationContext={remediationContext} remediationLoading={remediationLoading} />
      <TimelineList steps={steps} execution={execution} embedInWorkflowStepDrawer={embedInWorkflowStepDrawer} statusAnnouncement={statusAnnouncement} expandedId={expandedId} onToggleExpand={(id) => setExpandedId(expandedId === id ? null : id)} onOpenLogs={setLogsDrawerStepId} />
      <StepLogsDrawer step={logsDrawerStep} open={logsDrawerStepId != null} onClose={() => setLogsDrawerStepId(null)} contentRef={logsDrawerContentRef} />
    </>
  );
}
```

> **Note :** `useRealtime` doit être recalculé ou exposé par `useExecutionData`. Option simple : exposer `useRealtime: boolean` dans `UseExecutionDataReturn`.

---

### Structure cible des fichiers

```
idp-portal/frontend/src/
  hooks/
    useExecutionData.ts           ← CRÉÉ (~55 lignes)
    useAutoRemediationState.ts    ← CRÉÉ (~45 lignes)
    useStepUIState.ts             ← CRÉÉ (~35 lignes)
  components/execution/
    ExecutionTimeline.tsx         ← MODIFIÉ (729 → ~200 lignes, orchestrateur)
    ExecutionTimeline/            ← CRÉÉ (dossier)
      ExecutionStatusBanners.tsx  ← CRÉÉ (~130 lignes : 7 Alert/Card)
      RemediationPanel.tsx        ← CRÉÉ (~110 lignes : StructuredErrorCard + contexte)
      TimelineList.tsx            ← CRÉÉ (~80 lignes : list + aria-live + empty state)
      TimelineStepItem.tsx        ← CRÉÉ (~130 lignes : step + expand + ServiceNow)
      StepLogsDrawer.tsx          ← CRÉÉ (~60 lignes : Drawer + logs)
      index.ts                    ← CRÉÉ (barrel export)
```

---

### Points d'attention critiques

**1. Mocks de tests — ne pas casser l'isolation**

Les 35 tests dans `ExecutionTimeline.test.tsx` mockent `useWebSocket`, `useExecutionPolling`, `useRemediationSuggestions` au niveau module (`vi.mock('../../hooks/useWebSocket', ...)`). Ces mocks couvrent automatiquement les appels au sein de `useExecutionData` car c'est le même module résolu. **Ne pas déplacer** `useWebSocket`/`useExecutionPolling` dans un wrapper qui briserait le chemin de mock.

**2. `useRemediationContext` — pas mocké dans les tests**

`useRemediationContext` est importé (l.15 original) mais N'EST PAS mocké dans le fichier de test. Il retourne `{ context: null, loading: false }` par défaut (comportement du vrai hook quand le statut n'est pas FAILED). Après extraction dans `RemediationPanel`, si un test commence à échouer sur ce hook, ajouter :
```typescript
vi.mock('../../hooks/useRemediationContext', () => ({
  useRemediationContext: vi.fn(() => ({ context: null, loading: false })),
}));
```

**3. `FORCE_POLLING` — variable d'environnement de build**

`const FORCE_POLLING = import.meta.env.VITE_SIMULATE_EXECUTION === 'true';` doit être défini dans `useExecutionData.ts` (niveau module), pas dans le composant. Vitesse de tests : les tests n'utilisent pas ce flag (toujours `false` en test).

**4. `formatDuration` — utilitaire pur**

La fonction `formatDuration` (l.25-34) peut être déplacée dans `ExecutionTimeline/utils.ts` et importée par `TimelineStepItem` et `StepLogsDrawer`. Elle est déjà pure (pas de dépendance externe). Alternative : rester dans `ExecutionTimeline.tsx` et importer depuis le composant parent — moins propre.

**5. `@keyframes pulse` — style inline dans `<style>` tag**

Le bloc `<style>{`@keyframes pulse { ... }`}</style>` (l.663-668) est référencé par `TimelineStepItem` via `animation: step.status === 'RUNNING' ? 'pulse 1.5s ease-in-out infinite' : undefined`. Options :
- Déplacer le `<style>` tag dans `TimelineStepItem.tsx` — colocalisé avec l'usage
- Ou le garder dans `TimelineList.tsx` qui englobe les items

Recommandation : déplacer dans `TimelineStepItem.tsx`.

**6. `useMemo` pour `statusAnnouncement` et `failedStep`**

Ces deux `useMemo` dépendent de `steps`. Ils restent dans `ExecutionTimeline.tsx` pour alimenter respectivement `TimelineList` et `RemediationPanel`. Pas de déplacement dans les hooks.

**7. `useRealtime` — flag à exposer**

Le flag `const useRealtime = mode === 'realtime' && executionId != null;` contrôle l'affichage du spinner et de l'erreur dans `ExecutionTimeline`. Soit on l'expose dans `UseExecutionDataReturn`, soit on recalcule dans le composant parent (simple : `mode === 'realtime' && executionId != null`).

**8. Props `onViewLogs` dans `StructuredErrorCard`**

Dans l'actuel : `onViewLogs={() => setLogsDrawerStepId(failedStep.id)}`. Après extraction, `RemediationPanel` reçoit `onViewLogs: (stepId: number) => void` et l'appelle avec `failedStep.id`. `StepLogsDrawer` n'est plus déclenché depuis `RemediationPanel` directement — il est géré par `ExecutionTimeline` qui gère `logsDrawerStepId`.

---

### Précédents à reproduire

| Précédent | Pattern | Référence |
|-----------|---------|-----------|
| Story 34-11 — `useAuditFilters` | Hook extrait + composants AuditTable/AuditEntryDrawer | `src/hooks/useAuditFilters.ts` |
| Story 34-10 — `useCatalogState` | Hook extrait CatalogPage (601→267 lignes), interface typée | `src/hooks/useCatalogState.ts` |
| Story 26-4 — `useExecutionsData` | Double hook ExecutionsPage (1023→298 lignes) | `src/hooks/` |
| Story 33-5 — `ActionForm`/`ActionWizard` | Découpage composants React, props claires | commit `a0169fc` |

**Consulter en priorité** : `src/hooks/useAuditFilters.ts` (Story 34-11, pattern direct) et `src/components/audit/AuditTable.tsx` (composant extrait avec props typées).

---

### Intelligence git (commits récents)

```
789a14b feat(34-11): extraire useAuditFilters + AuditTable + AuditEntryDrawer depuis AuditPage (SOLID-FE-3)
92a2da8 feat(34-10): extraire useCatalogState depuis CatalogPage (SOLID-FE-2)
a0169fc feat(34-9): éliminer prop drilling variant/isBusinessProfile et extraire SortableStepCard (SOLID-FE-6, SOLID-FE-8)
```

**Patterns établis :**
- Hooks exportent une interface typée `UseXxxReturn`
- Composants extraits dans des sous-dossiers dédiés
- `vi.mock()` au niveau module reste suffisant pour couvrir les hooks extraits
- `npx tsc --noEmit` est le critère de validation TypeScript

---

### Project Structure Notes

- `src/hooks/useExecutionData.ts` : **CRÉER** — extraire logique WS + polling
- `src/hooks/useAutoRemediationState.ts` : **CRÉER** — machine à états auto-remédiation
- `src/hooks/useStepUIState.ts` : **CRÉER** — état expand/drawer/focus
- `src/components/execution/ExecutionTimeline.tsx` : **MODIFIER** (729 → ~200 lignes)
- `src/components/execution/ExecutionTimeline/ExecutionStatusBanners.tsx` : **CRÉER**
- `src/components/execution/ExecutionTimeline/RemediationPanel.tsx` : **CRÉER**
- `src/components/execution/ExecutionTimeline/TimelineList.tsx` : **CRÉER**
- `src/components/execution/ExecutionTimeline/TimelineStepItem.tsx` : **CRÉER**
- `src/components/execution/ExecutionTimeline/StepLogsDrawer.tsx` : **CRÉER**
- `src/components/execution/ExecutionTimeline/index.ts` : **CRÉER** (barrel)

**Aucun changement backend. Aucune migration DB. Impact purement frontend.**

### References

- [Source: idp-portal/frontend/src/components/execution/ExecutionTimeline.tsx] — fichier source complet, 729 lignes — analyse exhaustive ci-dessus
- [Source: idp-portal/frontend/src/components/execution/ExecutionTimeline.test.tsx] — 35 tests à préserver
- [Source: idp-portal/frontend/src/hooks/useAuditFilters.ts] — patron de référence direct (Story 34-11)
- [Source: idp-portal/frontend/src/hooks/useCatalogState.ts] — patron de référence (Story 34-10)
- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-FE-1] — God component critique, priorité CRITICAL
- [Source: _bmad-output/planning-artifacts/epic-34-codebase-review-restant-fev-2026.md#34.12] — priorité Critique, SOLID-FE-1
- [Source: _bmad-output/implementation-artifacts/34-11-frontend-use-audit-filters-composants-audit-page.md] — story précédente, patterns détaillés

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- ✅ `useExecutionData` extrait (63 lignes) : FORCE_POLLING, WebSocket + polling fallback, dérivation steps/execution/useRealtime
- ✅ `useAutoRemediationState` extrait (60 lignes) : machine à états auto-remédiation + reset executionId
- ✅ `useStepUIState` extrait (38 lignes) : expandedId, logsDrawerStepId, focus trap
- ✅ 5 sous-composants créés dans `ExecutionTimeline/` : ExecutionStatusBanners, RemediationPanel, TimelineList, TimelineStepItem, StepLogsDrawer + barrel index.ts
- ✅ `ExecutionTimeline.tsx` réduit de 729 → 130 lignes (orchestrateur pur)
- ✅ 34/34 tests passent sans modification du fichier de test
- ✅ `npx tsc --noEmit` : 0 erreur TypeScript
- ✅ `data-testid` existants préservés : polling-mode-alert, auto-remediation-failed-alert, auto-remediation-progress-card, parent-execution-alert, remediation-context-card
- ✅ Mocks vi.mock() au niveau module restent valides (useWebSocket, useExecutionPolling couverts via useExecutionData)

### File List

- `idp-portal/frontend/src/hooks/useExecutionData.ts` (CRÉÉ)
- `idp-portal/frontend/src/hooks/useAutoRemediationState.ts` (CRÉÉ)
- `idp-portal/frontend/src/hooks/useStepUIState.ts` (MODIFIÉ : commentaire focus trap corrigé)
- `idp-portal/frontend/src/components/execution/ExecutionTimeline.tsx` (MODIFIÉ : 729 → 130 lignes, prop formatDuration supprimée)
- `idp-portal/frontend/src/components/execution/ExecutionTimeline/ExecutionStatusBanners.tsx` (CRÉÉ, code-review: import direct formatDuration, type steps→ExecutionStepResponse[])
- `idp-portal/frontend/src/components/execution/ExecutionTimeline/RemediationPanel.tsx` (CRÉÉ)
- `idp-portal/frontend/src/components/execution/ExecutionTimeline/TimelineList.tsx` (CRÉÉ, code-review: import direct formatDuration, <style> pulse hoisted)
- `idp-portal/frontend/src/components/execution/ExecutionTimeline/TimelineStepItem.tsx` (CRÉÉ, code-review: import direct formatDuration, <style> pulse retiré)
- `idp-portal/frontend/src/components/execution/ExecutionTimeline/StepLogsDrawer.tsx` (CRÉÉ)
- `idp-portal/frontend/src/components/execution/ExecutionTimeline/index.ts` (CRÉÉ, code-review: export formatDuration ajouté)
- `idp-portal/frontend/src/components/execution/ExecutionTimeline/utils.ts` (CRÉÉ : formatDuration extraite)

## Change Log

| Date | Change |
|------|--------|
| 2026-02-22 | Story créée — SOLID-FE-1 : découpage ExecutionTimeline (729 lignes, 20 responsabilités). Analyse exhaustive : inventaire complet des responsabilités, interfaces complètes pour 3 hooks + 5 composants, props typées, points d'attention tests, structure cible fichiers. |
| 2026-02-23 | Implémentation complète — 3 hooks extraits, 5 sous-composants créés, orchestrateur 130 lignes, 34/34 tests passent, 0 erreur TypeScript. |
| 2026-02-23 | Code review — 2 MEDIUM + 3 LOW fixes auto-appliqués : (M1) `formatDuration` extraite dans `utils.ts`, prop drilling supprimé des 3 composants ; (M2) `<style>@keyframes pulse</style>` déplacé dans `TimelineList` (rendu une fois vs N fois) ; (L1) type `steps` de `ExecutionStatusBanners` → `ExecutionStepResponse[]` (suppression champs inutilisés) ; (L2) variable `failedStep` renommée `currentFailedStep` dans `statusAnnouncement` useMemo ; (L3) commentaire focus trap corrigé dans `useStepUIState`. 34/34 tests passent, 0 erreur TypeScript. |
