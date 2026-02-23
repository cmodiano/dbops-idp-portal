/**
 * useEligibleActions — Encapsulation DIP de getEligibleActionsForWorkflow (admin_service).
 * Story 35.3 (SOLID-FE-4): Supprime l'import direct d'admin_service dans WorkflowStepsEditor.tsx.
 */

import { useEffect, useState } from 'react';
import type { ActionListItem } from '../types/api';
import { getEligibleActionsForWorkflow } from '../services/admin_service';
import logger from '../services/logger';

export interface UseEligibleActionsReturn {
  eligibleActions: ActionListItem[];
  loadingActions: boolean;
  loadError: string | null;
}

export function useEligibleActions(): UseEligibleActionsReturn {
  const [eligibleActions, setEligibleActions] = useState<ActionListItem[]>([]);
  const [loadingActions, setLoadingActions] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoadingActions(true);
    setLoadError(null);

    getEligibleActionsForWorkflow()
      .then((actions) => {
        if (!cancelled) {
          setEligibleActions(Array.isArray(actions) ? actions : []);
        }
      })
      .catch((err) => {
        if (cancelled) return;
        logger.error('Failed to load eligible actions for workflow', {
          error: err instanceof Error ? err.message : String(err),
        });
        let errorMessage = 'Impossible de charger les actions éligibles';
        if (err instanceof Error) {
          errorMessage = err.message;
          if (err.message === 'Unknown error') {
            errorMessage =
              'Erreur lors du chargement des actions éligibles. Vérifiez votre connexion et vos permissions DBOPS.';
          }
        }
        setLoadError(errorMessage);
        setEligibleActions([]);
      })
      .finally(() => {
        if (!cancelled) setLoadingActions(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { eligibleActions, loadingActions, loadError };
}
