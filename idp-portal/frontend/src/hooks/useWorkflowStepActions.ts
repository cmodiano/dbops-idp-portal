/**
 * useWorkflowStepActions - DIP hook for fetching workflow step actions.
 * Story 34.13 (SOLID-FE-4): Encapsulates fetchCatalogActionById to remove
 * direct service dependency from ExecutionWizard.tsx.
 */

import { useEffect, useState } from 'react';
import { fetchCatalogActionById } from '../services/catalog_service';
import type { CatalogActionDetail } from '../services/catalog_service';

export interface UseWorkflowStepActionsOptions {
  open: boolean;
  actionId?: number;
  isWorkflow: boolean;
  currentStep: number;
  workflowSteps: Array<{ order: number; name: string | null; referenced_action_id?: number | null }>;
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
    // intentional: workflowStepActions excluded — written by this effect, read for cache check (avoids infinite loop)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, actionId, isWorkflow, currentStep, workflowSteps]);

  return { workflowStepActions, loadingWorkflowStepActions, workflowStepActionsError };
}
