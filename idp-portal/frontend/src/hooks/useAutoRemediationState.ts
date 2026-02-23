/**
 * useAutoRemediationState — Story 34.12 (SOLID-FE-1)
 *
 * Extracted from ExecutionTimeline.tsx.
 * Manages auto-remediation state machine driven by WebSocket lastMessage.
 */

import { useState, useEffect, useRef } from 'react';

export interface AutoRemediationState {
  inProgress: boolean;
  failed: boolean;
  childExecutionId: number | null;
  correctiveActionName: string | null;
  failureMessage: string | null;
}

const INITIAL_STATE: AutoRemediationState = {
  inProgress: false,
  failed: false,
  childExecutionId: null,
  correctiveActionName: null,
  failureMessage: null,
};

export function useAutoRemediationState(
  lastMessage: { type: string; data?: unknown } | null | undefined,
  executionId?: number | null,
): AutoRemediationState {
  const [state, setState] = useState<AutoRemediationState>(INITIAL_STATE);
  const prevExecutionIdRef = useRef(executionId);

  useEffect(() => {
    if (!lastMessage) return;

    if (lastMessage.type === 'auto_remediation_started') {
      const data = lastMessage.data as { child_execution_id?: number; corrective_action_name?: string } | undefined;
      setState(() => ({
        inProgress: true,
        failed: false,
        childExecutionId: data?.child_execution_id ?? null,
        correctiveActionName: data?.corrective_action_name ?? null,
        failureMessage: null,
      }));
    } else if (lastMessage.type === 'auto_remediation_failed') {
      const data = lastMessage.data as { child_execution_id?: number; message?: string } | undefined;
      setState((prev) => ({
        ...prev,
        inProgress: false,
        failed: true,
        childExecutionId: data?.child_execution_id ?? prev.childExecutionId,
        failureMessage: data?.message ?? 'Tentative de correction automatique échouée',
      }));
    }
  }, [lastMessage]);

  useEffect(() => {
    if (prevExecutionIdRef.current !== executionId) {
      setState(INITIAL_STATE);
      prevExecutionIdRef.current = executionId;
    }
  }, [executionId]);

  return state;
}
