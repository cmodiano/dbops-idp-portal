/**
 * usePendingApprovals - Hook wrapping approve/reject execution actions (Story 38.6, SOLID-FE-4).
 *
 * Wraps approveExecution + rejectExecution to remove direct service imports
 * from PendingApprovalsList.tsx.
 */
import { useState, useCallback } from 'react';
import { approveExecution, rejectExecution } from '../services/execution_service';

export function usePendingApprovals(onActionComplete: () => void) {
  const [actionLoading, setActionLoading] = useState(false);

  const approve = useCallback(async (executionId: number, comment?: string) => {
    setActionLoading(true);
    try {
      await approveExecution(executionId, comment);
      onActionComplete();
      return { success: true as const };
    } catch (err) {
      return { success: false as const, error: err instanceof Error ? err.message : 'Erreur lors de l\'approbation' };
    } finally {
      setActionLoading(false);
    }
  }, [onActionComplete]);

  const reject = useCallback(async (executionId: number, comment?: string) => {
    setActionLoading(true);
    try {
      await rejectExecution(executionId, comment);
      onActionComplete();
      return { success: true as const };
    } catch (err) {
      return { success: false as const, error: err instanceof Error ? err.message : 'Erreur lors du refus' };
    } finally {
      setActionLoading(false);
    }
  }, [onActionComplete]);

  return { approve, reject, actionLoading };
}
