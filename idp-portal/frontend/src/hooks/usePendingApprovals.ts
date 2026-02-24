/**
 * usePendingApprovals - Hook wrapping approve/reject execution actions (Story 38.6, SOLID-FE-4).
 *
 * Wraps approveExecution + rejectExecution to remove direct service imports
 * from PendingApprovalsList.tsx.
 */
import { useState, useCallback } from 'react';
import { approveExecution, rejectExecution } from '../services/execution_service';

export function usePendingApprovals(onActionComplete: () => void) {
  const [approveLoading, setApproveLoading] = useState(false);
  const [rejectLoading, setRejectLoading] = useState(false);

  const approve = useCallback(async (executionId: number, comment?: string) => {
    setApproveLoading(true);
    try {
      await approveExecution(executionId, comment);
      try { onActionComplete(); } catch { /* callback errors must not mask successful approval */ }
      return { success: true as const };
    } catch (err) {
      return { success: false as const, error: err instanceof Error ? err.message : 'Erreur lors de l\'approbation' };
    } finally {
      setApproveLoading(false);
    }
  }, [onActionComplete]);

  const reject = useCallback(async (executionId: number, comment?: string) => {
    setRejectLoading(true);
    try {
      await rejectExecution(executionId, comment);
      try { onActionComplete(); } catch { /* callback errors must not mask successful rejection */ }
      return { success: true as const };
    } catch (err) {
      return { success: false as const, error: err instanceof Error ? err.message : 'Erreur lors du refus' };
    } finally {
      setRejectLoading(false);
    }
  }, [onActionComplete]);

  return { approve, reject, approveLoading, rejectLoading };
}
