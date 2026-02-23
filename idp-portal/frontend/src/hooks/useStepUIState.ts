/**
 * useStepUIState — Story 34.12 (SOLID-FE-1)
 *
 * Extracted from ExecutionTimeline.tsx.
 * Manages expand/collapse, logs drawer, and focus trap state.
 */

import { useState, useRef, useEffect, useMemo } from 'react';
import type { ExecutionStepResponse } from '../types/api';

export interface UseStepUIStateReturn {
  expandedId: number | null;
  setExpandedId: (id: number | null) => void;
  logsDrawerStepId: number | null;
  setLogsDrawerStepId: (id: number | null) => void;
  logsDrawerStep: ExecutionStepResponse | null;
  logsDrawerContentRef: React.RefObject<HTMLDivElement>;
}

export function useStepUIState(steps: ExecutionStepResponse[]): UseStepUIStateReturn {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [logsDrawerStepId, setLogsDrawerStepId] = useState<number | null>(null);
  const logsDrawerContentRef = useRef<HTMLDivElement>(null);

  // Focus trap — move focus into drawer content when it opens
  useEffect(() => {
    if (logsDrawerStepId != null && logsDrawerContentRef.current) {
      logsDrawerContentRef.current.focus();
    }
  }, [logsDrawerStepId]);

  const logsDrawerStep = useMemo(
    () => (logsDrawerStepId != null ? steps.find((s) => s.id === logsDrawerStepId) : null) ?? null,
    [steps, logsDrawerStepId],
  );

  return { expandedId, setExpandedId, logsDrawerStepId, setLogsDrawerStepId, logsDrawerStep, logsDrawerContentRef };
}
