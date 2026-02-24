/**
 * useCancelRunningExecution - Hook wrapping cancelExecution for running executions (Story 38.6, SOLID-FE-4).
 *
 * Wraps cancelExecution to remove direct service imports from ExecutionsPage.tsx.
 * Distinct from useCancelExecution which handles scheduled execution cancellation.
 */
import { useCallback } from 'react';
import { cancelExecution } from '../services/execution_service';

export function useCancelRunningExecution() {
  const cancel = useCallback((executionId: number) => {
    return cancelExecution(executionId);
  }, []);

  return { cancelRunningExecution: cancel };
}
