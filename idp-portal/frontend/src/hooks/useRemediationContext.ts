/**
 * useRemediationContext - Hook for fetching remediation context (Story 9.2).
 *
 * AC2: Fetches context about child remediation executions for a parent.
 * AC3: Provides has_remediation and successful_remediation flags for UI display.
 */

import { useState, useEffect, useCallback } from 'react';
import { fetchRemediationContext } from '../services/execution_service';
import type { RemediationContext, ExecutionStatusType } from '../types/api';
import logger from '../services/logger';

interface UseRemediationContextResult {
  context: RemediationContext | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch remediation context for a failed execution.
 *
 * Only fetches context when executionStatus === 'FAILED'.
 * Resets context to null if status changes from FAILED to another status.
 *
 * @param executionId - Execution ID (or null if not available yet)
 * @param executionStatus - Current execution status (or null if not loaded)
 * @returns Object with context, loading, error, and refetch function
 */
export function useRemediationContext(
  executionId: number | null,
  executionStatus: ExecutionStatusType | null
): UseRemediationContextResult {
  const [context, setContext] = useState<RemediationContext | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchContext = useCallback(async () => {
    // Only fetch if we have an execution ID and status is FAILED
    if (executionId === null || executionStatus !== 'FAILED') {
      setContext(null);
      setLoading(false);
      setError(null);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const result = await fetchRemediationContext(executionId);
      setContext(result);
    } catch (err: unknown) {
      // Story 9-2 code-review fix: Better error handling for 404/403
      const error = err as { status?: number; message?: string };
      if (error.status === 404) {
        logger.warn('Execution not found for remediation context', { executionId });
        setContext({ has_remediation: false, successful_remediation: false, remediation_actions: [] });
        setError(null); // Not an error, just no context
      } else if (error.status === 403) {
        logger.error('Permission denied for remediation context', { executionId, error: err instanceof Error ? err.message : String(err) });
        setError(new Error('Accès refusé'));
        setContext(null);
      } else {
        logger.error('Failed to fetch remediation context', { executionId, error: err instanceof Error ? err.message : String(err) });
        setError(err instanceof Error ? err : new Error('Erreur inconnue'));
        setContext(null);
      }
    } finally {
      setLoading(false);
    }
  }, [executionId, executionStatus]);

  useEffect(() => {
    // Fetch context when executionId or status changes
    // Story 9-2 code-review fix: Use direct deps to avoid unnecessary re-fetches
    fetchContext();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [executionId, executionStatus]);

  // Reset context when status changes from FAILED to something else
  useEffect(() => {
    if (executionStatus !== 'FAILED') {
      setContext(null);
      setError(null);
    }
  }, [executionStatus]);

  return { context, loading, error, refetch: fetchContext };
}
