/**
 * useActionWizardState — Encapsulation DIP des appels de services pour ActionWizard.
 * Story 35.3 (SOLID-FE-4): Supprime les imports directs d'admin_service dans ActionWizard.tsx.
 *
 * Wraps :
 * - getTags (admin_service) → chargement tagsOptions à l'ouverture
 * - updateActionTags, updateActionSteps, updateWorkflowSteps, updateBusinessRulePolicies, patchAction
 */

import { useCallback, useEffect, useState } from 'react';
import type { ExecutionStep, WorkflowStep, ActionCreate } from '../types/api';
// Story 71.1, AC9: Re-export ApiError for DIP compliance in ActionWizard
export { ApiError } from '../services/api_client';
import {
  getTags,
  updateActionTags,
  updateActionSteps,
  updateWorkflowSteps,
  updateBusinessRulePolicies,
  patchAction,
} from '../services/admin_service';

export interface UseActionWizardStateOptions {
  open: boolean;
}

export interface UseActionWizardStateReturn {
  /** Options de tags pour le Select (chargées au montage) */
  tagsOptions: { value: string; label: string }[];
  /** Handlers encapsulant les appels de service */
  handleUpdateActionTags: (actionId: number, tagNames: string[]) => Promise<void>;
  handleUpdateActionSteps: (
    actionId: number,
    payload: { steps: ExecutionStep[] }
  ) => Promise<void>;
  handleUpdateWorkflowSteps: (actionId: number, payload: { steps: WorkflowStep[] }) => Promise<void>;
  handleUpdateBusinessRulePolicies: (actionId: number, inlineRules: null) => Promise<void>;
  handlePatchAction: (actionId: number, payload: Partial<ActionCreate>) => Promise<void>;
}

export function useActionWizardState({ open }: UseActionWizardStateOptions): UseActionWizardStateReturn {
  const [tagsOptions, setTagsOptions] = useState<{ value: string; label: string }[]>([]);

  // Chargement des tags à l'ouverture
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    getTags()
      .then((list) => {
        if (!cancelled) {
          setTagsOptions(list.map((t) => ({ value: t.name, label: t.name })));
        }
      })
      .catch(() => {
        if (!cancelled) setTagsOptions([]);
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  const handleUpdateActionTags = useCallback(async (actionId: number, tagNames: string[]): Promise<void> => {
    await updateActionTags(actionId, { tag_names: tagNames });
  }, []);

  const handleUpdateActionSteps = useCallback(async (
    actionId: number,
    payload: { steps: ExecutionStep[] }
  ): Promise<void> => {
    await updateActionSteps(actionId, payload);
  }, []);

  const handleUpdateWorkflowSteps = useCallback(async (actionId: number, payload: { steps: WorkflowStep[] }): Promise<void> => {
    await updateWorkflowSteps(actionId, payload);
  }, []);

  const handleUpdateBusinessRulePolicies = useCallback(async (actionId: number, inlineRules: null): Promise<void> => {
    await updateBusinessRulePolicies(actionId, inlineRules);
  }, []);

  const handlePatchAction = useCallback(async (actionId: number, payload: Partial<ActionCreate>): Promise<void> => {
    await patchAction(actionId, payload);
  }, []);

  return {
    tagsOptions,
    handleUpdateActionTags,
    handleUpdateActionSteps,
    handleUpdateWorkflowSteps,
    handleUpdateBusinessRulePolicies,
    handlePatchAction,
  };
}
