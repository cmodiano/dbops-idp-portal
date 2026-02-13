/**
 * useExecutionRestart - Hook for managing execution restart wizard state
 *
 * Story 26.4 - AC3: Extracted from ExecutionsPage.tsx to encapsulate restart logic.
 * Handles loading action details, preparing params, and managing wizard state.
 */
import { useState, useCallback } from 'react';
import { App } from 'antd';
import type { ExecutionResponse } from '../types/api';
import type { WizardInitialParams } from '../types/wizard';
import type { CatalogActionDetail } from '../services/catalog_service';
import { fetchCatalogActionById } from '../services/catalog_service';
import { prepareWizardParamsFromExecution } from '../utils/executionHelpers';
import logger from '../services/logger';

const MESSAGES = {
  RESTART_ACTION_UNAVAILABLE: 'Action non disponible — impossible de relancer cette exécution',
  RESTART_ERROR_TITLE: 'Erreur de relance',
  RESTART_ERROR_FALLBACK: 'Erreur lors de la préparation de la relance',
} as const;

export interface UseExecutionRestartReturn {
  restartWizardOpen: boolean;
  restartAction: CatalogActionDetail | null;
  restartAllowedEnvs: string[];
  restartInitialParams: WizardInitialParams | undefined;
  restartLoadingId: number | null;
  handleRestartExecution: (execution: ExecutionResponse) => Promise<void>;
  handleRestartWizardClose: () => void;
  handleRestartSuccess: (executionId: number) => void;
}

export const useExecutionRestart = (
  refetchCurrentState: () => Promise<void>,
  isRefreshingRef: React.MutableRefObject<boolean>,
): UseExecutionRestartReturn => {
  const { notification } = App.useApp();

  const [restartWizardOpen, setRestartWizardOpen] = useState(false);
  const [restartAction, setRestartAction] = useState<CatalogActionDetail | null>(null);
  const [restartAllowedEnvs, setRestartAllowedEnvs] = useState<string[]>([]);
  const [restartInitialParams, setRestartInitialParams] = useState<WizardInitialParams | undefined>(undefined);
  const [restartLoadingId, setRestartLoadingId] = useState<number | null>(null);

  const handleRestartExecution = useCallback(async (execution: ExecutionResponse) => {
    logger.debug('Restart execution requested', { executionId: execution.id, actionId: execution.action_id });

    if (!execution.action_id) {
      notification.error({ message: MESSAGES.RESTART_ERROR_TITLE, description: MESSAGES.RESTART_ACTION_UNAVAILABLE });
      logger.error('Restart failed: no action_id', { executionId: execution.id });
      return;
    }

    setRestartLoadingId(execution.id);
    try {
      const response = await fetchCatalogActionById(execution.action_id);
      const wizardParams = prepareWizardParamsFromExecution(execution);

      if (!wizardParams) {
        notification.error({ message: MESSAGES.RESTART_ERROR_TITLE, description: MESSAGES.RESTART_ACTION_UNAVAILABLE });
        logger.error('Restart failed: could not prepare params', { executionId: execution.id });
        return;
      }

      setRestartAction(response.data);
      setRestartAllowedEnvs(response.allowed_environments);
      setRestartInitialParams(wizardParams);
      setRestartWizardOpen(true);
    } catch (err) {
      const message = err instanceof Error ? err.message : MESSAGES.RESTART_ERROR_FALLBACK;
      notification.error({ message: MESSAGES.RESTART_ERROR_TITLE, description: message });
      logger.error('Restart execution failed', { executionId: execution.id, error: message });
    } finally {
      setRestartLoadingId(null);
    }
  }, [notification]);

  const handleRestartWizardClose = useCallback(() => {
    setRestartWizardOpen(false);
    setRestartAction(null);
    setRestartAllowedEnvs([]);
    setRestartInitialParams(undefined);
  }, []);

  // Story 22.14: Uses refetchCurrentState (refs) to avoid stale closure
  const handleRestartSuccess = useCallback((executionId: number) => {
    handleRestartWizardClose();

    if (!isRefreshingRef.current) {
      isRefreshingRef.current = true;
      refetchCurrentState().finally(() => {
        isRefreshingRef.current = false;
      });
    }

    logger.debug('Restart execution created', { executionId });
  }, [handleRestartWizardClose, refetchCurrentState, isRefreshingRef]);

  return {
    restartWizardOpen,
    restartAction,
    restartAllowedEnvs,
    restartInitialParams,
    restartLoadingId,
    handleRestartExecution,
    handleRestartWizardClose,
    handleRestartSuccess,
  };
};
