/**
 * useExecutionSteps - Hook for one-time fetch of execution steps (Story 38.6, SOLID-FE-4).
 *
 * Wraps getExecutionSteps to remove direct service imports from WorkflowExecutionGraph.tsx.
 * Used for terminal executions that don't need polling/WebSocket.
 */
import { useState, useEffect } from 'react';
import { getExecutionSteps } from '../services/execution_service';
import type { ExecutionStepResponse } from '../types/api';
import logger from '../services/logger';

export function useExecutionSteps(executionId: number | null, enabled: boolean) {
  const [steps, setSteps] = useState<ExecutionStepResponse[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || !executionId) {
      setSteps([]);
      setError(null);
      return;
    }
    let cancelled = false;
    setError(null);
    getExecutionSteps(executionId)
      .then((data) => {
        if (!cancelled) setSteps(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : 'Erreur inconnue';
          logger.error('Failed to load execution steps', { executionId, error: message });
          setError(message);
        }
      });
    return () => { cancelled = true; };
  }, [enabled, executionId]);

  return { steps, error };
}
