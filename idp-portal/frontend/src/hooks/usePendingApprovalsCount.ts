/**
 * usePendingApprovalsCount - Polling hook for pending approvals count (Story 8.8).
 *
 * AC7: Mise à jour temps réel du badge via polling.
 * AC4, AC6: Retourne count pour le badge dans TopNav.
 */

import { useState, useEffect, useCallback } from 'react';
import { getPendingApprovalsCount } from '../services/execution_service';
import { useAuth } from '../contexts/AuthContext';
import logger from '../services/logger';

/**
 * Default polling interval: 15 seconds.
 * Story 8.8 Dev Notes: Balance between server load and data freshness.
 * Reduced from 60s to 15s for faster approval notification visibility.
 */
const DEFAULT_POLLING_INTERVAL = 15_000; // 15 seconds

// Story 8.8 AC9 / Story 66.2 F2: real DBA profiles — 'dba' kept for legacy/edge-case safety
// Note: same constant exists in TopNav.tsx
const DBA_PROFILES = ['dba', 'dba_applicatif', 'dba_infrastructure'];

interface UsePendingApprovalsCountResult {
  count: number;
  loading: boolean;
  error: Error | null;
  refetch: () => Promise<void>;
}

/**
 * Hook to fetch and poll pending approvals count.
 *
 * @param pollingInterval - Polling interval in ms (default 15000)
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
    DBA_PROFILES.includes(user?.profile?.toLowerCase() ?? '') ||
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
      logger.error('Failed to fetch pending approvals count', { error: err instanceof Error ? err.message : String(err) });
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

    // Setup polling (AC7)
    const interval = setInterval(fetchCount, pollingInterval);

    // Refresh immediately when tab becomes visible again
    const handleVisibility = () => {
      if (!document.hidden) fetchCount();
    };
    document.addEventListener('visibilitychange', handleVisibility);

    // Cleanup on unmount
    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [fetchCount, pollingInterval, canApprove]);

  return { count, loading, error, refetch: fetchCount };
}
