/**
 * useRemediationSuggestions - Hook for fetching remediation suggestions (Story 9.1).
 *
 * AC1: Fetches suggestions when execution status is 'FAILED'.
 * AC5: Uses GET /api/v1/executions/{id}/remediation endpoint.
 */

import { useState, useEffect, useCallback } from 'react';
import { fetchRemediationSuggestions } from '../services/execution_service';
import type { RemediationSuggestion, ExecutionStatusType } from '../types/api';

interface UseRemediationSuggestionsResult {
  suggestions: RemediationSuggestion[] | null;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch remediation suggestions for a failed execution.
 *
 * Only fetches suggestions when executionStatus === 'FAILED'.
 * Resets suggestions to null if status changes from FAILED to another status.
 *
 * @param executionId - Execution ID (or null if not available yet)
 * @param executionStatus - Current execution status (or null if not loaded)
 * @returns Object with suggestions, loading, error, and refetch function
 */
export function useRemediationSuggestions(
  executionId: number | null,
  executionStatus: ExecutionStatusType | null
): UseRemediationSuggestionsResult {
  const [suggestions, setSuggestions] = useState<RemediationSuggestion[] | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchSuggestions = useCallback(async () => {
    // Only fetch if we have an execution ID and status is FAILED
    if (executionId === null || executionStatus !== 'FAILED') {
      setSuggestions(null);
      setLoading(false);
      setError(null);
      return;
    }

    try {
      setLoading(true);
      setError(null);
      const result = await fetchRemediationSuggestions(executionId);
      setSuggestions(result);
    } catch (err) {
      console.error('Failed to fetch remediation suggestions:', err);
      setError(err instanceof Error ? err : new Error('Unknown error'));
      setSuggestions(null);
    } finally {
      setLoading(false);
    }
  }, [executionId, executionStatus]);

  useEffect(() => {
    // Fetch suggestions when executionId or status changes
    fetchSuggestions();
  }, [fetchSuggestions]);

  // Reset suggestions when status changes from FAILED to something else
  useEffect(() => {
    if (executionStatus !== 'FAILED') {
      setSuggestions(null);
      setError(null);
    }
  }, [executionStatus]);

  return { suggestions, loading, error, refetch: fetchSuggestions };
}
