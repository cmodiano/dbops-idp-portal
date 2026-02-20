/**
 * useExecutionSubmit - Execution submission logic hook.
 * Extracted from ExecutionWizard.tsx (Story 17.2, Task 2.2).
 *
 * Handles immediate, scheduled, and recurring execution submissions.
 */

import { useCallback, useMemo, useState } from 'react';
import { App } from 'antd';
import dayjs from 'dayjs';
import { submitExecution } from '../services/execution_service';
import { createScheduledExecution } from '../services/scheduled_execution_service';
import type { RecurringPatternRequest } from '../types/api';
import logger from '../services/logger';

export interface SubmitImmediateParams {
  action_id: number;
  environment?: string;
  target_names?: string[];
  parameters: Record<string, unknown> | null;
  workflow_step_parameters?: Record<string, { parameters: Record<string, unknown> }>;
  parent_execution_id?: number | null;
  /** Story 31.8: Page me on failure. */
  page_me?: boolean;
}

export interface SubmitScheduledParams {
  action_id: number;
  environment: string;
  target_names?: string[];
  parameters: Record<string, unknown> | null;
  workflow_step_parameters?: Record<string, { parameters: Record<string, unknown> }>;
  scheduled_at?: string | null;
  recurring_pattern?: RecurringPatternRequest;
  /** Story 31.8: Page me on failure. */
  page_me?: boolean;
}

export interface SchedulingState {
  isScheduling: boolean;
  schedulingType: 'one-time' | 'daily' | 'weekly' | 'cron';
  scheduledAt: dayjs.Dayjs | null;
  dailyHour: number;
  dailyMinute: number;
  weeklyDayOfWeek: number;
  weeklyHour: number;
  weeklyMinute: number;
  cronExpression: string;
  cronIsValid: boolean | null;
  cronError: string;
  cronNextExecutions: string[];
  cronValidating: boolean;
  showCronHelper: boolean;
}

const initialSchedulingState: SchedulingState = {
  isScheduling: false,
  schedulingType: 'one-time',
  scheduledAt: null,
  dailyHour: 2,
  dailyMinute: 0,
  weeklyDayOfWeek: 1,
  weeklyHour: 14,
  weeklyMinute: 0,
  cronExpression: '',
  cronIsValid: null,
  cronError: '',
  cronNextExecutions: [],
  cronValidating: false,
  showCronHelper: false,
};

export interface UseExecutionSubmitReturn {
  submitImmediate: (params: SubmitImmediateParams) => Promise<number | null>;
  submitScheduled: (params: SubmitScheduledParams) => Promise<number | null>;
  isSubmitting: boolean;
  submitError: string | null;
  schedulingError: string | null;
  setSubmitError: (error: string | null) => void;
  setSchedulingError: (error: string | null) => void;
  scheduling: SchedulingState;
  updateScheduling: (updates: Partial<SchedulingState>) => void;
  resetScheduling: () => void;
}

function getSchedulingErrorMessage(error: Error & { code?: string; message?: string }): string {
  if (error.code === 'INVALID_SCHEDULED_DATE' || error.message?.includes('past')) {
    return 'La date planifiée doit être dans le futur (vérifiez l\'heure de votre appareil si ce message persiste)';
  }
  if (error.code === 'PERMISSION_DENIED' || error.message?.includes('permission') || error.message?.includes('403')) {
    return "Vous n'avez pas la permission de planifier cette action dans cet environnement";
  }
  if (error.code === 'ACTION_NOT_FOUND' || error.message?.includes('not found') || error.message?.includes('404')) {
    return 'Action introuvable ou non publiée';
  }
  if (error.code === 'INVALID_PARAMETERS') {
    return `Paramètre invalide : ${error.message}`;
  }
  return error.message || 'Une erreur est survenue lors de la planification';
}

export function useExecutionSubmit(): UseExecutionSubmitReturn {
  const { notification } = App.useApp();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [schedulingError, setSchedulingError] = useState<string | null>(null);
  const [scheduling, setScheduling] = useState<SchedulingState>({ ...initialSchedulingState });

  const updateScheduling = useCallback((updates: Partial<SchedulingState>) => {
    setScheduling((prev) => ({ ...prev, ...updates }));
  }, []);

  const resetScheduling = useCallback(() => {
    setScheduling({ ...initialSchedulingState });
    setSchedulingError(null);
  }, []);

  const submitImmediate = useCallback(async (params: SubmitImmediateParams): Promise<number | null> => {
    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const response = await submitExecution({
        action_id: params.action_id,
        environment: params.environment,
        target_names: params.target_names,
        parameters: params.parameters,
        workflow_step_parameters: params.workflow_step_parameters,
        parent_execution_id: params.parent_execution_id ?? null,
        page_me: params.page_me,
      });

      // Story 19.4 AC1: No success notification — ExecutionView opens automatically
      return response.execution_id;
    } catch (err) {
      const error = err as Error & { code?: string };
      let message = error.message || 'Erreur lors de la soumission';
      if (error.code === 'INVALID_PARENT_STATUS' || message.includes('FAILED')) {
        message = 'L\'exécution parente n\'est pas en échec';
      } else if (error.code === 'PARENT_NOT_FOUND' || message.includes('not found')) {
        message = 'L\'exécution parente est introuvable';
      } else if (error.code === 'FORBIDDEN' || message.includes('forbidden')) {
        message = 'Accès refusé à l\'exécution parente';
      }
      // Story 19.4 AC5: Error shown in wizard Alert via submitError, no notification popup
      setSubmitError(message);
      return null;
    } finally {
      setIsSubmitting(false);
    }
  }, []);

  const submitScheduled = useCallback(async (params: SubmitScheduledParams): Promise<number | null> => {
    setIsSubmitting(true);
    setSchedulingError(null);

    try {
      const response = await createScheduledExecution({
        action_id: params.action_id,
        environment: params.environment,
        parameters: params.parameters,
        // @ts-expect-error - backend may ignore this until Story 4.12 backend is implemented
        workflow_step_parameters: params.workflow_step_parameters,
        scheduled_at: params.scheduled_at,
        recurring_pattern: params.recurring_pattern,
        target_names: params.target_names,
        page_me: params.page_me,
      });

      if (import.meta.env.DEV) {
        logger.info('Scheduled execution created', { scheduledExecutionId: response.scheduled_execution_id });
      }

      return response.scheduled_execution_id;
    } catch (err) {
      const error = err as Error & { code?: string; correlation_id?: string };
      const errorMessage = getSchedulingErrorMessage(error);

      if (import.meta.env.DEV) {
        logger.error('Scheduled execution failed', { error: error.message, correlation_id: error.correlation_id });
      }

      notification.error({
        message: 'Erreur de planification',
        description: errorMessage,
        duration: 5,
      });

      setSchedulingError(errorMessage);
      return null;
    } finally {
      setIsSubmitting(false);
    }
  }, [notification]);

  return useMemo(
    () => ({
      submitImmediate,
      submitScheduled,
      isSubmitting,
      submitError,
      schedulingError,
      setSubmitError,
      setSchedulingError,
      scheduling,
      updateScheduling,
      resetScheduling,
    }),
    [
      submitImmediate,
      submitScheduled,
      isSubmitting,
      submitError,
      schedulingError,
      scheduling,
      updateScheduling,
      resetScheduling,
    ]
  );
}
