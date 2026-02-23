# Story 34.13 : Frontend — DIP services, props steps, useExecutionWizardState

Status: done

<!-- Réf: CODEBASE-REVIEW.md SOLID-FE-4, SOLID-FE-7, SOLID-FE-9 -->

## Story

En tant que mainteneur,
je veux réduire le couplage direct aux services dans les composants (DIP), alléger les props des steps du wizard (inventory via contexte), et extraire la logique de coordination de ExecutionWizard (7 useEffect) dans un hook dédié,
afin d'améliorer la testabilité et la maintenabilité du wizard d'exécution.

## Contexte

- **SOLID-FE-4** : `ExecutionWizard.tsx` importe directement `fetchCatalogActionById` (catalog_service) et `fetchInventoryItems` (execution_service) — 2 violations DIP. Un hook `useWorkflowStepActions` doit encapsuler `fetchCatalogActionById`. Le hook `useTargetInventory` (déjà créé en Story 17.2) encapsule déjà `fetchInventoryItems` mais n'est **pas utilisé** par ExecutionWizard.
- **SOLID-FE-7** : Les steps reçoivent trop de props par prop drilling : `TargetSelectionStep` (19 props), `ParametersFormStep` (15 props, dont 1 inutilisée `action`), `ConfirmationStep` (15 props). Un `WizardExecutionContext` fournit les données partagées (inventory, valeurs dérivées) directement aux steps.
- **SOLID-FE-9** : `ExecutionWizard.tsx` contient 7 `useEffect` + 2 `// eslint-disable-next-line react-hooks/exhaustive-deps`. La logique est extraite dans `useExecutionWizardState`. Les hooks `useTargetInventory` et `useWizardState` (déjà créés en Story 17.2) sont intégrés dans ce hook agrégateur.

## Découverte critique

> **`useTargetInventory` et `useWizardState` existent déjà** (`src/hooks/`) mais **ne sont PAS utilisés** par `ExecutionWizard.tsx`. Le composant a ses propres implémentations en double (inline state + useEffects). Cette story doit finaliser l'intégration de ces hooks.

## Acceptance Criteria

1. **Given** un sous-ensemble de composants cibles (ExecutionWizard, et ses services directs)
   **When** ils ont besoin d'appeler un service (catalog, execution)
   **Then** les appels passent via des hooks :
   - `useWorkflowStepActions` (CRÉER) encapsule `fetchCatalogActionById` pour charger les actions des steps workflow
   - `useTargetInventory` (DÉJÀ EXISTANT — l'intégrer dans `useExecutionWizardState`) encapsule `fetchInventoryItems`
   - `ExecutionWizard.tsx` ne contient plus aucun import direct de `fetchCatalogActionById` ni `fetchInventoryItems`

2. **And** les steps du ExecutionWizard consomment les données partagées via `WizardExecutionContext` (CRÉER) au lieu de props :
   - `TargetSelectionStep` : de 19 props → ≤12 props (objectif exact : 12)
   - `ParametersFormStep` : de 15 props → ≤11 props (objectif exact : 10, dont suppression de la prop `action` inutilisée)
   - `ConfirmationStep` : de 15 props → ≤12 props (objectif exact : 12)
   - Le contexte expose : `environmentsCache`, `inventoryData`, `inventoryWarnings`, `loadingInventory`, `derivedEnvironment`, `currentImpact`, `hasMixedEnvironments`, `resolvedPatternTargets`, `patternResolving`, `selectedServerNames`

3. **And** la logique de coordination de `ExecutionWizard` est extraite dans `useExecutionWizardState` (CRÉER) :
   - Les 7 `useEffect` + tout le state sont dans le hook
   - Le hook utilise `useTargetInventory`, `useWorkflowStepActions`, `usePatternResolver`, `useExecutionSubmit`, `useSchedulingValidation` en interne
   - `ExecutionWizard.tsx` appelle `useExecutionWizardState()` et fournit `WizardExecutionContext.Provider` aux steps
   - Les `// eslint-disable-next-line react-hooks/exhaustive-deps` sont soit supprimés (si deps corrigées) soit documentés avec justification `// intentional:`

4. **And** les tests existants passent sans modification des fichiers de test (2441 lignes au total sur 4 fichiers). Les mocks `vi.mock('../../services/execution_service', ...)` et `vi.mock('../../services/catalog_service', ...)` couvrent automatiquement les appels via les hooks.

5. **And** `npx tsc --noEmit` retourne 0 erreur TypeScript.

## Tasks / Subtasks

- [x] Task 1 — DIP services (SOLID-FE-4)
  - [x] 1.1 Créer `src/hooks/useWorkflowStepActions.ts` : encapsule le chargement des `CatalogActionDetail` par id pour les steps workflow (remplace le useEffect inline de ExecutionWizard)
  - [x] 1.2 Supprimer les imports directs `fetchCatalogActionById` et `fetchInventoryItems` de `ExecutionWizard.tsx`
  - [x] 1.3 Vérifier que les 4 fichiers de tests existants passent (les mocks module-level couvrent les hooks)

- [x] Task 2 — WizardExecutionContext (SOLID-FE-7)
  - [x] 2.1 Créer `src/contexts/WizardExecutionContext.tsx` avec `WizardExecutionContextValue` et `useWizardExecutionContext()`
  - [x] 2.2 Modifier `TargetSelectionStep.tsx` : retirer 7 props (via contexte), interface réduite à 12 props
  - [x] 2.3 Modifier `ParametersFormStep.tsx` : retirer 5 props (4 inventory via contexte + 1 `action` inutilisée), interface réduite à 10 props
  - [x] 2.4 Modifier `ConfirmationStep.tsx` : retirer 3 props (via contexte), interface réduite à 12 props

- [x] Task 3 — useExecutionWizardState (SOLID-FE-9)
  - [x] 3.1 Créer `src/hooks/useExecutionWizardState.ts` : agréger `useTargetInventory`, `useWorkflowStepActions`, `usePatternResolver`, `useExecutionSubmit`, `useSchedulingValidation`, état cible/paramètres, 4 useEffect, handlers (handleNext, handlePrev, handleSubmit, handleSubmitScheduled, handleKeyDown), construction de `wizardCtxValue`
  - [x] 3.2 Réviser les 2 `eslint-disable` : eslint-disable workflow actions documenté `// intentional:` dans useWorkflowStepActions ; eslint-disable inventory disparaît de ExecutionWizard (resté dans useTargetInventory)
  - [x] 3.3 Modifier `ExecutionWizard.tsx` : appeler `useExecutionWizardState()`, fournir `WizardExecutionContextProvider`, retirer tout state/effet inline et imports services directs, garder uniquement le JSX de composition (Modal + Steps + steps + Footer)

- [x] Task 4 — Tests et validation
  - [x] 4.1 Exécuter les 4 fichiers de tests ExecutionWizard — 77/77 tests passent sans modification
  - [x] 4.2 `npx tsc --noEmit` — 0 erreur TypeScript
  - [x] 4.3 Vérifier flux complet : ouverture wizard, étape 1 (cibles), étape 2 (params), étape 3 (confirmation + exécution)

## Dev Notes

### Analyse exhaustive de l'état actuel

#### ExecutionWizard.tsx (641 lignes) — violations identifiées

| # | Violation | Localisation | Solution |
|---|-----------|--------------|----------|
| 1 | Import direct `fetchCatalogActionById` | l.33 | → `useWorkflowStepActions` |
| 2 | Import direct `fetchInventoryItems` | l.34 | → `useTargetInventory` (déjà existant) |
| 3 | State + useEffect "Load workflow step actions" | l.165-295 | → `useWorkflowStepActions` |
| 4 | State + useEffect "Load environments" | l.174-326 | → `useTargetInventory` |
| 5 | State + useEffect "Load inventory data" | l.174-371 | → `useTargetInventory` |
| 6 | useEffect "Reset state" | l.239-275 | → `useExecutionWizardState` |
| 7 | useEffect "Validate workflow step params" | l.298-314 | → `useExecutionWizardState` |
| 8 | useEffect "Focus management" | l.374 | → `useExecutionWizardState` |
| 9 | useEffect "Re-apply form values" | l.377-382 | → `useExecutionWizardState` |
| 10 | `eslint-disable` deps workflow actions | l.294 | Documenter `// intentional:` |
| 11 | `eslint-disable` deps inventory | l.370 | Disparaît (dans useTargetInventory déjà) |
| 12 | Prop drilling 19 props → TargetSelectionStep | l.573-584 | → contexte (7 props) |
| 13 | Prop drilling 15 props → ParametersFormStep | l.587-595 | → contexte (4 props) + suppr. 1 inutilisée |
| 14 | Prop drilling 15 props → ConfirmationStep | l.598-606 | → contexte (3 props) |

#### Comptage précis des props actuelles

**TargetSelectionStep** (19 props) → **cible 12** (retirer 7 via contexte) :

| Prop | Destination |
|------|-------------|
| action | GARDER |
| allowedEnvironments | GARDER |
| selectedTargets | GARDER |
| onTargetsChange | GARDER |
| targetInputMode | GARDER |
| onTargetInputModeChange | GARDER |
| targetPattern | GARDER |
| onTargetPatternChange | GARDER |
| manualTargetInput | GARDER |
| onManualTargetInputChange | GARDER |
| selectedEnvironment | GARDER |
| onEnvironmentChange | GARDER |
| derivedEnvironment | → CONTEXTE |
| hasMixedEnvironments | → CONTEXTE |
| currentImpact | → CONTEXTE |
| environmentsCache | → CONTEXTE |
| inventoryWarnings | → CONTEXTE |
| resolvedPatternTargets | → CONTEXTE |
| patternResolving | → CONTEXTE |

**ParametersFormStep** (15 props) → **cible 10** (retirer 4 via contexte + 1 inutilisée) :

| Prop | Destination |
|------|-------------|
| form | GARDER |
| action | SUPPRIMER (non destructuré, inutilisé dans le composant) |
| parameterFields | GARDER |
| parameters | GARDER |
| onParametersChange | GARDER |
| isWorkflow | GARDER |
| workflowSteps | GARDER |
| workflowStepActions | GARDER |
| loadingWorkflowStepActions | GARDER |
| workflowStepActionsError | GARDER |
| workflowValidationSummary | GARDER |
| inventoryData | → CONTEXTE |
| inventoryWarnings | → CONTEXTE |
| loadingInventory | → CONTEXTE |
| selectedServerNames | → CONTEXTE |

**ConfirmationStep** (15 props) → **cible 12** (retirer 3 via contexte) :

| Prop | Destination |
|------|-------------|
| action | GARDER |
| selectedTargets | GARDER |
| derivedEnvironment | → CONTEXTE |
| currentImpact | → CONTEXTE |
| parameters | GARDER |
| submitError | GARDER |
| environmentsCache | → CONTEXTE |
| isScheduling | GARDER |
| scheduling | GARDER |
| onSchedulingChange | GARDER |
| schedulingError | GARDER |
| submitting | GARDER |
| schedulingValidation | GARDER |
| pageMeEnabled | GARDER |
| onPageMeChange | GARDER |

---

### Hook `useWorkflowStepActions` (CRÉER)

```typescript
// src/hooks/useWorkflowStepActions.ts
import { useEffect, useState } from 'react';
import { fetchCatalogActionById } from '../services/catalog_service';
import type { CatalogActionDetail } from '../services/catalog_service';

export interface UseWorkflowStepActionsOptions {
  open: boolean;
  actionId?: number;
  isWorkflow: boolean;
  currentStep: number;
  workflowSteps: Array<{ order: number; name: string | null; referenced_action_id: number }>;
}

export interface UseWorkflowStepActionsReturn {
  workflowStepActions: Record<number, CatalogActionDetail>;
  loadingWorkflowStepActions: boolean;
  workflowStepActionsError: string | null;
}

export function useWorkflowStepActions({
  open,
  actionId,
  isWorkflow,
  currentStep,
  workflowSteps,
}: UseWorkflowStepActionsOptions): UseWorkflowStepActionsReturn {
  const [workflowStepActions, setWorkflowStepActions] = useState<Record<number, CatalogActionDetail>>({});
  const [loadingWorkflowStepActions, setLoadingWorkflowStepActions] = useState(false);
  const [workflowStepActionsError, setWorkflowStepActionsError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !isWorkflow || currentStep !== 1) return;
    if (!workflowSteps || workflowSteps.length === 0) return;
    const referencedIds = Array.from(
      new Set(
        workflowSteps
          .map((s) => s.referenced_action_id)
          .filter((id): id is number => typeof id === 'number' && Number.isFinite(id))
      )
    );
    if (referencedIds.length === 0) return;

    let cancelled = false;
    setLoadingWorkflowStepActions(true);
    setWorkflowStepActionsError(null);

    Promise.all(
      referencedIds.map(async (id) => {
        if (workflowStepActions[id]) return workflowStepActions[id];
        const res = await fetchCatalogActionById(id);
        return res.data;
      })
    )
      .then((actions) => {
        if (!cancelled) {
          const map = { ...workflowStepActions };
          actions.forEach((a) => { map[a.id] = a; });
          setWorkflowStepActions(map);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setWorkflowStepActionsError(
            err instanceof Error ? err.message : 'Erreur lors du chargement des actions du workflow'
          );
        }
      })
      .finally(() => { if (!cancelled) setLoadingWorkflowStepActions(false); });

    return () => { cancelled = true; };
    // intentional: workflowStepActions excluded — read for cache check, written by this effect (avoids infinite loop)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, actionId, isWorkflow, currentStep, workflowSteps]);

  return { workflowStepActions, loadingWorkflowStepActions, workflowStepActionsError };
}
```

> **Note test** : `vi.mock('../../services/catalog_service', () => ({ fetchCatalogActionById: vi.fn() }))` dans `ExecutionWizard.test.tsx` couvre ce hook automatiquement via résolution module.

---

### Contexte `WizardExecutionContext` (CRÉER)

```typescript
// src/contexts/WizardExecutionContext.tsx
import { createContext, useContext } from 'react';
import type { InventoryItem, ExecutionEnvironment, ImpactLevel } from '../types/api';

export interface WizardExecutionContextValue {
  // Inventory (TargetSelectionStep + ParametersFormStep + ConfirmationStep)
  environmentsCache: InventoryItem[] | null;
  inventoryData: Record<string, InventoryItem[]>;
  inventoryWarnings: Record<string, boolean>;
  loadingInventory: boolean;
  // Derived from target state (TargetSelectionStep + ConfirmationStep)
  derivedEnvironment: ExecutionEnvironment | null;
  currentImpact: ImpactLevel | null;
  hasMixedEnvironments: boolean;
  // Pattern resolution (TargetSelectionStep)
  resolvedPatternTargets: Array<{ name: string; environment: string }>;
  patternResolving: boolean;
  // Server names for inventory filtering (ParametersFormStep)
  selectedServerNames: string[];
}

const WizardExecutionContext = createContext<WizardExecutionContextValue | null>(null);

export function useWizardExecutionContext(): WizardExecutionContextValue {
  const ctx = useContext(WizardExecutionContext);
  if (!ctx) throw new Error('useWizardExecutionContext must be used within WizardExecutionContext.Provider');
  return ctx;
}

export const WizardExecutionContextProvider = WizardExecutionContext.Provider;
```

> **Intégration dans ExecutionWizard** : le composant fournit le contexte en enveloppant son JSX dans `<WizardExecutionContextProvider value={wizardCtxValue}>`. Les tests ne nécessitent pas de setup supplémentaire car ils rendent `<ExecutionWizard ...>` qui fournit le Provider en interne.

---

### Hook `useExecutionWizardState` (CRÉER)

```typescript
// src/hooks/useExecutionWizardState.ts
// Agréger toute la logique de ExecutionWizard

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Form } from 'antd';
import { App } from 'antd';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import type { CatalogActionDetail } from '../services/catalog_service';
import type { ExecutionEnvironment, ImpactLevel, RecurringPatternRequest } from '../types/api';
import type { WizardInitialParams } from '../types/wizard';
import type { Target } from '../components/catalog/TargetSelector';
import { extractParameterFields } from './useDynamicForm';
import { usePatternResolver } from './usePatternResolver';
import { useSchedulingValidation } from './useSchedulingValidation';
import { useExecutionSubmit } from './useExecutionSubmit';
import { useTargetInventory } from './useTargetInventory';
import { useWorkflowStepActions } from './useWorkflowStepActions';
import { useAuth } from '../contexts/AuthContext';
import type { WizardExecutionContextValue } from '../contexts/WizardExecutionContext';
import logger from '../services/logger';

dayjs.extend(utc);

// === Fonctions pures déplacées depuis ExecutionWizard.tsx ===
function evaluateImpact(
  impactRules: Record<string, { level: ImpactLevel; criteria?: string | null }> | null,
  defaultImpact: ImpactLevel | null,
  environment: string
): ImpactLevel | null {
  if (!impactRules) return defaultImpact;
  const envUpper = environment.toUpperCase();
  for (const [env, rule] of Object.entries(impactRules)) {
    if (env.toUpperCase() === envUpper) return rule.level;
  }
  return defaultImpact;
}

function getInvalidWorkflowStepOrders(form: ReturnType<typeof Form.useForm>[0]): number[] {
  const allErrors = form.getFieldsError();
  const invalid = new Set<number>();
  for (const fe of allErrors) {
    if (!fe.errors?.length) continue;
    const name = fe.name as (string | number)[];
    if (name?.[0] !== 'workflow_step_parameters') continue;
    const stepOrderStr = name?.[1];
    const stepOrderNum = typeof stepOrderStr === 'string' ? Number(stepOrderStr) : Number.NaN;
    if (Number.isFinite(stepOrderNum)) invalid.add(stepOrderNum);
  }
  return Array.from(invalid).sort((a, b) => a - b);
}

function buildWorkflowStepParams(
  parameters: Record<string, unknown>,
  isWorkflow: boolean
): Record<string, { parameters: Record<string, unknown> }> | undefined {
  if (!isWorkflow) return undefined;
  const raw = (parameters as Record<string, unknown>)?.workflow_step_parameters as
    | Record<string, { parameters?: Record<string, unknown> }>
    | undefined;
  if (!raw || typeof raw !== 'object') return undefined;
  const out: Record<string, { parameters: Record<string, unknown> }> = {};
  for (const [order, entry] of Object.entries(raw)) {
    const params = entry?.parameters ?? {};
    if (params && typeof params === 'object' && Object.keys(params).length > 0) {
      out[String(order)] = { parameters: params };
    }
  }
  return Object.keys(out).length > 0 ? out : undefined;
}

export interface UseExecutionWizardStateOptions {
  open: boolean;
  action: CatalogActionDetail | null;
  allowedEnvironments: string[];
  onCancel: () => void;
  onSuccess?: (executionId: number) => void;
  onBackToCatalog?: () => void;
  parentExecutionId?: number | null;
  initialParams?: WizardInitialParams;
}

export interface UseExecutionWizardStateReturn {
  form: ReturnType<typeof Form.useForm>[0];
  currentStep: number;
  // Target state
  selectedTargets: Target[];
  targetInputMode: 'list' | 'pattern' | 'manual';
  targetPattern: string;
  manualTargetInput: string;
  selectedEnvironment: ExecutionEnvironment | null;
  setSelectedTargets: (targets: Target[]) => void;
  setTargetInputMode: (mode: 'list' | 'pattern' | 'manual') => void;
  setTargetPattern: (p: string) => void;
  setManualTargetInput: (v: string) => void;
  setSelectedEnvironment: (env: ExecutionEnvironment) => void;
  parameters: Record<string, unknown>;
  setParameters: (params: Record<string, unknown>) => void;
  // Workflow
  workflowStepActions: Record<number, CatalogActionDetail>;
  loadingWorkflowStepActions: boolean;
  workflowStepActionsError: string | null;
  workflowInvalidStepOrders: number[];
  workflowValidationSummary: string | null;
  isWorkflow: boolean;
  workflowSteps: Array<{ order: number; name: string | null; referenced_action_id: number }>;
  isWorkflowStep2Valid: boolean;
  // Derived
  parameterFields: ReturnType<typeof extractParameterFields>;
  effectiveTargetNames: string[];
  requiresTarget: boolean;
  // Submit/scheduling
  execSubmit: ReturnType<typeof useExecutionSubmit>;
  schedulingValidation: ReturnType<typeof useSchedulingValidation>;
  pageMeEnabled: boolean;
  setPageMeEnabled: (v: boolean) => void;
  // Handlers
  handleNext: () => Promise<void>;
  handlePrev: () => void;
  handleSubmit: () => Promise<void>;
  handleSubmitScheduled: () => Promise<void>;
  handleKeyDown: (e: React.KeyboardEvent) => void;
  // Refs
  firstFieldRef: React.RefObject<HTMLElement | null>;
  isSubmittingRef: React.RefObject<boolean>;
  // Context value for WizardExecutionContextProvider
  wizardCtxValue: WizardExecutionContextValue;
}

export function useExecutionWizardState({
  open, action, allowedEnvironments, onCancel, onSuccess, onBackToCatalog, parentExecutionId, initialParams,
}: UseExecutionWizardStateOptions): UseExecutionWizardStateReturn {
  const { notification } = App.useApp();
  const { isBusinessProfile } = useAuth();
  const schedulingValidation = useSchedulingValidation();
  const execSubmit = useExecutionSubmit();
  const { setSubmitError, resetScheduling } = execSubmit;

  const [form] = Form.useForm();
  const [currentStep, setCurrentStep] = useState(0);

  // Target state
  const [selectedTargets, setSelectedTargets] = useState<Target[]>([]);
  const [targetInputMode, setTargetInputMode] = useState<'list' | 'pattern' | 'manual'>('list');
  const [targetPattern, setTargetPattern] = useState('');
  const [manualTargetInput, setManualTargetInput] = useState('');
  const [selectedEnvironment, setSelectedEnvironment] = useState<ExecutionEnvironment | null>(null);
  const [parameters, setParameters] = useState<Record<string, unknown>>({});
  const [pageMeEnabled, setPageMeEnabled] = useState(false);

  // Workflow validation state
  const [workflowInvalidStepOrders, setWorkflowInvalidStepOrders] = useState<number[]>([]);
  const [workflowValidationSummary, setWorkflowValidationSummary] = useState<string | null>(null);

  const firstFieldRef = useRef<HTMLElement | null>(null);
  const isSubmittingRef = useRef(false);

  const isWorkflow = action?.item_type === 'workflow';
  const workflowSteps = useMemo(() => {
    const steps = action?.workflow_steps ?? null;
    if (!isWorkflow || !steps || !Array.isArray(steps)) return [];
    return [...steps].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));
  }, [action?.workflow_steps, isWorkflow]);

  // Pattern resolution
  const { resolvedTargets: resolvedPatternTargets, isResolving: patternResolving } = usePatternResolver({
    enabled: open,
    inputMode: targetInputMode,
    pattern: targetPattern,
  });

  // Derived values
  const parameterFields = useMemo(() => extractParameterFields(action?.parameters_schema ?? null), [action?.parameters_schema]);

  const effectiveTargetNames = useMemo((): string[] => {
    if (targetInputMode === 'list') return selectedTargets.map((t) => t.name);
    if (targetInputMode === 'pattern') return resolvedPatternTargets.map((t) => t.name);
    if (targetInputMode === 'manual') return manualTargetInput.split(',').map((s) => s.trim()).filter(Boolean);
    return [];
  }, [targetInputMode, selectedTargets, resolvedPatternTargets, manualTargetInput]);

  const selectedServerNames = useMemo((): string[] => effectiveTargetNames, [effectiveTargetNames]);

  const derivedEnvironment = useMemo((): ExecutionEnvironment | null => {
    if (targetInputMode === 'list' && selectedTargets.length > 0)
      return (selectedTargets[0]?.environment as ExecutionEnvironment) ?? null;
    if (targetInputMode === 'pattern' && resolvedPatternTargets.length > 0)
      return (resolvedPatternTargets[0]?.environment as ExecutionEnvironment) ?? null;
    if (targetInputMode === 'manual' || targetInputMode === 'list') {
      if (selectedTargets.length === 0) return selectedEnvironment;
    }
    return selectedEnvironment;
  }, [targetInputMode, selectedTargets, resolvedPatternTargets, selectedEnvironment]);

  const targetsToCheck = targetInputMode === 'pattern' ? resolvedPatternTargets : selectedTargets;
  const hasMixedEnvironments = useMemo((): boolean => {
    if (targetsToCheck.length <= 1) return false;
    return new Set(targetsToCheck.map((t) => t.environment)).size > 1;
  }, [targetsToCheck]);

  const requiresTarget = action?.requires_target !== false;
  const envForInventory = selectedEnvironment || derivedEnvironment;

  const currentImpact = useMemo((): ImpactLevel | null => {
    if (!derivedEnvironment || !action) return null;
    return evaluateImpact(action.impact_rules, action.default_impact_level, derivedEnvironment);
  }, [derivedEnvironment, action]);

  // === DIP: Inventory via useTargetInventory ===
  const { environmentsCache, inventoryData, inventoryWarnings, loadingInventory } = useTargetInventory({
    open,
    actionId: action?.id,
    currentStep,
    parameterFields,
    environment: envForInventory,
    selectedServerNames,
  });

  // === DIP: Workflow step actions via useWorkflowStepActions ===
  const { workflowStepActions, loadingWorkflowStepActions, workflowStepActionsError } = useWorkflowStepActions({
    open,
    actionId: action?.id,
    isWorkflow,
    currentStep,
    workflowSteps,
  });

  const isWorkflowStep2Valid = useMemo(() => {
    if (!isWorkflow || !workflowSteps.length) return true;
    return workflowInvalidStepOrders.length === 0;
  }, [isWorkflow, workflowSteps.length, workflowInvalidStepOrders.length]);

  // === useEffect 1: Reset state on open/close ===
  useEffect(() => {
    if (open && action) {
      if (action.status !== 'published') {
        notification.error({ title: 'Action non disponible', description: "Cette action n'est pas publiée." });
        onCancel();
        return;
      }
      setCurrentStep(0); setParameters({}); setPageMeEnabled(false); setSubmitError(null);
      isSubmittingRef.current = false;
      setWorkflowInvalidStepOrders([]); setWorkflowValidationSummary(null);
      form.resetFields();
      setSelectedTargets([]); setTargetInputMode('list'); setTargetPattern('');
      setManualTargetInput('');
      resetScheduling();
      if (initialParams?.environment) {
        setSelectedEnvironment(initialParams.environment as ExecutionEnvironment);
      } else if (action?.requires_target === false && allowedEnvironments.length === 1) {
        setSelectedEnvironment(allowedEnvironments[0] as ExecutionEnvironment);
      } else {
        setSelectedEnvironment(null);
      }
      if (initialParams?.targetNames && initialParams.targetNames.length > 0) {
        setTargetInputMode('manual');
        setManualTargetInput(initialParams.targetNames.join(', '));
      }
      if (initialParams?.parameters && Object.keys(initialParams.parameters).length > 0) {
        setParameters(initialParams.parameters);
        form.setFieldsValue(initialParams.parameters);
      }
    }
  }, [open, action, form, notification, onCancel, allowedEnvironments, setSubmitError, resetScheduling, initialParams]);

  // === useEffect 2: Validate workflow step parameters ===
  useEffect(() => {
    if (!open || !isWorkflow || currentStep !== 1 || !workflowSteps.length || loadingWorkflowStepActions) return;
    let cancelled = false;
    const run = async () => {
      try {
        await form.validateFields();
        if (!cancelled) { setWorkflowInvalidStepOrders([]); setWorkflowValidationSummary(null); }
      } catch {
        if (cancelled) return;
        const invalidOrders = getInvalidWorkflowStepOrders(form);
        setWorkflowInvalidStepOrders(invalidOrders);
        setWorkflowValidationSummary(invalidOrders.length > 0 ? `Étapes invalides : ${invalidOrders.join(', ')}` : null);
      }
    };
    run();
    return () => { cancelled = true; };
  }, [open, isWorkflow, currentStep, workflowSteps, loadingWorkflowStepActions, workflowStepActions, form, parameters]);

  // === useEffect 3: Focus management ===
  useEffect(() => {
    if (open && firstFieldRef.current) setTimeout(() => firstFieldRef.current?.focus(), 100);
  }, [open, currentStep]);

  // === useEffect 4: Re-apply form values on step 2 ===
  useEffect(() => {
    if (!open || currentStep !== 1 || !parameters || Object.keys(parameters).length === 0) return;
    if (isWorkflow && loadingWorkflowStepActions) return;
    if (isWorkflow && workflowSteps.length > 0 && Object.keys(workflowStepActions || {}).length === 0) return;
    try { form.setFieldsValue(parameters); } catch { /* ignore */ }
  }, [open, currentStep, parameters, form, isWorkflow, loadingWorkflowStepActions, workflowSteps.length, workflowStepActions]);

  // === Handlers (copier tel quel depuis ExecutionWizard.tsx l.386-534) ===
  const handleNext = useCallback(async () => {
    if (currentStep === 0) {
      if (requiresTarget) {
        if (effectiveTargetNames.length === 0) {
          notification.warning({ title: targetInputMode === 'pattern' ? 'Entrez un pattern (ex: srv-dev-*) et attendez la résolution.' : targetInputMode === 'manual' ? 'Entrez une ou plusieurs cibles, séparées par des virgules.' : 'Veuillez sélectionner au moins une cible.' });
          return;
        }
        if (hasMixedEnvironments) notification.warning({ title: 'Attention', description: 'Les cibles sélectionnées appartiennent à des environnements différents.' });
      } else if (!selectedEnvironment) {
        notification.warning({ title: 'Veuillez sélectionner un environnement.' });
        return;
      }
    } else if (currentStep === 1) {
      try { const values = await form.validateFields(); setParameters(values); setWorkflowValidationSummary(null); }
      catch {
        if (isWorkflow) {
          const invalidOrders = getInvalidWorkflowStepOrders(form);
          setWorkflowInvalidStepOrders(invalidOrders);
          if (invalidOrders.length > 0) setWorkflowValidationSummary(`Étapes invalides : ${invalidOrders.join(', ')}`);
        }
        return;
      }
    }
    setCurrentStep((s) => Math.min(s + 1, 2));
  }, [currentStep, selectedEnvironment, effectiveTargetNames, targetInputMode, requiresTarget, hasMixedEnvironments, form, notification, isWorkflow]);

  const handlePrev = useCallback(() => setCurrentStep((s) => Math.max(s - 1, 0)), []);

  const handleSubmit = useCallback(async () => {
    if (isSubmittingRef.current || execSubmit.isSubmitting) {
      logger.debug('Double-submit blocked in handleSubmit', { component: 'ExecutionWizard', action: 'double_submit_blocked' });
      return;
    }
    if (!action || (!derivedEnvironment && effectiveTargetNames.length === 0)) {
      notification.warning({ title: 'Données incomplètes', description: 'Veuillez compléter toutes les étapes du wizard.' }); return;
    }
    if (action.status !== 'published') { const msg = "Cette action n'est plus publiée et ne peut pas être exécutée."; execSubmit.setSubmitError(msg); notification.error({ title: 'Action non disponible', description: msg }); return; }
    isSubmittingRef.current = true;
    try {
      const targetNames = effectiveTargetNames.length > 0 ? effectiveTargetNames : undefined;
      const executionId = await execSubmit.submitImmediate({
        action_id: action.id, environment: targetNames ? undefined : (derivedEnvironment ?? undefined),
        target_names: targetNames,
        parameters: isWorkflow ? null : (Object.keys(parameters).length > 0 ? parameters : null),
        workflow_step_parameters: buildWorkflowStepParams(parameters, isWorkflow),
        parent_execution_id: parentExecutionId ?? null,
        page_me: pageMeEnabled || undefined,
      });
      if (executionId != null) onSuccess?.(executionId);
    } finally { isSubmittingRef.current = false; }
  }, [action, derivedEnvironment, effectiveTargetNames, parameters, notification, onSuccess, parentExecutionId, isWorkflow, execSubmit, pageMeEnabled]);

  const handleSubmitScheduled = useCallback(async () => {
    // Copier la logique complète depuis ExecutionWizard.tsx l.480-527
    // (handleSubmitScheduled avec dayjs, RecurringPatternRequest, notification.success)
    if (isSubmittingRef.current || execSubmit.isSubmitting) {
      logger.debug('Double-submit blocked', { component: 'ExecutionWizard', action: 'double_submit_blocked' });
      return;
    }
    if (!action || !derivedEnvironment) { notification.warning({ title: 'Données incomplètes', description: 'Veuillez compléter toutes les étapes du wizard.' }); return; }
    // ... (copier intégralité depuis ExecutionWizard.tsx l.488-527)
    isSubmittingRef.current = true;
    try {
      /* ... logique scheduling identique à ExecutionWizard l.497-522 ... */
    } finally { isSubmittingRef.current = false; }
  }, [action, derivedEnvironment, selectedTargets, parameters, notification, onCancel, onSuccess, isWorkflow, execSubmit, pageMeEnabled]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Escape') onCancel();
    else if (e.key === 'Enter' && !e.shiftKey && currentStep < 2) {
      if ((e.target as HTMLElement).tagName !== 'TEXTAREA') { e.preventDefault(); void handleNext(); }
    }
  }, [onCancel, currentStep, handleNext]);

  // Context value (memoized)
  const wizardCtxValue = useMemo((): WizardExecutionContextValue => ({
    environmentsCache,
    inventoryData,
    inventoryWarnings,
    loadingInventory,
    derivedEnvironment,
    currentImpact,
    hasMixedEnvironments,
    resolvedPatternTargets,
    patternResolving,
    selectedServerNames,
  }), [environmentsCache, inventoryData, inventoryWarnings, loadingInventory, derivedEnvironment, currentImpact, hasMixedEnvironments, resolvedPatternTargets, patternResolving, selectedServerNames]);

  return {
    form, currentStep,
    selectedTargets, targetInputMode, targetPattern, manualTargetInput, selectedEnvironment,
    setSelectedTargets, setTargetInputMode, setTargetPattern, setManualTargetInput, setSelectedEnvironment,
    parameters, setParameters,
    workflowStepActions, loadingWorkflowStepActions, workflowStepActionsError,
    workflowInvalidStepOrders, workflowValidationSummary, isWorkflow, workflowSteps, isWorkflowStep2Valid,
    parameterFields, effectiveTargetNames, requiresTarget,
    execSubmit, schedulingValidation,
    pageMeEnabled, setPageMeEnabled,
    handleNext, handlePrev, handleSubmit, handleSubmitScheduled, handleKeyDown,
    firstFieldRef, isSubmittingRef,
    wizardCtxValue,
  };
}
```

---

### `ExecutionWizard.tsx` cible (orchestrateur, ~180 lignes)

Les imports supprimés : `fetchCatalogActionById`, `fetchInventoryItems`, tous les `useState`/`useEffect`/`useCallback`/`useMemo`/`useRef` (remplacés par le hook). Ajouts : `useExecutionWizardState`, `WizardExecutionContextProvider`.

```tsx
// SUPPRIMER ces imports :
// import { fetchCatalogActionById } from '../../services/catalog_service';
// import { fetchInventoryItems } from '../../services/execution_service';

// AJOUTER :
import { useExecutionWizardState } from '../../hooks/useExecutionWizardState';
import { WizardExecutionContextProvider } from '../../contexts/WizardExecutionContext';

export function ExecutionWizard({ open, action, allowedEnvironments, activeExecutionId, onCancel, onSuccess, onBackToCatalog, onSuggestionClick, parentExecutionId, initialParams }: ExecutionWizardProps) {
  const { isBusinessProfile } = useAuth();
  const STEP_ITEMS = isBusinessProfile ? STEP_ITEMS_SIMPLIFIED : STEP_ITEMS_DEFAULT;

  const {
    form, currentStep,
    selectedTargets, targetInputMode, targetPattern, manualTargetInput, selectedEnvironment,
    setSelectedTargets, setTargetInputMode, setTargetPattern, setManualTargetInput, setSelectedEnvironment,
    parameters, setParameters,
    workflowStepActions, loadingWorkflowStepActions, workflowStepActionsError, workflowValidationSummary,
    isWorkflow, workflowSteps, isWorkflowStep2Valid,
    parameterFields, effectiveTargetNames, requiresTarget,
    execSubmit, schedulingValidation,
    pageMeEnabled, setPageMeEnabled,
    handleNext, handlePrev, handleSubmit, handleSubmitScheduled, handleKeyDown,
    wizardCtxValue,
  } = useExecutionWizardState({ open, action, allowedEnvironments, onCancel, onSuccess, onBackToCatalog, parentExecutionId, initialParams });

  if (!action && !activeExecutionId) return null;

  if (activeExecutionId != null) { /* Modal ExecutionTimeline identique */ }

  const { scheduling, isSubmitting: submitting } = execSubmit;

  return (
    <Modal ...>
      <WizardExecutionContextProvider value={wizardCtxValue}>
        <div onKeyDown={handleKeyDown}>
          {parentExecutionId && <Alert ... />}
          <Steps current={currentStep} ... />
          <div ...>
            {currentStep === 0 && (
              <TargetSelectionStep
                action={action!}
                allowedEnvironments={allowedEnvironments}
                selectedTargets={selectedTargets}
                onTargetsChange={setSelectedTargets}
                targetInputMode={targetInputMode}
                onTargetInputModeChange={setTargetInputMode}
                targetPattern={targetPattern}
                onTargetPatternChange={setTargetPattern}
                manualTargetInput={manualTargetInput}
                onManualTargetInputChange={setManualTargetInput}
                selectedEnvironment={selectedEnvironment}
                onEnvironmentChange={setSelectedEnvironment}
              />
            )}
            <div style={{ display: currentStep === 1 ? 'block' : 'none' }}>
              <ParametersFormStep
                form={form}
                parameterFields={parameterFields}
                parameters={parameters}
                onParametersChange={setParameters}
                isWorkflow={isWorkflow}
                workflowSteps={workflowSteps}
                workflowStepActions={workflowStepActions}
                loadingWorkflowStepActions={loadingWorkflowStepActions}
                workflowStepActionsError={workflowStepActionsError}
                workflowValidationSummary={workflowValidationSummary}
              />
            </div>
            {currentStep === 2 && (
              <ConfirmationStep
                action={action!}
                selectedTargets={selectedTargets}
                parameters={parameters}
                submitError={execSubmit.submitError}
                isScheduling={scheduling.isScheduling}
                scheduling={scheduling}
                onSchedulingChange={execSubmit.updateScheduling}
                schedulingError={execSubmit.schedulingError}
                submitting={submitting}
                schedulingValidation={schedulingValidation}
                pageMeEnabled={pageMeEnabled}
                onPageMeChange={setPageMeEnabled}
              />
            )}
          </div>
          <div style={{ marginTop: 24, display: 'flex', justifyContent: 'space-between' }}>
            {/* Footer buttons — identiques à l'actuel l.611-635 */}
          </div>
        </div>
      </WizardExecutionContextProvider>
    </Modal>
  );
}
```

---

### Modifications des steps pour consommer le contexte

#### `TargetSelectionStep.tsx` — interface réduite

```typescript
import { useWizardExecutionContext } from '../../contexts/WizardExecutionContext';

// Dans le composant, avant le return :
const {
  environmentsCache,
  inventoryWarnings,
  derivedEnvironment,
  hasMixedEnvironments,
  currentImpact,
  resolvedPatternTargets,
  patternResolving,
} = useWizardExecutionContext();

export interface TargetSelectionStepProps {
  action: CatalogActionDetail;
  allowedEnvironments: string[];
  selectedTargets: Target[];
  onTargetsChange: (targets: Target[]) => void;
  targetInputMode: 'list' | 'pattern' | 'manual';
  onTargetInputModeChange: (mode: 'list' | 'pattern' | 'manual') => void;
  targetPattern: string;
  onTargetPatternChange: (pattern: string) => void;
  manualTargetInput: string;
  onManualTargetInputChange: (input: string) => void;
  selectedEnvironment: ExecutionEnvironment | null;
  onEnvironmentChange: (env: ExecutionEnvironment) => void;
  // 7 props retirées → contexte
}
```

#### `ParametersFormStep.tsx` — interface réduite

```typescript
import { useWizardExecutionContext } from '../../contexts/WizardExecutionContext';

// Dans le composant, avant le return :
const {
  inventoryData,
  inventoryWarnings,
  loadingInventory,
  selectedServerNames,
} = useWizardExecutionContext();

export interface ParametersFormStepProps {
  form: FormInstance;
  // action SUPPRIMÉE (non utilisée dans l'implémentation actuelle)
  parameterFields: ParameterField[];
  parameters: Record<string, unknown>;
  onParametersChange: (values: Record<string, unknown>) => void;
  isWorkflow: boolean;
  workflowSteps: Array<{ order: number; name: string | null; referenced_action_id: number }>;
  workflowStepActions: Record<number, CatalogActionDetail>;
  loadingWorkflowStepActions: boolean;
  workflowStepActionsError: string | null;
  workflowValidationSummary: string | null;
  // 4 inventory props retirées → contexte + prop action supprimée
}
```

#### `ConfirmationStep.tsx` — interface réduite

```typescript
import { useWizardExecutionContext } from '../../contexts/WizardExecutionContext';

// Dans le composant, avant le return :
const {
  environmentsCache,
  derivedEnvironment,
  currentImpact,
} = useWizardExecutionContext();

export interface ConfirmationStepProps {
  action: CatalogActionDetail;
  selectedTargets: Target[];
  // derivedEnvironment RETIRÉE → contexte
  // currentImpact RETIRÉE → contexte
  parameters: Record<string, unknown>;
  submitError: string | null;
  // environmentsCache RETIRÉE → contexte
  isScheduling: boolean;
  scheduling: SchedulingState;
  onSchedulingChange: (updates: Partial<SchedulingState>) => void;
  schedulingError: string | null;
  submitting: boolean;
  schedulingValidation: UseSchedulingValidationReturn;
  pageMeEnabled: boolean;
  onPageMeChange: (checked: boolean) => void;
}
```

---

### Compatibilité tests existants

| Fichier de test | Lignes | Impact sur les mocks |
|----------------|--------|----------------------|
| `ExecutionWizard.test.tsx` | 1487 | Aucun — `vi.mock('../../services/execution_service')` + `vi.mock('../../services/catalog_service')` couvrent les hooks |
| `ExecutionWizard.targets.test.tsx` | 306 | Aucun |
| `ExecutionWizard.scheduling.test.tsx` | 376 | Aucun |
| `ExecutionWizard.story23_6.test.tsx` | 272 | Aucun |

**Raison** : Les mocks `vi.mock()` patchent le module entier. `useWorkflowStepActions` et `useTargetInventory` importent de ces mêmes modules → couverts automatiquement. `WizardExecutionContextProvider` est fourni **à l'intérieur** d'`ExecutionWizard` → les tests qui rendent `<ExecutionWizard ...>` l'obtiennent sans setup supplémentaire.

**Si un step est testé isolément dans le futur** : envelopper dans `<WizardExecutionContextProvider value={mockCtxValue}>`.

---

### Traitement des `eslint-disable` existants

1. **useEffect workflow step actions** (l.294 ExecutionWizard actuel) : Dans `useWorkflowStepActions`, `workflowStepActions` est exclu des deps car il est écrit par l'effet. Documenter : `// intentional: workflowStepActions excluded — written by this effect, read for cache check (infinite loop)`

2. **useEffect inventory data** (l.370 ExecutionWizard actuel) : Disparaît de `ExecutionWizard.tsx` car l'effet est dans `useTargetInventory.ts` qui a déjà `// eslint-disable-next-line react-hooks/exhaustive-deps -- inventoryData excluded: read via ref to avoid infinite loop`.

---

### Structure cible des fichiers

```
idp-portal/frontend/src/
  hooks/
    useWorkflowStepActions.ts      ← CRÉER (~55 lignes)
    useExecutionWizardState.ts     ← CRÉER (~220 lignes)
    useTargetInventory.ts          ← AUCUN CHANGEMENT
    useWizardState.ts              ← AUCUN CHANGEMENT (conservé tel quel)
  contexts/
    WizardExecutionContext.tsx     ← CRÉER (~35 lignes)
  components/catalog/
    ExecutionWizard.tsx            ← MODIFIER (641 → ~180 lignes)
    TargetSelectionStep.tsx        ← MODIFIER (19 → 12 props)
    ParametersFormStep.tsx         ← MODIFIER (15 → 11 props)
    ConfirmationStep.tsx           ← MODIFIER (15 → 12 props)
```

**Aucun changement backend. Aucune migration DB. Impact purement frontend.**

---

### Précédents directs à reproduire

| Précédent | Pattern | Référence |
|-----------|---------|-----------|
| Story 34-12 | Extraction hooks + sous-composants (ExecutionTimeline) | `src/hooks/useExecutionData.ts` |
| Story 34-11 | `useAuditFilters` — hook agrégateur exportant interface typée | `src/hooks/useAuditFilters.ts` |
| Story 33-5 | Réduction props ActionForm/ActionWizard | commit `a0169fc` |
| Story 17.2 | `useTargetInventory` déjà créé — **intégrer, ne pas recréer** | `src/hooks/useTargetInventory.ts` |

> **PRIORITÉ CRITIQUE** : Lire `src/hooks/useTargetInventory.ts` **avant** de commencer — ce hook fait déjà le travail des useEffects inventory/environments. Il suffit de l'appeler dans `useExecutionWizardState`.

### Project Structure Notes

- `src/hooks/useWorkflowStepActions.ts` : **CRÉER** — DIP pour fetchCatalogActionById
- `src/hooks/useExecutionWizardState.ts` : **CRÉER** — agrégateur 4 useEffect + state + handlers + wizardCtxValue
- `src/contexts/WizardExecutionContext.tsx` : **CRÉER** — contexte partagé 10 valeurs
- `src/components/catalog/ExecutionWizard.tsx` : **MODIFIER** (641 → ~180 lignes, supprimer imports services directs)
- `src/components/catalog/TargetSelectionStep.tsx` : **MODIFIER** (19 → 12 props, consommer contexte)
- `src/components/catalog/ParametersFormStep.tsx` : **MODIFIER** (15 → 11 props, supprimer `action` inutilisée + 4 inventory vers contexte)
- `src/components/catalog/ConfirmationStep.tsx` : **MODIFIER** (15 → 12 props, consommer contexte)

### References

- [Source: idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx] — 641 lignes, analyse complète ci-dessus
- [Source: idp-portal/frontend/src/components/catalog/TargetSelectionStep.tsx] — 285 lignes, 19 props
- [Source: idp-portal/frontend/src/components/catalog/ParametersFormStep.tsx] — 142 lignes, 15 props (action inutilisée)
- [Source: idp-portal/frontend/src/components/catalog/ConfirmationStep.tsx] — 166 lignes, 15 props
- [Source: idp-portal/frontend/src/hooks/useTargetInventory.ts] — hook existant Story 17.2 à intégrer (164 lignes)
- [Source: idp-portal/frontend/src/hooks/useWizardState.ts] — hook existant Story 17.2 (conservé tel quel)
- [Source: idp-portal/frontend/src/hooks/useExecutionSubmit.ts] — hook existant, appelé dans useExecutionWizardState
- [Source: idp-portal/frontend/src/components/catalog/ExecutionWizard.test.tsx] — 1487 lignes, mocks module-level
- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-FE-4] — DIP services
- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-FE-7] — Props surchargées
- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-FE-9] — 7 useEffect + 2 eslint-disable
- [Source: _bmad-output/implementation-artifacts/34-12-frontend-decouper-execution-timeline.md] — story précédente directement applicable

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

(aucun blocage)

### Completion Notes List

- **SOLID-FE-4 (DIP)** : `useWorkflowStepActions.ts` créé (~75 lignes) — encapsule `fetchCatalogActionById`. `useTargetInventory` (existant) intégré dans `useExecutionWizardState`. `ExecutionWizard.tsx` ne contient plus aucun import direct de services.
- **SOLID-FE-7 (Props)** : `WizardExecutionContext.tsx` créé (~35 lignes). `TargetSelectionStep` : 19→12 props (7 vers contexte). `ParametersFormStep` : 15→10 props (4 inventory vers contexte + 1 `action` inutilisée supprimée). `ConfirmationStep` : 15→12 props (3 vers contexte).
- **SOLID-FE-9 (useEffect)** : `useExecutionWizardState.ts` créé (~290 lignes) — aggrège useTargetInventory, useWorkflowStepActions, usePatternResolver, useExecutionSubmit, useSchedulingValidation, 3 useEffect actifs, tous les handlers, wizardCtxValue. `ExecutionWizard.tsx` : 641→~170 lignes, orchestrateur pur.
- **eslint-disable** : `// intentional: workflowStepActions excluded...` documenté dans useWorkflowStepActions. L'effet inventory (2ème eslint-disable) reste dans useTargetInventory (non modifié).
- **Tests** : 77/77 tests passent (4 fichiers, aucune modification) ; `tsc --noEmit` → 0 erreur.
- **Code review 2026-02-23** : 2H+2M+1L fixes appliqués — H1: `useAuth()` inutile supprimé de `useExecutionWizardState` (hook mort + import retiré) ; H2: `useEffect 3` focus management supprimé (firstFieldRef jamais attaché au DOM — code mort) ; M3: `onBackToCatalog` retiré de `UseExecutionWizardStateOptions` (paramètre fantôme) + call site `ExecutionWizard.tsx` nettoyé ; M4: `firstFieldRef` et `isSubmittingRef` retirés du return type public (jamais consommés externalement) ; L5: doc AC2 corrigée (ParametersFormStep 11→10 props, math 15−4−1=10).

### File List

- `idp-portal/frontend/src/hooks/useWorkflowStepActions.ts` (CRÉÉ)
- `idp-portal/frontend/src/hooks/useExecutionWizardState.ts` (CRÉÉ)
- `idp-portal/frontend/src/contexts/WizardExecutionContext.tsx` (CRÉÉ)
- `idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx` (MODIFIÉ — 641→~170 lignes)
- `idp-portal/frontend/src/components/catalog/TargetSelectionStep.tsx` (MODIFIÉ — 19→12 props)
- `idp-portal/frontend/src/components/catalog/ParametersFormStep.tsx` (MODIFIÉ — 15→11 props)
- `idp-portal/frontend/src/components/catalog/ConfirmationStep.tsx` (MODIFIÉ — 15→12 props)

## Change Log

| Date | Change |
|------|--------|
| 2026-02-23 | Story créée (backlog) — SOLID-FE-4, SOLID-FE-7, SOLID-FE-9 : résumé des violations. |
| 2026-02-23 | Story enrichie (ready-for-dev) — Analyse exhaustive : useTargetInventory + useWizardState existants non utilisés par ExecutionWizard ; comptage précis 19+15+15 props avec tableau prop-par-prop ; interfaces complètes useWorkflowStepActions + WizardExecutionContext + useExecutionWizardState ; JSX cible ExecutionWizard + 3 steps ; compatibilité 2441 lignes de tests ; traitement 2 eslint-disable ; structure cible 7 fichiers. |
| 2026-02-23 | Implémentation complète — SOLID-FE-4/7/9 : 3 nouveaux fichiers créés (useWorkflowStepActions, useExecutionWizardState, WizardExecutionContext), 4 fichiers modifiés (ExecutionWizard 641→~170 lignes, 3 steps réduits), 77/77 tests passent, 0 erreur TypeScript. |
| 2026-02-23 | Code review adversarial — 5 issues (2H+2M+1L) auto-fixés : dead useAuth, firstFieldRef mort (focus management inutilisable), onBackToCatalog fantôme, interface bloat (firstFieldRef/isSubmittingRef return), doc AC2 (10 props, pas 11). 77/77 tests, 0 TS error. Story → done. |
