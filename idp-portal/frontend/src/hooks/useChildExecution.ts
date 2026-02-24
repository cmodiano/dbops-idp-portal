/**
 * useChildExecution - Hook for loading child execution data (Story 38.6, SOLID-FE-4).
 *
 * Wraps getExecution + getExecutionSteps to remove direct service imports
 * from StepDetailDrawer.tsx. Used when a workflow step output contains a child_execution_id.
 */
import { useState, useEffect } from 'react';
import { getExecution, getExecutionSteps } from '../services/execution_service';
import type { ExecutionResponse, ExecutionStepResponse } from '../types/api';

export function useChildExecution(childExecutionId: number | null, enabled: boolean) {
  const [childExecution, setChildExecution] = useState<ExecutionResponse | null>(null);
  const [childSteps, setChildSteps] = useState<ExecutionStepResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!enabled || childExecutionId == null) {
      setChildExecution(null);
      setChildSteps([]);
      setLoading(false);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([getExecution(childExecutionId), getExecutionSteps(childExecutionId)])
      .then(([exec, steps]) => {
        if (!cancelled) {
          setChildExecution(exec);
          setChildSteps(steps);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Erreur de chargement');
          setChildExecution(null);
          setChildSteps([]);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [enabled, childExecutionId]);

  return { childExecution, childSteps, loading, error };
}
