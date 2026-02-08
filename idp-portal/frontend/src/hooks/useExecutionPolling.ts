/**
 * useExecutionPolling - Polling fallback for execution updates (Story 19.0).
 *
 * Used when WebSocket is unavailable (dev mode) or VITE_SIMULATE_EXECUTION=true.
 * Polls GET /executions/{id} and GET /executions/{id}/steps at a configurable interval.
 * Stops automatically when execution reaches a terminal status.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { getExecution, getExecutionSteps } from '../services/execution_service';
import type { ExecutionResponse, ExecutionStepResponse, ExecutionStatusType } from '../types/api';
import logger from '../services/logger';

const TERMINAL_STATUSES: ExecutionStatusType[] = ['COMPLETED', 'FAILED', 'CANCELLED', 'REJECTED'];

// Story 19.0: Default polling interval (LOW-2 fix)
const DEFAULT_POLLING_INTERVAL_MS = 2500;

export interface UseExecutionPollingOptions {
  executionId: number | null;
  enabled: boolean;
  interval?: number;
}

export interface UseExecutionPollingResult {
  execution: ExecutionResponse | null;
  steps: ExecutionStepResponse[];
  isPolling: boolean;
  error: Error | null;
}

export function useExecutionPolling({
  executionId,
  enabled,
  interval = DEFAULT_POLLING_INTERVAL_MS,
}: UseExecutionPollingOptions): UseExecutionPollingResult {
  const [execution, setExecution] = useState<ExecutionResponse | null>(null);
  const [steps, setSteps] = useState<ExecutionStepResponse[]>([]);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const isMountedRef = useRef(true);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (isMountedRef.current) {
      setIsPolling(false);
    }
  }, []);

  const fetchData = useCallback(async () => {
    if (executionId == null) return;

    try {
      const [execData, stepsData] = await Promise.all([
        getExecution(executionId),
        getExecutionSteps(executionId),
      ]);

      if (!isMountedRef.current) return;

      setExecution(execData);
      setSteps(stepsData);
      setError(null);

      // Stop polling on terminal status
      if (TERMINAL_STATUSES.includes(execData.status)) {
        stopPolling();
      }
    } catch (err) {
      if (!isMountedRef.current) return;
      const errorObj = err instanceof Error ? err : new Error(String(err));
      setError(errorObj);
      logger.warn('useExecutionPolling: fetch error', { error: errorObj.message });
    }
  }, [executionId, stopPolling]);

  useEffect(() => {
    isMountedRef.current = true;

    if (!enabled || executionId == null) {
      stopPolling();
      return;
    }

    // Initial fetch
    setIsPolling(true);
    fetchData();

    // Start interval
    intervalRef.current = setInterval(fetchData, interval);

    return () => {
      isMountedRef.current = false;
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [executionId, enabled, interval, fetchData, stopPolling]);

  return { execution, steps, isPolling, error };
}
