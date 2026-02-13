/**
 * useWizardState - Multi-step wizard state management hook.
 * Extracted from ExecutionWizard.tsx (Story 17.2, Task 2.1).
 *
 * Manages step navigation, step data persistence, and step validation.
 */

import { useCallback, useState } from 'react';

export interface WizardStepData {
  selectedTargets: import('./useTargetInventory').Target[];
  targetInputMode: 'list' | 'pattern' | 'manual';
  targetPattern: string;
  manualTargetInput: string;
  selectedEnvironment: import('../types/api').ExecutionEnvironment | null;
  parameters: Record<string, unknown>;
}

const initialStepData: WizardStepData = {
  selectedTargets: [],
  targetInputMode: 'list',
  targetPattern: '',
  manualTargetInput: '',
  selectedEnvironment: null,
  parameters: {},
};

export interface UseWizardStateOptions {
  totalSteps?: number;
}

export interface UseWizardStateReturn {
  currentStep: number;
  stepData: WizardStepData;
  updateStepData: (updates: Partial<WizardStepData>) => void;
  next: () => void;
  prev: () => void;
  goToStep: (step: number) => void;
  canProceed: boolean;
  setCanProceed: (value: boolean) => void;
  reset: () => void;
}

export function useWizardState(options: UseWizardStateOptions = {}): UseWizardStateReturn {
  const { totalSteps = 3 } = options;
  const [currentStep, setCurrentStep] = useState(0);
  const [stepData, setStepData] = useState<WizardStepData>({ ...initialStepData });
  const [canProceed, setCanProceed] = useState(false);

  const updateStepData = useCallback((updates: Partial<WizardStepData>) => {
    setStepData((prev) => ({ ...prev, ...updates }));
  }, []);

  const next = useCallback(() => {
    setCurrentStep((s) => Math.min(s + 1, totalSteps - 1));
  }, [totalSteps]);

  const prev = useCallback(() => {
    setCurrentStep((s) => Math.max(s - 1, 0));
  }, []);

  const goToStep = useCallback((step: number) => {
    if (step >= 0 && step < totalSteps) {
      setCurrentStep(step);
    }
  }, [totalSteps]);

  const reset = useCallback(() => {
    setCurrentStep(0);
    setStepData({ ...initialStepData });
    setCanProceed(false);
  }, []);

  return {
    currentStep,
    stepData,
    updateStepData,
    next,
    prev,
    goToStep,
    canProceed,
    setCanProceed,
    reset,
  };
}
