/**
 * useSchedulingValidation - Scheduling validation hook.
 * Extracted from ExecutionWizard.tsx (Story 17.2, Task 2.5).
 *
 * Validates scheduling dates, cron expressions, and provides next execution preview.
 */

import { useCallback } from 'react';
import dayjs from 'dayjs';
import { validateCronExpression, getCronNextExecutions } from '../services/scheduled_execution_service';
import { debounce } from '../utils/debounce';

export interface ScheduleValidation {
  isValid: boolean;
  error: string | null;
}

export interface UseSchedulingValidationReturn {
  validateSchedule: (type: 'one-time' | 'daily' | 'weekly' | 'cron', data: ScheduleData) => ScheduleValidation;
  validateCronDebounced: (expression: string, onResult: CronValidationCallback) => void;
  handleCronPresetChange: (value: string, onResult: CronValidationCallback) => void;
}

export interface ScheduleData {
  scheduledAt?: dayjs.Dayjs | null;
  cronExpression?: string;
  cronIsValid?: boolean | null;
}

export type CronValidationCallback = (result: {
  isValid: boolean | null;
  error: string;
  nextExecutions: string[];
  validating: boolean;
}) => void;

export function useSchedulingValidation(): UseSchedulingValidationReturn {
  const validateSchedule = useCallback((
    type: 'one-time' | 'daily' | 'weekly' | 'cron',
    data: ScheduleData
  ): ScheduleValidation => {
    if (type === 'one-time') {
      if (!data.scheduledAt) {
        return { isValid: false, error: 'Veuillez sélectionner une date et heure' };
      }
      if (data.scheduledAt.isBefore(dayjs())) {
        return { isValid: false, error: 'La date planifiée doit être dans le futur' };
      }
      return { isValid: true, error: null };
    }

    if (type === 'cron') {
      if (!data.cronExpression || !data.cronIsValid) {
        return { isValid: false, error: 'Veuillez saisir une expression cron valide' };
      }
      return { isValid: true, error: null };
    }

    // daily and weekly are always valid
    return { isValid: true, error: null };
  }, []);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  const validateCronDebounced = useCallback(
    debounce(async (expression: string, onResult: CronValidationCallback) => {
      if (!expression || !expression.trim()) {
        onResult({ isValid: null, error: '', nextExecutions: [], validating: false });
        return;
      }

      onResult({ isValid: null, error: '', nextExecutions: [], validating: true });

      try {
        const validation = await validateCronExpression(expression);

        if (validation.valid) {
          const nextExecs = await getCronNextExecutions(expression, 5);
          onResult({ isValid: true, error: '', nextExecutions: nextExecs, validating: false });
        } else {
          onResult({
            isValid: false,
            error: validation.error || 'Expression cron invalide',
            nextExecutions: [],
            validating: false,
          });
        }
      } catch {
        onResult({ isValid: false, error: 'Erreur de validation', nextExecutions: [], validating: false });
      }
    }, 500),
    []
  );

  const handleCronPresetChange = useCallback(
    (value: string, onResult: CronValidationCallback) => {
      if (value === 'custom') {
        onResult({ isValid: null, error: '', nextExecutions: [], validating: false });
      } else {
        validateCronDebounced(value, onResult);
      }
    },
    [validateCronDebounced]
  );

  return {
    validateSchedule,
    validateCronDebounced,
    handleCronPresetChange,
  };
}
