/**
 * usePendingApprovalsCount - Polling hook for pending approvals count (Story 8.8).
 *
 * AC7: Mise à jour temps réel du badge via polling.
 * AC4, AC6: Retourne count pour le badge dans TopNav.
 */

import { useState, useEffect, useCallback } from 'react';
import { getPendingApprovalsCount } from '../services/execution_service';
import { useAuth } from '../contexts/AuthContext';

/**
 * Default polling interval: 60 seconds.
 * Story 8.8 Dev Notes: Balance between server load and data freshness.
 * Can be reduced to 30s or increased to 120s based on monitoring.
 */
const DEFAULT_POLLING_INTERVAL = 60_000; // 60 seconds

interface UsePendingApprovalsCountResult {
  count: number;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch and poll pending approvals count.
 *
 * @param pollingInterval - Polling interval in ms (default 60000)
 * @returns Object with count, loading, error, and refetch function
 */
export function usePendingApprovalsCount(
  pollingInterval: number = DEFAULT_POLLING_INTERVAL
): UsePendingApprovalsCountResult {
  const [count, setCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  const { user } = useAuth();

  // Only DBA/DBOPS can see approvals (AC9)
  const canApprove =
    user?.profile?.toLowerCase() === 'dba' ||
    user?.profile?.toLowerCase() === 'dbops';

  const fetchCount = useCallback(async () => {
    if (!canApprove) {
      setCount(0);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const newCount = await getPendingApprovalsCount();
      setCount(newCount);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch pending approvals count:', err);
      setError(err instanceof Error ? err : new Error('Unknown error'));
      setCount(0);
    } finally {
      setLoading(false);
    }
  }, [canApprove]);

  useEffect(() => {
    // Initial fetch
    fetchCount();

    // Skip polling if user cannot approve
    if (!canApprove) {
      return;
    }

    // Setup polling (AC7: 60 second interval)
    const interval = setInterval(fetchCount, pollingInterval);

    // Cleanup on unmount
    return () => clearInterval(interval);
  }, [fetchCount, pollingInterval, canApprove]);

  return { count, loading, error, refetch: fetchCount };
}
