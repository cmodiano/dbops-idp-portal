/**
 * useExecutionData — Story 34.12 (SOLID-FE-1)
 *
 * Extracted from ExecutionTimeline.tsx.
 * Handles WebSocket connection + polling fallback, and derives steps/execution.
 */

import { useMemo } from 'react';
import { useWebSocket } from './useWebSocket';
import { useExecutionPolling } from './useExecutionPolling';
import type { ExecutionResponse, ExecutionStepResponse } from '../types/api';

const FORCE_POLLING = import.meta.env.VITE_SIMULATE_EXECUTION === 'true';

export interface UseExecutionDataProps {
  executionId?: number | null;
  executionProp?: ExecutionResponse | null;
  stepsProp?: ExecutionStepResponse[];
  mode?: 'realtime' | 'historical';
}

export interface UseExecutionDataReturn {
  steps: ExecutionStepResponse[];
  execution: ExecutionResponse | null;
  loading: boolean;
  error: string | null;
  isPolling: boolean;
  useRealtime: boolean;
  lastMessage: ReturnType<typeof useWebSocket>['lastMessage'];
}

export function useExecutionData({
  executionId,
  executionProp,
  stepsProp,
  mode,
}: UseExecutionDataProps): UseExecutionDataReturn {
  const useRealtime = mode === 'realtime' && executionId != null;
  const useWs = useRealtime && !FORCE_POLLING;

  const { steps: wsSteps, execution: wsExecution, loading: wsLoading, error: wsError, lastMessage } = useWebSocket(
    useWs ? executionId : null,
  );

  const wsHasError = useWs && wsError != null;
  const usePolling = useRealtime && (FORCE_POLLING || wsHasError);

  const { execution: pollExecution, steps: pollSteps, isPolling, error: pollError } = useExecutionPolling({
    executionId: executionId ?? null,
    enabled: usePolling,
    interval: 2500,
  });

  const loading = useWs ? wsLoading : false;
  const error = useWs && !wsHasError ? wsError : (pollError?.message ?? null);

  const steps = useMemo(() => {
    if (usePolling) return pollSteps;
    if (useWs) return wsSteps;
    return stepsProp ?? [];
  }, [usePolling, useWs, pollSteps, wsSteps, stepsProp]);

  const execution = usePolling ? pollExecution : (useWs ? wsExecution : executionProp ?? null);

  return { steps, execution, loading, error, isPolling, useRealtime, lastMessage };
}
