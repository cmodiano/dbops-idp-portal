/**
 * WizardExecutionContext - Shared context for ExecutionWizard steps.
 * Story 34.13 (SOLID-FE-7): Reduces prop drilling by providing inventory
 * and derived values directly to step components.
 */

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

// eslint-disable-next-line react-refresh/only-export-components
export function useWizardExecutionContext(): WizardExecutionContextValue {
  const ctx = useContext(WizardExecutionContext);
  if (!ctx) throw new Error('useWizardExecutionContext must be used within WizardExecutionContext.Provider');
  return ctx;
}

export const WizardExecutionContextProvider = WizardExecutionContext.Provider;
